#!/usr/bin/env python3
"""Assemble the schema-1 facility manifest from the container draft and the archive-only package request.

usage: assemble-manifest.py <native-input helper> <draft.json> <package-request.json> <out.manifest.json>
The output is the canonical single-line JSON, validated by the maintained reader, and is the dispatch input.
"""
import importlib.util, json, sys
from pathlib import Path
helper, draft, request, out = map(Path, sys.argv[1:5])
spec = importlib.util.spec_from_file_location('native', helper); N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
d = json.loads(draft.read_text()); r = json.loads(request.read_text())
value = {'schema': N.SCHEMA, 'platform': 'ubuntu-24.04-x11', 'packages': r['packages'], 'objects': d['objects'],
         'dataFiles': d['dataFiles'], 'keymaps': d['keymaps']}
raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
N.read_manifest(raw)
out.write_text(raw)
print(len(raw.encode()), N.sha(raw.encode()))
