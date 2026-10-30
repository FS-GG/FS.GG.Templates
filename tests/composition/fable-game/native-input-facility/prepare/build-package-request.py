#!/usr/bin/env python3
"""Host-side: join the container draft's installed package tuples to the signed snapshot Sources and emit
the closed fsgg.current-reference-noble-package-request/1 object. Uses the maintained helper's own parsers."""
import importlib.util, json, sys
from pathlib import Path
helper, metadata, draft, out = map(Path, sys.argv[1:5])
spec = importlib.util.spec_from_file_location('acq', helper); A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
d = json.loads(draft.read_text())
want = {(p['name'].removesuffix(':amd64'), p['version'], p['debSha256']) for p in d['packages']}
names = {(n, v) for n, v, _ in want}
binaries, sources = [], []
paths = sorted(metadata.glob('*Packages.xz')) + sorted(metadata.glob('*Sources.xz'))
for path in sorted(metadata.iterdir()):
    if not path.name.endswith('.xz'): continue
    for row in A.rows(path.read_bytes()):
        if 'binary-amd64' in path.name and (row.get('Package'), row.get('Version')) in names: binaries.append(row)
srcnames = {r.get('Source', r['Package']).split(' ', 1)[0] for r in binaries}
for path in sorted(metadata.iterdir()):
    if 'Sources' in path.name:
        for row in A.rows(path.read_bytes()):
            if row.get('Package') in srcnames: sources.append(row)
packages = []
for p in d['packages']:
    base = p['name'].removesuffix(':amd64')
    m = [r for r in binaries if r['Package'] == base and r['Version'] == p['version'] and r.get('SHA256') == p['debSha256']]
    binary, _ = A.binary_aliases(m)
    import re
    src = re.fullmatch(r'([^ ]+)(?: \(([^)]+)\))?', binary.get('Source', base))
    sname, sver = src[1], src[2] or binary['Version']
    cands = A.patched_sources(sname, sver, sources)
    files = sorted({(f['path'], f['sha256']) for c in cands[:1] for f in A.source_files(c) if f['path'].endswith('.dsc')})
    assert len(files) == 1, (base, files)
    packages.append({'name': p['name'], 'version': p['version'], 'debSha256': p['debSha256'],
                     'sourceUri': A.BASE + files[0][0], 'sourceSha256': files[0][1]})
packages.sort(key=lambda r: r['name'])
out.write_text(json.dumps({'schema': 'fsgg.current-reference-noble-package-request/1', 'packages': packages}, indent=2) + '\n')
print(len(packages), 'rows')
