#!/usr/bin/env python3
"""Admitted bounded three-family WASM custody pilot (FS-GG/.github#4710, C-J1).

Runs only from .github/workflows/wasm-custody-pilot.yml job custody-pilot, inside a fresh
delegated systemd-run unit. It executes pilot_sequence from the actual inline hosted caller
in fable-reference-public.yml at the same checked-out commit. That entry validates the
dispatch (admitted ref, recorded admission, workflow identity, first attempt), loads the
pinned managed-group owner, probes containment, provisions the browser-only subset and runs
the Chromium library scan plus the normal, forced-deadline and leader-exit cases per family.
Installed C stays held: RUNTIME_ADMITTED, the literal-false steps and custody_gate are untouched.
Exit 0 only when custody-pilot.json records disposition "completed".
"""
import json
import os
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORKFLOW = HERE.parents[2] / '.github/workflows/fable-reference-public.yml'


def actual_caller():
    text = WORKFLOW.read_text()
    blocks = re.findall(r"-- /usr/bin/python3 -I - <<'HOSTED_WASM'\n(.*?)\n          HOSTED_WASM", text, re.S)
    if len(blocks) != 1:
        raise SystemExit('exactly one actual hosted caller required')
    namespace = {'__name__': 'wasm_custody_pilot'}
    exec(compile('\n'.join(line[10:] for line in blocks[0].splitlines()), 'actual-hosted-workflow', 'exec'), namespace)
    return namespace


def main():
    start = time.monotonic()
    caller = actual_caller()
    if sys.argv[1:] == ['--print-webkit-packages']:
        # The admitted package list, one name per line, for the pre-unit apt step.
        packages = list(caller['PILOT_WEBKIT_PACKAGES'])
        if not packages or not all(re.fullmatch(r'[a-z0-9][a-z0-9.+-]{1,63}', name) for name in packages):
            raise SystemExit('admitted package list invalid')
        print('\n'.join(packages))
        return 0
    if sys.argv[1:] == ['--check-admission']:
        # Pre-host-write gate: refuse (exit 3) before the apt step unless source carries the admission.
        try:
            caller['admission_precheck'](os.environ, caller['PILOT_ADMISSION'])
        except ValueError as error:
            print('custody pilot refused before any host write: ' + str(error), file=sys.stderr)
            return 3
        print('custody pilot admission bound: ' + caller['PILOT_ADMISSION'])
        return 0
    if sys.argv[1:]:
        raise SystemExit('usage: wasm-custody-pilot.py [--print-webkit-packages | --check-admission]')
    summary = caller['pilot_sequence'](os.environ, start)
    print(json.dumps({key: summary.get(key) for key in ('disposition', 'reasons', 'evidence')}, indent=2, default=str))
    return 0 if summary['disposition'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
