#!/usr/bin/env python3
"""Finite read-only acquisition of the three admitted public Rendering inputs."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import signal
import stat
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZipFile

# Published Rendering 0.32.3: original producer 4ec6 (source run 39509314882/1, artifact
# 12305198394, custody 7dbd), published byte-for-byte by protected publisher 39817794639/1.
VERSION = '0.32.3'
SOURCE = '4ec6eafbbbf02264db9b0db4780c590abe0bf9cd'
CUSTODY_SHA256 = '7dbd4329546932c4c1d12767550b7b78aae85e32c81b354935b2c615b3e298c9'
# Raw NuGet repository-signed archive hashes, observed 2026-10-22; NOT lock hashes.
PUBLIC_SHA256 = {
    'FS.GG.UI.Scene': '9cc74f6af082089fb269d7d12c7f1e7ee7684ae3bdab51918b65e06e072a7ac8',
    'FS.GG.UI.KeyboardInput': '99aa6564e7a3b323da8346c50894f28eca8b981cc31ac763b8f34b19fd8beb4c',
    'FS.GG.UI.Scene.SvgBrowser': '8764ce047628f7f58d77e430b2afa0ffafb47560f7633abcf1c8dd12bf8710ad',
}
# NuGet signed GetContentHash excludes signature context. Authentic original archives
# supply these hashes; PackageArchiveReader.GetContentHashForSignedPackage in NuGet.Client
# delegates to SignedPackageArchiveUtility.GetPackageContentHash. Locked restore verifies.
LOCK_HASH = {
    'FS.GG.UI.Scene': 'CxghwCbdT5kQz3DArIFkFE1zVmtxmS5LCxR21l+hLwX4mu1xQCmPdAcaYDDOggOsIw9vMuOQGWmc1BImrNCPNg==',
    'FS.GG.UI.KeyboardInput': 'sz7lovxAAfq70N5eACOroVJsElW6zws7ig+NCQtO6E495YvaHgLcYbxaOp9ZXrrnluWx/a9KfMJsTVelVsMbmQ==',
    'FS.GG.UI.Scene.SvgBrowser': 'VcRGZ+vro3Y0vaLspoWZKsOB1b+2fL5tXeorz8PfsxWRme1gJlIGBX8zkHGAbvBF/a8f4XzpdilcnXPV8jQ9WA==',
}



# Source-local application protocol/domain edges are part of the shipped codec
# probes. They are not alternative producers for the three public UI packages.
LOCAL_PROJECT_REFERENCES = {
    'Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj':
        ['../../../Protocol/Protocol.fsproj', '../../../Domain/Domain.fsproj'],
    'Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj':
        ['../../../Domain/Domain.fsproj'],
}


def validate_project_references(tree, project, root):
    nodes = tree.findall('.//ProjectReference')
    expected = LOCAL_PROJECT_REFERENCES.get(project, [])
    if len(nodes) != len(expected) or sorted(node.attrib.get('Include', '') for node in nodes) != sorted(expected):
        raise ValueError('unexpected local project reference: ' + project)
    parents = {child: parent for parent in tree.iter() for child in parent}
    for node in nodes:
        ancestor = parents.get(node)
        while ancestor is not None:
            if 'Condition' in ancestor.attrib:
                raise ValueError('conditional ancestor of local project reference: ' + project)
            ancestor = parents.get(ancestor)
        if set(node.attrib) != {'Include'} or list(node):
            raise ValueError('conditional or altered local project reference: ' + project)
        target = root / Path(project).parent / node.attrib['Include']
        resolved = target.resolve()
        if not resolved.is_relative_to(root.resolve()) or target.is_symlink() or not resolved.is_file():
            raise ValueError('local project target absent or outside generated source: ' + project)


def validate_archive(path, identity, expected_raw_hash, custody_row):
    if not stat.S_ISREG(path.lstat().st_mode) or path.is_symlink():
        raise ValueError('regular archive required')
    raw = path.read_bytes()
    if len(raw) > 32 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_raw_hash:
        raise ValueError('public raw archive identity mismatch')
    entries = {}; inflated = 0
    with ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 2048:
            raise ValueError('archive entry bound exceeded')
        for info in infos:
            name = info.filename
            if not name or name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts or ':' in name or name in entries:
                raise ValueError('unsafe or duplicate archive entry')
            if info.file_size > 32 * 1024 * 1024 or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('unsafe archive size or symlink')
            inflated += info.file_size
            if inflated > 128 * 1024 * 1024:
                raise ValueError('archive expanded bound exceeded')
            if not info.is_dir():
                entries[name] = archive.read(info)
    if '.signature.p7s' not in entries:
        raise ValueError('observed public signature absent')
    payload = {n: hashlib.sha256(b).hexdigest() for n, b in sorted(entries.items()) if n != '.signature.p7s'}
    if payload != custody_row['payloadEntries']:
        raise ValueError('normalized custody payload mismatch')
    specs = [n for n in entries if '/' not in n and n.lower().endswith('.nuspec')]
    if len(specs) != 1:
        raise ValueError('exact root NuSpec required')
    spec = ET.fromstring(entries[specs[0]])
    field = lambda n: (spec.find('.//{*}' + n).text or '').strip()
    repository = spec.find('.//{*}repository')
    if field('id') != identity or field('version') != VERSION or repository is None or repository.attrib.get('commit') != SOURCE:
        raise ValueError('NuSpec package/source mismatch')
    dependencies = sorted(({'id': d.attrib['id'], 'version': d.attrib['version']} for d in spec.findall('.//{*}dependency')), key=lambda d: (d['id'], d['version']))
    if dependencies != custody_row['dependencies']:
        raise ValueError('NuSpec dependency mismatch')
    return {'id': identity, 'bytes': len(raw), 'rawSha256': expected_raw_hash,
            'rawSha512': base64.b64encode(hashlib.sha512(raw).digest()).decode(),
            'lockContentHash': LOCK_HASH.get(identity), 'payloadMatched': True, 'source': SOURCE}


def acquire(custody_path, output):
    custody_bytes = custody_path.read_bytes()
    if hashlib.sha256(custody_bytes).hexdigest() != CUSTODY_SHA256:
        raise ValueError('admitted custody identity mismatch')
    rows = {r['id']: r for r in json.loads(custody_bytes)['archives']}
    output.mkdir(mode=0o700)  # fresh; refuse replay/overwrites
    records = []; total = 0; started = time.monotonic()
    def deadline(*unused):
        raise TimeoutError('whole acquisition90s deadline')
    previous = signal.signal(signal.SIGALRM, deadline); signal.alarm(90)
    try:
        for identity, raw_hash in PUBLIC_SHA256.items():
            lower = identity.lower()
            uri = f'https://api.nuget.org/v3-flatcontainer/{lower}/{VERSION}/{lower}.{VERSION}.nupkg'
            row = {'id': identity, 'uri': uri, 'state': 'started'}; records.append(row)
            path = output / (identity + '.' + VERSION + '.nupkg')
            try:
                with urllib.request.urlopen(uri, timeout=20) as response, path.open('xb') as file:
                    row['httpStatus'] = response.status
                    if response.status != 200 or response.url != uri:
                        raise ValueError('unexpected public response/redirect')
                    size = 0
                    while True:
                        if time.monotonic() - started >= 90:
                            raise TimeoutError('acquisition deadline')
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        size += len(chunk); total += len(chunk)
                        if size > 32 * 1024 * 1024 or total > 64 * 1024 * 1024:
                            raise ValueError('acquisition byte bound')
                        file.write(chunk)
                row.update(validate_archive(path, identity, raw_hash, rows[identity])); row['state'] = 'matched'
            except BaseException as error:
                row.update(state='failed', error=type(error).__name__ + ': ' + str(error), partialBytes=path.stat().st_size if path.exists() else 0)
                raise
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, previous)
        (output / 'public-readback.json').write_text(json.dumps({'schema': 'fsgg.external-reference-public-input/1', 'records': records, 'elapsedSeconds': time.monotonic() - started, 'bytes': total, 'custodySha256': CUSTODY_SHA256, 'installedProof': False}, indent=2) + '\n')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: external-reference-public.py CUSTODY_JSON FRESH_OUTPUT')
    acquire(Path(sys.argv[1]), Path(sys.argv[2]))
