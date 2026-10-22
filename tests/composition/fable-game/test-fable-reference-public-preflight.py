#!/usr/bin/env python3
"""Synthetic input controls; preflight cannot install, build or query a feed."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import ast
import copy
import hashlib
import io
import json
import re
import time
import zipfile
import stat
import tarfile
import signal
import shutil
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

class PublicReferencePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.effect = self.root / 'effect'
        stub = self.root / 'dotnet'; stub.write_text('#!/bin/sh\ntouch "' + str(self.effect) + '"\nexit 99\n'); stub.chmod(0o700)
        self.env = {**os.environ, 'DOTNET_HOST_PATH': str(stub), 'QUINT_BIN': str(stub)}

    def args(self, mode='templates'):
        args = ['--mode', mode, '--template-version', '0.18.1', '--sha256', 'a'*64,
                '--descriptor-sha256', 'b'*64, '--source-revision', 'c'*40,
                '--tag-revision', 'c'*40, '--sdd-version', '2.1.0', '--sdd-sha256', 'd'*64,
                '--sdd-source-revision', 'e'*40, '--evidence-dir', str(self.root/'fresh'), '--preflight-only']
        if mode == 'full': args += ['--wizard-version', '0.16.0', '--wizard-sha256', 'f'*64, '--wizard-source-revision', 'a'*40]
        return args

    def wasm_args(self):
        return ['--mode', 'wasm', '--template-version', '0.19.1', '--sha256', 'a'*64,
                '--descriptor-sha256', 'b'*64, '--source-revision', 'c'*40,
                '--tag-revision', 'c'*40, '--evidence-dir', str(self.root/'fresh'), '--preflight-only']

    def run_preflight(self, args, expected):
        result = subprocess.run(['bash', str(HERE/'verify-fable-reference-public.sh'), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, expected, result.stderr)
        self.assertFalse(self.effect.exists()); self.assertFalse((self.root/'fresh').exists())

    def test_templates_only_is_independent_of_wizard(self): self.run_preflight(self.args(), True)
    def test_full_requires_selected_successor_inputs(self): self.run_preflight(self.args('full'), True)
    def test_historical_version_refused(self): self.run_preflight([a.replace('0.18.1', '0.18.0') for a in self.args()], False)
    def test_old_wizard_refused(self): self.run_preflight([a.replace('0.16.0', '0.15.0') for a in self.args('full')], False)
    def test_templates_mode_refuses_wizard_claim(self): self.run_preflight(self.args()+['--wizard-version', '0.16.0'], False)
    def test_unknown_mode_refused(self): self.run_preflight(self.args('unknown'), False)
    def test_missing_full_wizard_refused(self):
        args = self.args(); args[1] = 'full'; self.run_preflight(args, False)
    def test_different_tag_source_refused(self): self.run_preflight([a.replace('c'*40, 'b'*40) if i and self.args()[i-1]=='--tag-revision' else a for i,a in enumerate(self.args())], False)
    def test_source_newline_refused(self): self.run_preflight([a+'\n' if a=='c'*40 else a for a in self.args()], False)
    def test_duplicate_version_refused(self): self.run_preflight(self.args()+['--template-version', '0.18.1'], False)

    def test_wasm_direct_preflight_has_no_sdd_wizard_or_runtime_effect(self): self.run_preflight(self.wasm_args(), True)
    def test_wasm_requires_closed_successor(self): self.run_preflight([a.replace('0.19.1','0.18.1') for a in self.wasm_args()], False)
    def test_wasm_refuses_superseded_0190_with_truncated_guest(self): self.run_preflight([a.replace('0.19.1','0.19.0') for a in self.wasm_args()], False)
    def test_historical_route_cannot_claim_successor(self):
        for successor in ('0.19.0','0.19.1'):
            with self.subTest(successor=successor): self.run_preflight([a.replace('0.18.1',successor) for a in self.args()], False)
    def test_wasm_refuses_sdd_scope(self): self.run_preflight(self.wasm_args()+['--sdd-version','2.1.0'], False)
    def test_wasm_refuses_wizard_scope(self): self.run_preflight(self.wasm_args()+['--wizard-version','0.16.0'], False)
    def test_wasm_requires_exact_tag_source(self):
        args=self.wasm_args(); args[args.index('--tag-revision')+1]='f'*40; self.run_preflight(args, False)
    def test_wasm_source_newline_refused(self): self.run_preflight([a+'\n' if a=='c'*40 else a for a in self.wasm_args()], False)
    def test_wasm_archive_digest_required(self):
        args=self.wasm_args(); args[args.index('--sha256')+1]='a'*63; self.run_preflight(args, False)
    def test_wasm_preflight_requires_new_evidence(self):
        (self.root/'fresh').mkdir()
        result=subprocess.run(['bash',str(HERE/'verify-fable-reference-public.sh'),*self.wasm_args()],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0); self.assertFalse(self.effect.exists())


class CurrentPublicPreflightTests(unittest.TestCase):
    """Exercise the real shell boundary with immutable descriptor bytes and causal mutations."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.effect = self.root / 'runtime-effect'
        self.bin = self.root / 'bin'; self.bin.mkdir()
        # Any accidental acquisition/tool entry is observable, including --version.
        for name in ('dotnet', 'fsgg-sdd', 'new-sdd-workspace', 'quint', 'npm', 'node', 'curl', 'git'):
            path = self.bin / name
            path.write_text('#!/bin/sh\n: > "' + str(self.effect) + '"\nexit 99\n'); path.chmod(0o700)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'DOTNET_HOST_PATH': str(self.bin/'dotnet'), 'QUINT_BIN': str(self.bin/'quint')}
        self.descriptor = self.root / 'descriptor.yml'
        # The selected current-public provider is published 0.19.0: use its immutable descriptor bytes
        # (f5fbd06e, d7207cbd...), never the moving working-tree descriptor (0.19.1 since #730).
        self.descriptor.write_bytes((HERE/'current-public-descriptor-0.19.0.yml').read_bytes())
        self.manifest = self.root / 'inputs.json'
        self.output = self.root / 'fresh'
        self.value = {
            'schema': 'fable-reference-current-public/1',
            'packages': {
                'wizard': ['FS.GG.NewSddWorkspace', '0.19.0', 'cc1d3c12c1ed7e7128012063d7ab478c7198b523', '3c8150734814c3d5c4416535ff56f91a0570595bcc38cea6586012678a4e92b6'],
                'sdd': ['FS.GG.SDD.Cli', '2.2.0', 'cf2f046a10497a336d6243c9a314c3f91fb15771', '46b4b172eac65df00db43f813bd3d3fbafac5c6376da62a6d3c08fb05750cf28'],
                'initialOverlay': ['FS.GG.Workspace.Template', '0.18.2', '20c009bc6728302f9ed06fdf49cb2e8bd19e417d', '496aad0e89496719bc543edc6ffbf829a82307862e630ba4e174e374ac11cc4e'],
                'provider': ['FS.GG.Workspace.Template', '0.19.0', '8952e1c5753b0abc972154c7596ddc8da772b271', '187c995806bb2f22db67c8a9a67c251f46f339bf6350b8051035935d308b497f'],
            },
            'sources': {},
            'selection': {'lifecycle': 'typed-sdd', 'bundle': 'complete'},
            'referenceRenderingVersion': '0.31.0',
            'defaults': {'wizardLifecycle': 'sdd', 'providerLifecycle': 'typed-sdd', 'templateLifecycle': 'typed-sdd', 'bundle': 'player'},
            'parameterKeys': {'name': 'productName', 'identifier': 'rootNamespace'},
        }
        self.value['initialRegistration'] = {'soleWorkspaceRegistration': True, 'package': copy.deepcopy(self.value['packages']['initialOverlay'])}
        for role, revision, path, digest in [
            ('wizard', 'cc1d3c12c1ed7e7128012063d7ab478c7198b523', 'scripts/NewSddWorkspace/Program.fs', '09060748f44b555b1859e0fd0b720d06cc0d362d9c239f1f652905fbf2e62965'),
            ('descriptor', 'f5fbd06ed9e6df40f9037c7acddf9eca3c6a14fc', 'providers/fable-game.providers.yml', 'd7207cbde78f2890a63bbebf23c80bbcae8ce7f2405c0ceacf602dc6c185942c'),
            ('template', '8952e1c5753b0abc972154c7596ddc8da772b271', 'templates/fs-gg-fable-game/.template.config/template.json', 'f0f81f93b923084a56a42e2f8d008eb6fd7c5078afbc84b3b3781cfcfc2ffcff'),
            ('runtimeProject', '8952e1c5753b0abc972154c7596ddc8da772b271', 'templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj', '76bf18c19864218054c2824449b68b98a1c1b88a0311c378a951666f638c3a0b')]:
            self.value['sources'][role] = {'revision': revision, 'repositoryPath': path, 'sha256': digest}
        self.value['sources']['descriptor']['path'] = str(self.descriptor)

    def invoke(self, value=None, extra=(), preflight=True, raw=None):
        self.manifest.write_text(raw if raw is not None else json.dumps(self.value if value is None else value))
        args = ['--mode', 'current-public', '--current-public-inputs', str(self.manifest), '--evidence-dir', str(self.output)]
        if preflight: args.append('--preflight-only')
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run(['bash', str(HERE/'verify-fable-reference-public.sh'), *args, *extra], env=self.env, text=True, capture_output=True)
        self.assertFalse(self.effect.exists(), result.stderr)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'preflight modified input/output bytes')
        return result

    def creator020(self):
        value = copy.deepcopy(self.value)
        value['packages']['wizard'] = ['FS.GG.NewSddWorkspace', '0.20.0', '699f60851288f5f817b98856bdd3d220cf27dd09', 'ee8f4e33c0099b00888c50e4a5e32b3254a9d479211b39b44719fa8cf2925356']
        value['sources']['wizard'].update(revision='699f60851288f5f817b98856bdd3d220cf27dd09', sha256='4a4f3012f61a484ed09d3a14d923293c32d0ae8914ebdb53cc3abbde56ba0d06')
        return value

    def test_published020_plan_has_its_own_identity_and_no_receiver_acceptance_transfer(self):
        result = self.invoke(self.creator020()); self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['packages']['wizard'], self.creator020()['packages']['wizard'])
        self.assertEqual(plan['wizardArgv'][0], '<qualified-installed-Wizard0.20.0>')
        self.assertEqual(plan['wizardCohort']['selection'], 'selected020 source preparation')
        self.assertEqual(plan['wizardCohort']['embeddedCoordVersion'], '0.108.0')
        self.assertIn('no019-to020 acceptance transfer', plan['wizardCohort']['receiverEvidence'])
        self.assertEqual(plan['runtimeDisposition'], 'held')
        self.assertEqual(plan['packages']['initialOverlay'], self.value['packages']['initialOverlay'])
        self.assertEqual(plan['packages']['provider'], self.value['packages']['provider'])
        self.assertFalse(self.output.exists())

    def test_019_and020_cannot_mix_package_or_source_evidence(self):
        newer = self.creator020()
        for field in (1, 2, 3):
            for original, donor in [(self.value, newer), (newer, self.value)]:
                value = copy.deepcopy(original); value['packages']['wizard'][field] = donor['packages']['wizard'][field]
                with self.subTest(field=field, original=original['packages']['wizard'][1]):
                    self.assertNotEqual(self.invoke(value).returncode, 0)
        for original, donor in [(self.value, newer), (newer, self.value)]:
            value = copy.deepcopy(original); value['sources']['wizard'] = donor['sources']['wizard']
            self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_020_preserves_actual_omission_default_and_explicit_lifecycle_bundle_mapping(self):
        for lifecycle, bundle in [(None, None), ('none', 'player'), ('typed-sdd', 'complete'), ('sdd', 'studio'), ('spec-kit', 'tactical')]:
            value = self.creator020(); value['selection'] = dict(lifecycle=lifecycle, bundle=bundle)
            result = self.invoke(value); self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['providerParameters']['lifecycle'], lifecycle or 'sdd')
            self.assertEqual(plan['providerParameters']['bundle'], bundle or 'player')
            self.assertEqual('--lifecycle' in plan['wizardArgv'], lifecycle is not None)
            self.assertIn('--no-coordination', plan['wizardArgv'])
            self.assertIn('--no-governance', plan['wizardArgv'])

    def test_020_does_not_admit_signature_runtime_or_unselected_version_claims(self):
        for key in ('signatureTrust', 'runtimeAccepted', 'latestWizard'):
            value = self.creator020(); value[key] = True
            with self.subTest(key=key): self.assertNotEqual(self.invoke(value).returncode, 0)
        value = self.creator020(); value['packages']['wizard'][1] = '0.21.0'
        self.assertNotEqual(self.invoke(value).returncode, 0)
        # A release-original archive is not the selected signed public body.
        value = self.creator020(); value['packages']['wizard'][3] = '05ed18357132b2eb6013536206d83f0ca9d95e1d3fd41f78390fe99302e9767b'
        self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_020_keeps_descriptor_overlay_profile_and_runtime_holds(self):
        value = self.creator020(); value['initialRegistration']['package'] = value['packages']['provider']
        self.assertNotEqual(self.invoke(value).returncode, 0)
        value = self.creator020(); value['sources']['descriptor']['sha256'] = '668873206cbed9b6e47b939a6325039e3eb54fee59b420b089245fb9294bf3f6'
        self.assertNotEqual(self.invoke(value).returncode, 0)
        result = self.invoke(self.creator020(), preflight=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('pre-target Governance', result.stderr)
        self.assertIn('browser/native profiles', result.stderr)
        self.assertFalse(self.output.exists())

    def test_real_current_public_plan_distinguishes_roles_and_has_no_effects(self):
        result = self.invoke(); self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['packages']['initialOverlay'][1], '0.18.2')
        self.assertEqual(plan['packages']['provider'][1], '0.19.0')
        self.assertEqual(plan['providerParameters']['lifecycle'], 'typed-sdd')
        self.assertEqual(plan['runtimeDisposition'], 'held')
        self.assertEqual(plan['wizardCohort']['selection'], 'retained019 source compatibility')
        self.assertIsNone(plan['rendering']['providerUiTemplate'])
        self.assertIn('--pinned', plan['wizardArgv']); self.assertIn('--no-governance', plan['wizardArgv'])
        self.assertFalse(self.output.exists())

    def test_wizard_omission_and_explicit_none_are_distinct_from_provider_default(self):
        for lifecycle, bundle, expected in [(None, None, 'sdd'), ('none', 'player', 'none'), ('typed-sdd', 'complete', 'typed-sdd')]:
            value = copy.deepcopy(self.value); value['selection'] = dict(lifecycle=lifecycle, bundle=bundle)
            result = self.invoke(value); self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['providerParameters']['lifecycle'], expected)
            self.assertEqual(plan['providerParameters']['bundle'], bundle or 'player')
            self.assertEqual('--lifecycle' in plan['wizardArgv'], lifecycle is not None)

    def test_each_package_version_source_archive_and_role_join_refuses_causal_drift(self):
        for role in self.value['packages']:
            for field in (1, 2, 3):
                value = copy.deepcopy(self.value); value['packages'][role][field] = 'wrong'
                with self.subTest(role=role, field=field): self.assertNotEqual(self.invoke(value).returncode, 0)
        value = copy.deepcopy(self.value)
        value['packages']['provider'], value['packages']['initialOverlay'] = value['packages']['initialOverlay'], value['packages']['provider']
        self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_missing_or_conflicting_initial_custody_refuses(self):
        for change in ('missing', 'multiple', 'provider', 'numeric'):
            value = copy.deepcopy(self.value)
            if change == 'missing': del value['initialRegistration']
            elif change == 'multiple': value['initialRegistration']['soleWorkspaceRegistration'] = False
            elif change == 'numeric': value['initialRegistration']['soleWorkspaceRegistration'] = 1
            else: value['initialRegistration']['package'] = value['packages']['provider']
            with self.subTest(change=change): self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_descriptor_bytes_default_and_key_mutations_refuse(self):
        original = self.descriptor.read_text()
        for old, new in [('0.19.0', '0.18.2'), ('default: typed-sdd', 'default: none'), ('nameParameter: productName', 'nameParameter: name'), ('identifierParameter: rootNamespace', 'identifierParameter: namespace')]:
            self.descriptor.write_text(original.replace(old, new))
            with self.subTest(old=old): self.assertNotEqual(self.invoke().returncode, 0)
        self.descriptor.write_text(original)
        for field, key, wrong in [('defaults', 'wizardLifecycle', 'typed-sdd'), ('defaults', 'bundle', 'complete'), ('parameterKeys', 'name', 'name')]:
            value = copy.deepcopy(self.value); value[field][key] = wrong
            with self.subTest(key=key): self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_source_descriptor_and_false_rendering_claims_refuse(self):
        for key in ('revision', 'repositoryPath', 'sha256'):
            value = copy.deepcopy(self.value); value['sources']['descriptor'][key] = 'wrong'
            with self.subTest(key=key): self.assertNotEqual(self.invoke(value).returncode, 0)
        value = copy.deepcopy(self.value); value['referenceRenderingVersion'] = '0.32.1'
        self.assertNotEqual(self.invoke(value).returncode, 0)
        value = copy.deepcopy(self.value); value['packages']['rendering'] = ['FS.GG.UI.Template', '0.32.1']
        self.assertNotEqual(self.invoke(value).returncode, 0)

    def test_unsupported_lifecycle_bundle_mixed_route_and_duplicate_inputs_refuse(self):
        for key, wrong in [('lifecycle', 'unknown'), ('bundle', 'governed')]:
            value = copy.deepcopy(self.value); value['selection'][key] = wrong
            self.assertNotEqual(self.invoke(value).returncode, 0)
        for extra in [('--template-version', '0.19.0'), ('--mode', 'full'), ('--preflight-only',), ('--current-public-inputs', str(self.manifest))]:
            with self.subTest(extra=extra): self.assertNotEqual(self.invoke(extra=extra).returncode, 0)
        raw = json.dumps(self.value).replace('"schema":', '"schema": "duplicate", "schema":', 1)
        self.assertNotEqual(self.invoke(raw=raw).returncode, 0)

    def test_existing_root_and_dangling_root_refuse_without_runtime(self):
        self.output.mkdir(); (self.output/'owner').write_text('owner')
        self.assertNotEqual(self.invoke().returncode, 0)
        (self.output/'owner').unlink(); self.output.rmdir()
        self.output.symlink_to(self.root/'missing', target_is_directory=True)
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_non_preflight_refuses_before_historical_runtime_or_output_effects(self):
        result = self.invoke(preflight=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('pre-target Governance', result.stderr)
        self.assertIn('browser/native profiles', result.stderr)
        self.assertFalse(self.output.exists())


WORKFLOW=HERE.parents[2]/'.github/workflows/fable-reference-public.yml'

def actual_hosted_code():
    text=WORKFLOW.read_text()
    matches=re.findall(r"            -- /usr/bin/python3 -I - <<'HOSTED_WASM'\n(.*?)\n          HOSTED_WASM",text,re.S)
    if len(matches)!=1: raise AssertionError('exactly one actual hosted caller required')
    code='\n'.join(line[10:] for line in matches[0].splitlines())
    ast.parse(code)
    return text,code

class HostedWasmCallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'fielding_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.env={'EVENT':'pull_request','REPOSITORY':'FS-GG/FS.GG.Templates','HEAD_REPOSITORY':'FS-GG/FS.GG.Templates',
          'PR_HEAD':'a'*40,'WORKFLOW_REF':'FS-GG/FS.GG.Templates/.github/workflows/fable-reference-public.yml@refs/pull/1/merge',
          'WORKFLOW_SHA':'b'*40,'RUN_ID':'1','RUN_ATTEMPT':'1','IMAGE_OS':'Linux','IMAGE_VERSION':'X64'}

    def test_exact_same_repo_source_reaches_preparation(self):
        self.assertEqual(self.ns['validate_source'](self.env,'a'*40,self.root)['WORKFLOW_SHA'],'b'*40)
    def test_wrong_or_missing_source_bindings_refuse(self):
        for key,value in [('EVENT','workflow_dispatch'),('HEAD_REPOSITORY','attacker/fork'),('PR_HEAD','a'*39),('WORKFLOW_REF','other/path@ref'),('WORKFLOW_SHA','')]:
            env={**self.env,key:value}
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):self.ns['validate_source'](env,'a'*40,self.root)
        with self.assertRaises(ValueError):self.ns['validate_source'](self.env,'c'*40,self.root)
    def test_legacy_dispatch_is_separate_and_no_elevated_permission(self):
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' }}",self.text)
        self.assertIn('options: [templates, full]',self.text)
        self.assertIn('persist-credentials: false',self.text)
        self.assertNotRegex(self.text,r'(contents|actions|packages|id-token): write|secrets\.|pull_request_target:|continue-on-error')
    def test_budget_preserves_later_stages_and_never_renews(self):
        budget=self.ns['BUDGET'];self.assertEqual(sum(budget[k] for k in ('setup','custody','installed','collection','overhead'))+3*budget['cleanup'],2400)
        self.assertEqual(self.ns['phase_deadline'](100,'setup',100),940)
        self.assertEqual(self.ns['phase_deadline'](100,'installed',2100),2200)
        with self.assertRaises(ValueError):self.ns['phase_deadline'](100,'installed',2400)
        with self.assertRaises(ValueError):self.ns['phase_deadline'](100,'other',100)
    def test_fixed_checker_has_no_sdd_wizard_inputs(self):
        argv=self.ns['fixed_checker_argv'](self.root,self.root/'installed')
        self.assertIn('wasm',argv);self.assertIn('0.19.1',argv);self.assertNotIn('0.19.0',argv)
        self.assertEqual(argv.count(self.ns['PUBLISHED']),2)
        self.assertNotIn('--sdd-version',argv);self.assertNotIn('--wizard-version',argv)
    def test_literal_runtime_hold_cannot_acquire_or_start_c(self):
        def forbidden(*args,**kwargs):raise AssertionError('held caller reached the bound sequence')
        self.ns['hosted_sequence']=forbidden
        with self.assertRaisesRegex(RuntimeError,'C-J1 runtime held: managed-group contract bound'):self.ns['main']()
    def test_final_environment_is_fresh_and_does_not_inherit_credentials_or_profile(self):
        env=self.ns['fresh_environment'](self.root/'job',{'GH_TOKEN':'sensitive','MOZ_DISABLE_CONTENT_SANDBOX':'1'})
        self.assertNotIn('GH_TOKEN',env);self.assertNotIn('MOZ_DISABLE_CONTENT_SANDBOX',env)
        self.assertEqual(env['DOTNET_PROCESSOR_COUNT'],'2')
        self.assertEqual(list((self.root/'job/checker-packages').iterdir()),[])
        with self.assertRaises(ValueError):self.ns['fresh_environment'](self.root/'job',{})
    def transport(self,body,url='https://api.nuget.org/test'):
        response=io.BytesIO(body);response.geturl=lambda:url
        return lambda *args,**kwargs:response
    def test_actual_download_transport_good_bytes_and_changed_bytes(self):
        expected=hashlib.sha256(b'actual').hexdigest()
        row=self.ns['download']('https://api.nuget.org/test',self.root/'download',64,time.monotonic()+10,expected,transport=self.transport(b'actual'))
        self.assertEqual(row['bytes'],6);self.assertEqual(row['digest'],expected)
        with self.assertRaisesRegex(ValueError,'digest differs'):self.ns['download']('https://api.nuget.org/test',self.root/'bad',64,time.monotonic()+10,expected,transport=self.transport(b'changed'))
    def test_actual_download_refuses_wrong_origin_redirect_bound_and_expiry(self):
        cases=[('http://api.nuget.org/test',b'x','https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://unknown.invalid/test',b'x','https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x','https://unknown.invalid/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x'*11,'https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x','https://api.nuget.org/test',10,time.monotonic()-1)]
        for i,(url,body,final,cap,deadline) in enumerate(cases):
            with self.subTest(i=i),self.assertRaises(ValueError):self.ns['download'](url,self.root/str(i),cap,deadline,transport=self.transport(body,final))
    def package(self,path,wrong=False):
        with zipfile.ZipFile(path,'w') as z:
            for role,key,version in [('Client','vite','7.3.6'),('Browser.Tests','@playwright/test','1.63.0')]:
                if wrong and role=='Browser.Tests':version='1.62.0'
                prefix='content/templates/fs-gg-fable-game/'+role+'/'
                z.writestr(prefix+'package.json','{}')
                z.writestr(prefix+'package-lock.json',json.dumps({'packages':{'':{'devDependencies':{key:version}},'node_modules/'+key:{'resolved':'https://registry.npmjs.org/example/-/example.tgz','integrity':'sha512-abc'}}}))
    def test_actual_package_seed_uses_only_downloaded_modern_locks(self):
        archive=self.root/'package';self.package(archive)
        out=self.ns['seed_from_package'](archive,self.root/'seed',time.monotonic()+10)
        self.assertEqual(sorted(p.name for p in out.iterdir()),['Browser.Tests','Client'])
        self.assertEqual(sorted(p.name for p in (out/'Client').iterdir()),['package-lock.json','package.json'])
    def test_wrong_browser_lock_blocks_acquisition(self):
        archive=self.root/'package';self.package(archive,True)
        with self.assertRaisesRegex(ValueError,'dependency version differs'):self.ns['seed_from_package'](archive,self.root/'seed',time.monotonic()+10)
    def test_actual_tool_failures_collected_and_block_dependent_stages(self):
        outputs={'--version':'wrong','--list-runtimes':'Microsoft.NETCore.App 10.0.11 [/tool]'}
        def inert(argv,cwd,env):return outputs.get(argv[-1],'wrong')
        env={'DOTNET_HOST_PATH':'/qualified/dotnet','FSGG_WASM_FABLE_CORE':'/qualified/fable.dll','FSGG_WASM_WASI_ROOT':'/qualified/wasi'}
        with self.assertRaisesRegex(ValueError,'tool prerequisites failed'):self.ns['qualify_tools'](self.root,env,inert)
        retained=json.loads((self.root/'actual-tool-findings.json').read_text())
        self.assertGreaterEqual(len(retained['failures']),6)
    def test_private_download_refuses_late_eof_and_covers_open_with_one_wall_timer(self):
        clock=[1.0]
        class Late(io.BytesIO):
            def read(self,n):clock[0]=11.0;return b''
        response=Late();response.geturl=lambda:'https://api.nuget.org/test'
        with patch.object(self.ns['time'],'monotonic',lambda:clock[0]),self.assertRaisesRegex(ValueError,'deadline'):
            self.ns['download']('https://api.nuget.org/test',self.root/'late',64,10.0,transport=lambda *a,**k:response)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        previous=signal.getsignal(signal.SIGALRM);entered=[]
        def blocked_open(*args,**kwargs):
            entered.append(True);signal.getsignal(signal.SIGALRM)(signal.SIGALRM,None)
        with self.assertRaisesRegex(TimeoutError,'wall deadline'):
            self.ns['download']('https://api.nuget.org/test',self.root/'never-opened',64,time.monotonic()+10,transport=blocked_open)
        self.assertTrue(entered);self.assertFalse((self.root/'never-opened').exists())
        self.assertEqual(signal.getsignal(signal.SIGALRM),previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))

    def test_private_seed_refuses_population_and_oversized_lock_before_decompression(self):
        path=self.root/'over-populated.zip'
        with zipfile.ZipFile(path,'w') as z:
            for n in range(2048):z.writestr(str(n),b'')
        with patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('unbounded CRC')),patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('decompression before population')),self.assertRaises(ValueError):
            self.ns['seed_from_package'](path,self.root/'no-seed',time.monotonic()+10)
        self.assertFalse((self.root/'no-seed').exists())
        path=self.root/'oversized-lock.zip';self.package(path)
        # Rewrite exact selected lock with a declared payload beyond the closed limit.
        with zipfile.ZipFile(path) as z:entries={i.filename:z.read(i) for i in z.infolist()}
        key='content/templates/fs-gg-fable-game/Client/package-lock.json';entries[key]=b'x'*1048577
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,raw in entries.items():z.writestr(name,raw)
        with patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('decompression before selected byte cap')),self.assertRaisesRegex(ValueError,'lock byte'):
            self.ns['seed_from_package'](path,self.root/'no-large-seed',time.monotonic()+10)
        self.assertFalse((self.root/'no-large-seed').exists())

    def tar_fixture(self, entries):
        path=self.root/'fixture.tar.gz'
        with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as source:
            for name,kind,body,target in entries:
                item=tarfile.TarInfo(name);item.type=kind;item.mode=0o755;item.size=len(body);item.linkname=target
                source.addfile(item,io.BytesIO(body))
        return path

    def test_private_tar_streams_finite_regular_files_and_links_without_getmembers(self):
        path=self.tar_fixture([('bin/',tarfile.DIRTYPE,b'',''),('bin/tool',tarfile.REGTYPE,b'inert',''),('bin/link',tarfile.SYMTYPE,b'','tool')])
        with patch.object(tarfile.TarFile,'getmembers',side_effect=AssertionError('unbounded header list')):
            row=self.ns['unpack_tar'](path,self.root/'tar-root',100,time.monotonic()+10,10)
        self.assertEqual(row['members'],3);self.assertEqual(row['expandedBytes'],5)
        self.assertEqual(os.readlink(self.root/'tar-root/bin/link'),'tool')

    def test_private_tar_rejects_member_population_and_extended_metadata_early(self):
        path=self.tar_fixture([('a',tarfile.REGTYPE,b'x',''),('b',tarfile.REGTYPE,b'x','')])
        with self.assertRaisesRegex((ValueError,RuntimeError),'population'):
            self.ns['unpack_tar'](path,self.root/'tar-partial',100,time.monotonic()+10,1)
        self.assertFalse((self.root/'tar-partial/b').exists())
        path=self.tar_fixture([('pax',tarfile.XHDTYPE,b'x'*1048577,'')])
        with self.assertRaisesRegex(RuntimeError,'metadata byte'):
            self.ns['unpack_tar'](path,self.root/'pax-refused',2097152,time.monotonic()+10,10)
        self.assertFalse((self.root/'pax-refused').exists())

    def archive_fixture(self, entries):
        path=self.root/'fixture.zip'
        if path.exists():path.unlink()
        rows=[]
        with zipfile.ZipFile(path,'w') as z:
            for name,mode,body in entries:
                i=zipfile.ZipInfo(name);i.create_system=3;i.external_attr=mode<<16;z.writestr(i,body)
                rows.append({'name':name,'mode':mode,'bytes':len(body),'link':body.decode() if stat.S_ISLNK(mode) else None})
        expected={'members':len(rows),'logicalBytes':sum(r['bytes'] for r in rows),'symlinks':sum(r['link'] is not None for r in rows),'layoutSha256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        # Explicit inert archive source adapter; production never learns this fixture as authority.
        self.ns['BROWSER_ARCHIVES']={'fixture':{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.ns['BROWSER_LAYOUTS']={'fixture':expected}
        return path,expected

    def test_private_extractor_preserves_relative_library_link_and_executable_mode(self):
        path,_=self.archive_fixture([('lib/',0o40755,b''),('lib/real.so',0o100644,b'library'),('lib/alias.so',0o120777,b'real.so'),('browser',0o100755,b'inert-no-execution')])
        root=self.root/'fresh';record=self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
        self.assertEqual(os.readlink(root/'lib/alias.so'),'real.so')
        self.assertEqual((root/'lib/alias.so').read_bytes(),b'library')
        self.assertEqual(stat.S_IMODE((root/'browser').stat().st_mode),0o755)
        self.assertEqual(record['state'],'extracted-data-not-registered-not-qualified')

    def test_private_extractor_refuses_traversal_special_duplicate_and_links_before_writes(self):
        cases=[
          [('../outside',0o100644,b'x')], [('/absolute',0o100644,b'x')],
          [('a//b',0o100644,b'x')], [('bad\\name',0o100644,b'x')],
          [('device',0o20644,b'')], [('setuid',0o104755,b'x')],
          [('dup',0o100644,b'a'),('dup',0o100644,b'b')],
          [('alias',0o120777,b'../outside')], [('alias',0o120777,b'missing')],
          [('alias',0o120777,b'real'),('alias/child',0o100644,b'x'),('real',0o100644,b'x')],
          [('a',0o120777,b'b'),('b',0o120777,b'a')]]
        for index,entries in enumerate(cases):
            with self.subTest(index=index):
                path,_=self.archive_fixture(entries);root=self.root/f'refused-{index}'
                with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
                self.assertFalse(root.exists())

    def test_private_extractor_refuses_changed_layout_and_raw_bytes(self):
        path,expected=self.archive_fixture([('inert',0o100644,b'x')])
        self.ns['BROWSER_LAYOUTS']['fixture']={**expected,'layoutSha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'layout differs'):self.ns['extract_browser_archive']('fixture',path,self.root/'bad-layout',time.monotonic()+10)
        self.assertFalse((self.root/'bad-layout').exists())
        self.ns['BROWSER_LAYOUTS']['fixture']=expected;path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,self.root/'bad-raw',time.monotonic()+10)
        self.assertFalse((self.root/'bad-raw').exists())

    def test_private_extractor_refuses_expired_original_deadline_and_existing_root(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')])
        with self.assertRaisesRegex(ValueError,'deadline'):self.ns['extract_browser_archive']('fixture',path,self.root/'expired',time.monotonic()-1)
        root=self.root/'occupied';root.mkdir()
        with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
        self.assertEqual(list(root.iterdir()),[])

    def test_private_extractor_refuses_filesystem_symlink_ancestor(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')])
        real=self.root/'real';real.mkdir();alias=self.root/'alias';alias.symlink_to(real,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ancestor'):self.ns['extract_browser_archive']('fixture',path,alias/'fresh',time.monotonic()+10)
        self.assertEqual(list(real.iterdir()),[])

    def test_private_extractor_retains_partial_data_and_refuses_late_terminal_read(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')]);clock=[1.0]
        original=zipfile.ZipFile.open
        class LateEof:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def read(self,n):
                result=self.stream.read(n)
                if not result:clock[0]=20.0
                return result
        def opened(source,*args,**kwargs):return LateEof(original(source,*args,**kwargs))
        root=self.root/'partial'
        with patch.object(self.ns['time'],'monotonic',lambda:clock[0]),patch.object(zipfile.ZipFile,'open',opened),self.assertRaisesRegex(ValueError,'deadline'):
            self.ns['extract_browser_archive']('fixture',path,root,10.0)
        self.assertEqual((root/'inert').read_bytes(),b'x')
        self.assertEqual(stat.S_IMODE((root/'inert').stat().st_mode),0o600)

    def test_private_layout_enforces_cardinality_byte_and_link_caps(self):
        path,expected=self.archive_fixture([('inert',0o100644,b'x')])
        for key,value in [('members',2),('logicalBytes',2),('symlinks',1)]:
            with self.subTest(key=key),zipfile.ZipFile(path) as z,self.assertRaises(ValueError):
                self.ns['inspect_browser_layout'](z,{**expected,key:value},time.monotonic()+10)

    def test_browser_archive_inputs_refuse_changed_raw_bytes_before_install(self):
        calls=[]
        def changed(name,url,expected,maximum):
            calls.append((url,expected,maximum));p=self.root/name;p.write_bytes(b'changed');return p
        with self.assertRaisesRegex(ValueError,'raw bytes differ'):self.ns['browser_archive_inputs'](changed)
        self.assertEqual(len(calls),1)
        self.assertNotIn('"install","chromium"',self.code)

    def test_release_build_precedes_browser_and_provisioned_is_not_qualified(self):
        self.assertLess(self.code.index('"--locked-mode"'),self.code.index('"Release"'))
        self.assertLess(self.code.index('"Release"'),self.code.index('browser_inputs=browser_archive_inputs(get)'))
        self.assertIn('provisioned-not-qualified',self.code)
        self.assertIn('observedAt',self.code)


    def test_public_url_rejects_authority_controls_before_transport(self):
        good=['https://api.nuget.org/test','https://api.nuget.org:443/test']
        for url in good:self.assertEqual(self.ns['public_url'](url),url)
        for url in ['https://api.nuget.org:444/test','https://api.nuget.org:/test','https://user@api.nuget.org/test','https://user:secret@api.nuget.org/test','https://api.nuget.org/%0aheader','https://api.nuget.org/test\n','https://api.nuget.org\\@other.invalid/test','https://api.nuget.org/test#fragment','https://api.nuget.org.evil.invalid/test']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.ns['public_url'](url)
    def test_per_hop_redirect_refuses_unselected_intermediate_before_open(self):
        request=self.ns['urllib'].request.Request('https://api.nuget.org/start')
        handler=self.ns['ClosedRedirect']();contacts=[]
        # Execute the actual inherited redirect flow; the fake opener records any next request.
        class Opener:
            def open(self,req,*args,**kwargs):contacts.append(req.full_url);return io.BytesIO(b'body')
        handler.parent=Opener()
        headers={'location':'https://unknown.invalid/then-back-to-allowed'}
        response=io.BytesIO(b'')
        with self.assertRaises(ValueError):handler.http_error_302(request,response,302,'found',headers)
        self.assertEqual(contacts,[])
    def test_per_hop_redirect_good_chain_cap_and_auth_refusal(self):
        request=self.ns['urllib'].request.Request('https://api.nuget.org/start')
        handler=self.ns['ClosedRedirect']()
        for i in range(5):
            request=handler.redirect_request(request,None,302,'found',{},'https://raw.githubusercontent.com/next'+str(i))
            self.assertEqual(request.get_method(),'GET')
            self.assertFalse(request.has_header('Authorization'))
        with self.assertRaisesRegex(ValueError,'hop cap'):handler.redirect_request(request,None,302,'found',{},'https://api.nuget.org/end')
        handler=self.ns['ClosedRedirect']();request=self.ns['urllib'].request.Request('https://api.nuget.org/start',headers={'Authorization':'secret'})
        with self.assertRaisesRegex(ValueError,'auth-free'):handler.redirect_request(request,None,302,'found',{},'https://api.nuget.org/end')
    def test_initial_origin_is_checked_before_opener_creation_and_proxy_disabled(self):
        with patch.object(self.ns['urllib'].request,'build_opener') as make:
            with self.assertRaises(ValueError):self.ns['open_public']('https://unknown.invalid/',10)
            make.assert_not_called()
            self.ns['open_public']('https://api.nuget.org/test',10)
            handlers=make.call_args.args
            self.assertEqual(handlers[0].proxies,{})
            self.assertIsInstance(handlers[1],self.ns['ClosedRedirect'])
    def test_new_actions_are_immutable_and_admission_not_assert_dependent(self):
        job=self.text.split('  wasm-installed-c:',1)[1]
        uses=re.findall(r'uses: ([^\s]+)',job)
        self.assertEqual(uses,['actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'])
        tree=ast.parse(self.code)
        self.assertFalse(any(isinstance(node,ast.Assert) for node in ast.walk(tree)))
        self.assertIn('sys.flags.optimize != 0',self.code)


    def test_original_acquisition_failure_survives_independent_report_failure(self):
        def fail(*args,**kwargs):raise RuntimeError('original acquisition failure')
        with patch.object(Path,'write_text',side_effect=OSError('report failure')):
            with self.assertRaisesRegex(RuntimeError,'original acquisition failure') as caught:
                self.ns['prepare_inputs'](self.root,self.root,{},fail,fail,time.monotonic()+10)
        self.assertTrue(any('independent download reporting failure' in note for note in caught.exception.__notes__))


    def test_stock_boundary_metadata_cannot_claim_universal_signal_safety(self):
        selected=self.ns['stock_boundary_metadata']()
        self.assertEqual(self.ns['validate_stock_boundary_metadata'](selected),selected)
        for key,value in [('chromiumSelection','sandbox-enabled'),('firefoxSelection','content-sandbox-disabled'),('canonicalSignalBoundary','all-transitive-signals-pidfd-safe'),('qualification','passed')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_stock_boundary_metadata']({**selected,key:value})
    def test_actual_stock_selection_preserves_weaker_chromium_and_enabled_firefox(self):
        env={'FSGG_WASM_FIREFOX_PROFILE':'content-sandbox-enabled'}
        argv={'chromium':['--headless','--no-sandbox','--remote-debugging-pipe','--no-startup-window','--user-data-dir=/owned/profile'],
              'firefox':['-no-remote','-headless','-profile','/owned/profile','-juggler-pipe','-silent'],
              'webkit':['--inspector-pipe','--headless','--no-startup-window']}
        for family,args in argv.items():self.assertEqual(self.ns['check_stock_launch_selection'](family,args,env)['fullCanonicalAdmission'],'pending')
        for key,value in [('MOZ_DISABLE_CONTENT_SANDBOX','1'),('PLAYWRIGHT_EXECUTABLE_PATH','/system/browser'),('PLAYWRIGHT_BROWSER_CHANNEL','chrome'),('NODE_OPTIONS','--require=/other'),('PW_TEST_CONNECT_WS_ENDPOINT','ws://other')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['check_stock_launch_selection']('chromium',argv['chromium'],{**env,key:value})
        with self.assertRaises(ValueError):self.ns['check_stock_launch_selection']('chromium',[a for a in argv['chromium'] if a!='--no-sandbox'],env)
    def test_actual_stock_source_guard_rejects_changed_config_and_launcher(self):
        template=self.root/'template.zip'
        self.package(template)
        with self.assertRaises((ValueError,KeyError)):self.ns['inspect_stock_sources'](template,self.root/'node_modules')
        template=self.root/'stock.zip';source_map=self.ns['STOCK_INPUTS'];npm_map=self.ns['STOCK_LAUNCHER_INPUTS']
        # Execute the actual final byte guard using inert declared source adapters; this
        # fixture proves rejection/fielding, never authentic stock/browser qualification.
        raw=b'fixture';digest=hashlib.sha256(raw).hexdigest()
        with zipfile.ZipFile(template,'w') as z:
            for name in source_map:z.writestr('content/templates/fs-gg-fable-game/'+name,raw)
        for name in npm_map:
            path=self.root/'node_modules'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.ns['STOCK_INPUTS']={name:digest for name in source_map}
        self.ns['STOCK_LAUNCHER_INPUTS']={name:digest for name in npm_map}
        observations=self.ns['inspect_stock_sources'](template,self.root/'node_modules');self.assertEqual(len(observations),7)
        (self.root/'node_modules'/next(iter(npm_map))).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'launcher source differs'):self.ns['inspect_stock_sources'](template,self.root/'node_modules')

    def registry_fixture(self, asset='chromium-headless1243', mode=0o755):
        name,directory,relative=self.ns['BROWSER_REGISTRY'][asset]
        registry=self.root/'browsers';registry.mkdir()
        staged=registry/('.staging-'+asset);staged.mkdir()
        executable=staged/relative;executable.parent.mkdir(parents=True,exist_ok=True);executable.write_bytes(b'inert executable bytes');executable.chmod(mode)
        archive=self.root/'browser.zip'
        with zipfile.ZipFile(archive,'w') as out:
            info=zipfile.ZipInfo(relative);info.external_attr=(stat.S_IFREG|mode)<<16
            out.writestr(info,executable.read_bytes())
        self.ns['BROWSER_ARCHIVES'][asset]={**self.ns['BROWSER_ARCHIVES'][asset],'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
        receipt={'asset':asset,'root':str(staged),'archiveSha256':self.ns['BROWSER_ARCHIVES'][asset]['sha256'],**self.ns['BROWSER_LAYOUTS'][asset],'state':'extracted-data-not-registered-not-qualified'}
        return asset,archive,receipt,registry,executable

    def test_actual_registry_mapping_and_extraction_marker_semantics(self):
        args=self.registry_fixture();result=self.ns['register_browser_archive'](*args[:4],time.monotonic()+10)
        self.assertEqual(Path(result['directory']).name,'chromium_headless_shell-1243')
        self.assertEqual(result['state'],'registered-installation-complete-host-validation-pending')
        self.assertEqual((Path(result['directory'])/'INSTALLATION_COMPLETE').read_bytes(),b'')
        self.assertFalse((Path(result['directory'])/'DEPENDENCIES_VALIDATED').exists())
        self.assertEqual(result['executableSha256'],hashlib.sha256(Path(result['executable']).read_bytes()).hexdigest())
        self.assertFalse(Path(args[2]['root']).exists())

    def test_registration_refuses_changed_executable_before_marker(self):
        args=self.registry_fixture();args[4].write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'bytes differ'):self.ns['register_browser_archive'](*args[:4],time.monotonic()+10)
        self.assertFalse((args[4].parents[1]/'INSTALLATION_COMPLETE').exists())

    def test_registration_refuses_nonexecutable_or_unsafe_mode(self):
        for mode in (0o644,0o777,0o4755):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                self.root=Path(temp);args=self.registry_fixture(mode=mode)
                with self.assertRaisesRegex(ValueError,'mode'):self.ns['register_browser_archive'](*args[:4],time.monotonic()+10)

    def test_registration_refuses_forged_dependency_and_install_markers(self):
        for marker in ('DEPENDENCIES_VALIDATED','INSTALLATION_COMPLETE'):
            with self.subTest(marker=marker),tempfile.TemporaryDirectory() as temp:
                self.root=Path(temp);args=self.registry_fixture();(Path(args[2]['root'])/marker).write_text('')
                with self.assertRaisesRegex(ValueError,'marker'):self.ns['register_browser_archive'](*args[:4],time.monotonic()+10)

    def test_registration_refuses_symlink_executable_or_expired_deadline(self):
        args=self.registry_fixture();args[4].unlink();args[4].symlink_to(self.root/'other')
        with self.assertRaisesRegex(ValueError,'symlink'):self.ns['register_browser_archive'](*args[:4],time.monotonic()+10)
        with self.assertRaisesRegex(ValueError,'deadline'):self.ns['register_browser_archive'](*args[:4],time.monotonic()-1)

    def validation_fixture(self):
        registrations=[]
        for asset,(name,directory,relative) in self.ns['BROWSER_REGISTRY'].items():
            tree=self.root/'browsers'/directory;tree.mkdir(parents=True)
            executable=tree/relative;executable.parent.mkdir(parents=True,exist_ok=True);executable.write_bytes(b'inert executable fixture')
            registrations.append({'asset':asset,'name':name,'directory':str(tree),'executable':str(tree/relative)})
        core=self.root/'npm-seed/Browser.Tests/node_modules/playwright-core/lib/coreBundle.js';core.parent.mkdir(parents=True);core.write_bytes(b'inert stock module')
        self.ns['STOCK_LAUNCHER_INPUTS']['playwright-core/lib/coreBundle.js']=hashlib.sha256(core.read_bytes()).hexdigest()
        metadata=core.parent.parent/'browsers.json';metadata.write_text(json.dumps({'browsers':[{'name':name,'revision':directory.rsplit('-',1)[1]} for name,directory,relative in self.ns['BROWSER_REGISTRY'].values()]}))
        self.ns['STOCK_LAUNCHER_INPUTS']['playwright-core/browsers.json']=hashlib.sha256(metadata.read_bytes()).hexdigest()
        return registrations

    def test_chromium_support_paths_use_both_selected_archive_directories(self):
        registrations=self.validation_fixture()
        self.assertEqual(self.ns['chromium_support_directories'](self.root,registrations),[
            str(self.root/'browsers/chromium-1243/chrome-linux64'),
            str(self.root/'browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64')])

    def test_chromium_support_path_refusals_precede_stock_execution(self):
        registrations=self.validation_fixture()
        def execute(*args):raise AssertionError('stock execution must remain blocked')
        for key,value in [('directory',str(self.root/'foreign')),('executable',str(self.root/'browsers/chromium-1243/chrome-linux/chrome')),('name','firefox')]:
            changed=copy.deepcopy(registrations);changed[0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'support selection'):
                self.ns['validate_registered_browsers'](self.root,{},changed,execute)
        executable=Path(registrations[0]['executable']);directory=executable.parent
        executable.unlink();directory.rmdir();directory.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'support directory'):
            self.ns['validate_registered_browsers'](self.root,{},registrations,execute)

    def test_chromium_support_refuses_missing_or_duplicate_registration(self):
        registrations=self.validation_fixture()
        for changed in (registrations[1:],registrations+[registrations[0]]):
            with self.subTest(count=len(changed)),self.assertRaisesRegex(ValueError,'missing/ambiguous'):
                self.ns['chromium_support_directories'](self.root,changed)

    def test_chromium_support_refuses_missing_or_symlink_executable(self):
        registrations=self.validation_fixture();executable=Path(registrations[1]['executable']);executable.unlink()
        with self.assertRaisesRegex(ValueError,'executable missing/nonregular'):
            self.ns['chromium_support_directories'](self.root,registrations)
        executable.symlink_to(Path(registrations[0]['executable']))
        with self.assertRaisesRegex(ValueError,'executable missing/nonregular'):
            self.ns['chromium_support_directories'](self.root,registrations)

    def test_host_validation_calls_stock_validator_without_install_or_forged_marker(self):
        registrations=self.validation_fixture();calls=[]
        def execute(argv,cwd,env):
            calls.append(argv);self.assertEqual(argv[1],str(self.root/'browser-host-validation.cjs'))
            self.assertFalse(any(ord(c)<32 for arg in argv for c in arg))
            script=Path(argv[1]).read_text();self.assertIn('validateHostRequirementsForExecutablesIfNeeded(actual',script)
            self.assertIn('require(process.argv[2]),expected=JSON.parse(process.argv[3])',script)
            self.assertNotIn('writeFile',script);self.assertNotIn('registry.install',script)
            return json.dumps({'platform':'ubuntu24.04-x64','names':[r['name'] for r in registrations],'state':'stock-host-validation-passed-runtime-pending'})
        result=self.ns['validate_registered_browsers'](self.root,{},registrations,execute)
        self.assertEqual(len(calls),1);self.assertEqual(result['chromiumSupport'],'pending-selected-archive-library-validation')
        self.assertEqual(result['chromiumSupportDirectories'],self.ns['chromium_support_directories'](self.root,registrations))
        self.assertEqual(result['runtime'],'not-run')
        self.assertFalse(any((Path(r['directory'])/'DEPENDENCIES_VALIDATED').exists() for r in registrations))

    def test_host_validation_refuses_skipped_or_cached_validation_before_execute(self):
        registrations=self.validation_fixture()
        def execute(*args):raise AssertionError('execute must remain blocked')
        for key in ('PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS','PLAYWRIGHT_HOST_PLATFORM_OVERRIDE','NODE_OPTIONS'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'override'):self.ns['validate_registered_browsers'](self.root,{key:'1'},registrations,execute)
        (Path(registrations[0]['directory'])/'DEPENDENCIES_VALIDATED').write_text('')
        with self.assertRaisesRegex(ValueError,'absent'):self.ns['validate_registered_browsers'](self.root,{},registrations,execute)

    def test_host_validation_failure_does_not_become_runtime_pass(self):
        registrations=self.validation_fixture()
        def execute(*args):raise RuntimeError('actual missing host dependency')
        with self.assertRaisesRegex(RuntimeError,'missing host dependency'):self.ns['validate_registered_browsers'](self.root,{},registrations,execute)
        with self.assertRaisesRegex(RuntimeError,'no provisioning, custody pilot or installed C admitted'):self.ns['main']()

    def test_source_only_pr_job_runs_controls_and_disables_runtime_and_upload(self):
        job=self.text.split('  wasm-installed-c:',1)[1]
        self.assertIn('name: WASM caller source preparation (runtime held)',job)
        steps=re.findall(r'^      - name: (.*?)\n(.*?)(?=^      - name: |\Z)',job,re.S|re.M)
        self.assertEqual([name for name,body in steps],['Check out exact reviewed Templates source','Qualify actual inline hosted input and budget controls','Prepare closed hosted WASM caller','Retain independent partial installed C evidence'])
        controls=steps[1][1]
        self.assertNotIn('        if:',controls)
        self.assertIn('python3 tests/composition/fable-game/test-fable-reference-public-preflight.py',controls)
        self.assertIn('bash -n tests/composition/fable-game/verify-fable-reference-public.sh',controls)
        for name,body in steps[2:]:
            with self.subTest(step=name):
                self.assertEqual(re.findall(r'^        if: (.*)$',body,re.M),['${{ false }}'])
        # The declared source boundary is closed: no additional executable step can
        # bypass either the static controls or the two literal runtime holds.
        self.assertEqual(len(steps),4)
        tree=ast.parse(self.code)
        # The inline refusal is a literal: RUNTIME_ADMITTED is assigned False exactly once and main's
        # first statement refuses on it before the bound sequence.
        held=[node for node in ast.walk(tree) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='RUNTIME_ADMITTED' for target in node.targets)]
        self.assertEqual(len(held),1);self.assertIs(held[0].value.value,False)
        self.assertFalse(any(isinstance(node,ast.Global) and 'RUNTIME_ADMITTED' in node.names for node in ast.walk(tree)))
        main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
        guard=main.body[0]
        self.assertIsInstance(guard,ast.If);self.assertEqual(ast.unparse(guard.test),'not RUNTIME_ADMITTED')
        self.assertEqual(len(guard.body),1);self.assertIsInstance(guard.body[0],ast.Raise)
        with patch.object(subprocess,'run',side_effect=AssertionError('runtime must stay held')),patch.object(subprocess,'Popen',side_effect=AssertionError('runtime must stay held')):
            with self.assertRaisesRegex(RuntimeError,'no provisioning, custody pilot or installed C admitted'):
                self.ns['main']()

class FakeRefused(RuntimeError):
    def __init__(self, code, receipt=None):
        super().__init__(code);self.code=code;self.receipt=receipt

class FakeGroupFailed(RuntimeError):
    def __init__(self, receipt):
        super().__init__(receipt['firstCause']);self.receipt=receipt

class FakeOwner:
    """Records exactly what the caller hands the contract; never launches anything."""
    Refused=FakeRefused;GroupFailed=FakeGroupFailed
    def __init__(self, outcome='succeeded', available=True, stdout=None):
        self.calls=[];self.outcome=outcome;self.available=available;self.stdout=stdout
    def probe(self):
        return {'schema':'fsgg.managed-group-contract/1','available':self.available,'refusal':None if self.available else 'delegated-root-invalid'}
    def run(self, profile, *, env, deadline, out_dir):
        self.calls.append({'profile':profile,'env':env,'deadline':deadline,'outDir':out_dir})
        os.mkdir(out_dir,0o700)
        receipt={'outcome':'succeeded','cleanup':'observed-empty-removed','custody':'contained','profileSha256':'f'*64,
                 'owner':{'sha256':'d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0'},'firstCause':None}
        if self.outcome=='refused':raise FakeRefused('executable-identity-mismatch',{**receipt,'outcome':'refused','firstCause':'Refused: executable-identity-mismatch'})
        if self.outcome=='failed':raise FakeGroupFailed({**receipt,'outcome':'failed','firstCause':'RuntimeError: leader exited with live contained members'})
        if self.outcome=='unclean':receipt['cleanup']='unknown'
        if self.outcome=='crash':raise OSError('unexpected owner failure')
        Path(out_dir,'stdout.log').write_text(self.stdout(profile) if self.stdout else 'stdout of '+profile['argv'][0])
        return receipt

class ManagedGroupBindingTests(unittest.TestCase):
    """Caller-side binding of fsgg.managed-group-contract/1 (C-J1); no tool, browser or network effect."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(os.path.realpath(self.temp.name))
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'binding_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        self.tool=self.root/'tool';self.tool.write_bytes(b'#!/bin/sh\nexit 0\n');self.tool.chmod(0o700)
        self.identities={};self.ns['bind_identity'](self.identities,str(self.tool),'verified-archive-member')

    def executor(self, owner, deadline=None, receipts=None, phase='setup'):
        receipts=[] if receipts is None else receipts
        return self.ns['managed_executor'](owner,self.root,deadline or time.monotonic()+60,self.identities,phase,receipts),receipts

    def test_owner_pin_is_the_exact_merged_supplier(self):
        owner=self.ns['OWNER']
        self.assertEqual(owner,{'repository':'FS-GG/FS.GG.Coordination','commit':'ac22206560f3eddfea524ce8f752ff1d0dfeec4e',
            'path':'eng/managed_group_owner.py','sha256':'d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0',
            'bytes':45315,'contract':'fsgg.managed-group-contract/1'})
        self.assertEqual(self.ns['public_url'](self.ns['OWNER_URL']),'https://raw.githubusercontent.com/FS-GG/FS.GG.Coordination/ac22206560f3eddfea524ce8f752ff1d0dfeec4e/eng/managed_group_owner.py')

    def fixture_acquire(self, body):
        def acquire(url,path,maximum,deadline,expected):
            self.assertEqual(url,self.ns['OWNER_URL']);path.write_bytes(body)
            return {'url':url,'bytes':len(body),'digest':hashlib.sha256(body).hexdigest()}
        return acquire

    def test_owner_digest_mismatch_refuses_before_import(self):
        marker=self.root/'imported'
        body=('open('+repr(str(marker))+',"w").close()\n').encode()
        with self.assertRaisesRegex(ValueError,'owner pin differs'):
            self.ns['load_owner'](self.root,time.monotonic()+10,self.fixture_acquire(body))
        self.assertFalse(marker.exists());self.assertFalse((self.root/'managed-owner.json').exists())

    def fixture_owner(self, schema):
        body=('import hashlib,os\nCONTRACT_SCHEMA='+repr(schema)+'\nOWNER_PATH=os.path.abspath(__file__)\n'
              'import pathlib\nOWNER_SHA256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()\n').encode()
        self.ns['OWNER']={**self.ns['OWNER'],'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
        return body

    def test_owner_import_binds_contract_and_self_hash(self):
        body=self.fixture_owner('fsgg.managed-group-contract/1')
        module=self.ns['load_owner'](self.root,time.monotonic()+10,self.fixture_acquire(body))
        self.assertEqual(module.OWNER_SHA256,self.ns['OWNER']['sha256'])
        self.assertEqual(stat.S_IMODE((self.root/'owner/managed_group_owner.py').stat().st_mode),0o400)
        self.assertFalse((self.root/'owner/__pycache__').exists())
        self.assertEqual(json.loads((self.root/'managed-owner.json').read_text())['commit'],'ac22206560f3eddfea524ce8f752ff1d0dfeec4e')
        with self.assertRaisesRegex(ValueError,'owner root occupied'):
            self.ns['load_owner'](self.root,time.monotonic()+10,self.fixture_acquire(body))

    def test_owner_import_refuses_another_contract(self):
        body=self.fixture_owner('fsgg.managed-group-contract/2')
        with self.assertRaisesRegex(ValueError,'imported managed-group owner identity differs'):
            self.ns['load_owner'](self.root,time.monotonic()+10,self.fixture_acquire(body))

    def environ(self):
        return {'EVENT':'pull_request','REPOSITORY':'FS-GG/FS.GG.Templates','HEAD_REPOSITORY':'FS-GG/FS.GG.Templates',
          'PR_HEAD':'a'*40,'CHECKOUT_HEAD':'a'*40,'WORKFLOW_REF':'FS-GG/FS.GG.Templates/.github/workflows/fable-reference-public.yml@refs/pull/1/merge',
          'WORKFLOW_SHA':'b'*40,'RUN_ID':'1','RUN_ATTEMPT':'1','GITHUB_WORKSPACE':str(self.root/'workspace'),'RUNNER_TEMP':str(self.root)}

    def test_unavailable_containment_refuses_before_provisioning_acquisition(self):
        owner=FakeOwner(available=False);loaded=[]
        def load(root,deadline):loaded.append(deadline);return owner
        def provision(*args,**kwargs):raise AssertionError('provisioning acquisition before containment probe')
        self.ns['load_owner']=load;self.ns['prepare_inputs']=provision
        with self.assertRaisesRegex(ValueError,'containment unavailable: delegated-root-invalid'):
            self.ns['hosted_sequence'](self.environ(),time.monotonic())
        job=self.root/'fable-wasm-installed-c'
        self.assertEqual(len(loaded),1);self.assertEqual(owner.calls,[])
        self.assertFalse(json.loads((job/'managed-owner-probe.json').read_text())['available'])
        self.assertEqual(sorted(p.name for p in job.iterdir()),['checker-http','checker-packages','evidence','home','managed-owner-probe.json','source.json','tmp'])

    def test_available_containment_hands_one_executor_and_setup_deadline_to_provisioning(self):
        owner=FakeOwner();seen=[]
        self.ns['load_owner']=lambda root,deadline:owner
        def provision(root,workspace,env,execute,acquire,deadline,identities):
            seen.append((root,workspace,deadline,identities,acquire));return 'provisioned'
        self.ns['prepare_inputs']=provision
        start=time.monotonic()
        self.assertEqual(self.ns['hosted_sequence'](self.environ(),start),'provisioned')
        root,workspace,deadline,identities,acquire=seen[0]
        self.assertEqual(root,self.root/'fable-wasm-installed-c');self.assertEqual(workspace,self.root/'workspace')
        self.assertLessEqual(deadline,start+self.ns['BUDGET']['setup']+1);self.assertEqual(identities,{})
        self.assertIs(acquire,self.ns['download'])

    def test_executor_builds_exact_contract_profile_and_returns_stdout(self):
        owner=FakeOwner();deadline=time.monotonic()+60
        execute,receipts=self.executor(owner,deadline)
        env={'PATH':'/usr/bin:/bin','HOME':str(self.root),'CI':'true'}
        self.assertEqual(execute([str(self.tool),'--version'],self.root,env),'stdout of '+str(self.tool))
        self.assertEqual(execute([str(self.tool),'--info'],self.root,env),'stdout of '+str(self.tool))
        first,second=owner.calls
        profile=first['profile']
        self.assertEqual(set(profile),{'schema','name','root','executable','leaderImages','argv','cwd','environmentKeys','containment','limits','retirement'})
        self.assertEqual(profile['schema'],'fsgg.managed-group-profile/1');self.assertEqual(profile['containment'],'cgroup2-delegated')
        self.assertRegex(profile['name'],r'^[a-z0-9][a-z0-9.-]{0,63}$')
        self.assertEqual(profile['root'],str(self.root));self.assertEqual(profile['cwd'],str(self.root))
        digest=hashlib.sha256(self.tool.read_bytes()).hexdigest()
        self.assertEqual(profile['executable'],{'path':str(self.tool),'sha256':digest});self.assertEqual(profile['leaderImages'],[digest])
        self.assertEqual(profile['argv'],[str(self.tool),'--version']);self.assertEqual(profile['environmentKeys'],['CI','HOME','PATH'])
        self.assertEqual(first['env'],env)
        self.assertEqual(profile['retirement'],{'onLeaderExit':'require-empty','leaderExitSettleSeconds':2,'termGraceSeconds':5,'cleanupSeconds':self.ns['BUDGET']['cleanup']})
        self.assertEqual(set(profile['limits']),{'pidsMax','memoryMaxBytes','stdoutBytes','stderrBytes'})
        # One original phase deadline for every group: no per-call renewal.
        self.assertEqual(first['deadline'],deadline);self.assertEqual(second['deadline'],deadline)
        self.assertNotEqual(first['outDir'],second['outDir'])
        for call in owner.calls:self.assertEqual(Path(call['outDir']).parent,self.root/'managed')
        index=json.loads((self.root/'managed-receipts.json').read_text())
        self.assertEqual([row['status'] for row in index],['succeeded','succeeded'])
        self.assertEqual(index[0]['identityBasis'],'verified-archive-member')

    def test_executor_resolves_symlinked_argv_to_bound_real_executable(self):
        alias=self.root/'alias';alias.symlink_to(self.tool)
        owner=FakeOwner();execute,_=self.executor(owner)
        execute([str(alias),'x'],self.root,{})
        profile=owner.calls[0]['profile']
        self.assertEqual(profile['executable']['path'],str(self.tool));self.assertEqual(profile['argv'],[str(alias),'x'])

    def test_executor_refuses_relative_or_unbound_executable_before_owner(self):
        owner=FakeOwner();execute,receipts=self.executor(owner)
        other=self.root/'other';other.write_bytes(b'x');other.chmod(0o700)
        for argv,message in [(['node','--version'],'must be absolute'),([str(other)],'identity not bound'),([],'exact argv')]:
            with self.subTest(argv=argv),self.assertRaisesRegex(ValueError,message):execute(argv,self.root,{})
        self.assertEqual(owner.calls,[]);self.assertEqual(receipts,[]);self.assertFalse((self.root/'managed-receipts.json').exists())

    def test_second_receipt_list_cannot_reuse_groups_or_overwrite_the_index(self):
        owner=FakeOwner();execute,receipts=self.executor(owner)
        execute([str(self.tool)],self.root,{})
        other,_=self.executor(owner,receipts=[],phase='setup')
        with self.assertRaisesRegex(ValueError,'sequence reused'):other([str(self.tool)],self.root,{})
        self.assertEqual(len(owner.calls),1)
        self.assertEqual(len(json.loads((self.root/'managed-receipts.json').read_text())),1)
        custody,_=self.executor(owner,receipts=receipts,phase='custody')
        custody([str(self.tool)],self.root,{})
        self.assertEqual([row['phase'] for row in json.loads((self.root/'managed-receipts.json').read_text())],['setup','custody'])

    def test_executor_retains_receipt_and_raises_first_cause(self):
        for outcome,message,status in [('refused','refused: executable-identity-mismatch','refused'),
                                        ('failed','failed: RuntimeError: leader exited with live contained members','failed'),
                                        ('unclean','receipt differs from contained success','succeeded')]:
            with self.subTest(outcome=outcome):
                shutil.rmtree(self.root/'managed',ignore_errors=True)
                owner=FakeOwner(outcome);execute,receipts=self.executor(owner)
                with self.assertRaisesRegex(RuntimeError,message) as caught:execute([str(self.tool)],self.root,{})
                self.assertEqual(receipts[-1]['status'],status)
                self.assertEqual(json.loads((self.root/'managed-receipts.json').read_text())[-1]['status'],status)
                if outcome!='unclean':self.assertIsInstance(caught.exception.__cause__,(FakeRefused,FakeGroupFailed))

    def test_unexpected_owner_exception_keeps_a_terminal_index_status(self):
        execute,receipts=self.executor(FakeOwner('crash'))
        with self.assertRaisesRegex(OSError,'unexpected owner failure'):execute([str(self.tool)],self.root,{})
        self.assertEqual(json.loads((self.root/'managed-receipts.json').read_text())[-1]['status'],'error')

    def test_bind_identity_refuses_symlink_drift_conflict_and_unknown_basis(self):
        alias=self.root/'alias';alias.symlink_to(self.tool)
        cases=[((str(alias),'host-observed'),{},'symlink-free'),
               ((str(self.tool),'verified-download'),{'expected':'0'*64},'bytes differ'),
               ((str(self.tool),'host-observed'),{},'conflicting'),
               ((str(self.tool),'trusted'),{},'unknown executable identity basis'),
               ((str(self.tool),'verified-archive-member'),{'images':[]},'leader images')]
        for args,kwargs,message in cases:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):
                self.ns['bind_identity'](self.identities,*args,**kwargs)

    def test_each_playwright_invocation_is_its_own_group(self):
        calls=[]
        def execute(argv,cwd,env):calls.append((argv,cwd,env));return '{}'
        tests=self.root/'Browser.Tests';node=self.root/'node'
        for family in ('chromium','firefox','webkit'):
            self.ns['managed_playwright'](execute,node,tests,family,{'CI':'true'},list_only=True)
            self.ns['managed_playwright'](execute,node,tests,family,{'CI':'true'})
        self.assertEqual(len(calls),6)
        self.assertEqual(calls[0][0],[str(node),str(tests/'node_modules/@playwright/test/cli.js'),'test','--config','wasm-public.generated.config.ts','--list','--reporter=json'])
        self.assertEqual(calls[1][0][-3:],['--workers=1','--retries=0','--max-failures=1'])
        self.assertEqual([env['PLAYWRIGHT_BROWSER_FAMILY'] for _,_,env in calls],['chromium','chromium','firefox','firefox','webkit','webkit'])
        with self.assertRaisesRegex(ValueError,'unselected browser family'):self.ns['managed_playwright'](execute,node,tests,'msedge',{})

    def test_provisioning_binds_identities_and_cwd_inside_profile_root(self):
        code=self.code
        self.assertIn('bind_identity(identities,str(rustup),"verified-download",expected=rust_digest)',code)
        self.assertIn('"installer-copy-of-verified-download",expected=rust_digest',code)
        self.assertIn('images=[shell_sha,node["sha256"]]',code)
        self.assertNotRegex(code,r'\],workspace,env\)')
        for bare in ('["node","--version"]','["npm","--version"]','["rustc","--version"]','["cargo","--version"]'):self.assertNotIn(bare,code)

    def test_receiver_targets_published_0191(self):
        self.assertEqual(self.ns['TEMPLATE_VERSION'],'0.19.1')
        self.assertEqual(self.ns['PUBLISHED'],'1e95dddb6326d276773154df1336599907d8dbfe')
        self.assertEqual(self.ns['PACKAGE_SHA'],'5d1886c37b6e6a0d64c3998ee23e76b4c5ba8b8a0c2136200c377d7bbab7d0c6')
        self.assertEqual(self.ns['DESCRIPTOR_SHA'],'10b532dacb0fba79c1c9dc666487f78903e1fd1a09fc757932f605a3f055f5f7')
        url,digest,_=self.ns['ENDPOINTS']['template']
        self.assertEqual(url,'https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.19.1/fs.gg.workspace.template.0.19.1.nupkg')
        self.assertEqual(digest,self.ns['PACKAGE_SHA'])
        self.assertIn('/'+self.ns['PUBLISHED']+'/providers/fable-game.providers.yml',self.ns['ENDPOINTS']['descriptor'][0])

    def test_hosted_step_runs_the_owner_in_a_fresh_delegated_unit_with_hard_limits(self):
        job=self.text.split('  wasm-installed-c:',1)[1]
        step=job.split('      - name: Prepare closed hosted WASM caller',1)[1].split("HOSTED_WASM",1)[0]
        self.assertEqual(re.findall(r'^        if: (.*)$',step,re.M),['${{ false }}'])
        for required in ('sudo -n systemd-run --quiet --wait --pipe --collect --service-type=exec','-p Delegate=yes','-p User="$(id -un)"',
                         '-p NoNewPrivileges=yes','-p KillMode=control-group','-p TimeoutStopSec=5','-p TasksMax=6144','-p MemoryMax=12G',
                         '-p RuntimeMaxSec=2400','--setenv=CHECKOUT_HEAD="$checkout_head"','-- /usr/bin/python3 -I - <<'):
            with self.subTest(required=required):self.assertIn(required,step)
        self.assertEqual(self.ns['BUDGET']['job'],2400)

    def test_binding_probe_job_is_non_required_and_provisions_nothing(self):
        probe=self.text.split('  managed-group-binding:',1)[1].split('  wasm-installed-c:',1)[0]
        self.assertIn('(non-required)',probe)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository",probe)
        self.assertEqual(re.findall(r'uses: ([^\s]+)',probe),['actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'])
        self.assertIn('--expect unavailable',probe);self.assertIn('--expect contained',probe)
        for absent in ('HOSTED_WASM','upload-artifact','prepare_inputs','playwright'):self.assertNotIn(absent,probe)
        self.assertIn('tests/composition/fable-game/managed-group-binding-probe.py',self.text.split('jobs:',1)[0])


OWNER_FILE=os.environ.get('FSGG_MANAGED_GROUP_OWNER')

@unittest.skipUnless(OWNER_FILE,'set FSGG_MANAGED_GROUP_OWNER to the pinned owner file to run real-contract refusals')
class RealOwnerBindingTests(unittest.TestCase):
    """The caller's profiles and refusals against the real pinned owner, where no unit is delegated."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(os.path.realpath(self.temp.name))
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'real_owner_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        source=Path(OWNER_FILE).read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),self.ns['OWNER']['sha256'])
        def copy(url,path,maximum,deadline,expected):
            path.write_bytes(source);return {'url':url,'bytes':len(source),'digest':hashlib.sha256(source).hexdigest()}
        self.owner=self.ns['load_owner'](self.root,time.monotonic()+10,copy)
        self.shell,_=self.ns['host_image']('/bin/sh')
        self.identities={};self.ns['bind_identity'](self.identities,self.shell,'host-observed')
        self.receipts=[]

    def test_caller_profile_is_valid_under_the_real_contract(self):
        captured=FakeOwner();execute=self.ns['managed_executor'](captured,self.root,time.monotonic()+60,self.identities,'setup',[])
        self.identities[self.shell]={**self.identities[self.shell],'leaderImages':[self.identities[self.shell]['sha256'],'e'*64]}
        execute(['/bin/sh','-c','true'],self.root,{'PATH':'/usr/bin:/bin'})
        profile,digest=self.owner.validate_profile(captured.calls[0]['profile'])
        self.assertRegex(digest,r'^[0-9a-f]{64}$');self.assertEqual(profile['retirement']['onLeaderExit'],'require-empty')

    def test_every_caller_argv_is_valid_under_the_real_contract(self):
        # Drive the actual call sites through the executor, then put each profile through the real schema.
        registrations=[]
        for asset,(name,directory,relative) in self.ns['BROWSER_REGISTRY'].items():
            tree=self.root/'browsers'/directory;tree.mkdir(parents=True)
            executable=tree/relative;executable.parent.mkdir(parents=True,exist_ok=True);executable.write_bytes(b'inert')
            registrations.append({'asset':asset,'name':name,'directory':str(tree),'executable':str(executable)})
        core=self.root/'npm-seed/Browser.Tests/node_modules/playwright-core/lib/coreBundle.js';core.parent.mkdir(parents=True);core.write_bytes(b'inert')
        self.ns['STOCK_LAUNCHER_INPUTS']['playwright-core/lib/coreBundle.js']=hashlib.sha256(b'inert').hexdigest()
        metadata=core.parent.parent/'browsers.json';metadata.write_text(json.dumps({'browsers':[{'name':n,'revision':d.rsplit('-',1)[1]} for n,d,_ in self.ns['BROWSER_REGISTRY'].values()]}))
        self.ns['STOCK_LAUNCHER_INPUTS']['playwright-core/browsers.json']=hashlib.sha256(metadata.read_bytes()).hexdigest()
        tools=self.root/'tools';toolchain=self.ns['rust_toolchain_bin'](self.root)
        node=tools/('node-archive/node-v'+self.ns['TOOLS']['node']+'-linux-x64/bin/node')
        wasi=tools/'wasi/wasi-sdk-34.0-x86_64-linux'
        paths=[node,tools/'bin/npm',toolchain/'rustc',toolchain/'cargo',tools/'cargo/bin/rustup',tools/'dotnet/dotnet',wasi/'bin/clang']
        for path in paths:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'#!/bin/sh\n');path.chmod(0o700)
            self.ns['bind_identity'](self.identities,str(path),'verified-archive-member')
        accepted={'platform':'ubuntu24.04-x64','names':[r['name'] for r in registrations],'state':'stock-host-validation-passed-runtime-pending'}
        captured=FakeOwner(stdout=lambda profile:json.dumps(accepted) if str(core) in profile['argv'] else '')
        execute=self.ns['managed_executor'](captured,self.root,time.monotonic()+60,self.identities,'setup',self.receipts)
        env={'PATH':'/usr/bin:/bin','FSGG_WASM_FIREFOX_PROFILE':'content-sandbox-enabled','DOTNET_HOST_PATH':str(tools/'dotnet/dotnet'),
             'FSGG_WASM_FABLE_CORE':str(self.root/'fable.dll'),'FSGG_WASM_WASI_ROOT':str(wasi)}
        self.ns['validate_registered_browsers'](self.root,env,registrations,execute)
        with self.assertRaises(ValueError):self.ns['qualify_tools'](self.root,env,execute)
        for family in ('chromium','firefox','webkit'):
            self.ns['managed_playwright'](execute,node,self.root,family,env,list_only=True)
        self.assertGreaterEqual(len(captured.calls),10)
        for call in captured.calls:
            with self.subTest(argv=call['profile']['argv'][:2]):self.owner.validate_profile(call['profile'])

    def run_refused(self, deadline, code):
        receipts=self.receipts
        execute=self.ns['managed_executor'](self.owner,self.root,deadline,self.identities,'setup',receipts)
        with self.assertRaisesRegex(RuntimeError,'refused: '+code):execute(['/bin/sh','-c','echo launched'],self.root,{'PATH':'/usr/bin:/bin'})
        receipt=json.loads((Path(receipts[-1]['outDir'])/'receipt.json').read_text())
        self.assertEqual(receipt['launch'],{'attempted':False,'launched':False,'error':None})
        self.assertEqual(receipt['owner']['sha256'],self.ns['OWNER']['sha256']);self.assertEqual(receipt['refusal'],code)

    def test_real_contract_refusals_precede_any_launch(self):
        self.run_refused(time.monotonic()-1,'deadline-exhausted')
        self.identities[self.shell]={**self.identities[self.shell],'sha256':'0'*64}
        self.run_refused(time.monotonic()+60,'executable-identity-mismatch')

    def test_real_probe_without_delegated_unit_refuses_containment(self):
        if self.owner.probe()['available']:self.skipTest('this host delegates a cgroup; the hosted unit probe covers containment')
        with self.assertRaisesRegex(ValueError,'containment unavailable'):self.ns['probe_containment'](self.owner,self.root)
        self.run_refused(time.monotonic()+60,'containment-unavailable')


if __name__ == '__main__': unittest.main()
