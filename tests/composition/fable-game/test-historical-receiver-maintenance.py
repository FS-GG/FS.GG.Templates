"""Inert controls for actual historical maintenance guards and shell fielding."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('maintenance', HERE / 'historical-receiver-maintenance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receiver = self.root / 'receiver'; self.receiver.mkdir()
        (self.receiver / 'Server.Tests').mkdir()
        self.manifest = self.receiver / m.MANIFEST
        self.manifest.write_bytes(b'<Project><ItemGroup>' + m.OLD + b'</ItemGroup></Project>')
        self.lock = self.receiver / m.LOCK
        self.original = {'dependencies': {'net10.0': {
            m.PACKAGE: {'type': 'Direct', 'requested': '[10.0.0, )', 'resolved': '10.0.0', 'dependencies': {'Microsoft.AspNetCore.SignalR.Common': '10.0.0'}},
            'Microsoft.AspNetCore.SignalR.Common': {'type': 'Transitive', 'resolved': '10.0.0', 'contentHash': 'inert-original'},
            'FSharp.Core': {'type': 'Direct', 'requested': '[10.1.400, )', 'resolved': '10.1.400', 'contentHash': 'inert-fixed'},
        }}}
        self.lock.write_text(json.dumps(self.original))
        (self.receiver / 'authored.fs').write_text('owner source')
        self.archive = self.root / 'inert.nupkg'; self.archive.write_bytes(b'fixture-not-a-runtime-archive')
        self.config = self.root / 'public.config'; self.config.write_text(m.PUBLIC_CONFIG)
        self.state = self.root / 'state.json'; self.output = self.root / 'receipt.json'
        self.log = self.root / 'restore.log'; self.log.write_text('inert restore adapter')
        self.original_baselines = m.BASELINES; self.original_manifest = m.MANIFEST_SHA
        self.addCleanup(setattr, m, 'BASELINES', self.original_baselines)
        self.addCleanup(setattr, m, 'MANIFEST_SHA', self.original_manifest)
        m.BASELINES = {'0.10.0': (m.sha(self.archive), m.sha(self.lock)), '0.11.0': (m.sha(self.archive), m.sha(self.lock))}
        m.MANIFEST_SHA = m.sha(self.manifest)

    def prepare(self):
        return m.prepare(self.receiver, self.archive, '0.10.0', self.config, self.state)

    def regenerate(self):
        value = copy.deepcopy(self.original)
        graph = value['dependencies']['net10.0']
        graph[m.PACKAGE].update(requested='[10.0.13, )', resolved='10.0.13', dependencies={'Microsoft.AspNetCore.SignalR.Common': '10.0.13'})
        graph['Microsoft.AspNetCore.SignalR.Common'].update(resolved='10.0.13', contentHash='inert-maintained')
        self.lock.write_text(json.dumps(value))
        return value

    def finish(self):
        return m.finish(self.receiver, self.archive, '0.10.0', self.config, self.state, self.log, self.output)

    def test_actual_exact_delta_and_receipt_preserve_historical_identity(self):
        original_manifest = self.manifest.read_bytes(); original_archive = self.archive.read_bytes()
        saved = self.prepare(); self.regenerate(); receipt = self.finish()
        self.assertEqual(self.manifest.read_bytes(), original_manifest.replace(m.OLD, m.NEW))
        self.assertEqual(self.archive.read_bytes(), original_archive)
        self.assertEqual(receipt['originalLockSha256'], saved['originalLockSha256'])
        self.assertEqual(receipt['upgradedLockSha256'], m.sha(self.lock))
        self.assertEqual(receipt['historicalTemplateVersion'], '0.10.0')
        self.assertEqual(receipt['resolvedSignalRCommon'], '10.0.13')
        self.assertEqual(receipt['executionBoundary'], 'root-build-test-browser-must-run-after-maintenance')

    def test_archive_manifest_missing_lock_and_closed_config_refuse_before_write(self):
        for change in ('archive', 'manifest', 'missing-lock', 'config'):
            with self.subTest(change=change):
                path = {'archive': self.archive, 'manifest': self.manifest, 'missing-lock': self.lock, 'config': self.config}[change]
                old = path.read_bytes()
                if change == 'missing-lock': path.unlink()
                else: path.write_bytes(old + b'drift')
                with self.assertRaises(ValueError): self.prepare()
                self.assertFalse(self.state.exists())
                path.write_bytes(old)

    def test_unrelated_source_or_lock_changes_are_refused(self):
        self.prepare(); self.regenerate()
        (self.receiver / 'authored.fs').write_text('drift')
        with self.assertRaisesRegex(ValueError, 'outside exact'): self.finish()
        (self.receiver / 'authored.fs').write_text('owner source')
        (self.receiver / 'unrelated.lock.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'population'): self.finish()
        self.assertFalse(self.output.exists())

    def test_unrelated_direct_and_transitive_graph_drift_are_refused(self):
        self.prepare()
        for name in ('FSharp.Core', 'Unrelated.New'):
            with self.subTest(name=name):
                value = self.regenerate(); graph = value['dependencies']['net10.0']
                graph[name] = {'type': 'Direct' if name == 'FSharp.Core' else 'Transitive', 'resolved': 'foreign'}
                self.lock.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'unrelated'): self.finish()
                self.assertFalse(self.output.exists())

    def test_remaining_vulnerable_common_or_unpatched_manifest_is_refused(self):
        self.prepare(); value = self.regenerate()
        value['dependencies']['net10.0']['Microsoft.AspNetCore.SignalR.Common']['resolved'] = '10.0.0'
        self.lock.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'vulnerable'): self.finish()
        self.regenerate(); self.manifest.write_bytes(self.manifest.read_bytes().replace(b'10.0.13', b'10.0.12'))
        with self.assertRaisesRegex(ValueError, 'manifest'): self.finish()

    def test_stale_receipt_binding_and_changed_public_source_refuse(self):
        self.prepare(); self.regenerate(); saved = self.state.read_text()
        state = json.loads(saved); state['receiver'] = '/foreign'; self.state.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'stale'): self.finish()
        self.state.write_text(saved); self.config.write_text(m.PUBLIC_CONFIG + '<!-- foreign -->')
        with self.assertRaisesRegex(ValueError, 'configuration'): self.finish()
        self.assertFalse(self.output.exists())

    def test_existing_receipt_and_source_symlink_refuse(self):
        self.prepare(); self.regenerate(); self.output.write_text('retained original')
        with self.assertRaisesRegex(ValueError, 'fresh external receipt'): self.finish()
        self.assertEqual(self.output.read_text(), 'retained original')
        (self.receiver / 'link').symlink_to(self.root / 'foreign')
        with self.assertRaisesRegex(ValueError, 'symlink'): m.snapshot(self.receiver)

    def test_exact_archive_final_lf_restored_but_other_lock_changes_refused(self):
        folder = self.receiver / 'Domain'; folder.mkdir()
        other = folder / 'packages.lock.json'; raw = b'{"version":1,"dependencies":{}}\n'; other.write_bytes(raw)
        with ZipFile(self.archive, 'w') as archive:
            archive.writestr('content/templates/fs-gg-fable-game/Domain/packages.lock.json', raw)
        m.BASELINES['0.10.0'] = (m.sha(self.archive), m.sha(self.lock))
        self.prepare(); self.regenerate(); other.write_bytes(raw[:-1])
        receipt = self.finish()
        self.assertEqual(other.read_bytes(), raw)
        self.assertEqual(receipt['serializerRestorations'], [{'path': 'Domain/packages.lock.json', 'observedSha256': hashlib.sha256(raw[:-1]).hexdigest(), 'restoredSha256': hashlib.sha256(raw).hexdigest()}])
        self.output.unlink(); other.write_bytes(raw.replace(b'1', b'2'))
        with self.assertRaisesRegex(ValueError, 'beyond serializer'): self.finish()
        self.assertFalse(self.output.exists())

    def test_actual_caller_maintains_all_four_before_root_work_and_records_v6(self):
        source = (HERE / 'verify-svg-typed-receivers.sh').read_text()
        maintenance = source.index('for receiver in clean retained sdd-none wizard; do\n  maintain_receiver')
        build = source.index('for receiver in clean retained sdd-none wizard; do\n  build_env')
        self.assertLess(source.index("'installed skills were refreshed during adoption'"), maintenance)
        self.assertLess(maintenance, build)
        self.assertIn('schema:"fsgg.svg-typed-receivers/6"', source)
        self.assertEqual(source.count('(cd "$out/$receiver" && env "${maintenance_env[@]}" dotnet restore Server.Tests/Server.Tests.fsproj'), 2)
        self.assertEqual(source.count('rootBuildTestBrowser:"passed-after-dependency-maintenance"'), 4)
        self.assertEqual(source.count('rootBuildTestBrowser:"passed"'), 0)
        self.assertIn('installedPublicQualification:"passed-after-dependency-maintenance"', source)
        for key in ('cleanMaintenance', 'retainedMaintenance', 'noneMaintenance', 'wizardMaintenance'):
            self.assertIn('$' + key + '[0]', source)

    def test_actual_caller_failed_restore_cannot_finish_or_build(self):
        source = (HERE / 'verify-svg-typed-receivers.sh').read_text()
        function = 'maintain_receiver() {' + source.split('maintain_receiver() {', 1)[1].split('\n}\n', 1)[0] + '\n}\n'
        tools = self.root / 'tools'; tools.mkdir()
        helper = self.root / 'tests/composition/fable-game/historical-receiver-maintenance.py'; helper.parent.mkdir(parents=True)
        helper.write_text('import pathlib,sys\np=pathlib.Path(sys.argv[sys.argv.index("--state")+1]);p.write_text(sys.argv[1])\n')
        dotnet = tools / 'dotnet'; dotnet.write_text('#!/bin/sh\necho retained-original-restore-failure >&2\nexit 23\n'); dotnet.chmod(0o755)
        out = self.root / 'out'; out.mkdir()
        setup = 'set -euo pipefail\nroot="$1"\nout="$2"\ncurrent_package=current\nold_package=old\ntemplate_version=0.11.0\nolder_template_version=0.10.0\nwizard_template_version=0.19.0\nwizard_package=wizardarchive\n'
        for receiver in ('clean', 'retained', 'sdd-none', 'wizard'):
            (out / receiver).mkdir()
            result = subprocess.run(['bash', '-c', setup + function + f'maintain_receiver {receiver}\ntouch "$out/unexpected-build"', 'fixture', str(self.root), str(out)], env={**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH']}, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('retained-original-restore-failure', result.stderr)
            self.assertEqual((out / (receiver + '-dependency-maintenance-state.json')).read_text(), 'prepare')
        self.assertFalse((out / 'unexpected-build').exists())


    def test_actual_four_path_caller_reaches_finish_only_after_two_audited_restores(self):
        source = (HERE / 'verify-svg-typed-receivers.sh').read_text()
        function = 'maintain_receiver() {' + source.split('maintain_receiver() {', 1)[1].split('\n}\n', 1)[0] + '\n}\n'
        tools = self.root / 'tools'; tools.mkdir()
        trace = self.root / 'calls.jsonl'
        helper = self.root / 'tests/composition/fable-game/historical-receiver-maintenance.py'; helper.parent.mkdir(parents=True)
        helper.write_text('import json,os,pathlib,sys\na=sys.argv[1:]\nwith open(os.environ["TRACE"],"a") as f:f.write(json.dumps({"helper":a})+"\\n")\n')
        dotnet = tools / 'dotnet'
        dotnet.write_text('#!/usr/bin/env python3\nimport json,os,sys\na=sys.argv[1:]\nassert a[:2]==["restore","Server.Tests/Server.Tests.fsproj"]\nassert all(x in a for x in ["-p:NuGetAudit=true","-p:NuGetAuditMode=all","-p:TreatWarningsAsErrors=true"])\nwith open(os.environ["TRACE"],"a") as f:f.write(json.dumps({"dotnet":a,"cwd":os.getcwd(),"fsharp":os.environ.get("FSharpCoreImplicitPackageVersion")})+"\\n")\n')
        dotnet.chmod(0o755)
        out = self.root / 'out'; out.mkdir()
        for receiver in ('clean', 'retained', 'sdd-none', 'wizard'):
            tree = out / receiver / 'Server.Tests'; tree.mkdir(parents=True)
            (tree / 'Server.Tests.fsproj').write_text('inert source')
            (tree / 'packages.lock.json').write_text('{}')
        setup = 'set -euo pipefail\nroot="$1"\nout="$2"\ncurrent_package=current\nold_package=old\ntemplate_version=0.11.0\nolder_template_version=0.10.0\nwizard_template_version=0.19.0\nwizard_package=wizardarchive\n'
        result = subprocess.run(['bash', '-c', setup + function + 'for receiver in clean retained sdd-none wizard; do maintain_receiver "$receiver"; done\ntouch "$out/root-build-reached"', 'fixture', str(self.root), str(out)], env={**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'], 'TRACE': str(trace)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertEqual(len(rows), 16)
        for index, receiver in enumerate(('clean', 'retained', 'sdd-none', 'wizard')):
            prepare, regeneration, locked, finish = rows[index*4:index*4+4]
            self.assertEqual(prepare['helper'][0], 'prepare'); self.assertEqual(finish['helper'][0], 'finish')
            args = prepare['helper']; self.assertEqual(args[args.index('--version')+1], '0.10.0' if receiver == 'retained' else ('0.19.0' if receiver == 'wizard' else '0.11.0'))
            self.assertIn('-p:RestoreLockedMode=false', regeneration['dotnet']); self.assertIn('--force-evaluate', regeneration['dotnet'])
            self.assertNotIn('-p:RestoreLockedMode=false', locked['dotnet']); self.assertIn('--locked-mode', locked['dotnet'])
            self.assertEqual(regeneration['cwd'], str(out / receiver)); self.assertEqual(locked['cwd'], str(out / receiver))
            self.assertEqual(regeneration['fsharp'], '10.1.400' if receiver == 'retained' else None)
        self.assertTrue((out / 'root-build-reached').exists())

    def test_actual_final_receipt_distinguishes_scaffold_from_maintained_execution(self):
        source = (HERE / 'verify-svg-typed-receivers.sh').read_text()
        command = 'jq -n --arg templates' + source.split('jq -n --arg templates', 1)[1].split('\necho "svg-typed-receivers:', 1)[0]
        for receiver in ('clean', 'retained', 'sdd-none', 'wizard'):
            (self.root / (receiver + '-foundation-browser.json')).write_text('{}')
            (self.root / (receiver + '-dependency-maintenance.json')).write_text(json.dumps({'phase': 'audited-public-regeneration-and-locked-restore-passed', 'resolvedSignalRCommon': '10.0.13', 'historicalTemplateVersion': '0.10.0' if receiver == 'retained' else '0.11.0'}))
        (self.root / 'wizard-compatibility.json').write_text(json.dumps({'phase':'exact-original-before-adoption','scaffoldTemplateVersion':'0.19.0','templatePinning':False}))
        value=json.loads((self.root / 'wizard-dependency-maintenance.json').read_text());value.update(cohort='wizard-legacy-compatibility',scaffoldTemplateVersion='0.19.0');(self.root / 'wizard-dependency-maintenance.json').write_text(json.dumps(value))
        setup = 'set -euo pipefail\nout="$1"\ntemplates_source=source\nrendering_revision=rendering\nolder_templates_revision=older\nscene_package=scene\nkeyboard_package=keyboard\nbrowser_package=browser\ncurrent_package=template\nsha() { echo fixture; }\ntree_sha() { echo fixture; }\nfable_api_sha() { echo fixture; }\n'
        result = subprocess.run(['bash', '-c', setup + command, 'fixture', str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.root / 'svg-typed-receivers.json').read_text())
        self.assertEqual(receipt['schema'], 'fsgg.svg-typed-receivers/6')
        self.assertEqual(receipt['historicalScaffold']['archives'], 'unchanged-original-public-bytes')
        self.assertEqual(receipt['historicalScaffold']['execution'], 'dependency-maintained-receivers')
        self.assertEqual(len(receipt['dependencyMaintenance']), 4)
        for receiver in ('clean', 'retained', 'sddNone', 'wizard'):
            self.assertEqual(receipt['journeys'][receiver]['rootBuildTestBrowser'], 'passed-after-dependency-maintenance')
        (self.root / 'wizard-dependency-maintenance.json').write_text('{"phase":"failed","resolvedSignalRCommon":"10.0.0"}')
        result = subprocess.run(['bash', '-c', setup + command, 'fixture', str(self.root)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)



class WizardCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.receiver = self.root / 'wizard'
        (self.receiver / 'Server.Tests').mkdir(parents=True); (self.receiver / '.fsgg').mkdir()
        self.archive = self.root / 'template.nupkg'; self.tool = self.root / 'wizard.nupkg'
        self.manifest = self.receiver / m.MANIFEST; self.manifest.write_bytes(b'<Project>' + m.OLD.replace(b'10.0.0', b'10.0.12') + b'</Project>')
        self.lock = self.receiver / m.LOCK; self.lock.write_text('{"dependencies":{}}')
        self.config = {'identity':'FS.GG.Workspace.Template.FableGame.LegacySvgFoundation','symbols':{'svgFoundation':{'isRequired':True}}}
        self.raw = json.dumps(self.config).encode()
        with ZipFile(self.archive,'w') as z:
            z.writestr('FS.GG.Workspace.Template.nuspec','<package><metadata><version>0.19.0</version><repository commit="8952e1c5753b0abc972154c7596ddc8da772b271"/></metadata></package>')
            z.writestr(m.LEGACY_MEMBER+'.template.config/template.json',self.raw)
            z.writestr('content/templates/fs-gg-fable-game/.template.config/template.json','{"symbols":{"bundle":{}}}')
            for name in (m.MANIFEST,m.LOCK):z.writestr(m.LEGACY_MEMBER+name,(self.receiver/name).read_bytes())
        with ZipFile(self.tool,'w') as z:
            z.writestr('FS.GG.NewSddWorkspace.nuspec','<package><metadata><version>0.11.1</version><repository commit="f0f6d13313c90ae38bff42416e90b6b36bc7161d"/></metadata></package>')
        descriptor=self.receiver/'.fsgg/providers.yml'; descriptor.write_text('inert exact descriptor')
        self.params=[{'key':'lifecycle','value':'none'},{'key':'productName','value':'WizardReceiver'},{'key':'rootNamespace','value':'WizardReceiver'},{'key':'svgFoundation','value':'false'}]
        self.provenance=self.receiver/'.fsgg/scaffold-provenance.json'
        self.provenance.write_text(json.dumps({'generator':{'version':'1.7.0'},'outcome':'providerSucceeded','effectiveParameters':self.params}))
        (self.receiver/'.fsgg/workspace-initialization.json').write_text('{"status":"pending"}')
        self.registry=self.root/'registry.json'; self.rows={'Packages':[{'Details':{'PackageId':'FS.GG.Workspace.Template','Version':'0.19.0'},'MountPointUri':str(self.archive)}]};self.registry.write_text(json.dumps(self.rows))
        self.output=self.root/'guard.json'
        for key,value in {'LEGACY_ARCHIVE':m.sha(self.archive),'WIZARD_ARCHIVE':m.sha(self.tool),'LEGACY_MANIFEST':m.sha(self.manifest),'LEGACY_LOCK':m.sha(self.lock),'LEGACY_CONFIG':hashlib.sha256(self.raw).hexdigest(),'WIZARD_DESCRIPTOR':m.sha(descriptor)}.items():
            manager=patch.object(m,key,value);manager.start();self.addCleanup(manager.stop)

    def guard(self):return m.wizard_guard(self.receiver,self.archive,self.registry,self.tool,self.output)

    def test_real_guard_binds_member_role_and_actual_distinct_cohort(self):
        record=self.guard();self.assertFalse(record['templatePinning']);self.assertEqual(record['scaffoldTemplateVersion'],'0.19.0')
        config=self.root/'public.config';config.write_text(m.PUBLIC_CONFIG)
        state=self.root/'state.json';saved=m.prepare(self.receiver,self.archive,'0.19.0',config,state,self.output)
        self.assertNotIn('historicalTemplateVersion',saved);self.assertEqual(saved['cohort'],'wizard-legacy-compatibility')
        self.assertIn(b'10.0.13',self.manifest.read_bytes())
        with self.assertRaises(ValueError):m.prepare(self.receiver,self.archive,'0.11.0',config,self.root/'wrong-state',self.output)

    def test_actual_guard_retains_wrong_registry_or_effective_parameter_first_cause(self):
        for kind in ('wrong-version','duplicate','bundle','initial-svg','manifest','tool'):
            with self.subTest(kind=kind):
                rows=copy.deepcopy(self.rows);params=copy.deepcopy(self.params);original=self.manifest.read_bytes();tool=self.tool.read_bytes()
                if kind=='wrong-version':rows['Packages'][0]['Details']['Version']='0.11.0'
                if kind=='duplicate':rows['Packages']*=2
                if kind=='bundle':params.append({'key':'bundle','value':'player'})
                if kind=='initial-svg':(self.receiver/'SvgFoundation').mkdir()
                if kind=='manifest':self.manifest.write_bytes(original+b'drift')
                if kind=='tool':self.tool.write_bytes(tool+b'drift')
                self.registry.write_text(json.dumps(rows));value=json.loads(self.provenance.read_text());value['effectiveParameters']=params;self.provenance.write_text(json.dumps(value))
                with self.assertRaises(ValueError):self.guard()
                refusal=json.loads(self.output.read_text());self.assertEqual(refusal['phase'],'refused');self.assertTrue(refusal['firstCause'])
                self.output.unlink();self.manifest.write_bytes(original);self.tool.write_bytes(tool)
                if kind=='initial-svg':(self.receiver/'SvgFoundation').rmdir()

    def test_legacy_maintenance_refuses_missing_evidence_or_wrong_role(self):
        config=self.root/'public.config';config.write_text(m.PUBLIC_CONFIG)
        with self.assertRaisesRegex(ValueError,'role/evidence'):m.prepare(self.receiver,self.archive,'0.19.0',config,self.root/'state')
        self.guard();wrong=self.root/'clean';self.receiver.rename(wrong)
        with self.assertRaisesRegex(ValueError,'role/evidence'):m.prepare(wrong,self.archive,'0.19.0',config,self.root/'state',self.output)

if __name__ == '__main__':
    unittest.main()
