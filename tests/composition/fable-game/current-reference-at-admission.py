#!/usr/bin/env python3
"""Dispatch-bound admission of the current-public full AT run (FS-GG/.github#4817).

The source gate stays closed: with no admission the full route is held. Root lifts it for ONE run by supplying
the string this module issues as the `current-public-at-admission` dispatch input. The string states the exact tuple
the run may execute and an expiry; the run recomputes that tuple from what is actually running and refuses on any
difference. The string is not a credential: anyone can compute it, so its strength is the exact binding, the expiry
and the single-run census below, not secrecy.

  admission := fsgg.at-admission/1;notBefore=<UTC>;notAfter=<UTC>;sha256=<digest of the canonical tuple>
  tuple     := schema, scope single-run, notBefore, notAfter, Templates revision, caller repository+revision, producer
               (version, source, run, artifact, archive/custody digests), facility manifest digest, install roots digest

`python3 current-reference-at-admission.py issue ...` prints the string and the tuple, after checking that the plan's
template defaults the same FS.GG.UI version as the producer. `census` is the single-run control, scoped to the
notBefore..notAfter window of this admission and to the exact Rendering caller workflow path: it refuses unless this is
attempt 1, no other run in the window has passed the guard step, and no other run in the window is queued or running
its current-public job (symmetric, regardless of run id). `census-dry-run` is the read-only identity probe for a
non-admitted preflight.
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
TIME = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'
FORMAT = re.compile(r'fsgg\.at-admission/1;notBefore=(%s);notAfter=(%s);sha256=([0-9a-f]{64})' % (TIME, TIME))
SKEW = datetime.timedelta(minutes=2)
MAX_HORIZON = datetime.timedelta(days=7)
GUARD_STEP = 'Refuse held current AT before acquisition or setup'
JOB_PREFIX = 'Current published composition and held AT journey'
CALLER_REPOSITORY = 'FS-GG/FS.GG.Rendering'
CALLER_WORKFLOW = 'templates-external-reference-qualification.yml'
UI_DEFAULTS = (('content/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj', 'FsGgSvgInputVersion'),
               ('content/templates/fs-gg-fable-game/SvgFoundation/Studio/Studio.fsproj', 'FsGgSvgAuthoringVersion'))
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


def tuple_of(templates, caller_repository, caller, producer, manifest_sha256, roots_sha256, not_before, not_after):
    return {'schema': SCHEMA, 'scope': 'single-run', 'notBefore': not_before, 'notAfter': not_after, 'templates': {'revision': templates},
            'caller': {'repository': caller_repository, 'revision': caller},
            'producer': {key: producer[key] for key in sorted(PRODUCER_KEYS)},
            'facility': {'manifestSha256': manifest_sha256}, 'installRoots': {'requestSha256': roots_sha256}}


def admission_string(value):
    return 'fsgg.at-admission/1;notBefore=%s;notAfter=%s;sha256=%s' % (value['notBefore'], value['notAfter'], sha(canonical(value)))


def roots_sha256():
    return sha((HERE / 'fixtures/noble-source-prefix-request.json').read_bytes())


def running_facts(environment, not_before, not_after, git=None):
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
    return tuple_of(templates, environment.get('GITHUB_REPOSITORY', ''), caller_revision, producer, manifest_sha256, roots_sha256(), not_before, not_after)


def verify(environment, now=None, git=None):
    """Pure check, run at every guard site: format, expiry, horizon and the exact running tuple."""
    supplied = environment.get('FSGG_CURRENT_PUBLIC_AT_ADMISSION', '')
    match = FORMAT.fullmatch(supplied)
    need(match, 'no valid dispatch-bound admission supplied')
    not_before, not_after, digest = match.groups()
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        start, expiry = parse_time(not_before), parse_time(not_after)
    except ValueError as error:
        raise Held('current public AT held: admission time malformed') from error
    need(now >= start - SKEW, 'admission is not valid before ' + not_before)
    need(now < expiry, 'admission expired at ' + not_after)
    need(start < expiry <= start + MAX_HORIZON, 'admission window is empty or beyond the 7 day horizon')
    facts = running_facts(environment, not_before, not_after, git)
    need(facts['caller']['repository'] == CALLER_REPOSITORY, 'caller repository differs')
    need(sha(canonical(facts)) == digest, 'admission does not match the running tuple')
    return facts


def _api(path, token, opener=urllib.request.urlopen):
    request = urllib.request.Request('https://api.github.com' + path, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'fsgg-at-admission', **({'Authorization': 'Bearer ' + token} if token else {})})
    with opener(request, timeout=30) as response:
        return json.load(response)


def _identity(environment):
    need(environment.get('GITHUB_REPOSITORY') == CALLER_REPOSITORY and environment.get('GITHUB_RUN_ID', '').isdigit() and
         re.fullmatch(re.escape('%s/.github/workflows/%s@' % (CALLER_REPOSITORY, CALLER_WORKFLOW)) + r'\S+', environment.get('GITHUB_WORKFLOW_REF', '')),
         'caller workflow identity unreadable (GITHUB_WORKFLOW_REF must name the Rendering caller)')
    return int(environment['GITHUB_RUN_ID'])


def _runs(environment, api, window=None):
    seen = []
    query = '' if window is None else '&created=%s..%s' % window
    for page in range(1, 6):
        try:
            batch = api('/repos/%s/actions/workflows/%s/runs?event=workflow_dispatch&per_page=100&page=%d%s' % (CALLER_REPOSITORY, CALLER_WORKFLOW, page, query))
        except Exception as error:  # noqa: BLE001 - any failure to read the census refuses
            raise Held('current public AT held: run census unavailable (%s)' % type(error).__name__) from error
        rows = batch.get('workflow_runs')
        need(type(rows) is list, 'run census malformed')
        seen.extend(rows)
        if len(rows) < 100:
            return seen
    raise Held('current public AT held: run census exceeds its bound')


def census_dry_run(environment, api=None):
    """Read-only identity probe for a non-admitted preflight: proves the reusable workflow sees the Rendering caller's
    identity and can read the caller's run list, before any real run depends on it."""
    api = api or (lambda path: _api(path, environment.get('GH_TOKEN') or environment.get('GITHUB_TOKEN')))
    run = _identity(environment)
    return {'identity': environment['GITHUB_WORKFLOW_REF'].split('@', 1)[0], 'run': run, 'attempt': environment.get('GITHUB_RUN_ATTEMPT'),
            'runsListed': len(_runs(environment, api))}


def census(environment, not_before, not_after, api=None):
    """Single-run control within the admission window. Fail closed on anything unknown."""
    api = api or (lambda path: _api(path, environment.get('GH_TOKEN') or environment.get('GITHUB_TOKEN')))
    need(environment.get('GITHUB_RUN_ATTEMPT') == '1', 'a rerun cannot reuse a single-run admission')
    mine = _identity(environment)
    window = [row for row in _runs(environment, api, (not_before, not_after))
              if row['id'] != mine and not_before <= row.get('created_at', not_before) <= not_after]
    for row in window:
        try:
            jobs = api('/repos/%s/actions/runs/%d/jobs?filter=all&per_page=100' % (CALLER_REPOSITORY, row['id']))['jobs']
        except Exception as error:  # noqa: BLE001
            raise Held('current public AT held: run census unavailable (%s)' % type(error).__name__) from error
        current = [job for job in jobs if job.get('name', '').startswith(JOB_PREFIX)]
        if row.get('status') != 'completed' and not current:
            raise Held('current public AT held: run %d is starting inside the admission window' % row['id'])
        for job in current:
            need(job.get('status') == 'completed', 'run %d is queued or running its current-public job' % row['id'])
            for step in job.get('steps', []):
                need(not (step['name'] == GUARD_STEP and step.get('conclusion') == 'success'), 'run %d already passed the admission guard in this window' % row['id'])
    return {'runsInWindow': len(window) + 1, 'run': mine, 'attempt': 1, 'window': [not_before, not_after]}


def guard(environment, now=None, git=None, api=None, with_census=False):
    facts = verify(environment, now, git)
    receipt = {'admission': 'verified', 'tupleSha256': sha(canonical(facts)), 'notBefore': facts['notBefore'], 'notAfter': facts['notAfter']}
    if with_census:
        receipt['census'] = census(environment, facts['notBefore'], facts['notAfter'], api)
    return receipt


def producer_rows(workflow_text):
    rows = {}
    for key, name in PRODUCER_KEYS.items():
        found = re.findall(r"^      %s: \$\{\{ inputs\.rendering-input-source == 'current-public-composition' && '([^']+)'" % name, workflow_text, re.M)
        need(len(found) == 1, 'producer row absent/ambiguous: ' + name)
        rows[key] = found[0]
    return rows


def check_plan_defaults(plan, archive, producer_version):
    """Refuse an admission for a plan whose template defaults a different FS.GG.UI version than the producer."""
    import zipfile
    template = plan.get('template', {})
    need(type(template) is dict and re.fullmatch('[0-9a-f]{64}', str(template.get('sha256', ''))), 'plan template identity absent')
    raw = Path(archive).read_bytes()
    need(sha(raw) == template['sha256'], 'template archive differs from the plan (%s)' % template.get('version'))
    found = {}
    with zipfile.ZipFile(Path(archive)) as package:
        for member, key in UI_DEFAULTS:
            text = package.read(member).decode()
            values = re.findall(r'<%s Condition="[^"]*">([^<]+)</%s>' % (key, key), text)
            need(len(values) == 1, 'template default %s absent/ambiguous' % key)
            found[key] = values[0]
    bad = {key: value for key, value in found.items() if value != producer_version}
    need(not bad, 'plan template %s defaults FS.GG.UI %s but the producer is %s' % (template.get('version'), bad, producer_version))
    return found


def issue(templates, caller, manifest_path, not_after, plan_path, archive_path, now=None, not_before=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    for label, revision in (('templates', templates), ('caller', caller)):
        need(re.fullmatch('[0-9a-f]{40}', revision), label + ' revision must be a full commit')
    start = not_before or now.strftime('%Y-%m-%dT%H:%M:%SZ')
    begin, expiry = parse_time(start), parse_time(not_after)
    need(begin <= now + SKEW and now < expiry <= begin + MAX_HORIZON, 'window must start now (not in the future), end in the future and span at most 7 days')
    native = native_helper()
    manifest_sha256 = native.sha(native.canonical(native.read_manifest(Path(manifest_path).read_text())))
    producer = producer_rows((ROOT / '.github/workflows/fable-external-reference-source.yml').read_text())
    check_plan_defaults(json.loads(Path(plan_path).read_text()), archive_path, producer['version'])
    value = tuple_of(templates, CALLER_REPOSITORY, caller, producer, manifest_sha256, roots_sha256(), start, not_after)
    return admission_string(value), value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('issue')
    one.add_argument('--templates', required=True, help='Templates commit the run will execute')
    one.add_argument('--caller', required=True, help='Rendering commit the run is dispatched at')
    one.add_argument('--manifest', required=True, type=Path)
    one.add_argument('--not-after', required=True, help='UTC expiry, e.g. 2026-11-02T00:00:00Z (max 7 days after now)')
    one.add_argument('--plan', required=True, type=Path, help='the typed current-composition plan the run will use (ProviderTool current-composition-plan output)')
    one.add_argument('--template-archive', required=True, type=Path, help='the published template nupkg the plan names')
    sub.add_parser('census-dry-run', help='read-only: prove the caller identity and run-list access inside the reusable workflow')
    sub.add_parser('guard', help='verify the supplied admission against the running tuple and run the single-run census')
    args = parser.parse_args(argv)
    if args.command == 'issue':
        text, value = issue(args.templates, args.caller, args.manifest, args.not_after, args.plan, args.template_archive)
        print(json.dumps({'admission': text, 'tuple': value}, indent=2, sort_keys=True))
    elif args.command == 'census-dry-run':
        print(json.dumps(census_dry_run(os.environ), sort_keys=True))
    else:
        print(json.dumps(guard(os.environ, with_census=True), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Held as error:
        print(error, file=sys.stderr)
        sys.exit(1)
