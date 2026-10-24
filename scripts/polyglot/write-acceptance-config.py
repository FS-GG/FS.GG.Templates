"""Mechanical fixed configuration for the maintained SDD driver; no SDK policy."""
import json
import math
import os
from pathlib import Path
import sys
import time

provider, private = sys.argv[1:]
if provider not in ('typescript-cli', 'javascript-cli', 'rust-cli', 'go-cli'):
    raise ValueError('closed provider required')
root = Path(private)
remaining = float(os.environ['FSGG_QUALIFICATION_WORK_END_MONOTONIC']) - time.monotonic() - 60
if not math.isfinite(remaining) or remaining < 1:
    raise ValueError('original qualification clock exhausted')
end = min(300, remaining)
dotnet = os.environ['FSGG_QUALIFIED_DOTNET']
# Native image/closure and task cache preparation belong to the independently
# admitted outer profile, not the declarations in this mechanically written file.
runtime = {'mode': 'native-runtime', 'backend': 'pid-namespace',
           'cwd': str(root), 'timeoutSeconds': min(180, end),
           'cleanupSeconds': 30, 'outputBytes': 8*1048576}
fixture = json.loads((root / 'request.json').read_bytes())
config = {'sourceRoot': os.environ['FSGG_SDD_SOURCE_ROOT'],
          'fixtureManifest': str(root / 'request.json'),
          'cliCommand': [dotnet, 'exec', '--fx-version', '10.0.12', os.environ['FSGG_SDD_CLI_DLL']],
          'verifyCommand': [dotnet, 'exec', '--fx-version', '10.0.12', os.environ['FSGG_POLYGLOT_TOOL_DLL'], 'readback'],
          'transportExecutable': dotnet, 'runtime': runtime,
          'verification': dict(runtime, timeoutSeconds=min(60, end)),
          'totalSeconds': end,
          'fixtureExpectations': fixture['fixtureExpectations']}
with (root / 'config.json').open('x') as stream:
    json.dump(config, stream, indent=2)
    stream.flush()
    os.fsync(stream.fileno())
