#!/usr/bin/env python3
"""Dispatch-bound admission of the current-public full AT run (FS-GG/.github#4817).

The source gate stays closed: with no admission the full route is held. Root lifts it for ONE run by supplying
the string this module issues as the `current-public-at-admission` dispatch input. The string states the exact tuple
the run may execute and an expiry; the run recomputes that tuple from what is actually running and refuses on any
difference. The string is not a credential: anyone can compute it, so its strength is the exact binding, the expiry
and the single-run census below, not secrecy.

  admission := fsgg.at-admission/1;notAfter=<UTC RFC3339 Z>;sha256=<digest of the canonical tuple>
  tuple     := schema, scope single-run, notAfter, Templates revision, caller repository+revision, producer
               (version, source, run, artifact, archive/custody digests), facility manifest digest, install roots digest

`python3 current-reference-at-admission.py issue ...` prints the string and the tuple. `census` is the single-run
control: it refuses unless this is attempt 1 and no other run of the same caller workflow has passed (or is passing)
the admission guard step.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCHEMA = 'fsgg.at-admission/1'
PREFIX = 'fsgg.at-admission/1;'
FORMAT = re.compile(r'fsgg\.at-admission/1;notAfter=(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ);sha256=([0-9a-f]{64})')
MAX_HORIZON = datetime.timedelta(days=7)
GUARD_STEP = 'Refuse held current AT before acquisition or setup'
CALLER_REPOSITORY = 'FS-GG/FS.GG.Rendering'
PRODUCER_KEYS = {'version': 'PRODUCER_VERSION', 'source': 'PRODUCER_SOURCE', 'run': 'PRODUCER_RUN', 'artifact': 'PRODUCER_ARTIFACT',
                 'archiveSha256': 'PRODUCER_ARCHIVE_SHA256', 'custodySha256': 'PRODUCER_CUSTODY_SHA256'}


class Held(RuntimeError):
    pass


def need(value, message):
    if not value:
        raise Held('current public AT held: ' + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def native_helper():
    spec = importlib.util.spec_from_file_location('admission_native', HERE / 'current-reference-native-input.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_time(text):
    return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


def tuple_of(templates, caller_repository, caller, producer, manifest_sha256, roots_sha256, not_after):
    return {'schema': SCHEMA, 'scope': 'single-run', 'notAfter': not_after, 'templates': {'revision': templates},
            'caller': {'repository': caller_repository, 'revision': caller},
            'producer': {key: producer[key] for key in sorted(PRODUCER_KEYS)},
            'facility': {'manifestSha256': manifest_sha256}, 'installRoots': {'requestSha256': roots_sha256}}


def admission_string(value):
    return '%snotAfter=%s;sha256=%s' % (PREFIX, value['notAfter'], sha(canonical(value)))


def roots_sha256():
    return sha((HERE / 'fixtures/noble-source-prefix-request.json').read_bytes())


def running_facts(environment, not_after, git=None):
    """The tuple as this run actually sees it. Missing facts refuse."""
    git = git or (lambda *args: subprocess.check_output(['git', '-C', str(ROOT), *args], text=True, timeout=20).strip())
    need(environment.get('RENDERING_INPUT_SOURCE') == 'current-public-composition', 'admission applies only to the current-public-composition route')
    producer = {key: environment.get(name, '') for key, name in PRODUCER_KEYS.items()}
    need(all(producer.values()), 'producer tuple absent from the running environment')
    raw = environment.get('FSGG_CURRENT_NATIVE_INPUT_FACILITY', '')
    need(raw, 'facility manifest absent from the running environment')
    native = native_helper()
    try:
        manifest_sha256 = native.sha(native.canonical(native.read_manifest(raw)))
    except (RuntimeError, ValueError) as error:
        raise Held('current public AT held: facility manifest invalid: %s' % error) from error
    caller_revision = environment.get('GITHUB_SHA', '')
    need(re.fullmatch('[0-9a-f]{40}', caller_revision), 'caller revision absent')
    try:
        templates = git('rev-parse', 'HEAD')
    except (OSError, subprocess.SubprocessError) as error:
        raise Held('current public AT held: Templates revision unreadable') from error
    need(re.fullmatch('[0-9a-f]{40}', templates), 'Templates revision unreadable')
    return tuple_of(templates, environment.get('GITHUB_REPOSITORY', ''), caller_revision, producer, manifest_sha256, roots_sha256(), not_after)


def verify(environment, now=None, git=None):
    """Pure check, run at every guard site: format, expiry, horizon and the exact running tuple."""
    supplied = environment.get('FSGG_CURRENT_PUBLIC_AT_ADMISSION', '')
    match = FORMAT.fullmatch(supplied)
    need(match, 'no valid dispatch-bound admission supplied')
    not_after, digest = match.groups()
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        expiry = parse_time(not_after)
    except ValueError as error:
        raise Held('current public AT held: admission expiry malformed') from error
    need(now < expiry, 'admission expired at ' + not_after)
    need(expiry - now <= MAX_HORIZON, 'admission expiry is beyond the 7 day horizon')
    facts = running_facts(environment, not_after, git)
    need(facts['caller']['repository'] == CALLER_REPOSITORY, 'caller repository differs')
    need(sha(canonical(facts)) == digest, 'admission does not match the running tuple')
    return facts


def _api(path, token, opener=urllib.request.urlopen):
    request = urllib.request.Request('https://api.github.com' + path, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'fsgg-at-admission', **({'Authorization': 'Bearer ' + token} if token else {})})
    with opener(request, timeout=30) as response:
        return json.load(response)


def census(environment, api=None):
    """Single-run control. Fail closed on anything unknown: attempt, workflow identity or an unreadable run list."""
    api = api or (lambda path: _api(path, environment.get('GH_TOKEN') or environment.get('GITHUB_TOKEN')))
    need(environment.get('GITHUB_RUN_ATTEMPT') == '1', 'a rerun cannot reuse a single-run admission')
    repository, run_id = environment.get('GITHUB_REPOSITORY', ''), environment.get('GITHUB_RUN_ID', '')
    reference = re.fullmatch(r'([^/]+/[^/]+)/\.github/workflows/([A-Za-z0-9_.-]+\.yml)@\S+', environment.get('GITHUB_WORKFLOW_REF', ''))
    need(repository == CALLER_REPOSITORY and run_id.isdigit() and reference and reference[1] == repository, 'caller workflow identity unreadable')
    workflow = reference[2]
    mine, seen = int(run_id), []
    for page in range(1, 6):
        try:
            batch = api('/repos/%s/actions/workflows/%s/runs?event=workflow_dispatch&per_page=100&page=%d' % (repository, workflow, page))
        except Exception as error:  # noqa: BLE001 - any failure to read the census refuses
            raise Held('current public AT held: run census unavailable (%s)' % type(error).__name__) from error
        rows = batch.get('workflow_runs')
        need(type(rows) is list, 'run census malformed')
        seen.extend(rows)
        if len(rows) < 100:
            break
    else:
        raise Held('current public AT held: run census exceeds its bound')
    for row in seen:
        if row['id'] == mine:
            continue
        try:
            jobs = api('/repos/%s/actions/runs/%d/jobs?filter=all&per_page=100' % (repository, row['id']))['jobs']
        except Exception as error:  # noqa: BLE001
            raise Held('current public AT held: run census unavailable (%s)' % type(error).__name__) from error
        for job in jobs:
            for step in job.get('steps', []):
                if step['name'] != GUARD_STEP:
                    continue
                passed = step.get('conclusion') == 'success'
                running = step.get('conclusion') is None and row['id'] < mine and job.get('status') in ('in_progress', 'queued')
                need(not passed, 'run %d already passed the admission guard' % row['id'])
                need(not running, 'earlier run %d is at the admission guard' % row['id'])
    return {'runsExamined': len(seen), 'run': mine, 'attempt': 1}


def guard(environment, now=None, git=None, api=None, with_census=False):
    facts = verify(environment, now, git)
    receipt = {'admission': 'verified', 'tupleSha256': sha(canonical(facts)), 'notAfter': facts['notAfter']}
    if with_census:
        receipt['census'] = census(environment, api)
    return receipt


def producer_rows(workflow_text):
    rows = {}
    for key, name in PRODUCER_KEYS.items():
        found = re.findall(r"^      %s: \$\{\{ inputs\.rendering-input-source == 'current-public-composition' && '([^']+)'" % name, workflow_text, re.M)
        need(len(found) == 1, 'producer row absent/ambiguous: ' + name)
        rows[key] = found[0]
    return rows


def issue(templates, caller, manifest_path, not_after, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    for label, revision in (('templates', templates), ('caller', caller)):
        need(re.fullmatch('[0-9a-f]{40}', revision), label + ' revision must be a full commit')
    expiry = parse_time(not_after)
    need(now < expiry <= now + MAX_HORIZON, 'expiry must be in the future and within 7 days')
    native = native_helper()
    manifest_sha256 = native.sha(native.canonical(native.read_manifest(Path(manifest_path).read_text())))
    producer = producer_rows((ROOT / '.github/workflows/fable-external-reference-source.yml').read_text())
    value = tuple_of(templates, CALLER_REPOSITORY, caller, producer, manifest_sha256, roots_sha256(), not_after)
    return admission_string(value), value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('issue')
    one.add_argument('--templates', required=True, help='Templates commit the run will execute')
    one.add_argument('--caller', required=True, help='Rendering commit the run is dispatched at')
    one.add_argument('--manifest', required=True, type=Path)
    one.add_argument('--not-after', required=True, help='UTC expiry, e.g. 2026-11-02T00:00:00Z (max 7 days)')
    sub.add_parser('guard', help='verify the supplied admission against the running tuple and run the single-run census')
    args = parser.parse_args(argv)
    if args.command == 'issue':
        text, value = issue(args.templates, args.caller, args.manifest, args.not_after)
        print(json.dumps({'admission': text, 'tuple': value}, indent=2, sort_keys=True))
    else:
        print(json.dumps(guard(os.environ, with_census=True), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Held as error:
        print(error, file=sys.stderr)
        sys.exit(1)
