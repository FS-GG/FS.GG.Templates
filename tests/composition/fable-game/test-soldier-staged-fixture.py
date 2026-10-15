"""Finite inert controls and data-only verification for the maintained staged report."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
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

    def test_actual_verifier_keeps_compile_profile_and_selected_order(self):
        source = (Path(__file__).parent / 'verify-soldier-reference-candidate.sh').read_text()
        self.assertIn('237f66bcce46c9e6227a266231342b34367b060c', source)
        self.assertIn('staged', source)
        self.assertNotIn('NuGetAudit=false', source)
        self.assertNotIn('window.svgFoundation =', (Path(__file__).parent / 'soldier-staged-journey.js').read_text())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        parser = argparse.ArgumentParser(); parser.add_argument('--verify', type=Path, required=True); parser.add_argument('--manifest', type=Path, required=True); parser.add_argument('--rendering', required=True); parser.add_argument('--templates', required=True)
        args = parser.parse_args(); raw = args.manifest.read_bytes()
        print(json.dumps(verify(json.loads(args.verify.read_text()), json.loads(raw), raw, args.rendering, args.templates), sort_keys=True))
    else:
        unittest.main()
