#!/usr/bin/env python3
"""Binding probe for the C-J1 managed-group contract (non-required, no provisioning).

It executes the actual inline hosted WASM caller's pin, owner loading, containment probe and
managed executor against the real pinned fsgg.managed-group-contract/1 owner, using tiny host
commands only. It acquires no toolchain or package and runs no browser, WASM journey or
installed C; those stay held by the caller's literal gates.

--expect unavailable: outside a delegated unit, the probe and every run refuse before launch.
--expect contained:   inside a fresh delegated unit, a bound group succeeds with birth binding,
                      a detached leftover fails under require-empty and is retired, and drifted,
                      unbound or expired calls refuse before launch.
"""
import argparse
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
    blocks = re.findall(r"-- /usr/bin/python3 - <<'HOSTED_WASM'\n(.*?)\n          HOSTED_WASM", text, re.S)
    if len(blocks) != 1:
        raise SystemExit('exactly one actual hosted caller required')
    namespace = {'__name__': 'managed_group_binding_probe'}
    exec(compile('\n'.join(line[10:] for line in blocks[0].splitlines()), 'actual-hosted-workflow', 'exec'), namespace)
    return namespace


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect', choices=('unavailable', 'contained'), required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--tasks-max')
    parser.add_argument('--memory-max')
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    if not root.is_absolute() or os.path.lexists(root):
        raise SystemExit('fresh absolute probe root required')
    root.mkdir(mode=0o700)
    root = pathlib.Path(os.path.realpath(root))
    caller = actual_caller()
    checks = []

    def check(name, ok, detail=None):
        checks.append({'check': name, 'passed': bool(ok), 'detail': detail})

    def refusal(call):
        try:
            call()
        except (RuntimeError, ValueError) as error:
            return str(error)
        return None

    def last_receipt(receipts):
        return json.loads((pathlib.Path(receipts[-1]['outDir']) / 'receipt.json').read_text())

    deadline = time.monotonic() + 120
    owner = caller['load_owner'](root, deadline)  # genuine closed acquisition of the exact pin
    check('owner-pin', owner.OWNER_SHA256 == caller['OWNER']['sha256'] and owner.CONTRACT_SCHEMA == caller['OWNER']['contract'])
    env = {'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin'}
    identities, receipts = {}, []
    shell, _ = caller['host_image']('/bin/sh')
    caller['bind_identity'](identities, shell, 'host-observed')
    execute = caller['managed_executor'](owner, root, deadline, identities, 'setup', receipts)

    if args.expect == 'unavailable':
        cause = refusal(lambda: caller['probe_containment'](owner, root))
        check('probe-refuses', cause is not None and 'containment unavailable' in cause, cause)
        cause = refusal(lambda: execute(['/bin/sh', '-c', 'echo launched'], root, env))
        check('run-refuses-before-launch', cause is not None and 'refused: containment-unavailable' in cause, cause)
        if receipts:
            receipt = last_receipt(receipts)
            check('nothing-launched', receipt['launch'] == {'attempted': False, 'launched': False, 'error': None} and receipt['refusal'] == 'containment-unavailable', receipt['launch'])
    else:
        probe = caller['probe_containment'](owner, root)
        check('probe-available', probe['available'], probe.get('refusal'))
        unit = pathlib.Path(probe['delegatedRoot'])
        for name, expected in (('pids.max', args.tasks_max), ('memory.max', args.memory_max)):
            actual = (unit / name).read_text().strip() if (unit / name).is_file() else None
            check('unit-hard-limit:' + name, expected is not None and actual == expected, actual)
        output = execute(['/bin/sh', '-c', 'sleep 0.3; printf bound'], root, env)
        receipt = last_receipt(receipts)
        check('bound-group-succeeds', output == 'bound' and receipt['outcome'] == 'succeeded', output)
        check('birth-bound', receipt['leader']['image'] == 'admitted' and receipt['leader']['noNewPrivileges'] == '1', receipt['leader'])
        check('contained-and-removed', receipt['custody'] == 'contained' and receipt['cleanup'] == 'observed-empty-removed' and receipt['residualInRoot'] == [], [receipt['custody'], receipt['cleanup']])
        check('receipt-owner-pin', receipt['owner']['sha256'] == caller['OWNER']['sha256'])
        check('require-empty-profile', receipt['profile']['retirement']['onLeaderExit'] == 'require-empty')
        cause = refusal(lambda: execute(['/bin/sh', '-c', 'setsid sleep 60 </dev/null >/dev/null 2>&1 & echo started'], root, env))
        check('detached-leftover-fails', cause is not None and 'leader exited with live contained members' in cause, cause)
        receipt = last_receipt(receipts)
        check('detached-leftover-retired', receipt['cleanup'] == 'observed-empty-removed' and receipt['residualInRoot'] == [] and bool(receipt['residualAfterLeaderExit']) and (receipt['retirement']['termSignals'] > 0 or receipt['retirement']['cgroupKill']), [receipt['cleanup'], receipt['retirement']])
        bound = identities[shell]
        identities[shell] = {**bound, 'sha256': '0' * 64}
        cause = refusal(lambda: execute(['/bin/sh', '-c', 'echo drifted'], root, env))
        check('drifted-identity-refuses', cause is not None and 'refused: executable-identity-mismatch' in cause, cause)
        check('drift-not-launched', last_receipt(receipts)['launch']['attempted'] is False)
        identities[shell] = bound
        count = len(receipts)
        cause = refusal(lambda: execute(['/usr/bin/true'], root, env))
        check('unbound-executable-refuses', cause is not None and 'identity not bound' in cause and len(receipts) == count, cause)
        expired = caller['managed_executor'](owner, root, time.monotonic() - 1, identities, 'setup', receipts)
        cause = refusal(lambda: expired(['/bin/sh', '-c', 'echo late'], root, env))
        check('expired-phase-refuses', cause is not None and 'refused: deadline-exhausted' in cause, cause)

    result = {'schema': 'fsgg.templates.managed-group-binding-probe/1', 'expect': args.expect,
              'owner': caller['OWNER'], 'checks': checks, 'passed': bool(checks) and all(c['passed'] for c in checks)}
    (root / 'binding-probe.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
