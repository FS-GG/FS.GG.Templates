#!/usr/bin/env python3
"""Admitted downloaded-only installed WASM journey (FS-GG/.github#4710, C-J1 installed C).

Runs only from .github/workflows/wasm-installed-c.yml job installed-c, inside a fresh delegated
systemd-run unit. It executes admitted_installed_sequence from the actual inline hosted caller in
fable-reference-public.yml at the same checked-out commit. While INSTALLED_ADMISSION is None that
entry refuses before any acquisition. Once admitted it validates the dispatch, requires the
recorded WebKit host packages, provisions, qualifies tools, opens custody_gate for this entry only
and runs installed C: the checker's downloaded source stage plus 27 Playwright cases, each list/test
invocation its own require-empty managed group. Exit 0 only when installed C records "passed".
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
    namespace = {'__name__': 'wasm_installed_c'}
    exec(compile('\n'.join(line[10:] for line in blocks[0].splitlines()), 'actual-hosted-workflow', 'exec'), namespace)
    return namespace


def main():
    if sys.argv[1:] == ['--check-admission']:
        # Pre-host-write gate: refuse (exit 3) before the apt step unless source carries the admission.
        caller = actual_caller()
        try:
            caller['admission_precheck'](os.environ, caller['INSTALLED_ADMISSION'])
        except ValueError as error:
            print('installed C refused before any host write: ' + str(error), file=sys.stderr)
            return 3
        print('installed C admission bound: ' + caller['INSTALLED_ADMISSION'])
        return 0
    if sys.argv[1:]:
        raise SystemExit('usage: wasm-installed-c.py [--check-admission]')
    start = time.monotonic()
    summary = actual_caller()['admitted_installed_sequence'](os.environ, start)
    print(json.dumps({key: summary.get(key) for key in ('disposition', 'evidence')}, indent=2, default=str))
    return 0 if summary['disposition'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
