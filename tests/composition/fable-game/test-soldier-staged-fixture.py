"""Finite inert controls and data-only verification for the maintained staged report."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess
import unittest

CASES = ['soldier-local', 'soldier-external', *[f'soldier-population-{n}' for n in (1, 100, 250, 500, 1000)], 'soldier-churn']

def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()

def verify(report, manifest, manifest_raw, rendering, templates):
    assert re.fullmatch('[0-9a-f]{40}', rendering) and re.fullmatch('[0-9a-f]{40}', templates), 'exact source inputs required'
    assert manifest['schema'] == 'fsgg.svg-coherence.fixture/v1'
    assert report['schema'] == 'fsgg.svg-coherence.page-results/v1'
    assert report['outcome'] == 'soldier-functional-completed' and report['integrity'] == 'verified-before-and-after'
    assert report['manifestSha256'] == digest(manifest_raw) and report['artifact'] == manifest, 'download/manifest identity'
    assert manifest['workloadSha256'] == digest(canonical(manifest['workload'])), 'workload identity'
    identity = {key: manifest[key] for key in ('files', 'packages', 'sourceSha256', 'workloadSha256')}
    assert manifest['artifactId'] == digest(canonical(identity)), 'artifact identity'
    workload = manifest['workload']; inputs = workload['input']
    assert workload['profile'] == 'soldier-functional' and workload['cases'] == CASES
    assert workload['method'] == {'caseTimeoutMilliseconds': 60000}
    assert inputs['renderingRevision'] == rendering and inputs['templatesRevision'] == templates
    assert inputs['actualEntry'] == 'soldier-player/index.html' and inputs['adapterEntry'] == 'soldier-staged-journey.js'
    assert inputs['candidateVersion'] == '0.32.0'
    flags = inputs['evaluatedProperties']
    assert all(flags[name] == 'true' for name in ('FsGgExternalReferenceCandidate', 'FsGgSvgRuntimeCandidate', 'FsGgSvgInputCandidate', 'FsGgSvgNetworkCandidate'))
    assert flags.get('FsGgLegacyPreview') != 'true'
    assert len(report['cases']) == len(CASES)
    for row, kind in zip(report['cases'], CASES):
        assert row['kind'] == kind and row['repetition'] == 0 and row['outcome'] == 'pass'
        assert row['integrity'] == 'verified-before-and-after'
        observation = row['observations']
        assert observation['skipped'] is False and observation['retried'] is False and observation['flaky'] is False
        assert observation['assertions'] and all(item['name'] and item['passed'] is True for item in observation['assertions'])
        assert observation['cleanup']['owned'] == 0 and observation['cleanup']['frameDisposed'] is True
    assert report['driver'].get('resumeObserved') is True, 'staged positive resume was not observed'
    assert report['driver']['downloadObserved'] is True and report['driver']['browserCleanup'] == 'observed-closed'
    full=report['cases'][-1]['observations']['details']['fullExport']
    assert full['uses']==2000 and full['symbols']==6
    assert len(report['driver']['fullWorldExports'])==1 and report['driver']['fullWorldExports'][0]['sha256']==full['sha256']
    assert report['driver']['args'] == ['--disable-gpu']
    assert report['driver']['serverCleanup']['status']=='observed-exited'
    assert all(report['claims'][key] is False for key in ('gpuQualified', 'performanceAccepted', 'representativeSoldierQualified'))
    return {'cases': len(CASES), 'result': 'verified', 'profile': 'soldier-functional', 'gpuQualified': False, 'publication': False, 'installedAcceptance': False}


def verify_negative(report, mutant):
    assert report.get('schema') == 'fsgg.svg-coherence.page-results/v1'
    assert report.get('outcome') in ('failed', 'capability-check-failed')
    driver = report.get('driver', {})
    assert driver.get('downloadObserved') is True and driver.get('browserCleanup') == 'observed-closed'
    assert 'mutant survived' not in json.dumps(report).lower(), 'surviving mutant is not killed'
    assert all(report.get('claims', {}).get(key) is False for key in ('gpuQualified', 'performanceAccepted', 'representativeSoldierQualified'))
    capability_errors = {'wrong-entry': 'wrong actual player entry', 'source-hash': 'Artifact identity mismatch',
                         'asset-hash': 'Workload contract hash mismatch', 'bundle-hash': 'Artifact hash mismatch: soldier-player/',
                         'workload-hash': 'Workload contract hash mismatch', 'stale-checkpoint': 'Stale or foreign checkpoint'}
    rows = report.get('cases', [])
    def failed_case(kind, message):
        matches = [row for row in rows if row.get('kind') == kind]
        assert len(matches) == 1 and matches[0].get('outcome') == 'failed', 'targeted case did not fail'
        row = matches[0]
        assert row.get('error') == message, 'unrelated failure does not kill mutant'
        observation = row.get('observations', {})
        assert any(item.get('name') == message and item.get('passed') is False for item in observation.get('assertions', []))
        assert observation.get('cleanup', {}).get('frameDisposed') is True
        return observation
    if mutant in capability_errors:
        assert rows == [] and 'artifact' not in report
        assert report.get('verificationError') == 'Downloaded staged input identity mismatch'
        if mutant == 'bundle-hash':
            assert re.fullmatch(r'Artifact hash mismatch: soldier-player/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+', report.get('error', ''))
            assert '..' not in report['error'].split('/')
        else:
            assert report.get('error') == capability_errors[mutant]
    elif mutant == 'missing-mount':
        assert [row.get('kind') for row in rows] == CASES
        for kind in CASES:
            failed_case(kind, 'Soldier opt-in/mount control missing from actual entry')
    elif mutant == 'missing-case':
        assert report.get('error') == 'downloaded case removed by explicit negative control'
        assert [row.get('kind') for row in rows] == CASES[:-1] and all(row.get('outcome') == 'pass' for row in rows)
    elif mutant == 'stale-epoch-accepted':
        failed_case('soldier-external', 'soldier soldier-external: stale epoch reply refused')
    elif mutant == 'incomplete-export':
        observed = failed_case('soldier-churn', 'soldier soldier-churn: complete 2000-use six-symbol export')
        assert observed.get('details', {}).get('fullExport', {}).get('uses') == 1999
    elif mutant == 'owner-leak':
        observed = failed_case('soldier-external', 'soldier soldier-external: zero reported owned resources')
        assert observed['cleanup'].get('owned') != 0
    elif mutant == 'artifact-before-download':
        assert report.get('integrity') == 'failed-before-download' and report.get('error') == 'Manifest changed during run'
    elif mutant == 'artifact-after-download':
        assert report.get('error') == 'downloaded artifact identity altered by explicit negative control'
        assert report.get('verificationError') == 'Downloaded staged input identity mismatch'
        assert report.get('artifact', {}).get('files', [{}])[0].get('sha256') == 'altered'
    else:
        raise AssertionError('unknown staged mutant')
    return {'mutant': mutant, 'result': 'killed-by-specific-evidence'}


class StagedInputTests(unittest.TestCase):
    def setUp(self):
        self.rendering, self.templates = 'a' * 40, 'b' * 40
        self.manifest = {'schema': 'fsgg.svg-coherence.fixture/v1', 'files': [], 'packages': [], 'sourceSha256': 'sha256:' + 'c' * 64,
                         'workload': {'profile': 'soldier-functional', 'cases': CASES, 'method': {'caseTimeoutMilliseconds': 60000},
                                      'input': {'renderingRevision': self.rendering, 'templatesRevision': self.templates, 'candidateVersion': '0.32.0', 'actualEntry': 'soldier-player/index.html', 'adapterEntry': 'soldier-staged-journey.js', 'evaluatedProperties': {'FsGgExternalReferenceCandidate': 'true', 'FsGgSvgRuntimeCandidate': 'true', 'FsGgSvgInputCandidate': 'true', 'FsGgSvgNetworkCandidate': 'true'}}}}
        self.manifest['workloadSha256'] = digest(canonical(self.manifest['workload']))
        self.manifest['artifactId'] = digest(canonical({key: self.manifest[key] for key in ('files', 'packages', 'sourceSha256', 'workloadSha256')}))
        self.raw = canonical(self.manifest)
        observation = {'assertions': [{'name': 'inert assertion', 'passed': True}], 'skipped': False, 'retried': False, 'flaky': False, 'cleanup': {'owned': 0, 'frameDisposed': True}, 'details': {'fullExport': {'uses': 2000, 'symbols': 6, 'sha256': 'sha256:'+'d'*64}}}
        self.report = {'schema': 'fsgg.svg-coherence.page-results/v1', 'artifact': copy.deepcopy(self.manifest), 'manifestSha256': digest(self.raw), 'outcome': 'soldier-functional-completed', 'integrity': 'verified-before-and-after', 'cases': [{'kind': kind, 'repetition': 0, 'outcome': 'pass', 'integrity': 'verified-before-and-after', 'observations': copy.deepcopy(observation)} for kind in CASES], 'driver': {'resumeObserved': True, 'downloadObserved': True, 'browserCleanup': 'observed-closed', 'args': ['--disable-gpu'], 'serverCleanup': {'status': 'observed-exited'}, 'fullWorldExports': [{'sha256':'sha256:'+'d'*64}]}, 'claims': {'gpuQualified': False, 'performanceAccepted': False, 'representativeSoldierQualified': False}}

    def test_complete_inert_input_passes(self):
        self.assertEqual(verify(self.report, self.manifest, self.raw, self.rendering, self.templates)['cases'], 8)

    def test_wrong_source_entry_workload_artifact_and_optin_refuse(self):
        for mutate in [lambda m: m['workload']['input'].update(renderingRevision='f' * 40), lambda m: m['workload']['input'].update(actualEntry='index.html'), lambda m: m.update(workloadSha256='foreign'), lambda m: m.update(artifactId='foreign'), lambda m: m['workload']['input']['evaluatedProperties'].update(FsGgExternalReferenceCandidate='false')]:
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(self.manifest); mutate(value)
                report=copy.deepcopy(self.report)
                if value['workloadSha256'] != 'foreign' and value['artifactId'] != 'foreign':
                    value['workloadSha256']=digest(canonical(value['workload']))
                    value['artifactId']=digest(canonical({key:value[key] for key in ('files','packages','sourceSha256','workloadSha256')}))
                    report['artifact']=copy.deepcopy(value); report['manifestSha256']=digest(canonical(value))
                with self.assertRaises(AssertionError): verify(report, value, canonical(value), self.rendering, self.templates)

    def test_missing_failed_retried_case_and_leak_refuse(self):
        for mutate in [lambda r: r['cases'].pop(), lambda r: r['cases'][0].update(outcome='failed'), lambda r: r['cases'][1]['observations'].update(retried=True), lambda r: r['cases'][2]['observations'].update(assertions=[]), lambda r: r['cases'][3]['observations']['cleanup'].update(owned=1), lambda r: r['driver'].update(downloadObserved=False), lambda r: r['driver'].update(browserCleanup='unknown'), lambda r: r.update(manifestSha256='foreign')]:
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(self.report); mutate(value)
                with self.assertRaises(AssertionError): verify(value, self.manifest, self.raw, self.rendering, self.templates)

    def test_negative_oracle_refuses_survivor_and_unrelated_failures(self):
        base = copy.deepcopy(self.report)
        base.pop('artifact')
        base.update(outcome='failed', cases=[], error='Stale or foreign checkpoint', verificationError='Downloaded staged input identity mismatch')
        self.assertEqual(verify_negative(base, 'stale-checkpoint')['result'], 'killed-by-specific-evidence')
        for mutate in (lambda r: r.update(verificationError='Soldier mutant survived: stale-checkpoint'),
                       lambda r: r.update(error='Case exceeded 60000ms'),
                       lambda r: r['driver'].update(browserCleanup='unknown')):
            value = copy.deepcopy(base); mutate(value)
            with self.assertRaises(AssertionError): verify_negative(value, 'stale-checkpoint')
        # A matching failure from another injection is not this mutant's evidence.
        with self.assertRaises(AssertionError): verify_negative(base, 'wrong-entry')
        with self.assertRaises(AssertionError): verify_negative(base, 'unknown')

    def test_each_negative_branch_requires_its_specific_evidence(self):
        capability = {'wrong-entry': 'wrong actual player entry', 'source-hash': 'Artifact identity mismatch',
                      'asset-hash': 'Workload contract hash mismatch', 'bundle-hash': 'Artifact hash mismatch: soldier-player/',
                      'workload-hash': 'Workload contract hash mismatch', 'stale-checkpoint': 'Stale or foreign checkpoint'}
        mutants = ['missing-mount', *capability, 'missing-case', 'stale-epoch-accepted', 'incomplete-export', 'owner-leak', 'artifact-before-download', 'artifact-after-download']
        self.assertEqual(len(mutants), 13)
        for mutant in mutants:
            with self.subTest(mutant=mutant):
                value = copy.deepcopy(self.report); value['outcome'] = 'failed'
                def fail(kind, message):
                    row = next(row for row in value['cases'] if row['kind'] == kind)
                    row.update(outcome='failed', error=message)
                    row['observations']['assertions'] = [{'name': message, 'passed': False}]
                    return row['observations']
                if mutant in capability:
                    value.pop('artifact')
                    error = 'Artifact hash mismatch: soldier-player/assets/index-fixture.js' if mutant == 'bundle-hash' else capability[mutant]
                    value.update(outcome='failed', cases=[], error=error, verificationError='Downloaded staged input identity mismatch')
                elif mutant == 'missing-mount':
                    for kind in CASES: fail(kind, 'Soldier opt-in/mount control missing from actual entry')
                elif mutant == 'missing-case':
                    value['cases'].pop(); value['error'] = 'downloaded case removed by explicit negative control'
                elif mutant == 'stale-epoch-accepted':
                    fail('soldier-external', 'soldier soldier-external: stale epoch reply refused')
                elif mutant == 'incomplete-export':
                    fail('soldier-churn', 'soldier soldier-churn: complete 2000-use six-symbol export')['details']['fullExport']['uses'] = 1999
                elif mutant == 'owner-leak':
                    fail('soldier-external', 'soldier soldier-external: zero reported owned resources')['cleanup']['owned'] = None
                elif mutant == 'artifact-before-download':
                    value.update(integrity='failed-before-download', error='Manifest changed during run')
                elif mutant == 'artifact-after-download':
                    value.update(error='downloaded artifact identity altered by explicit negative control', verificationError='Downloaded staged input identity mismatch')
                    value['artifact']['files'] = [{'sha256': 'altered'}]
                self.assertEqual(verify_negative(value, mutant)['mutant'], mutant)
                survivor = copy.deepcopy(value); survivor['verificationError'] = 'Soldier mutant survived: '+mutant
                with self.assertRaisesRegex(AssertionError, 'surviving mutant'): verify_negative(survivor, mutant)
                unrelated = copy.deepcopy(self.report); unrelated.update(outcome='failed', error='Case exceeded 60000ms')
                with self.assertRaises(AssertionError): verify_negative(unrelated, mutant)

    def test_actual_named_wait_deadline_and_first_failure(self):
        adapter = Path(__file__).parent / 'soldier-staged-journey.js'
        script = r"""
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source = readFileSync(process.argv[1], 'utf8');
const {waitForSoldierCondition} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
let now = 0, ticks = 0;
const clock = {now: () => now, expired: () => false, delay: async () => { ticks++; now += 5000; }};
await waitForSoldierCondition(() => true, 'already complete', clock);
assert.equal(ticks, 0);
await assert.rejects(waitForSoldierCondition(() => false, 'semantic keyboard route', clock), /soldier wait deadline: semantic keyboard route/);
assert.equal(now, 10000); assert.equal(ticks, 2);
await assert.rejects(waitForSoldierCondition(() => false, 'expired owner', {...clock, expired: () => true}), /expired owner/);
assert.equal(ticks, 2);
const first = new Error('first product refusal');
await assert.rejects(waitForSoldierCondition(() => { throw first; }, 'later timeout', clock), error => error === first);
"""
        result = subprocess.run(['node', '--input-type=module', '-e', script, str(adapter)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unobserved_or_missing_resume_refuses(self):
        for observed in (False, None, 'true'):
            with self.subTest(observed=observed):
                value = copy.deepcopy(self.report)
                if observed is None:
                    value['driver'].pop('resumeObserved')
                else:
                    value['driver']['resumeObserved'] = observed
                with self.assertRaisesRegex(AssertionError, 'resume was not observed'):
                    verify(value, self.manifest, self.raw, self.rendering, self.templates)

    def test_actual_workflow_pins_order_budget_and_separate_evidence(self):
        root=Path(__file__).parents[3]
        workflow=(root/'.github/workflows/svg-preview-c.yml').read_text()
        pin=re.search(r'repository: FS-GG/FS.GG.Rendering\n          ref: ([0-9a-f]{40})',workflow).group(1)
        self.assertIn('expected_source='+pin,workflow)
        for path in ('verify-soldier-reference-candidate.sh', 'soldier-staged-journey.js', 'test-soldier-staged-fixture.py'):
            self.assertEqual(workflow.count("      - 'tests/composition/fable-game/"+path+"'"), 2)

        self.assertLess(workflow.index('Preflight soldier staged source'),workflow.index('Install browser hosts'))
        self.assertNotIn('FSGG_PYTHON_COORDINATION_ROOT:', workflow)
        self.assertIn('timeout-minutes: 90',workflow)
        self.assertIn('10m ',workflow); self.assertIn('50m ',workflow)
        self.assertIn('soldier-staged-consumer/*.world.svg',workflow)
        source=(Path(__file__).parent/'verify-soldier-reference-candidate.sh').read_text()
        self.assertLess(source.index('prepare_svg_source_python_fixture "$root" "$out"'), source.index('[[ -n "${FSGG_PYTHON_COORDINATION_ROOT:-}" ]]'))
        self.assertIn('--base /soldier-player/',source)
        self.assertIn('--urls http://127.0.0.1:0 --webroot "$sealed"',source)
        self.assertIn('env -i PATH=',source)
        self.assertLess(source.index('producer-fixture-input.json'),source.index('dotnet pack '))
        self.assertLess(source.index('staged-input.json'),source.index('dotnet publish '))
        self.assertIn('--deadline-ms 120000',source)
        self.assertIn('server custody changed; refusing kill',source)
        self.assertIn('owned server listener did not settle',source)
        # 750s positive +13*120s adversarial +90s shutdown reserve fit the2400s server lifetime.
        self.assertLessEqual(750+13*120+90,2400)

    def test_uninstall_identity_parser_refuses_foreign_or_ambiguous_package(self):
        import tempfile
        from zipfile import ZipFile
        source = (Path(__file__).parent / 'verify-soldier-reference-candidate.sh').read_text()
        code = source.split("<<'PYTEMPLATEID'\n", 1)[1].split('\nPYTEMPLATEID', 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            for identity, ambiguous, expected in [('FS.GG.Workspace.Template', False, 0), ('Foreign.Template', False, 1), ('FS.GG.Workspace.Template', True, 1)]:
                archive = Path(folder) / 'fixture.nupkg'
                with ZipFile(archive, 'w') as package:
                    package.writestr('fixture.nuspec', '<package><metadata><id>'+identity+'</id></metadata></package>')
                    if ambiguous: package.writestr('second.nuspec', '<package/>')
                result = subprocess.run([sys.executable, '-c', code, str(archive)], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected == 0: self.assertEqual(result.stdout.strip(), identity)

    def test_actual_verifier_keeps_compile_profile_and_selected_order(self):
        source = (Path(__file__).parent / 'verify-soldier-reference-candidate.sh').read_text()
        self.assertIn('237f66bcce46c9e6227a266231342b34367b060c', source)
        self.assertIn('staged', source)
        self.assertNotIn('NuGetAudit=false', source)
        self.assertIn('template_id="$(python3 - "${archives[0]}"', source)
        self.assertIn('dotnet new uninstall "$template_id"', source)
        self.assertIn('! grep -F -- "$template_id"', source)
        self.assertIn('--verify-negative "$out/staged-negative-$mutant.json" --mutant "$mutant"', source)
        self.assertNotIn('window.svgFoundation =', (Path(__file__).parent / 'soldier-staged-journey.js').read_text())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--verify-negative':
        parser = argparse.ArgumentParser(); parser.add_argument('--verify-negative', type=Path, required=True); parser.add_argument('--mutant', required=True)
        args = parser.parse_args()
        print(json.dumps(verify_negative(json.loads(args.verify_negative.read_text()), args.mutant), sort_keys=True))
    elif len(sys.argv) > 1 and sys.argv[1] == '--verify':
        parser = argparse.ArgumentParser(); parser.add_argument('--verify', type=Path, required=True); parser.add_argument('--manifest', type=Path, required=True); parser.add_argument('--rendering', required=True); parser.add_argument('--templates', required=True)
        args = parser.parse_args(); raw = args.manifest.read_bytes()
        print(json.dumps(verify(json.loads(args.verify.read_text()), json.loads(raw), raw, args.rendering, args.templates), sort_keys=True))
    else:
        unittest.main()
