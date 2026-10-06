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

SOURCE = '6c9f766fdd91483c2de6f061e75589e94852a265'
CUSTODY_SHA256 = 'ecd0c5d742fd8d19d5659991e413e92971c1d2cb9aea913faa2bb249f53f577d'
# Raw NuGet repository-signed archive hashes, observed 2026-10-06; NOT lock hashes.
PUBLIC_SHA256 = {
    'FS.GG.UI.Scene': 'e7ef01527a626a97b64d213274d2ca9e1577bbd25f8beb85c35947b2e7d302c4',
    'FS.GG.UI.KeyboardInput': 'a5e1a1793fecfe4c05eeebde56660f9752cb7a7fe1111d18f59b2f61ad478b72',
    'FS.GG.UI.Scene.SvgBrowser': '8eba2376c84ef908d93a67cc379a10accd26a1165ba217393e67669fa2740cc1',
}
# NuGet signed GetContentHash excludes signature context. Authentic original archives
# supply these hashes; PackageArchiveReader.GetContentHashForSignedPackage in NuGet.Client
# delegates to SignedPackageArchiveUtility.GetPackageContentHash. Locked restore verifies.
LOCK_HASH = {
    'FS.GG.UI.Scene': '3oifBGdPvhLfZBXgeJVB8ycJfs7PgJEX9xm6UaDQhqhauVtitr4sj1Bzu0l4rZMXZS6vA+j4/77w/rxNtUdm3w==',
    'FS.GG.UI.KeyboardInput': '3l3iYwmyNSbOl2Ui5QmryOaDUl2r+smp0Dl4VQ55LKaVT4mJw+/JiUnLlrjQAAn/U22QtMUMg8sRiODG1fQHjQ==',
    'FS.GG.UI.Scene.SvgBrowser': 'eXi251Nj5MNQ0myqDjFBtxB+k6x5gnhh7YhE34ItNg3fwlQvPP65X7SxT7AO+11DsR82t5aDd5nQCIpPz2U1zA==',
}


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
    if field('id') != identity or field('version') != '0.32.1' or repository is None or repository.attrib.get('commit') != SOURCE:
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
            uri = f'https://api.nuget.org/v3-flatcontainer/{lower}/0.32.1/{lower}.0.32.1.nupkg'
            row = {'id': identity, 'uri': uri, 'state': 'started'}; records.append(row)
            path = output / (identity + '.0.32.1.nupkg')
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
