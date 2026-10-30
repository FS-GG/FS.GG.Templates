#!/usr/bin/env python3
"""Controls of the dispatch-bound current-public AT admission; no network, desktop or install runs here."""
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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
NOT_AFTER = '2026-11-02T12:00:00Z'


def environment(admission, **changes):
    producer = A.producer_rows(WORKFLOW.read_text())
    env = {'RENDERING_INPUT_SOURCE': 'current-public-composition', 'GITHUB_SHA': CALLER, 'GITHUB_REPOSITORY': A.CALLER_REPOSITORY,
           'FSGG_CURRENT_NATIVE_INPUT_FACILITY': MANIFEST.read_text(), 'FSGG_CURRENT_PUBLIC_AT_ADMISSION': admission,
           'GITHUB_RUN_ID': '500', 'GITHUB_RUN_ATTEMPT': '1',
           'GITHUB_WORKFLOW_REF': 'FS-GG/FS.GG.Rendering/.github/workflows/templates-external-reference-qualification.yml@refs/heads/main',
           **{name: producer[key] for key, name in A.PRODUCER_KEYS.items()}}
    env.update(changes)
    return env


def issued(**changes):
    text, value = A.issue(changes.get('templates', TEMPLATES), changes.get('caller', CALLER), MANIFEST, changes.get('not_after', NOT_AFTER), now=NOW)
    return text


git = lambda *args: TEMPLATES


class AdmissionControls(unittest.TestCase):
    def test_issued_admission_binds_the_exact_running_tuple(self):
        text = issued()
        self.assertRegex(text, r'^fsgg\.at-admission/1;notAfter=2026-11-02T12:00:00Z;sha256=[0-9a-f]{64}$')
        facts = A.verify(environment(text), NOW, git)
        self.assertEqual({'schema', 'scope', 'notAfter', 'templates', 'caller', 'producer', 'facility', 'installRoots'}, set(facts))
        self.assertEqual('single-run', facts['scope'])
        self.assertEqual('0.32.4', facts['producer']['version'])
        self.assertEqual('40737624380', facts['producer']['run'])
        self.assertEqual('4ede04be66cedffc8551cd14045bab714aa358a7', facts['producer']['source'])
        self.assertEqual('073f3a94a98c34068c40ea887cba5c6b09836b4cc8a67b287978ea1e5cff6a31', facts['facility']['manifestSha256'])
        self.assertEqual(text, A.admission_string(facts))

    def test_every_single_difference_in_the_running_tuple_refuses(self):
        text = issued()
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
        self.assertEqual(10, refused)
        print('admission tuple mismatch refusals:', refused)

    def test_other_routes_repositories_and_missing_facts_refuse(self):
        text = issued()
        for label, changes in {'route': {'RENDERING_INPUT_SOURCE': 'palette-heading'}, 'repository': {'GITHUB_REPOSITORY': 'FS-GG/Other'},
                               'no facility': {'FSGG_CURRENT_NATIVE_INPUT_FACILITY': ''}, 'bad facility': {'FSGG_CURRENT_NATIVE_INPUT_FACILITY': '{}'},
                               'no caller sha': {'GITHUB_SHA': ''}, 'no producer': {'PRODUCER_RUN': ''}}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                A.verify(environment(text, **changes), NOW, git)
        with self.assertRaisesRegex(A.Held, 'Templates revision unreadable'):
            A.verify(environment(text), NOW, lambda *a: (_ for _ in ()).throw(OSError('no git')))

    def test_format_expiry_and_horizon_refuse(self):
        good = issued()
        digest = good.rsplit('sha256=', 1)[1]
        for label, value in {'empty': '', 'anything': 'anything', 'bare digest': digest, 'wrong prefix': good.replace('fsgg.at-admission/1', 'fsgg.at-admission/2'),
                             'upper digest': good.upper(), 'short digest': good[:-1], 'trailing text': good + ' ', 'bad date': good.replace('2026-11-02', '2026-13-02')}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                A.verify(environment(value), NOW, git)
        with self.assertRaisesRegex(A.Held, 'expired'):
            A.verify(environment(good), NOW + datetime.timedelta(days=2), git)
        with self.assertRaisesRegex(A.Held, 'expired'):
            A.verify(environment(good), parse := A.parse_time(NOT_AFTER), git)
        far = A.admission_string(A.tuple_of(TEMPLATES, A.CALLER_REPOSITORY, CALLER, A.producer_rows(WORKFLOW.read_text()), A.native_helper().sha(A.native_helper().canonical(json.loads(MANIFEST.read_text()))), A.roots_sha256(), '2026-12-30T00:00:00Z'))
        with self.assertRaisesRegex(A.Held, '7 day horizon'):
            A.verify(environment(far), NOW, git)
        for bad in ['2026-10-31T00:00:00Z', '2026-12-30T00:00:00Z', 'tomorrow']:
            with self.assertRaises((A.Held, ValueError)):
                A.issue(TEMPLATES, CALLER, MANIFEST, bad, now=NOW)
        with self.assertRaises(A.Held):
            A.issue('abc', CALLER, MANIFEST, NOT_AFTER, now=NOW)

    def test_the_source_gate_stays_closed_without_a_verifying_admission(self):
        self.assertIsNone(O.CURRENT_PUBLIC_AT_ADMISSION)
        for value in ['', 'anything', 'inert-control-only', issued()]:
            with self.subTest(value[:16]), self.assertRaisesRegex(RuntimeError, 'held'):
                O.current_public_at_admission({'FSGG_CURRENT_PUBLIC_AT_ADMISSION': value})

    def test_the_actual_gate_admits_only_the_tuple_that_is_really_running(self):
        head = subprocess.check_output(['git', '-C', str(HERE.parents[2]), 'rev-parse', 'HEAD'], text=True).strip()
        now = datetime.datetime.now(datetime.timezone.utc)
        not_after = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        text, _ = A.issue(head, CALLER, MANIFEST, not_after)
        O.current_public_at_admission(environment(text))
        stale, _ = A.issue('e' * 40, CALLER, MANIFEST, not_after)
        with self.assertRaisesRegex(RuntimeError, 'does not match the running tuple'):
            O.current_public_at_admission(environment(stale))
        with self.assertRaisesRegex(RuntimeError, 'does not match the running tuple'):
            O.current_public_at_admission(environment(text, GITHUB_SHA='c' * 40))


def run(identifier, steps, status='completed'):
    return {'id': identifier}, {'jobs': [{'status': status, 'steps': [{'name': A.GUARD_STEP, **step} for step in steps]}]}


class CensusControls(unittest.TestCase):
    def api(self, runs, failing=None):
        table = {row['id']: jobs for row, jobs in runs}
        def call(path):
            if failing:
                raise failing
            if '/runs?' in path:
                return {'workflow_runs': [row for row, _ in runs] if 'page=1' in path else []}
            return table[int(path.split('/runs/')[1].split('/')[0])]
        return call

    def test_first_run_passes_and_records_its_scope(self):
        env = environment('x')
        self.assertEqual({'runsExamined': 1, 'run': 500, 'attempt': 1}, A.census(env, self.api([({'id': 500}, {'jobs': []})])))
        preflight = run(499, [{'status': 'completed', 'conclusion': 'skipped'}])
        refused_guard = run(498, [{'status': 'completed', 'conclusion': 'failure'}])
        self.assertEqual(3, A.census(env, self.api([({'id': 500}, {'jobs': []}), preflight, refused_guard]))['runsExamined'])

    def test_second_run_fails_closed(self):
        env = environment('x')
        for label, other in {'passed earlier': run(400, [{'status': 'completed', 'conclusion': 'success'}]),
                             'passed later id': run(600, [{'status': 'completed', 'conclusion': 'success'}]),
                             'running earlier': run(450, [{'status': 'in_progress', 'conclusion': None}], 'in_progress'),
                             'queued earlier': run(450, [{'status': 'pending', 'conclusion': None}], 'queued')}.items():
            with self.subTest(label), self.assertRaises(A.Held):
                A.census(env, self.api([({'id': 500}, {'jobs': []}), other]))
        # a later in-progress run is that run's problem: it sees this one and refuses itself
        later = run(600, [{'status': 'in_progress', 'conclusion': None}], 'in_progress')
        A.census(env, self.api([({'id': 500}, {'jobs': []}), later]))

    def test_rerun_unreadable_census_and_foreign_workflow_refuse(self):
        mine = [({'id': 500}, {'jobs': []})]
        with self.assertRaisesRegex(A.Held, 'rerun'):
            A.census(environment('x', GITHUB_RUN_ATTEMPT='2'), self.api(mine))
        for changes in [{'GITHUB_WORKFLOW_REF': 'FS-GG/FS.GG.Templates/.github/workflows/x.yml@refs/heads/main'}, {'GITHUB_WORKFLOW_REF': ''},
                        {'GITHUB_RUN_ID': 'x'}, {'GITHUB_REPOSITORY': 'FS-GG/Other'}]:
            with self.subTest(changes), self.assertRaisesRegex(A.Held, 'identity unreadable'):
                A.census(environment('x', **changes), self.api(mine))
        with self.assertRaisesRegex(A.Held, 'census unavailable'):
            A.census(environment('x'), self.api(mine, failing=OSError('down')))
        many = lambda path: {'workflow_runs': [{'id': 1000 + i} for i in range(100)]} if '/runs?' in path else {'jobs': []}
        with self.assertRaisesRegex(A.Held, 'exceeds its bound'):
            A.census(environment('x'), many)

    def test_workflow_guard_step_runs_the_binding_with_the_token_and_nothing_wider(self):
        text = WORKFLOW.read_text()
        step = text.split('      - name: Refuse held current AT before acquisition or setup\n', 1)[1].split('\n      - ', 1)[0]
        self.assertIn("if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}", step)
        self.assertIn('current-reference-at-caller.py guard', step)
        self.assertIn('GH_TOKEN: ${{ github.token }}', step)
        self.assertEqual(1, text.count('FSGG_CURRENT_PUBLIC_AT_ADMISSION: ${{ inputs.current-public-at-admission }}'))
        self.assertRegex(text, r'(?m)^permissions:\n  contents: read\n  actions: read\n')
        self.assertTrue(text.index('Refuse held current AT before acquisition or setup') < text.index('Acquire declared current Noble inputs'))
        self.assertTrue(text.index('Refuse held current AT before acquisition or setup') < text.index('Install declared Noble snapshot roots'))


if __name__ == '__main__':
    unittest.main()
