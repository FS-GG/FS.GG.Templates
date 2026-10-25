#!/usr/bin/env python3
"""Acquire declared current-reference Noble inputs; never install or execute them.

Signature/plaintext and signed-index semantics follow Coordination c068e1cc
 deployment/qualification-runner/noble-inputs.py. This is not a resolver or a
 facility/runtime qualification. One original deadline; no retry or overwrite.
"""
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
ORIGIN = 'https://snapshot.ubuntu.com'
BASE = ORIGIN + '/ubuntu/20261024T000000Z/'
SIGNER = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'
KEYRING_SHA256 = '80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31'
RELEASES = {
    'noble': 'cdb2f31d809f589719a53c6ad15f255b27569c4059542ada282aaa21b8e164b0',
    'noble-updates': '4fcba3fb02086679f7e86677e320b92e0d076a8c02e30dc0abbbe06b67640db7',
    'noble-security': 'e56daa3c9903f06da8161b4f0e61a747aab215647f4bfabbecd5655631200f09',
}
COMPONENTS = ('main', 'universe')
MAX_FILE = 128 * 1024**2
MAX_TOTAL = 512 * 1024**2
MAX_EXPANDED = 256 * 1024**2
MAX_REQUESTS = 2048


def need(value, message):
    if not value:
        raise RuntimeError('Noble acquisition: ' + message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(value):
    need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+._/@-]*', value)
         and not any(p in ('', '.', '..') for p in value.split('/'))
         and not PurePosixPath(value).is_absolute(), 'unsafe archive/index path')
    return value


def fields(block):
    result = {}
    key = None
    for line in block.splitlines():
        if line.startswith((' ', '\t')):
            need(key is not None, 'orphan index continuation')
            result[key] += '\n' + line[1:]
        else:
            need(':' in line, 'malformed index field')
            key, value = line.split(':', 1)
            need(re.fullmatch('[A-Za-z0-9-]+', key) and key not in result, 'duplicate index field')
            result[key] = value.strip()
    return result


def rows(raw):
    # Ubuntu's original Noble indexes append a second empty XZ stream.
    # Authenticate the compressed whole, then bound every concatenated stream.
    pending, chunks, total = raw, [], 0
    for _ in range(4):
        decoder = lzma.LZMADecompressor(memlimit=128 * 1024**2)
        chunk = decoder.decompress(pending, max_length=MAX_EXPANDED - total + 1)
        total += len(chunk)
        need(total <= MAX_EXPANDED and decoder.eof, 'index decompression exceeded bound/truncated stream')
        chunks.append(chunk)
        pending = decoder.unused_data
        if not pending:
            break
    need(not pending, 'index trailing bytes/stream count exceeded')
    plain = b''.join(chunks)
    for block in plain.decode('utf-8').split('\n\n'):
        if block.strip():
            need(len(block.encode()) <= 1024**2, 'index stanza exceeded bound')
            yield fields(block)


class Budget:
    def __init__(self, seconds=240, clock=time.monotonic):
        self.clock = clock
        self.deadline = clock() + seconds
        self.bytes = 0
        self.requests = 0

    def remaining(self):
        remaining = self.deadline - self.clock()
        need(remaining > 0, 'original deadline exhausted')
        return remaining


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('Noble acquisition: redirect refused')


def fetch(uri, expected, size, target, budget, opener=None):
    need(uri.startswith(BASE) and relative(uri[len(BASE):]), 'nonselected origin/snapshot')
    need(re.fullmatch('[0-9a-f]{64}', expected) and type(size) is int and 0 < size <= MAX_FILE,
         'archive identity/body bound absent')
    budget.remaining()
    need(budget.requests < MAX_REQUESTS and budget.bytes + size <= MAX_TOTAL, 'population bound exceeded')
    budget.requests += 1
    need(not target.exists() and not target.is_symlink(), 'output already exists')
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(urllib.request.Request(uri, headers={'Accept-Encoding': 'identity'}),
                     timeout=min(30, budget.remaining())) as response:
        need(response.status == 200 and response.geturl() == uri, 'original HTTP status/origin differs')
        with target.open('xb') as stream:
            h = hashlib.sha256()
            count = 0
            while True:
                budget.remaining()
                block = response.read(min(65536, size + 1 - count))
                if not block:
                    break
                count += len(block)
                budget.bytes += len(block)
                need(count <= size and budget.bytes <= MAX_TOTAL, 'original body exceeded bound')
                stream.write(block)
                h.update(block)
            need(count == size and h.hexdigest() == expected, 'original body size/digest differs')
    budget.remaining()
    return target


def signed_release(raw_path, keyring, suite, budget):
    with keyring.open('rb') as stream:
        key_bytes = stream.read(1024**2 + 1)
    need(len(key_bytes) <= 1024**2 and digest(key_bytes) == KEYRING_SHA256, 'trusted source keyring differs')
    with tempfile.TemporaryDirectory(prefix='current-noble-signature-') as scratch:
        plain = Path(scratch) / 'verified'
        result = subprocess.run(['gpgv', '--keyring', str(keyring), '--status-fd', '1',
                                 '--output', str(plain), str(raw_path)], capture_output=True,
                                timeout=budget.remaining())
        budget.remaining()
        valid = [line.split() for line in result.stdout.decode().splitlines()
                 if line.startswith('[GNUPG:] VALIDSIG ')]
        need(result.returncode == 0 and len(result.stdout) <= 65536 and len(result.stderr) <= 65536
             and len(valid) == 1 and valid[0][-1] == SIGNER
             and b'[GNUPG:] GOODSIG ' in result.stdout, 'original archive signature refused')
        text = plain.read_text()
    need(len(text.encode()) <= 1024**2 and re.search(r'^Suite: ' + re.escape(suite) + '$', text, re.M)
         and re.search(r'^Origin: Ubuntu$', text, re.M)
         and re.search(r'^Codename: noble$', text, re.M), 'signed release identity differs')
    need('\nSHA256:\n' in text, 'signed SHA256 index absent')
    result = {}
    for line in text.split('\nSHA256:\n', 1)[1].splitlines():
        if not line.startswith(' '):
            break
        parts = line.split()
        need(len(parts) == 3 and re.fullmatch('[0-9a-f]{64}', parts[0]), 'malformed signed index')
        name = relative(parts[2])
        need(name not in result and parts[1].isdigit(), 'duplicate signed index')
        result[name] = (parts[0], int(parts[1]))
    return result


def select(package, binaries, sources):
    name = package['name'].removesuffix(':amd64')
    matches = [r for r in binaries if r.get('Package') == name and r.get('Version') == package['version']
               and r.get('Architecture') in ('amd64', 'all') and r.get('SHA256') == package['debSha256']]
    # Identical signed rows can occur in security and updates; conflicting joins refuse.
    unique = {json.dumps(r, sort_keys=True) for r in matches}
    need(len(unique) == 1, 'exact declared binary absent/ambiguous: ' + name)
    binary = matches[0]
    source = re.fullmatch(r'([^ ]+)(?: \(([^)]+)\))?', binary.get('Source', name))
    need(source is not None, 'binary Source field malformed')
    source_name, version = source[1], source[2] or binary['Version']
    matches = [r for r in sources if r.get('Package') == source_name and r.get('Version') == version]
    need(len({json.dumps(r, sort_keys=True) for r in matches}) == 1, 'patched binary/source version join absent/ambiguous')
    source = matches[0]
    source_files = []
    for line in source.get('Checksums-Sha256', '').splitlines():
        if not line.strip():
            continue
        parts = line.split()
        need(len(parts) == 3 and re.fullmatch('[0-9a-f]{64}', parts[0]) and parts[1].isdigit(), 'source checksum malformed')
        filename = relative(parts[2])
        need('/' not in filename, 'source filename must be a leaf')
        source_files.append({'path': relative(source['Directory']) + '/' + filename,
                             'sha256': parts[0], 'bytes': int(parts[1])})
    need(1 <= len(source_files) <= 32 and len({r['path'] for r in source_files}) == len(source_files)
         and any(r['path'].endswith('.dsc') for r in source_files), 'complete source archive closure absent')
    allowed = []
    for row in source_files:
        # sourceUri is an identity assertion, never the download destination.
        for origin in (BASE, 'https://archive.ubuntu.com/ubuntu/', 'https://security.ubuntu.com/ubuntu/'):
            if package['sourceUri'] == origin + row['path'] and package['sourceSha256'] == row['sha256']:
                allowed.append(row)
    need(len(allowed) == 1, 'declared source archive not in exact patched Sources stanza')
    return {'package': name, 'version': binary['Version'], 'architecture': binary['Architecture'],
            'binary': {'path': relative(binary['Filename']), 'sha256': binary['SHA256'], 'bytes': int(binary['Size'])},
            'sourcePackage': source_name, 'sourceVersion': version, 'sourceFiles': source_files,
            'depends': binary.get('Depends', ''), 'preDepends': binary.get('Pre-Depends', '')}


def acquire(manifest, out, keyring, budget=None):
    spec = importlib.util.spec_from_file_location('current_native_manifest', HERE / 'current-reference-native-input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package_request = manifest.get('schema') == 'fsgg.current-reference-noble-package-request/1'
    if package_request:
        need(set(manifest) == {'schema', 'packages'}, 'closed package request required')
        module.validate_packages(manifest['packages'])
    else:
        module.manifest(manifest)
    need(not out.exists() and not out.is_symlink(), 'fresh acquisition output required')
    out.mkdir(mode=0o700)
    budget = budget or Budget()
    binaries, sources, releases, indexes, index_identities = [], [], [], [], []
    for suite, sha256 in RELEASES.items():
        # Pinned release sizes are closed source inputs, not Content-Length authority.
        size = {'noble': 255850, 'noble-updates': 126125, 'noble-security': 126127}[suite]
        path = fetch(BASE + 'dists/' + suite + '/InRelease', sha256, size, out / (suite + '.InRelease'), budget)
        index = signed_release(path, keyring, suite, budget)
        releases.append({'suite': suite, 'sha256': sha256, 'signer': SIGNER})
        for component in COMPONENTS:
            for kind, destination in [('binary-amd64/Packages.xz', binaries), ('source/Sources.xz', sources)]:
                name = component + '/' + kind
                need(name in index, 'required signed index missing')
                sha256, size = index[name]
                path = fetch(BASE + 'dists/' + suite + '/' + name, sha256, size,
                             out / (suite + '-' + component + '-' + kind.replace('/', '-')), budget)
                indexes.append((kind, path))
                index_identities.append({'suite': suite, 'path': name, 'sha256': sha256, 'bytes': size})
                budget.remaining()
    for kind, path in indexes:
        if kind.startswith('binary'):
            for row in rows(path.read_bytes()):
                if any(row.get('Package') == p['name'].removesuffix(':amd64') and row.get('Version') == p['version']
                       for p in manifest['packages']):
                    binaries.append(row)
            budget.remaining()
    source_names = {r.get('Source', r['Package']).split(' ', 1)[0] for r in binaries}
    for kind, path in indexes:
        if kind.startswith('source'):
            for row in rows(path.read_bytes()):
                if row.get('Package') in source_names:
                    sources.append(row)
            budget.remaining()
    selected = [select(package, binaries, sources) for package in manifest['packages']]
    acquired = {}
    for package in selected:
        for row in [package['binary'], *package['sourceFiles']]:
            old = acquired.get(row['path'])
            need(old is None or old == row, 'conflicting shared archive identity')
            if old is None:
                target = out / 'archives' / row['path']
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fetch(BASE + row['path'], row['sha256'], row['bytes'], target, budget)
                acquired[row['path']] = row
    receipt = {'schema': 'fsgg.current-reference-noble-acquisition/1', 'snapshot': BASE,
               'keyringSha256': KEYRING_SHA256,
               'inputKind': 'source-package-request' if package_request else 'native-input-facility',
               ('packageRequestSha256' if package_request else 'manifestSha256'): digest(module.canonical(manifest)),
               'acquisitionHelperSha256': digest(Path(__file__).read_bytes()),
               'releases': releases, 'indexes': index_identities, 'packages': selected,
               'bytes': budget.bytes, 'requests': budget.requests,
               'declaredArchivesVerified': True, 'dependencyResolution': 'not-run', 'installation': False,
               'runtimeQualification': False, 'actualAT': False, 'nativeImeAcceptance': False}
    budget.remaining()
    (out / 'acquisition.json').write_text(json.dumps(receipt, indent=2) + '\n')
    budget.remaining()  # Persistence is part of the original operation, including a late return.
    return receipt


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--package-request', type=Path, help='Bounded archive-only package request; no facility/keymap claim')
    parser.add_argument('--keyring', type=Path, default=Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('current_native_manifest_cli', HERE / 'current-reference-native-input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.package_request:
        with args.package_request.open('rb') as stream:
            raw = stream.read(65537)
        need(0 < len(raw) <= 65536, 'package request absent/oversized')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                need(key not in result, 'duplicate package request field')
                result[key] = value
            return result
        request = json.loads(raw, object_pairs_hook=unique)
        need(type(request) is dict and request.get('schema') == 'fsgg.current-reference-noble-package-request/1', 'archive-only request schema differs')
    else:
        request = module.read_manifest(os.environ.get('FSGG_CURRENT_NATIVE_INPUT_FACILITY', ''))
    acquire(request, args.output, args.keyring)
