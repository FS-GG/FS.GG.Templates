#!/usr/bin/env python3
"""Held D5 consumer of the canonical managed owner; this file is not a supervisor.

Transport decisions concern process receipts only. ProviderTool remains the sole
receiver/backend policy owner. No CLI mode launches a workload.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time

HERE = Path(__file__).resolve().parent
ADMISSION = None
# The existing retained outer controller is4816-specific. Do not impersonate4816,
# patch its module globals, or copy it. A reviewed explicit caller seam is required.
OUTER_CALLER_CONTRACT = None
WORKFLOW = 'FS-GG/FS.GG.Templates/.github/workflows/svg-release-d5-current-public.yml@refs/heads/main'
READER = {'revision': '1d832f2214147065bb56e0afd76d600ed01bd27d',
          'path': 'tests/composition/fable-game/retained-reference-rehearsal.py',
          'sha256': '4e4fb76333804a3f16c36ef16ae1fd8aac165fae6b5cf8492157f87f18dcfd43'}
OWNER = {'revision': 'ac22206560f3eddfea524ce8f752ff1d0dfeec4e',
         'path': 'eng/managed_group_owner.py', 'bytes': 45315,
         'sha256': 'd846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0'}
# The supplied acquisition and canonical build receipts were inspected, not run.
GO = {'url': 'https://go.dev/dl/go1.24.1.linux-amd64.tar.gz',
      'sha256': 'cb2396bae64183cdccf81a9a6df0aea3bce9511fc21469fb89a0c00470088073',
      'maximumBytes': 134217728}
LMT = {'sourceSha256': '88bc47acae2c26919ab96a5cafa80b12fac762092c57840a2baad1afcc7feda3',
       'sha256': '37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10',
       'ldflags': '-buildid=IvXAt1kJ-3iINki1alCT/Ut12KGabgkWIkwVpw-xO/c4zkZMLAubfWHvjZOY8o/8-oR_8tNNndNgfMVoD8F -B 0x03d1703027f57ed4dd2ba90b7cdfc8cdea2815da'}
BUDGET = {'setup': 720, 'generation': 360, 'backend': 480,
          'collection': 120, 'cleanup': 30, 'overhead': 90}
UNIT = {'CPUQuota': '200%', 'MemoryMax': '8G', 'MemorySwapMax': '0',
        'TasksMax': '512', 'RuntimeMaxSec': '1800', 'TimeoutStopSec': '5',
        'Delegate': 'yes', 'NoNewPrivileges': 'yes', 'KillMode': 'control-group'}
SOURCE_KEYS = ('EVENT', 'REPOSITORY', 'REF', 'SHA', 'ADMITTED_REF', 'CHECKOUT_HEAD',
               'WORKFLOW_REF', 'WORKFLOW_SHA', 'RUN_ID', 'RUN_ATTEMPT', 'UNIT_NAME', 'ADMISSION')


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate receipt property')
        result[key] = value
    return result


def read_json(path, maximum=131072):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
            'bounded regular receipt required')
    return json.loads(path.read_text(), object_pairs_hook=unique)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def admission_join(env, selected):
    """Pure join; production only calls this with the source literal ADMISSION."""
    require(selected is not None, 'HELD: runtime admission None; retirement unqualified')
    require(re.fullmatch(r'https://github.com/FS-GG/\.github/issues/4849#issuecomment-[0-9]+', selected), 'wrong D5 admission')
    require(env.get('ADMISSION') == selected, 'admission input differs')
    require(env.get('EVENT') == 'workflow_dispatch' and env.get('REPOSITORY') == 'FS-GG/FS.GG.Templates', 'same-repository dispatch required')
    require(env.get('REF') == 'refs/heads/main' and env.get('RUN_ATTEMPT') == '1', 'main first attempt required')
    head = env.get('SHA', '')
    require(re.fullmatch(r'[0-9a-f]{40}', head) and all(env.get(k) == head for k in ('ADMITTED_REF', 'CHECKOUT_HEAD', 'WORKFLOW_SHA')), 'source/checkout/workflow differs')
    require(env.get('WORKFLOW_REF') == WORKFLOW and re.fullmatch(r'[0-9]+', env.get('RUN_ID', '')), 'workflow/run identity differs')
    require(env.get('UNIT_NAME') == 'fsgg-mg-templates-d5-' + env['RUN_ID'] + '-1', 'D5 unit identity differs')
    return {key: env[key] for key in SOURCE_KEYS}


def original_clock(path, source, boot, now):
    """Validate the actual first-step observation; never start or renew its clock."""
    value = read_json(path, 4096)
    keys = tuple(k for k in SOURCE_KEYS if k not in ('ADMISSION', 'ADMITTED_REF', 'CHECKOUT_HEAD'))
    require(value.get('source') == {key: source[key] for key in keys}, 'first clock source differs')
    require(value.get('scope') == 'first-workflow-step' and value.get('boot') == boot, 'first clock boot/scope differs')
    start = value.get('startedMonotonic')
    require(type(start) in (int, float) and math.isfinite(start) and 0 <= start <= now, 'first clock invalid')
    require(now + 1800 + 5 + 30 < start + 2100, 'original setup consumed unit/readback reserve')
    return start


def phase_deadline(start, phase, now):
    phases = ('setup', 'generation', 'backend')
    require(phase in phases and all(type(v) in (int, float) and math.isfinite(v) for v in (start, now)), 'invalid original phase')
    require(0 <= start <= now, 'original phase clock differs')
    cap = start + sum(BUDGET[p] for p in phases[:phases.index(phase) + 1])
    deadline = min(now + BUDGET[phase], cap)
    require(deadline > now, 'original phase deadline expired')
    return deadline


def load_reader(workspace):
    """Read-only immutable dependency. Its4816 product/controller entry is never called."""
    workspace = Path(workspace).resolve()
    path = workspace / READER['path']
    require(path.is_file() and not path.is_symlink() and sha(path) == READER['sha256'], 'reviewed repaired capacity reader dependency unavailable')
    spec = importlib.util.spec_from_file_location('d5_canonical_capacity_reader', path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def managed_transport(caller, owner, root, deadline, identities, phase, receipts):
    """Use the existing executor unchanged; no local fork/kill/wait/supervision."""
    require(phase in ('setup', 'generation', 'backend'), 'closed D5 phase required')
    require(getattr(owner, 'OWNER_SHA256', None) == OWNER['sha256'], 'managed owner identity differs')
    # Existing phase tags select receipt names only; D5 retains its original deadline.
    tag = {'setup': 'setup', 'generation': 'custody', 'backend': 'installed'}[phase]
    return caller['managed_executor'](owner, root, deadline, identities, tag, receipts)


def refusal_receipt(owner, receipt, directory, argv, cwd, env):
    """Authenticate a genuine managed command failure, retaining its failed outcome.

    This establishes only the expected positive-nonzero *transport* result. The
    original actual JSON and owner snapshots still require F# backend validation.
    """
    require(receipt.get('schema') == 'fsgg.managed-group-receipt/1'
            and receipt.get('contract') == 'fsgg.managed-group-contract/1', 'wrong process receipt')
    require(receipt.get('owner', {}).get('sha256') == OWNER['sha256'], 'receipt owner differs')
    require(read_json(Path(directory) / 'receipt.json') == receipt, 'original process receipt differs')
    profile = receipt['profile']
    _, digest = owner.validate_profile(profile)
    require(receipt.get('profileSha256') == digest and profile['argv'] == argv
            and profile['cwd'] == str(cwd) and profile['environmentKeys'] == sorted(env), 'command/profile join differs')
    require(profile['executable']['path'] == os.path.realpath(argv[0]), 'receipt executable differs')
    require(str(Path(directory).resolve()) == str(Path(directory))
            and Path(directory).is_relative_to(Path(profile['root']))
            and Path(cwd).is_relative_to(Path(profile['root'])), 'receipt root/directory differs')
    require(receipt.get('launch', {}).get('attempted') is True and receipt.get('launch', {}).get('launched') is True, 'refusal command was not launched')
    require(profile['retirement']['onLeaderExit'] == 'require-empty', 'wrong retirement policy')
    require(profile['containment'] == 'cgroup2-delegated', 'wrong containment policy')
    exit_value = receipt.get('exit') or {}
    code = exit_value.get('code')
    require(type(code) is int and 0 < code <= 255 and exit_value.get('signal') is None, 'expected positive nonzero exit required')
    require(receipt.get('outcome') == 'failed' and receipt.get('refusal') is None
            and receipt.get('firstCause') == 'RuntimeError: command failed with exit ' + str(code)
            and receipt.get('additionalFailures') == [], 'non-command failure cannot be expected refusal')
    require(receipt.get('cleanup') == 'observed-empty-removed' and receipt.get('custody') == 'contained'
            and receipt.get('escaped') == [] and receipt.get('residualInRoot') == [], 'refusal process retirement unqualified')
    retirement = receipt.get('retirement') or {}
    require(retirement.get('leaderReaped') is True and retirement.get('leafRemoved') is True
            and retirement.get('populatedAfter') is False, 'refusal process not reaped/removed')
    require(all(row.get('removed') is True for row in receipt.get('createdCgroups', [])), 'created process group remains')
    for name in ('stdout', 'stderr'):
        stream = receipt.get('streams', {}).get(name, {})
        path = Path(directory) / (name + '.log')
        require(stream.get('eof') is True and stream.get('capped') is False and stream.get('sinkError') is None, 'refusal stream unqualified')
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216
                and path.stat().st_size == stream.get('bytes') and sha(path) == stream.get('sha256'), 'original refusal stream differs')
    return Path(directory) / 'stdout.log'


def wrong_profile(execute, owner, receipts, argv, sdd_core, typed_arguments, cwd, env):
    """Only the actual typed d5-refused plan may consume an expected nonzero."""
    require(isinstance(typed_arguments, list) and 0 < len(typed_arguments) <= 128
            and all(isinstance(v, str) for v in typed_arguments), 'bounded typed refusal argv required')
    require(len(argv) >= 3 and argv[1] == str(sdd_core) and argv[2:] == typed_arguments and typed_arguments[:2] == ['typed-sdd', 'author']
            and '--backend' not in typed_arguments, 'typed refusal argv differs')
    require(typed_arguments.count('--work') == 1 and typed_arguments.index('--work') + 1 < len(typed_arguments)
            and typed_arguments[typed_arguments.index('--work') + 1] == 'd5-refused', 'wrong refusal work')
    require(Path(sdd_core).is_absolute() and Path(sdd_core).is_file() and not Path(sdd_core).is_symlink(), 'regular installed SDD core required')
    core_hash = sha(sdd_core)
    previous = len(receipts)
    try:
        execute(argv, cwd, env, inputs=[Path(sdd_core)])
    except RuntimeError as failure:
        cause = failure.__cause__
        require(isinstance(cause, owner.GroupFailed) and len(receipts) == previous + 1, 'not the original managed command failure')
        entry = receipts[-1]
        require(entry.get('status') == 'failed' and entry.get('executable') == os.path.realpath(argv[0])
                and entry.get('inputs', {}).get(str(sdd_core)) == core_hash and sha(sdd_core) == core_hash, 'managed index/input join differs')
        return refusal_receipt(owner, cause.receipt, entry['outDir'], argv, cwd, env)
    raise ValueError('wrong-profile author unexpectedly succeeded')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    require(args == ['--check-admission'], 'usage: d5-managed-runtime.py --check-admission')
    admission_join(os.environ, ADMISSION)
    # No environment/CLI bypass; this remains a source integration prerequisite.
    require(OUTER_CALLER_CONTRACT is not None, 'HELD: canonical D5 outer caller contract unavailable')
    raise ValueError('HELD: runtime assembly and retirement remain unqualified')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(3)
