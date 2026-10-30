#!/usr/bin/env python3
"""Controls of the dispatch-bound current-public AT admission; no network, desktop or install runs here."""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('admission_controls', HERE / 'current-reference-at-admission.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
ORCA_SPEC = importlib.util.spec_from_file_location('admission_orca', HERE / 'external-reference-orca.py')
O = importlib.util.module_from_spec(ORCA_SPEC)
ORCA_SPEC.loader.exec_module(O)
MANIFEST = HERE / 'native-input-facility/noble-20261024.manifest.json'
WORKFLOW = HERE.parents[2] / '.github/workflows/fable-external-reference-source.yml'
TEMPLATES, CALLER = 'a' * 40, 'b' * 40
NOW = datetime.datetime(2026, 11, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
NOT_BEFORE, NOT_AFTER = '2026-11-01T12:00:00Z', '2026-11-02T12:00:00Z'
REF = 'FS-GG/FS.GG.Rendering/.github/workflows/templates-external-reference-qualification.yml@refs/heads/main'
FSPROJ = '<Project><PropertyGroup><%s Condition="\'$(%s)\' == \'\'">%s</%s></PropertyGroup></Project>'


def template_fixture(directory, version, name='template.nupkg'):
    """A minimal template archive plus the plan that names it."""
    archive = Path(directory) / name
    with zipfile.ZipFile(archive, 'w') as package:
        for member, key in A.UI_DEFAULTS:
            package.writestr(member, FSPROJ % (key, key, version, key))
    plan = Path(directory) / (name + '.plan.json')
    plan.write_text(json.dumps({'template': {'id': 'FS.GG.Workspace.Template', 'version': '0.20.x', 'sha256': A.sha(archive.read_bytes())}}))
    return plan, archive


def environment(admission, **changes):
    producer = A.producer_rows(WORKFLOW.read_text())
    env = {'RENDERING_INPUT_SOURCE': 'current-public-composition', 'GITHUB_SHA': CALLER, 'GITHUB_REPOSITORY': A.CALLER_REPOSITORY,
           'FSGG_CURRENT_NATIVE_INPUT_FACILITY': MANIFEST.read_text(), 'FSGG_CURRENT_PUBLIC_AT_ADMISSION': admission,
           'GITHUB_RUN_ID': '500', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_WORKFLOW_REF': REF,
           **{name: producer[key] for key, name in A.PRODUCER_KEYS.items()}}
    env.update(changes)
    return env


git = lambda *args: TEMPLATES


class AdmissionControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plan, self.archive = template_fixture(self.tmp.name, A.producer_rows(WORKFLOW.read_text())['version'])

    def issued(self, **changes):
        text, value = A.issue(changes.get('templates', TEMPLATES), changes.get('caller', CALLER), MANIFEST, changes.get('not_after', NOT_AFTER),
                              changes.get('plan', self.plan), changes.get('archive', self.archive), now=NOW, not_before=changes.get('not_before'))
        return text

    def test_issued_admission_binds_the_exact_running_tuple(self):
        text = self.issued()
        self.assertRegex(text, r'^fsgg\.at-admission/1;notBefore=2026-11-01T12:00:00Z;notAfter=2026-11-02T12:00:00Z;sha256=[0-9a-f]{64}$')
        facts = A.verify(environment(text), NOW, git)
        self.assertEqual({'schema', 'scope', 'notBefore', 'notAfter', 'templates', 'caller', 'producer', 'facility', 'installRoots'}, set(facts))
        self.assertEqual('single-run', facts['scope'])
        self.assertEqual('0.32.4', facts['producer']['version'])
        self.assertEqual('40737624380', facts['producer']['run'])
        self.assertEqual('4ede04be66cedffc8551cd14045bab714aa358a7', facts['producer']['source'])
        self.assertEqual('073f3a94a98c34068c40ea887cba5c6b09836b4cc8a67b287978ea1e5cff6a31', facts['facility']['manifestSha256'])
        self.assertEqual(text, A.admission_string(facts))

    def test_every_single_difference_in_the_running_tuple_refuses(self):
        text = self.issued()
        refused = 0
        for name in list(A.PRODUCER_KEYS.values()):
            with self.assertRaisesRegex(A.Held, 'does not match the running tuple'):
                A.verify(environment(text, **{name: 'f' * 8 + environment(text)[name]}), NOW, git)
            refused += 1
        manifest = json.loads(MANIFEST.read_text()); manifest['keymaps']['de'] = '0' * 64
        for label, changes, revision in [('caller revision', {'GITHUB_SHA': 'c' * 40}, TEMPLATES), ('templates revision', {}, 'd' * 40),
                                         ('manifest bytes', {'FSGG_CURRENT_NATIVE_INPUT_FACILITY': json.dumps(manifest, sort_keys=True, separators=(',', ':'))}, TEMPLATES)]:
            with self.subTest(label), self.assertRaisesRegex(A.Held, 'does not match the running tuple'):
                A.verify(environment(text, **changes), NOW, lambda *a, r=revision: r)
            refused += 1
        with patch.object(A, 'roots_sha256', lambda: '0' * 64), self.assertRaisesRegex(A.Held, 'does not match the running tuple'):
            A.verify(environment(text), NOW, git)
        refused += 1
        # the window itself is part of the tuple: a string whose dates were edited keeps its digest and is refused
        for edited in [text.replace('notBefore=2026-11-01T12:00:00Z', 'notBefore=2026-10-31T12:00:00Z'), text.replace('notAfter=2026-11-02T12:00:00Z', 'notAfter=2026-11-03T12:00:00Z')]:
            with self.assertRaisesRegex(A.Held, 'does not match the running tuple'):
                A.verify(environment(edited), NOW, git)
            refused += 1
        self.assertEqual(12, refused)
        print('admission tuple mismatch refusals:', refused)

    def test_other_routes_repositories_and_missing_facts_refuse(self):
        text = self.issued()
        for label, changes in {'route': {'RENDERING_INPUT_SOURCE': 'palette-heading'}, 'repository': {'GITHUB_REPOSITORY': 'FS-GG/Other'},
                               'no facility': {'FSGG_CURRENT_NATIVE_INPUT_FACILITY': ''}, 'bad facility': {'FSGG_CURRENT_NATIVE_INPUT_FACILITY': '{}'},
                               'no caller sha': {'GITHUB_SHA': ''}, 'no producer': {'PRODUCER_RUN': ''}}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                A.verify(environment(text, **changes), NOW, git)
        with self.assertRaisesRegex(A.Held, 'Templates revision unreadable'):
            A.verify(environment(text), NOW, lambda *a: (_ for _ in ()).throw(OSError('no git')))

    def test_format_window_expiry_and_horizon_refuse(self):
        good = self.issued()
        digest = good.rsplit('sha256=', 1)[1]
        for label, value in {'empty': '', 'anything': 'anything', 'bare digest': digest, 'wrong prefix': good.replace('fsgg.at-admission/1', 'fsgg.at-admission/2'),
                             'old format': 'fsgg.at-admission/1;notAfter=2026-11-02T12:00:00Z;sha256=' + digest, 'upper digest': good.upper(),
                             'short digest': good[:-1], 'trailing text': good + ' ', 'bad date': good.replace('2026-11-02', '2026-13-02')}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                A.verify(environment(value), NOW, git)
        with self.assertRaisesRegex(A.Held, 'expired'):
            A.verify(environment(good), NOW + datetime.timedelta(days=2), git)
        with self.assertRaisesRegex(A.Held, 'expired'):
            A.verify(environment(good), A.parse_time(NOT_AFTER), git)
        with self.assertRaisesRegex(A.Held, 'not valid before'):
            A.verify(environment(good), NOW - datetime.timedelta(minutes=10), git)
        producer = A.producer_rows(WORKFLOW.read_text())
        manifest = A.native_helper().sha(A.native_helper().canonical(json.loads(MANIFEST.read_text())))
        far = A.admission_string(A.tuple_of(TEMPLATES, A.CALLER_REPOSITORY, CALLER, producer, manifest, A.roots_sha256(), NOT_BEFORE, '2026-12-30T00:00:00Z'))
        with self.assertRaisesRegex(A.Held, '7 day horizon'):
            A.verify(environment(far), NOW, git)
        for bad in [dict(not_after='2026-10-31T00:00:00Z'), dict(not_after='2026-12-30T00:00:00Z'), dict(not_after='tomorrow'),
                    dict(not_before='2026-11-05T00:00:00Z', not_after='2026-11-06T00:00:00Z'), dict(templates='abc')]:
            with self.assertRaises((A.Held, ValueError)):
                self.issued(**bad)

    def test_issue_refuses_a_plan_whose_template_defaults_another_ui_version_than_the_producer(self):
        # the 0.20.0 case: the template defaults FS.GG.UI 0.32.3 while the producer is 0.32.4
        stale_plan, stale_archive = template_fixture(self.tmp.name, '0.32.3', 'stale.nupkg')
        with self.assertRaisesRegex(A.Held, "defaults FS.GG.UI .*0.32.3.* but the producer is 0.32.4"):
            self.issued(plan=stale_plan, archive=stale_archive)
        # one project right, the other stale
        mixed = Path(self.tmp.name) / 'mixed.nupkg'
        with zipfile.ZipFile(mixed, 'w') as package:
            package.writestr(A.UI_DEFAULTS[0][0], FSPROJ % (A.UI_DEFAULTS[0][1], A.UI_DEFAULTS[0][1], '0.32.4', A.UI_DEFAULTS[0][1]))
            package.writestr(A.UI_DEFAULTS[1][0], FSPROJ % (A.UI_DEFAULTS[1][1], A.UI_DEFAULTS[1][1], '0.32.3', A.UI_DEFAULTS[1][1]))
        plan = Path(self.tmp.name) / 'mixed.plan.json'
        plan.write_text(json.dumps({'template': {'version': '0.20.x', 'sha256': A.sha(mixed.read_bytes())}}))
        with self.assertRaisesRegex(A.Held, 'FsGgSvgAuthoringVersion'):
            self.issued(plan=plan, archive=mixed)
        # an archive that is not the one the plan names, an unreadable plan and a missing default all refuse
        with self.assertRaisesRegex(A.Held, 'differs from the plan'):
            self.issued(archive=stale_archive)
        with self.assertRaises(A.Held):
            A.check_plan_defaults({'template': {}}, self.archive, '0.32.4')
        empty = Path(self.tmp.name) / 'empty.nupkg'
        with zipfile.ZipFile(empty, 'w') as package:
            for member, key in A.UI_DEFAULTS:
                package.writestr(member, '<Project/>')
        with self.assertRaisesRegex(A.Held, 'absent/ambiguous'):
            A.check_plan_defaults({'template': {'sha256': A.sha(empty.read_bytes())}}, empty, '0.32.4')
        self.assertEqual({k: '0.32.4' for _, k in A.UI_DEFAULTS}, A.check_plan_defaults(json.loads(self.plan.read_text()), self.archive, '0.32.4'))

    def test_the_source_gate_stays_closed_without_a_verifying_admission(self):
        self.assertIsNone(O.CURRENT_PUBLIC_AT_ADMISSION)
        for value in ['', 'anything', 'inert-control-only', self.issued()]:
            with self.subTest(value[:16]), self.assertRaisesRegex(RuntimeError, 'held'):
                O.current_public_at_admission({'FSGG_CURRENT_PUBLIC_AT_ADMISSION': value})

    def test_the_actual_gate_admits_only_the_tuple_that_is_really_running(self):
        head = subprocess.check_output(['git', '-C', str(HERE.parents[2]), 'rev-parse', 'HEAD'], text=True).strip()
        now = datetime.datetime.now(datetime.timezone.utc)
        not_after = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        text, _ = A.issue(head, CALLER, MANIFEST, not_after, self.plan, self.archive)
        O.current_public_at_admission(environment(text))
        stale, _ = A.issue('e' * 40, CALLER, MANIFEST, not_after, self.plan, self.archive)
        with self.assertRaisesRegex(RuntimeError, 'does not match the running tuple'):
            O.current_public_at_admission(environment(stale))
        with self.assertRaisesRegex(RuntimeError, 'does not match the running tuple'):
            O.current_public_at_admission(environment(text, GITHUB_SHA='c' * 40))


def job(status='completed', steps=(), name=A.JOB_PREFIX + ' / External reference immutable preflight and optional full qualification'):
    return {'name': name, 'status': status, 'steps': [{'name': A.GUARD_STEP, **step} for step in steps]}


def entry(identifier, jobs, created='2026-11-01T13:00:00Z', status='completed'):
    return ({'id': identifier, 'created_at': created, 'status': status}, {'jobs': jobs})


PASSED = [{'status': 'completed', 'conclusion': 'success'}]
SKIPPED = [{'status': 'completed', 'conclusion': 'skipped'}]
REFUSED = [{'status': 'completed', 'conclusion': 'failure'}]
RUNNING = [{'status': 'in_progress', 'conclusion': None}]


class CensusControls(unittest.TestCase):
    def api(self, runs, failing=None):
        table = {row['id']: jobs for row, jobs in runs}
        paths = []
        def call(path):
            paths.append(path)
            if failing:
                raise failing
            if '/runs?' in path:
                return {'workflow_runs': [row for row, _ in runs] if 'page=1' in path else []}
            return table[int(path.split('/runs/')[1].split('/')[0])]
        call.paths = paths
        return call

    def census(self, runs, env=None, **kw):
        return A.census(env or environment('x'), NOT_BEFORE, NOT_AFTER, self.api(runs, **kw))

    def test_first_run_passes_and_records_its_window(self):
        mine = ({'id': 500, 'created_at': '2026-11-01T12:30:00Z', 'status': 'in_progress'}, {'jobs': []})
        result = self.census([mine])
        self.assertEqual({'runsInWindow': 1, 'run': 500, 'attempt': 1, 'window': [NOT_BEFORE, NOT_AFTER]}, result)
        others = [entry(499, [job(steps=SKIPPED)]), entry(498, [job(steps=REFUSED)]), entry(497, [job('completed', [])])]
        self.assertEqual(4, self.census([mine, *others])['runsInWindow'])

    def test_only_the_admission_window_and_the_exact_caller_workflow_are_counted(self):
        api = self.api([entry(500, [])])
        A.census(environment('x'), NOT_BEFORE, NOT_AFTER, api)
        self.assertIn('/repos/FS-GG/FS.GG.Rendering/actions/workflows/templates-external-reference-qualification.yml/runs?', api.paths[0])
        self.assertIn('created=%s..%s' % (NOT_BEFORE, NOT_AFTER), api.paths[0])
        # an old pass under a different admission (created before notBefore) does not block a new one
        old = entry(400, [job(steps=PASSED)], created='2026-10-30T09:00:00Z')
        self.assertEqual(1, self.census([entry(500, []), old])['runsInWindow'])
        # a pass inside the window does block
        inside = entry(400, [job(steps=PASSED)], created='2026-11-01T12:10:00Z')
        with self.assertRaisesRegex(A.Held, 'already passed the admission guard'):
            self.census([entry(500, []), inside])
        # after the window's end it no longer counts
        late = entry(400, [job(steps=PASSED)], created='2026-11-03T00:00:00Z')
        self.assertEqual(1, self.census([entry(500, []), late])['runsInWindow'])

    def test_concurrency_is_symmetric_and_a_queued_run_with_no_steps_refuses(self):
        for label, other in {'running earlier id': entry(450, [job('in_progress', RUNNING)]), 'running later id': entry(600, [job('in_progress', RUNNING)]),
                             'queued earlier id with no steps': entry(450, [job('queued', [])]), 'queued later id with no steps': entry(600, [job('queued', [])]),
                             'run queued, jobs not created yet': entry(600, [], status='queued'), 'run in progress without a current job': entry(450, [], status='in_progress')}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                self.census([entry(500, []), other])
        # other-route jobs of a running run do not block; only the current-public job counts
        other_route = entry(600, [job('in_progress', RUNNING, name='Retained 0.32.4 originals and complete unpublished palette journey / x'), job('completed', SKIPPED)], status='in_progress')
        self.assertEqual(2, self.census([entry(500, []), other_route])['runsInWindow'])

    def test_rerun_unreadable_census_foreign_workflow_and_bounds_refuse(self):
        mine = [entry(500, [])]
        with self.assertRaisesRegex(A.Held, 'rerun'):
            self.census(mine, environment('x', GITHUB_RUN_ATTEMPT='2'))
        for changes in [{'GITHUB_WORKFLOW_REF': 'FS-GG/FS.GG.Templates/.github/workflows/templates-external-reference-qualification.yml@refs/heads/main'},
                        {'GITHUB_WORKFLOW_REF': 'FS-GG/FS.GG.Rendering/.github/workflows/other.yml@refs/heads/main'},
                        {'GITHUB_WORKFLOW_REF': 'FS-GG/FS.GG.Rendering/.github/workflows/templates-external-reference-qualification.yml.bak@refs/heads/main'},
                        {'GITHUB_WORKFLOW_REF': ''}, {'GITHUB_RUN_ID': 'x'}, {'GITHUB_REPOSITORY': 'FS-GG/Other'}]:
            with self.subTest(changes), self.assertRaisesRegex(A.Held, 'identity unreadable'):
                self.census(mine, environment('x', **changes))
        with self.assertRaisesRegex(A.Held, 'census unavailable'):
            self.census(mine, failing=OSError('down'))
        many = lambda path: {'workflow_runs': [{'id': 1000 + i, 'created_at': NOT_BEFORE} for i in range(100)]} if '/runs?' in path else {'jobs': []}
        with self.assertRaisesRegex(A.Held, 'exceeds its bound'):
            A.census(environment('x'), NOT_BEFORE, NOT_AFTER, many)

    def test_dry_run_proves_identity_inside_the_reusable_workflow_without_consuming_anything(self):
        api = self.api([entry(500, [job(steps=PASSED)])])
        result = A.census_dry_run(environment(''), api)
        self.assertEqual({'identity': REF.split('@')[0], 'run': 500, 'attempt': '1', 'runsListed': 1}, result)
        self.assertFalse(any('/jobs' in path for path in api.paths))  # read-only list; no admission, no job reads
        for ref in ['FS-GG/FS.GG.Templates/.github/workflows/fable-external-reference-source.yml@refs/heads/main', '']:
            with self.assertRaisesRegex(A.Held, 'identity unreadable'):
                A.census_dry_run(environment('', GITHUB_WORKFLOW_REF=ref), api)
        with self.assertRaisesRegex(A.Held, 'census unavailable'):
            A.census_dry_run(environment(''), self.api([], failing=OSError('403')))

    def test_workflow_guard_step_and_dry_run_step_wiring(self):
        text = WORKFLOW.read_text()
        guard = text.split('      - name: Refuse held current AT before acquisition or setup\n', 1)[1].split('\n      - ', 1)[0]
        self.assertIn("if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}", guard)
        self.assertIn('current-reference-at-caller.py guard', guard)
        self.assertIn('GH_TOKEN: ${{ github.token }}', guard)
        dry = text.split('      - name: Dry-run the single-run census identity (read-only, no admission)\n', 1)[1].split('\n      - ', 1)[0]
        self.assertIn("if: ${{ inputs.rendering-input-source == 'current-public-composition' }}", dry)
        self.assertIn('current-reference-at-admission.py census-dry-run', dry)
        self.assertIn('GH_TOKEN: ${{ github.token }}', dry)
        self.assertEqual(1, text.count('FSGG_CURRENT_PUBLIC_AT_ADMISSION: ${{ inputs.current-public-at-admission }}'))
        self.assertRegex(text, r'(?m)^permissions:\n  contents: read\n  actions: read\n')
        order = [text.index(marker) for marker in ['Dry-run the single-run census identity', 'Refuse held current AT before acquisition or setup',
                                                    'Acquire declared current Noble inputs', 'Install declared Noble snapshot roots']]
        self.assertEqual(order, sorted(order))


if __name__ == '__main__':
    unittest.main()
