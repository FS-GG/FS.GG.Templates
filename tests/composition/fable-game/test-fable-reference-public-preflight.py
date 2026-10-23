#!/usr/bin/env python3
"""Synthetic input controls; preflight cannot install, build or query a feed."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import ast
import importlib.util
import base64
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
        return ['--mode', 'wasm', '--template-version', '0.19.3', '--sha256', 'a'*64,
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

    # Current public cohorts (FS-GG/.github#4709): Workspace + SDD 2.4.0 + Wizard 0.21.0. CURRENT is the
    # accepted historical 0.19.2 cohort; CURRENT193 is the current public 0.19.3 cohort (published bytes).
    CURRENT = {'--sha256': 'ef5c5c2fb2de372a427c5abaf8bb4cdf91d7776b5628f07c016d4eb9ac87469a',
               '--descriptor-sha256': 'e8dbf8958f90d522e577378ae36b0e131954e400991d542ae9709ac32c713e3b',
               '--source-revision': 'd15f085ff4d64b7736e09ff263644b3c86a576a6',
               '--tag-revision': 'd15f085ff4d64b7736e09ff263644b3c86a576a6',
               '--sdd-sha256': '1df2e74faebd388f90b813ed9d7497f4247f977718469c9247b37111d791921f',
               '--sdd-source-revision': 'c1fee66a34ec8d222586eb708ddff4973ad5594e',
               '--wizard-sha256': '4326f57dc41ab3feaf6b7b693dcdc2867e818b0567af27da505b571aace4e190',
               '--wizard-source-revision': '12480a2083a00e0ccc91f3e0f3111d56108d755c'}
    CURRENT193 = {**CURRENT, '--sha256': '9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2',
               '--descriptor-sha256': '6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006',
               '--source-revision': '7be0bcf5886d39a8161b186beb8cc06e82415f1e',
               '--tag-revision': '7be0bcf5886d39a8161b186beb8cc06e82415f1e'}
    def current_args(self, mode='full', version='0.19.2', identities=None):
        c = identities or (self.CURRENT193 if version == '0.19.3' else self.CURRENT)
        args = ['--mode', mode, '--template-version', version, '--sha256', c['--sha256'],
                '--descriptor-sha256', c['--descriptor-sha256'], '--source-revision', c['--source-revision'],
                '--tag-revision', c['--tag-revision'], '--sdd-version', '2.4.0', '--sdd-sha256', c['--sdd-sha256'],
                '--sdd-source-revision', c['--sdd-source-revision'], '--evidence-dir', str(self.root/'fresh'), '--preflight-only']
        if mode == 'full': args += ['--wizard-version', '0.21.0', '--wizard-sha256', c['--wizard-sha256'], '--wizard-source-revision', c['--wizard-source-revision']]
        return args
    def test_current_public_full_cohort_accepted(self): self.run_preflight(self.current_args(), True)
    def test_current_public_templates_cohort_accepted(self): self.run_preflight(self.current_args('templates'), True)
    def test_current_public_identity_mutations_refused(self):
        base = self.current_args()
        for flag in self.CURRENT:
            for index, value in enumerate(base):
                if value == flag:
                    mutated = list(base); old = mutated[index+1]
                    mutated[index+1] = ('0' if old[0] != '0' else '1') + old[1:]
                    if flag == '--source-revision':
                        tag = mutated.index('--tag-revision'); mutated[tag+1] = mutated[index+1]
                    with self.subTest(flag=flag): self.run_preflight(mutated, False)
    def test_current_public_0193_cohort_accepted(self):
        for mode in ('full', 'templates'):
            with self.subTest(mode=mode): self.run_preflight(self.current_args(mode, '0.19.3'), True)
    def test_current_public_0193_identity_mutations_refused(self):
        base = self.current_args('full', '0.19.3')
        for flag in ('--sha256', '--descriptor-sha256', '--source-revision'):
            mutated = list(base); index = mutated.index(flag); old = mutated[index+1]
            mutated[index+1] = ('0' if old[0] != '0' else '1') + old[1:]
            if flag == '--source-revision': mutated[mutated.index('--tag-revision')+1] = mutated[index+1]
            with self.subTest(flag=flag): self.run_preflight(mutated, False)
    def test_current_public_cohort_identities_cannot_stand_in_for_each_other(self):
        # Each version binds its own published bytes: 0.19.2 identities cannot claim 0.19.3, nor the reverse.
        for mode in ('full', 'templates'):
            with self.subTest(mode=mode, claim='0.19.3'): self.run_preflight(self.current_args(mode, '0.19.3', self.CURRENT), False)
            with self.subTest(mode=mode, claim='0.19.2'): self.run_preflight(self.current_args(mode, '0.19.2', self.CURRENT193), False)
        text = (HERE/'verify-fable-reference-public.sh').read_text()
        rows = {'current_template_shas': ('ef5c5c2fb2de372a427c5abaf8bb4cdf91d7776b5628f07c016d4eb9ac87469a', '9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2'),
                'current_template_revisions': ('d15f085ff4d64b7736e09ff263644b3c86a576a6', '7be0bcf5886d39a8161b186beb8cc06e82415f1e'),
                'current_descriptor_shas': ('e8dbf8958f90d522e577378ae36b0e131954e400991d542ae9709ac32c713e3b', '6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006')}
        for table, (v192, v193) in rows.items():
            with self.subTest(table=table):
                self.assertIn('declare -A %s=([0.19.2]=%s [0.19.3]=%s)' % (table, v192, v193), text)
    def test_current_public_runtime_branches_key_on_cohort_membership(self):
        # The overlay/Wizard-hive, typed/public-default Wizard and public-default runtime branches apply to
        # every current-public cohort; none is keyed on a literal version any more.
        text = (HERE/'verify-fable-reference-public.sh').read_text()
        self.assertEqual(text.count('\nif [[ "$current_public" == true ]]; then\n'), 2)
        self.assertEqual(text.count('\nif [[ "$mode" == full && "$current_public" == true ]]; then\n'), 1)
        self.assertNotRegex(text, r'"\$version" == 0\.19\.[23] *\]\]; then')
    def test_current_public_cross_cohort_refused(self):
        for old, new in (('2.4.0', '2.1.0'), ('0.21.0', '0.16.0'), ('0.21.0', '0.20.0'), ('0.19.2', '0.19.1')):
            with self.subTest(old=old, new=new): self.run_preflight([a.replace(old, new) if a == old else a for a in self.current_args()], False)
        historical = [a.replace('0.16.0', '0.21.0') if a == '0.16.0' else a for a in self.args('full')]
        self.run_preflight(historical, False)
    def test_wasm_direct_preflight_has_no_sdd_wizard_or_runtime_effect(self): self.run_preflight(self.wasm_args(), True)
    def test_wasm_requires_closed_successor(self): self.run_preflight([a.replace('0.19.3','0.18.1') for a in self.wasm_args()], False)
    def test_wasm_refuses_superseded_0190_with_truncated_guest(self): self.run_preflight([a.replace('0.19.3','0.19.0') for a in self.wasm_args()], False)
    def test_wasm_refuses_superseded_0191(self): self.run_preflight([a.replace('0.19.3','0.19.1') for a in self.wasm_args()], False)
    def test_wasm_refuses_0192_with_the_0_3_0_receiver(self): self.run_preflight([a.replace('0.19.3','0.19.2') for a in self.wasm_args()], False)
    def test_historical_route_cannot_claim_successor(self):
        for successor in ('0.19.0','0.19.1','0.19.2','0.19.3'):
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
        argv=self.ns['fixed_checker_argv'](self.root,self.root/'installed','/usr/bin/bash')
        self.assertEqual(argv[0],'/usr/bin/bash')
        self.assertIn('wasm',argv);self.assertIn('0.19.3',argv);self.assertNotIn('0.19.2',argv);self.assertNotIn('0.19.1',argv)
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
        body=ast.get_source_segment(self.code,next(n for n in ast.parse(self.code).body if isinstance(n,ast.FunctionDef) and n.name=='prepare_inputs'))
        self.assertLess(body.index('provider_tool_restore_argv(dotnet,project,config)'),body.index('provider_tool_build_argv(dotnet,project)'))
        self.assertLess(body.index('provider_tool_build_argv(dotnet,project)'),body.index('register_browsers(root,downloads,seed,env,execute,get,deadline)'))
        self.assertIn('browser_inputs=browser_archive_inputs(get)',self.code)
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
        def execute(argv,cwd,env,inputs=()):
            calls.append(argv);self.assertEqual(list(map(str,inputs)),[argv[1]])
            self.assertRegex(argv[1],r'/browser-host-validation\.[0-9a-f]{64}\.cjs$')
            self.assertEqual(Path(argv[1]).name.split('.')[1],hashlib.sha256(Path(argv[1]).read_bytes()).hexdigest())
            self.assertEqual(stat.S_IMODE(Path(argv[1]).stat().st_mode),0o400)
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
        def execute(*args,**kwargs):raise RuntimeError('actual missing host dependency')
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
    def __init__(self, outcome='succeeded', available=True, stdout=None, validate=None, cgroup=None, events=None, fail_on=None):
        self.calls=[];self.outcome=outcome;self.available=available;self.stdout=stdout;self.envs={};self.validate=validate
        self.cgroup=cgroup;self.events=events or {} # (delegated root, leaf) fixture dirs; event -> mutation before the hook
        self.fail_on=fail_on # profile -> outcome override for that one call, or None
    def env_of(self, profile):
        return self.envs[id(profile)]
    def probe(self):
        return {'schema':'fsgg.managed-group-contract/1','available':self.available,'refusal':None if self.available else 'delegated-root-invalid'}
    def hooks(self, control):
        # The real owner's public hook events, in order; a raising hook is a group failure there too.
        if control is None:return
        context={'delegatedRoot':str(self.cgroup[0]) if self.cgroup else None,'leaf':str(self.cgroup[1]) if self.cgroup else None}
        for event in ('after-birth','poll','before-retire','before-remove','after-cleanup'):
            if event in self.events:self.events[event]()
            try:control(event,dict(context))
            except Exception as error:raise FakeGroupFailed({'outcome':'failed','cleanup':'observed-empty-removed','custody':'contained','firstCause':'hook:'+type(error).__name__})
    def run(self, profile, *, env, deadline, out_dir, control=None):
        if self.validate:self.validate(profile) # the real schema, at the moment of each run
        self.calls.append({'profile':profile,'env':env,'deadline':deadline,'outDir':out_dir})
        outcome=(self.fail_on(profile) if self.fail_on else None) or self.outcome
        if outcome not in ('refused','crash'):self.hooks(control) # the real owner refuses before any launch or hook
        self.envs[id(profile)]=env
        os.mkdir(out_dir,0o700)
        receipt={'outcome':'succeeded','cleanup':'observed-empty-removed','custody':'contained','profileSha256':'f'*64,
                 'owner':{'sha256':'d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0'},'firstCause':None}
        if outcome=='refused':raise FakeRefused('executable-identity-mismatch',{**receipt,'outcome':'refused','firstCause':'Refused: executable-identity-mismatch'})
        if outcome=='failed':raise FakeGroupFailed({**receipt,'outcome':'failed','firstCause':'RuntimeError: leader exited with live contained members'})
        if outcome=='unclean':receipt['cleanup']='unknown'
        if outcome=='crash':raise OSError('unexpected owner failure')
        Path(out_dir,'stdout.log').write_text(self.stdout(profile) if self.stdout else 'stdout of '+profile['argv'][0])
        return receipt

def _tar(path, members):
    with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as out:
        for name,body in members:
            info=tarfile.TarInfo(name);info.mode=0o755;info.size=len(body);out.addfile(info,io.BytesIO(body))

def _browser_zip(path, relative):
    body=b'inert browser executable fixture'
    with zipfile.ZipFile(path,'w') as z:
        info=zipfile.ZipInfo(relative);info.create_system=3;info.external_attr=(stat.S_IFREG|0o755)<<16;z.writestr(info,body)
    rows=[{'name':relative,'mode':stat.S_IFREG|0o755,'bytes':len(body),'link':None}]
    layout={'members':1,'logicalBytes':len(body),'symlinks':0,'layoutSha256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    return {'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},layout

def fixture_world(ns, base, owner):
    """Run the actual provisioning sequence, tool qualification and installed C on inert fixtures.

    Every process the caller would start goes through managed_executor into ``owner`` (a FakeOwner),
    whose stdout callback plays the tools. Nothing is downloaded or executed."""
    root=base/'job';workspace=base/'workspace';fixtures=base/'fixtures';fixtures.mkdir()
    checker=workspace/'tests/composition/fable-game/verify-fable-reference-public.sh';checker.parent.mkdir(parents=True)
    checker.write_bytes((HERE/'verify-fable-reference-public.sh').read_bytes())
    env=ns['fresh_environment'](root,{})
    tools=root/'tools';T=ns['TOOLS'];node_name='node-v'+T['node']+'-linux-x64'
    # Template archive: seed locks plus the stock template inputs, with fixture digests admitted.
    template=fixtures/'template.zip';stock={}
    with zipfile.ZipFile(template,'w') as z:
        for role,key,version in [('Client','vite','7.3.6'),('Browser.Tests','@playwright/test',T['playwright'])]:
            prefix='content/templates/fs-gg-fable-game/'+role+'/'
            lock=json.dumps({'packages':{'':{'devDependencies':{key:version}},'node_modules/'+key:{'resolved':'https://registry.npmjs.org/x/-/x.tgz','integrity':'sha512-abc'}}}).encode()
            z.writestr(prefix+'package.json','{}');z.writestr(prefix+'package-lock.json',lock)
            if role=='Browser.Tests':stock['Browser.Tests/package-lock.json']=hashlib.sha256(lock).hexdigest()
        for name in ('Browser.Tests/playwright.config.ts','SvgFoundation/vite.config.js'):
            z.writestr('content/templates/fs-gg-fable-game/'+name,name);stock[name]=hashlib.sha256(name.encode()).hexdigest()
    ns['STOCK_INPUTS']=stock
    files={'template':template.read_bytes(),'descriptor':b'descriptor','guest':b'guest'}
    _tar(fixtures/'wasi.tgz',[('wasi-sdk-34.0-x86_64-linux/bin/clang',b'#!/bin/sh\n')]);files['wasi']=(fixtures/'wasi.tgz').read_bytes()
    files['dotnet-releases.json']=json.dumps({'releases':[{'sdks':[{'version':T['sdk'],'files':[{'rid':'linux-x64','name':'dotnet-sdk-linux-x64.tar.gz','url':'https://builds.dotnet.microsoft.com/dotnet/sdk.tar.gz','hash':'ab'*64}]}]}]}).encode()
    _tar(fixtures/'dotnet.tgz',[('dotnet',b'#!/bin/sh\n# dotnet\n')]);files['dotnet.tar.gz']=(fixtures/'dotnet.tgz').read_bytes()
    files['node-SHASUMS256.txt']=('a'*64+'  '+node_name+'.tar.gz\n').encode()
    _tar(fixtures/'node.tgz',[(node_name+'/bin/node',b'#!/bin/sh\n# node\n')]);files['node.tar.gz']=(fixtures/'node.tgz').read_bytes()
    files['npm-metadata.json']=json.dumps({'name':'npm','version':T['npm'],'dist':{'tarball':'https://registry.npmjs.org/npm/-/npm-'+T['npm']+'.tgz','integrity':'sha512-'+base64.b64encode(b'x'*64).decode()}}).encode()
    _tar(fixtures/'npm.tgz',[('package/bin/npm-cli.js',b'// npm')]);files['npm.tgz']=(fixtures/'npm.tgz').read_bytes()
    rustup=b'#!/bin/sh\n# rustup-init fixture\n';files['rustup-init']=rustup
    files['rustup-init.sha256']=(hashlib.sha256(rustup).hexdigest()+'  rustup-init\n').encode()
    for asset,(name,directory,relative) in ns['BROWSER_REGISTRY'].items():
        identity,layout=_browser_zip(fixtures/(asset+'.zip'),relative)
        ns['BROWSER_ARCHIVES'][asset]={**ns['BROWSER_ARCHIVES'][asset],**identity};ns['BROWSER_LAYOUTS'][asset]=layout
        files[asset+'.zip']=(fixtures/(asset+'.zip')).read_bytes()
    def acquire(url,path,maximum,deadline,expected,algorithm='sha256'):
        path.write_bytes(files[path.name]);return {'url':url,'bytes':path.stat().st_size,'digest':'fixture','observedAt':0}
    fable=b'fable entrypoint fixture';ns['FABLE_SHA']=hashlib.sha256(fable).hexdigest()
    seed_core=root/'npm-seed/Browser.Tests/node_modules'
    webkit=ns.get('PILOT_WEBKIT_PACKAGES') or []
    core=('const deps = {\n      "ubuntu24.04-x64": {\n        tools: ["xvfb"],\n        webkit: [\n'+',\n'.join('          '+json.dumps(x) for x in webkit+webkit[:1])+'\n        ],\n        lib2package: {}\n      }\n};\n').encode()
    launcher={'playwright-core/lib/coreBundle.js':core,'playwright/lib/runner/index.js':b'runner','playwright/lib/index.js':b'index',
              'playwright-core/browsers.json':json.dumps({'browsers':[{'name':n,'revision':d.rsplit('-',1)[1]} for n,d,_ in ns['BROWSER_REGISTRY'].values()]}).encode()}
    ns['STOCK_LAUNCHER_INPUTS']={k:hashlib.sha256(v).hexdigest() for k,v in launcher.items()}
    installed=root/'installed';results=installed/'browser'
    def report_for(family,stats=False):
        tests=[{'projectName':family,'projectId':family} for _ in range(9)]
        value={'config':{'projects':[{'name':family}]},'suites':[{'specs':[{'tests':tests}],'suites':[]}]}
        if stats:value['stats']={'expected':9,'unexpected':0,'flaky':0,'skipped':0}
        return value
    outputs={'--version':{'dotnet':T['sdk'],'node':'v'+T['node'],'npm':T['npm'],'rustc':'rustc 1.90.0 (1159e78c4 2025-09-14)','cargo':'cargo 1.90.0 (840b83a10 2025-07-30)','dll':'fable'}}
    def play(profile):
        argv=profile['argv'];exe=Path(argv[0]).name;cwd=Path(profile['cwd'])
        root=Path(profile['root']);tools=root/'tools' # the run's own root, not the world default
        if exe=='systemctl':
            return 'TasksMax=6144\nMemoryMax=12884901888\nRuntimeMaxUSec=40min\nDelegate=yes\nNoNewPrivileges=yes\nKillMode=control-group\nTimeoutStopUSec=5s\nUser=runner\n'
        if exe=='rustup-init':
            target=tools/'cargo/bin/rustup';target.parent.mkdir(parents=True);target.write_bytes(rustup);target.chmod(0o700)
        elif argv[1:3]==['target','add']:
            for name in ('rustc','cargo'):
                target=ns['rust_toolchain_bin'](root)/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'#!/bin/sh\n');target.chmod(0o700)
        elif argv[1:3]==['target','list']:return 'wasm32-unknown-unknown\n'
        elif argv[1:3]==['tool','install']:
            (tools/'fable').mkdir();(tools/'fable/fable.dll').write_bytes(fable)
            (tools/'fable/fable.nuspec').write_text('<package><metadata><id>fable</id><version>'+T['fable']+'</version></metadata></package>')
        elif len(argv)>1 and argv[1]=='build':
            output=workspace/'src/FS.GG.Templates.ProviderTool/bin/Release/net10.0/FS.GG.Templates.ProviderTool.dll';output.parent.mkdir(parents=True);output.write_bytes(b'dll')
        elif len(argv)>1 and argv[1]=='ci' and cwd.name=='Browser.Tests':
            for name,body in launcher.items():
                target=cwd/'node_modules'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
        elif len(argv)>1 and argv[1]=='--list-runtimes':return 'Microsoft.NETCore.App '+T['runtime']+' [/fixture]\n'
        elif exe=='clang':return 'clang version 23.1.0-wasi-sdk (https://github.com/llvm/llvm-project 895aa2c896ada719451be2e3673c83da8ddf1141)\n'
        elif argv[-1]=='--version':return outputs['--version']['dll' if argv[-2].endswith('.dll') else exe]
        elif 'browser-host-validation' in ' '.join(argv):
            return json.dumps({'platform':'ubuntu24.04-x64','names':[n for n,_,_ in ns['BROWSER_REGISTRY'].values()],'state':'stock-host-validation-passed-runtime-pending'})
        elif exe=='verify-fable-reference-public.sh' or (len(argv)>1 and argv[1].endswith('verify-fable-reference-public.sh')):
            evidence=Path(argv[argv.index('--evidence-dir')+1])
            # The real shell refuses unless the evidence dir is 0700 and holds only qualification.json.
            if stat.S_IMODE(evidence.stat().st_mode)!=0o700 or sorted(os.listdir(evidence))!=['qualification.json']:
                raise RuntimeError('checker usage: evidence dir must be 0700 with only qualification.json')
            (evidence/'direct/Browser.Tests').mkdir(parents=True)
        elif len(argv)>2 and argv[2]=='test':
            family=owner.env_of(profile)['PLAYWRIGHT_BROWSER_FAMILY']
            if '--list' in argv:return json.dumps(report_for(family))
            (Path(owner.env_of(profile)['FSGG_WASM_RESULTS'])/family/'report.json').write_text(json.dumps(report_for(family,True)))
        return ''
    return {'root':root,'workspace':workspace,'env':env,'acquire':acquire,'play':play,'installed':installed,'results':results}

def drive_every_call_site(ns, base, owner):
    """Run the actual provisioning sequence, tool qualification and installed C on inert fixtures."""
    world=fixture_world(ns,base,owner)
    root,workspace,env,acquire,play=world['root'],world['workspace'],world['env'],world['acquire'],world['play']
    owner.stdout=play
    identities={};receipts=[]
    setup=ns['managed_executor'](owner,root,time.monotonic()+600,identities,'setup',receipts)
    provisioned=ns['prepare_inputs'](root,workspace,env,setup,acquire,time.monotonic()+600,identities)
    ns['qualify_tools'](root,env,setup)
    installed_run=ns['managed_executor'](owner,root,time.monotonic()+600,identities,'installed',receipts)
    summary=ns['installed_c'](root,workspace,env,installed_run,identities,provisioned['node'])
    return root,receipts,summary

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
            seen.append((root,workspace,deadline,identities,acquire));return {'node':'/node'}
        def installed(*args,**kwargs):raise AssertionError('installed C ran past the custody gate')
        self.ns['prepare_inputs']=provision;self.ns['installed_c']=installed;self.ns['qualify_tools']=lambda root,env,execute:None
        start=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'custody pilot remain unadmitted; installed C held'):
            self.ns['hosted_sequence'](self.environ(),start)
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

    def test_unexpected_owner_exception_keeps_the_first_report_note(self):
        (self.root/'managed-receipts.json').mkdir() # every index write fails
        execute,receipts=self.executor(FakeOwner('crash'))
        with self.assertRaisesRegex(OSError,'unexpected owner failure') as caught:execute([str(self.tool)],self.root,{})
        notes=[n for n in caught.exception.__notes__ if 'independent managed receipt reporting failure' in n]
        self.assertEqual(len(notes),2) # the index write before run and the one after

    def test_every_call_site_is_one_bounded_group_and_each_playwright_invocation_its_own(self):
        owner=FakeOwner()
        root,receipts,summary=drive_every_call_site(self.ns,self.root,owner)
        self.assertEqual(summary['disposition'],'passed')
        self.assertEqual([r['phase'] for r in receipts],['setup']*18+['installed']*7)
        self.assertEqual([r['status'] for r in receipts],['succeeded']*25)
        identities=set()
        for call in owner.calls:
            profile=call['profile']
            with self.subTest(argv=profile['argv'][:3]):
                self.assertTrue(Path(profile['argv'][0]).is_absolute())
                self.assertFalse(any(ord(c)<32 or ord(c)==127 for arg in profile['argv'] for c in arg))
                self.assertTrue(profile['cwd']==str(root) or profile['cwd'].startswith(str(root)+'/'))
                self.assertEqual(profile['retirement']['onLeaderExit'],'require-empty')
                self.assertEqual(profile['environmentKeys'],sorted(call['env']))
                identities.add(profile['executable']['path'])
        self.assertEqual(len({call['outDir'] for call in owner.calls}),25)
        playwright=[call for call in owner.calls if len(call['profile']['argv'])>2 and call['profile']['argv'][2]=='test']
        self.assertEqual([(call['env']['PLAYWRIGHT_BROWSER_FAMILY'],'--list' in call['profile']['argv']) for call in playwright],
            [('chromium',True),('firefox',True),('webkit',True),('chromium',False),('firefox',False),('webkit',False)])
        for call in playwright:
            self.assertEqual(call['env']['FSGG_WASM_RESULTS'],str(root/'installed/browser'))
            self.assertEqual((call['env']['FsGgWasmPolicyExample'],call['env']['FSGG_WASM_POLICY_EXAMPLE']),('true','true'))
            self.assertEqual(call['env']['FSGG_WASM_FIREFOX_PROFILE'],'content-sandbox-enabled')
            self.assertNotIn('PLAYWRIGHT_EXECUTABLE_PATH',call['env']);self.assertNotIn('MOZ_DISABLE_CONTENT_SANDBOX',call['env'])
            self.assertEqual(call['profile']['cwd'],str(root/'installed/direct/Browser.Tests'))
        checker=[r for r in receipts if r['executable'].endswith('bash')]
        self.assertEqual(len(checker),1);self.assertEqual(len(checker[0]['inputs']),1)
        validator=[call['profile']['argv'][1] for call in owner.calls if 'browser-host-validation' in ' '.join(call['profile']['argv'])]
        self.assertEqual(len(validator),1);self.assertRegex(validator[0],r'browser-host-validation\.[0-9a-f]{64}\.cjs$')
        self.assertEqual(json.loads((root/'installed-c.json').read_text())['families']['webkit']['stats']['expected'],9)

    def test_shell_checker_no_longer_starts_playwright(self):
        text=(HERE/'verify-fable-reference-public.sh').read_text()
        wasm=text[text.index(': "${FSGG_WASM_SDK_ARCHIVE'):text.index(': "${QUINT_BIN')]
        self.assertNotIn('@playwright/test/cli.js',wasm);self.assertNotIn('PLAYWRIGHT_BROWSER_FAMILY=',wasm)
        self.assertIn("'browserCases':'managed-groups-in-caller'",wasm);self.assertIn('wasm_status=source-passed',wasm)

    def test_installed_c_refuses_wrong_case_population_or_failed_family(self):
        report={'config':{'projects':[{'name':'firefox'}]},'suites':[{'specs':[{'tests':[{'projectName':'firefox','projectId':'firefox'}]*8}]}]}
        with self.assertRaisesRegex(ValueError,'nine definitions'):self.ns['check_wasm_list'](report,'firefox')
        with self.assertRaisesRegex(ValueError,'exact selected family'):self.ns['check_wasm_list'](report,'webkit')
        stats={'config':{'projects':[{'name':'webkit'}]},'stats':{'expected':8,'unexpected':1,'flaky':0,'skipped':0}}
        with self.assertRaisesRegex(ValueError,'family webkit stats differ'):self.ns['check_wasm_result'](stats,'webkit')
        # A failed Playwright group stops installed C at that family and keeps its receipt.
        owner=FakeOwner()
        original=FakeOwner.run
        def run(self_,profile,**kwargs):
            if len(profile['argv'])>2 and profile['argv'][2]=='test' and '--list' not in profile['argv']:
                self_.outcome='failed'
            return original(self_,profile,**kwargs)
        with patch.object(FakeOwner,'run',run),self.assertRaisesRegex(RuntimeError,'leader exited with live contained members'):
            drive_every_call_site(self.ns,self.root,owner)
        index=json.loads((self.root/'job/managed-receipts.json').read_text())
        self.assertEqual(index[-1]['status'],'failed');self.assertEqual(len(index),23)
        self.assertFalse((self.root/'job/installed/browser/chromium/report.json').exists())
        summary=json.loads((self.root/'job/installed-c.json').read_text())
        self.assertEqual(summary['disposition'],'failed');self.assertIn('leader exited with live contained members',summary['firstCause'])

    def test_moved_assertions_refuse_each_population_and_stats_drift(self):
        def listing(name='firefox',project='firefox',ident='firefox',count=9):
            return {'config':{'projects':[{'name':name}]},'suites':[{'specs':[{'tests':[{'projectName':project,'projectId':ident}]*count}]}]}
        self.assertEqual(self.ns['check_wasm_list'](listing(),'firefox'),9)
        for kwargs in ({'project':'chromium'},{'ident':'chromium'}):
            with self.subTest(**kwargs),self.assertRaisesRegex(ValueError,'wrong selected project population'):self.ns['check_wasm_list'](listing(**kwargs),'firefox')
        good={'expected':9,'unexpected':0,'flaky':0,'skipped':0}
        self.assertEqual(self.ns['check_wasm_result']({'config':{'projects':[{'name':'webkit'}]},'stats':good},'webkit'),good)
        for key in ('unexpected','flaky','skipped'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'stats differ'):
                self.ns['check_wasm_result']({'config':{'projects':[{'name':'webkit'}]},'stats':{**good,key:1}},'webkit')
        with self.assertRaisesRegex(ValueError,'runtime family differs'):
            self.ns['check_wasm_result']({'config':{'projects':[{'name':'chromium'}]},'stats':good},'webkit')

    def test_installed_c_refuses_an_occupied_evidence_root(self):
        owner=FakeOwner();execute,_=self.executor(owner)
        (self.root/'installed').mkdir()
        with self.assertRaisesRegex(ValueError,'installed evidence root occupied'):
            self.ns['installed_c'](self.root,self.root,{},execute,self.identities,str(self.tool))
        self.assertEqual(owner.calls,[])

    def test_hosted_sequence_qualifies_tools_then_hands_installed_c_its_own_phase_deadline(self):
        owner=FakeOwner();made=[];order=[]
        self.ns['load_owner']=lambda root,deadline:owner
        original=self.ns['managed_executor']
        def executor(owner_,root,deadline,identities,phase,receipts):
            run=original(owner_,root,deadline,identities,phase,receipts);made.append((phase,deadline,receipts,run));return run
        self.ns['managed_executor']=executor
        def provision(root,workspace,env,execute,acquire,deadline,identities):order.append(('provision',execute,deadline));return {'node':'/node'}
        def qualify(root,env,execute):order.append(('qualify',execute))
        def gate(provisioned):order.append(('gate',provisioned['node']))
        def installed(root,workspace,env,execute,identities,node):order.append(('installed',execute,node));return 'installed'
        self.ns.update(prepare_inputs=provision,qualify_tools=qualify,custody_gate=gate,installed_c=installed)
        start=time.monotonic()
        self.assertEqual(self.ns['hosted_sequence'](self.environ(),start),'installed')
        self.assertEqual([step[0] for step in order],['provision','qualify','gate','installed'])
        (setup_phase,setup,setup_receipts,setup_run),(installed_phase,deadline,installed_receipts,installed_run)=made
        self.assertEqual((setup_phase,installed_phase),('setup','installed'))
        self.assertIs(order[0][1],setup_run);self.assertIs(order[1][1],setup_run);self.assertIs(order[3][1],installed_run)
        self.assertEqual(order[0][2],setup);self.assertIs(setup_receipts,installed_receipts)
        budget=self.ns['BUDGET']
        self.assertLessEqual(deadline,start+budget['job']-budget['cleanup']-budget['collection']-budget['overhead']+1)
        self.assertNotEqual(deadline,setup);self.assertLessEqual(deadline-time.monotonic(),budget['installed'])

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

    def test_receiver_targets_published_0193(self):
        # Published Workspace.Template 0.19.3: signed nuget.org archive, peeled tag commit, descriptor bytes.
        self.assertEqual(self.ns['TEMPLATE_VERSION'],'0.19.3')
        self.assertEqual(self.ns['PUBLISHED'],'7be0bcf5886d39a8161b186beb8cc06e82415f1e')
        self.assertEqual(self.ns['PACKAGE_SHA'],'9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2')
        self.assertEqual(self.ns['DESCRIPTOR_SHA'],'6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006')
        url,digest,_=self.ns['ENDPOINTS']['template']
        self.assertEqual(url,'https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.19.3/fs.gg.workspace.template.0.19.3.nupkg')
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

    def test_every_call_site_is_valid_under_the_real_contract(self):
        # Every provisioning, tool-qualification and installed-C call site, through the real schema.
        owner=FakeOwner(validate=self.owner.validate_profile)
        drive_every_call_site(self.ns,self.root,owner)
        self.assertEqual(len(owner.calls),25)

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


PILOT_WORKFLOW_FILE=HERE.parents[2]/'.github/workflows/wasm-custody-pilot.yml'
PILOT_URL='https://github.com/FS-GG/.github/issues/4710#issuecomment-6349235037'

class PilotOwner(FakeOwner):
    """Fake owner for the custody pilot: plays each case and writes a receipt shaped like the real one."""
    def __init__(self, world, behaviour=None, validate=None):
        super().__init__(validate=validate);self.world=world;self.behaviour=behaviour or {};self.case_calls=[]
    def run(self, profile, *, env, deadline, out_dir, control=None):
        if self.validate:self.validate(profile)
        self.calls.append({'profile':profile,'env':env,'deadline':deadline,'outDir':out_dir});self.envs[id(profile)]=env
        os.mkdir(out_dir,0o700);argv=profile['argv'];stdout='';stderr='';cause=None;residual=[]
        receipt={'outcome':'succeeded','refusal':None,'cleanup':'observed-empty-removed','custody':'contained','exit':{'code':0,'signal':None},
            'leader':{'image':'admitted','noNewPrivileges':'1'},'members':{'observed':3},'residualAfterLeaderExit':[],'residualInRoot':[],'escaped':[],
            'retirement':{'termSignals':0,'cgroupKill':False},'timing':{'stopSeconds':1.0},'profileSha256':'f'*64,
            'owner':{'sha256':'d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0'},'firstCause':None}
        if Path(argv[0]).name=='systemctl':
            case=('unit',None)
            stdout='' if self.behaviour.get('unit-empty') else 'TasksMax=4096\nMemoryMax=8589934592\nRuntimeMaxUSec=30min\nDelegate=yes\nNoNewPrivileges=yes\nKillMode=control-group\nTimeoutStopUSec=5s\nUser=runner\n'
        elif 'browser-host-validation' in ' '.join(argv):
            rows=json.loads(argv[3]);names=[r['name'] for r in rows];case=('host',names[0])
            if self.behaviour.get('webkit-deps') and names==['webkit']:
                stderr='Error: Host system is missing dependencies to run browsers.\n  libflite1\n';cause='RuntimeError: command failed with exit 1'
            else:stdout=json.dumps({'platform':'ubuntu24.04-x64','names':names,'state':'stock-host-validation-passed-runtime-pending'})
        elif Path(argv[0]).name=='ldd':
            case=('scan',None)
            if self.behaviour.get('scan-fail'):cause='RuntimeError: command failed with exit 1'
            missing=self.behaviour.get('missing')
            stdout=''.join(a+':\n\tlibc.so.6 => /lib/libc.so.6 (0x1)\n'+('\t'+missing+' => not found\n' if missing and a.endswith('chrome-headless-shell') else '') for a in argv[1:])
        elif len(argv)>2 and argv[2]=='test' and '--config' in argv:
            family=env['PILOT_FAMILY'];case=('normal',family)
            stats={'expected':1,'unexpected':0,'flaky':0,'skipped':0}
            if self.behaviour.get(case)=='fail':stats={'expected':0,'unexpected':1,'flaky':0,'skipped':0};cause='RuntimeError: command failed with exit 1'
            if self.behaviour.get(case)=='raise':raise OSError('owner pipe broke')
            if self.behaviour.get(case)!='no-report':Path(env['PILOT_RESULTS'],family,'normal-report.json').write_text(json.dumps({'stats':stats}))
            if self.behaviour.get(case)=='report-unreadable':Path(env['PILOT_RESULTS'],family,'normal-report.json').chmod(0)
            if self.behaviour.get(case)=='leftover':cause='RuntimeError: leader exited with live contained members';residual=[{'pid':9}]
            if self.behaviour.get(case)=='other-failure':cause='RuntimeError: command failed with signal 9'
        elif len(argv) in (4,5) and argv[1].endswith('.cjs') and argv[3] in ('hold','exit','survive'):
            family,mode=argv[2],argv[3];case=({'hold':'forced','exit':'exit','survive':'survivor'}[mode],family)
            receipt['members']={'observed':3,'sample':[{'pid':2},{'pid':1}]}
            stdout='' if self.behaviour.get(case)=='no-launch' else json.dumps({'launched':True,'family':family,'mode':mode,'version':'1','descendants':[{'pid':2,'comm':'browser'},{'pid':3,'comm':'gpu'}]})+'\n'
            if mode=='hold' and self.behaviour.get(case)!='not-held':cause='TimeoutError: original deadline exhausted';receipt['exit']=None
            if mode=='exit' and self.behaviour.get(case)=='leftover':cause='RuntimeError: leader exited with live contained members';residual=[{'pid':7}]
            if mode=='survive' and self.behaviour.get(case)!='no-survivor':cause='RuntimeError: leader exited with live contained members';residual=[{'pid':2}]
            if mode=='survive' and self.behaviour.get(case)=='holder-only':residual=[{'pid':1}] # the holder alone outlived the leader
        else:
            case=None;stdout=self.world['play'](profile)
        if case and case[0] not in ('host','unit'):self.case_calls.append((case,deadline))
        if self.behaviour.get(case)=='unknown-cleanup':receipt['cleanup']='unknown';cause=cause or 'RuntimeError: cleanup unqualified: unknown'
        if self.behaviour.get(case)=='escaped':receipt['escaped']=[{'pid':5}]
        Path(out_dir,'stdout.log').write_text(stdout);Path(out_dir,'stderr.log').write_text(stderr)
        receipt['residualAfterLeaderExit']=residual
        if cause:receipt.update(outcome='failed',firstCause=cause)
        Path(out_dir,'receipt.json').write_text(json.dumps(receipt))
        if cause:raise FakeGroupFailed(receipt)
        return receipt

def write_host_evidence(ns, host, state):
    """Fixture of the shared recorded WebKit host-package step's evidence."""
    if state=='missing' or host.exists():return
    host.mkdir(mode=0o700);packages=ns['PILOT_WEBKIT_PACKAGES']
    (host/'packages.txt').write_text('\n'.join(packages)+'\n')
    (host/'dpkg-before.tsv').write_text('libc6\t2.39-0ubuntu8\tii \nlibgtk-4-1\t4.14.0-1\tii \n')
    installed=packages if state!='partial' else packages[:-1]
    (host/'dpkg-after.tsv').write_text('libc6\t2.39-0ubuntu8\tii \n'+''.join(p+'\t1.0-'+p+'\tii \n' for p in sorted(installed)))
    (host/'apt-sources.txt').write_text('### /etc/apt/sources.list\ndeb http://azure.archive.ubuntu.com/ubuntu noble main\n')
    (host/'install.log').write_text('Ign:4 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 libopus0 1.4\nGet:1 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 libflite1 2.2 [1 kB]\nGet:2 http://archive.ubuntu.com/ubuntu noble/main amd64 libopus0 1.4 [2 kB]\nGet:3 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 libx11-6 1 [3 kB]\nErr:5 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 libz 1\nSetting up libflite1\n')
    (host/'dpkg-diff.txt').write_text('> libflite1\n');(host/'fallback.txt').write_text('already-present\n')
    (host/'update-attempted.txt').write_text('attempted\n');(host/'update-exit.txt').write_text('124\n' if state=='update-timeout' else '100\n');(host/'update.log').write_text('W: failed source\n')
    if state!='not-attempted':(host/'install-attempted.txt').write_text('attempted\n')
    exits={'failed':'100\n','update-timeout':'100\n','timeout':'124\n','killed':'137\n','interrupted':'not-run\n','not-attempted':'not-run\n'}
    (host/'install-exit.txt').write_text(exits.get(state,'0\n'));(host/'step-complete.txt').write_text('step-exit 0\n')
    (host/'post-step-check.txt').write_text('apt-dpkg-processes '+('2' if state=='lingering' else '0')+'\n');(host/'post-step-processes.txt').write_text('')

class CustodyPilotTests(unittest.TestCase):
    """The admitted custody pilot entry on inert fixtures; nothing is downloaded, launched or uploaded."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(os.path.realpath(self.temp.name))
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'pilot_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns);self.ns['PILOT_ADMISSION']=PILOT_URL # closed in source; test-only admission
        self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        self.workflow=PILOT_WORKFLOW_FILE.read_text()

    def environ(self, **changes):
        sha='c'*40
        value={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main','SHA':sha,'ADMITTED_REF':sha,'CHECKOUT_HEAD':sha,
            'ADMISSION':PILOT_URL,'WORKFLOW_REF':'FS-GG/FS.GG.Templates/.github/workflows/wasm-custody-pilot.yml@refs/heads/main','WORKFLOW_SHA':sha,
            'RUN_ID':'7','RUN_ATTEMPT':'1','RUNNER_TEMP':str(self.root/'rt'),'UNIT_NAME':'fsgg-mg-templates-pilot-7-1',
            'HOST_EVIDENCE':str(self.root/'rt/wasm-custody-pilot-host')}
        value.update(changes);return value

    def pilot(self, behaviour=None, validate=None, owner_available=True):
        (self.root/'world').mkdir()
        world=fixture_world(self.ns,self.root/'world',None)
        owner=PilotOwner(world,behaviour,validate);owner.available=owner_available
        self.ns['load_owner']=lambda root,deadline:owner;self.ns['download']=world['acquire']
        (self.root/'rt').mkdir(exist_ok=True)
        self.host_evidence((behaviour or {}).get('host','installed'))
        return owner

    def host_evidence(self, state):
        write_host_evidence(self.ns,self.root/'rt/wasm-custody-pilot-host',state)

    def test_dispatch_validation_binds_admitted_ref_admission_workflow_and_first_attempt(self):
        source=self.ns['validate_dispatch_source'](self.environ(),'c'*40,self.root/'rt/p')
        self.assertEqual((source['ADMITTED_REF'],source['ADMISSION']),('c'*40,PILOT_URL))
        for key,value in [('EVENT','pull_request'),('REPOSITORY','attacker/fork'),('REF','refs/heads/other'),('ADMITTED_REF','d'*40),('SHA','d'*40),
                          ('ADMISSION',PILOT_URL+'0'),('WORKFLOW_REF','FS-GG/FS.GG.Templates/.github/workflows/fable-reference-public.yml@refs/heads/main'),
                          ('WORKFLOW_SHA',''),('WORKFLOW_SHA','d'*40),('RUN_ATTEMPT','2'),('ADMITTED_REF','C'*40),
                          ('UNIT_NAME','fsgg-mg-templates-pilot-7-2'),('HOST_EVIDENCE',str(self.root/'elsewhere'))]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_dispatch_source'](self.environ(**{key:value}),'c'*40,self.root/'rt/p')
        with self.assertRaisesRegex(ValueError,'admitted_ref'):self.ns['validate_dispatch_source'](self.environ(),'d'*40,self.root/'rt/p')

    def test_pilot_budget_fits_the_admitted_unit_and_never_renews(self):
        budget=self.ns['PILOT_BUDGET']
        self.assertEqual(budget['setup']+budget['custody']+2*budget['cleanup']+budget['collection']+budget['overhead'],budget['job'])
        self.assertLess(budget['job'],1800)
        self.assertEqual(self.ns['pilot_deadline'](100,'setup',100),700)
        self.assertEqual(self.ns['pilot_deadline'](100,'custody',700),1330)
        self.assertEqual(self.ns['pilot_deadline'](100,'custody',800),1360) # the job end, never renewed
        for phase,now in [('custody',1360),('installed',100)]:
            with self.subTest(phase=phase),self.assertRaises(ValueError):self.ns['pilot_deadline'](100,phase,now)

    def test_pilot_sequence_runs_scan_and_three_cases_per_family_as_bounded_groups(self):
        owner=self.pilot();start=time.monotonic()
        summary=self.ns['pilot_sequence'](self.environ(),start)
        self.assertEqual(summary['disposition'],'completed',summary.get('reasons'))
        self.assertEqual({k:v['disposition'] for k,v in summary['libraryScan'].items()},{'chromium-headless1243':'support-complete','chromium-full1243':'support-complete'})
        self.assertEqual({f:{c:r['disposition'] for c,r in rows.items()} for f,rows in summary['cases'].items()},
            {f:{'normal':'clean-stock-shutdown','forced':'deadline-retired','exit':'browser-exited-with-leader','survivor':'leftover-retired'} for f in ('chromium','firefox','webkit')})
        self.assertEqual(summary['platformLabel'],'ubuntu-24.04 + recorded packages')
        self.assertEqual(summary['hostPackages']['state'],'installed');self.assertTrue(summary['hostPackages']['listedEqualsAdmittedList'])
        self.assertIs(summary['hostPackages']['admittedListMatchesPinnedPlaywright'],True)
        self.assertEqual(summary['hostPackages']['changed'],{'libgtk-4-1':['4.14.0-1','1.0-libgtk-4-1']})
        self.assertEqual(set(summary['unit']['matchesAdmission'].values()),{True})
        self.assertEqual(summary['cases']['firefox']['forced']['observedBrowserMembers'],[{'pid':2,'comm':'browser'}])
        self.assertEqual(summary['cases']['webkit']['survivor']['survivingBrowserMembers'],[{'pid':2,'comm':'browser'}])
        root=self.root/'rt/wasm-custody-pilot';receipts=json.loads((root/'managed-receipts.json').read_text())
        self.assertEqual([r['phase'] for r in receipts],['setup']*6+['custody']*14)
        self.assertTrue(receipts[0]['executable'].endswith('systemctl'))
        self.assertEqual({f:r['state'] for f,r in summary['hostValidation']['families'].items()},{f:'stock-host-validation-passed-runtime-pending' for f in ('chromium','firefox','webkit')})
        cases=[c for c,_ in owner.case_calls]
        self.assertEqual(cases,[('scan',None)]*2+[(k,f) for f in ('chromium','firefox','webkit') for k in ('normal','forced','exit','survivor')])
        custody=start+self.ns['PILOT_BUDGET']['job']-sum(self.ns['PILOT_BUDGET'][k] for k in ('cleanup','collection','overhead'))
        for (case,family),deadline in owner.case_calls:
            self.assertLessEqual(deadline,custody+1)
            self.assertLessEqual(deadline-start,self.ns['PILOT_BUDGET']['job'])
        forced=[d for (c,_),d in owner.case_calls if c=='forced']
        self.assertTrue(all(d-time.monotonic()<=self.ns['PILOT_CASE_SECONDS']['forced'] for d in forced))
        for call in owner.calls:
            profile=call['profile']
            with self.subTest(argv=profile['argv'][:3]):
                self.assertTrue(profile['cwd']==str(root) or profile['cwd'].startswith(str(root)+'/'))
                self.assertFalse(any(ord(c)<32 for arg in profile['argv'] for c in arg))
                self.assertEqual(profile['retirement']['onLeaderExit'],'require-empty')
        normal=[c for c in owner.calls if '--config' in c['profile']['argv']]
        self.assertEqual([c['env']['PILOT_FAMILY'] for c in normal],['chromium','firefox','webkit'])
        for call in normal:
            self.assertEqual(call['env']['FSGG_WASM_FIREFOX_PROFILE'],'content-sandbox-enabled')
            self.assertNotIn('MOZ_DISABLE_CONTENT_SANDBOX',call['env']);self.assertNotIn('PLAYWRIGHT_EXECUTABLE_PATH',call['env'])
        # Pilot code files are content-addressed, read-only and recorded as group inputs.
        for name in ('config','spec','hold'):
            path=Path(summary['pilotFiles'][name])
            self.assertEqual(path.name.split('.')[1],hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o400)
        self.assertTrue(all(r['inputs'] for r in receipts if r['phase']=='custody' and not r['executable'].endswith('ldd')))
        evidence=root/'pilot-evidence';manifest=json.loads((evidence/'manifest.json').read_text())
        self.assertIn('custody-pilot.json',[f['path'] for f in manifest['files']]);self.assertLessEqual(manifest['totalBytes'],45*1048576)
        self.assertEqual(json.loads((evidence/'custody-pilot.json').read_text())['disposition'],'completed')
        self.assertEqual(summary['source']['ADMISSION'],PILOT_URL)
        self.assertFalse((root/'tools/dotnet').exists());self.assertFalse((root/'tools/cargo').exists())

    def test_classification_records_leftovers_missing_libraries_and_custody_failures(self):
        self.pilot({'missing':'libfoo.so.1',('normal','firefox'):'leftover',('exit','webkit'):'leftover'})
        summary=self.ns['pilot_sequence'](self.environ(),time.monotonic())
        self.assertEqual(summary['disposition'],'completed')
        self.assertEqual(summary['libraryScan']['chromium-headless1243']['disposition'],'support-missing')
        self.assertEqual(list(summary['libraryScan']['chromium-headless1243']['missing'].values()),[['libfoo.so.1']])
        self.assertEqual(summary['cases']['firefox']['normal']['disposition'],'stock-leftover-retired')
        self.assertEqual(summary['cases']['webkit']['exit']['disposition'],'leftover-retired')
        for behaviour,family,case,expected in [({('forced','chromium'):'not-held'},'chromium','forced','unexpected'),
                                               ({('normal','webkit'):'unknown-cleanup'},'webkit','normal','run-failed'),
                                               ({('normal','chromium'):'fail'},'chromium','normal','run-failed')]:
            with self.subTest(case=case,family=family):
                shutil.rmtree(self.root/'rt');shutil.rmtree(self.root/'world')
                self.ns={'__name__':'pilot_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns);self.ns['PILOT_ADMISSION']=PILOT_URL # closed in source; test-only admission
                self.pilot(behaviour)
                summary=self.ns['pilot_sequence'](self.environ(),time.monotonic())
                self.assertEqual(summary['cases'][family][case]['disposition'],expected)
                self.assertEqual(summary['disposition'],'incomplete');self.assertTrue(summary['reasons'])

    def run_pilot(self, behaviour):
        if (self.root/'rt').exists():shutil.rmtree(self.root/'rt')
        if (self.root/'world').exists():shutil.rmtree(self.root/'world')
        self.ns={'__name__':'pilot_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns);self.ns['PILOT_ADMISSION']=PILOT_URL # closed in source; test-only admission
        self.pilot(behaviour)
        return self.ns['pilot_sequence'](self.environ(),time.monotonic())

    def test_missing_webkit_host_libraries_are_evidence_not_an_abort(self):
        summary=self.run_pilot({'webkit-deps':True,('normal','webkit'):'fail'})
        states={f:r['state'] for f,r in summary['hostValidation']['families'].items()}
        self.assertEqual(states,{'chromium':'stock-host-validation-passed-runtime-pending','firefox':'stock-host-validation-passed-runtime-pending','webkit':'host-dependencies-missing'})
        self.assertIn('missing dependencies',summary['hostValidation']['families']['webkit']['stderr'])
        self.assertEqual(sorted(summary['cases']),['chromium','firefox','webkit'])
        self.assertEqual(summary['cases']['chromium']['normal']['disposition'],'clean-stock-shutdown')
        self.assertEqual(summary['cases']['webkit']['normal']['disposition'],'run-failed')
        self.assertEqual(summary['disposition'],'incomplete')

    def test_each_false_completion_guard_is_causal(self):
        cases=[({('forced','firefox'):'no-launch'},'firefox','forced','unexpected'),
               ({('exit','chromium'):'no-launch'},'chromium','exit','unexpected'),
               ({('exit','webkit'):'unknown-cleanup'},'webkit','exit','unexpected'),
               ({('exit','firefox'):'escaped'},'firefox','exit','unexpected'),
               ({('normal','firefox'):'no-report'},'firefox','normal','run-failed'),
               ({('normal','chromium'):'other-failure'},'chromium','normal','run-failed'),
               ({('normal','webkit'):'escaped'},'webkit','normal','run-failed'),
               ({('forced','webkit'):'escaped'},'webkit','forced','unexpected')]
        for behaviour,family,case,expected in cases:
            with self.subTest(behaviour=behaviour):
                summary=self.run_pilot(behaviour)
                self.assertEqual(summary['cases'][family][case]['disposition'],expected)
                self.assertEqual(summary['disposition'],'incomplete')
        summary=self.run_pilot({'scan-fail':True})
        self.assertEqual({r['disposition'] for r in summary['libraryScan'].values()},{'scan-failed'})
        self.assertEqual(summary['disposition'],'incomplete')

    def test_survivor_must_outlive_the_leader_and_be_retired(self):
        summary=self.run_pilot({('survivor','firefox'):'no-survivor'})
        self.assertEqual(summary['cases']['firefox']['survivor']['disposition'],'unexpected')
        self.assertEqual(summary['disposition'],'incomplete')
        for behaviour in ({('survivor','webkit'):'no-launch'},{('survivor','chromium'):'unknown-cleanup'},{('survivor','chromium'):'escaped'},{('survivor','firefox'):'holder-only'}):
            with self.subTest(behaviour=behaviour):
                family=next(iter(behaviour))[1]
                self.assertEqual(self.run_pilot(behaviour)['cases'][family]['survivor']['disposition'],'unexpected')

    def test_host_package_evidence_states_and_label(self):
        for state,label,expected in [('missing','ubuntu-24.04','host-evidence-missing'),('failed','ubuntu-24.04 + recorded packages','install-failed'),
                                     ('partial','ubuntu-24.04 + recorded packages','install-failed'),('timeout','ubuntu-24.04 + recorded packages','install-timed-out'),
                                     ('interrupted','ubuntu-24.04 + recorded packages','install-interrupted'),
                                     ('killed','ubuntu-24.04 + recorded packages','install-timed-out'),
                                     ('update-timeout','ubuntu-24.04 + recorded packages','install-failed'),
                                     ('not-attempted','ubuntu-24.04 + recorded packages','install-not-reached')]:
            with self.subTest(state=state):
                summary=self.run_pilot({'host':state})
                self.assertEqual((summary['platformLabel'],summary['hostPackages']['state']),(label,expected))
                if state=='partial':self.assertEqual(summary['hostPackages']['listedMissingAfter'],[self.ns['PILOT_WEBKIT_PACKAGES'][-1]])
                if state in ('timeout','killed'):self.assertEqual((summary['hostPackages']['timedOut'],summary['hostPackages']['installTimedOut']),(True,True))
                if state=='update-timeout':self.assertEqual((summary['hostPackages']['timedOut'],summary['hostPackages']['updateTimedOut'],summary['hostPackages']['installTimedOut']),(True,True,False))
                if state=='not-attempted':self.assertEqual((summary['hostPackages']['updateAttempted'],summary['hostPackages']['attempted']),(True,False))
        summary=self.run_pilot({})
        self.assertEqual(summary['hostPackages']['listedVersions']['libflite1'],'1.0-libflite1')
        self.assertEqual((summary['hostPackages']['updateExit'],summary['hostPackages']['state']),('100','installed'))
        self.assertEqual(summary['hostPackages']['fetchHosts'],{'azure.archive.ubuntu.com':2,'archive.ubuntu.com':1})
        self.assertEqual((summary['hostPackages']['postStepAptProcesses'],summary['hostPackages']['fallback'],summary['hostPackages']['timedOut']),(0,'already-present',False))
        self.assertEqual(self.run_pilot({'host':'lingering'})['hostPackages']['postStepAptProcesses'],2)
        self.assertIn('libflite1',summary['hostPackages']['added'])
        files=[f['path'] for f in json.loads((self.root/'rt/wasm-custody-pilot/pilot-evidence/manifest.json').read_text())['files']]
        for name in ('packages.txt','dpkg-before.tsv','dpkg-after.tsv','apt-sources.txt','update-exit.txt','install.log','install-exit.txt',
                     'install-attempted.txt','step-complete.txt','fallback.txt','post-step-check.txt'):self.assertIn('host-packages/'+name,files)

    def test_unit_properties_are_read_back_and_compared(self):
        summary=self.run_pilot({'unit-empty':True})
        self.assertEqual(set(summary['unit']['matchesAdmission'].values()),{False})
        summary=self.run_pilot({})
        self.assertEqual(summary['unit']['properties']['MemoryMax'],str(8*1073741824))

    def test_inline_caller_block_keeps_its_yaml_indentation(self):
        # A line below the block indent ends the YAML scalar: the workflow file breaks and the
        # extracted code loses characters. Every non-empty line must keep the 10-space indent.
        lines=WORKFLOW.read_text().split('\n')
        start=next(i for i,x in enumerate(lines) if "-- /usr/bin/python3 -I - <<'HOSTED_WASM'" in x)
        end=next(i for i in range(start+1,len(lines)) if lines[i]=='          HOSTED_WASM')
        self.assertEqual([i+1 for i in range(start+1,end) if lines[i] and not lines[i].startswith(' '*10)],[])

    @unittest.skipUnless(shutil.which('node'),'node is required to syntax-check the pilot scripts')
    def test_pilot_javascript_is_syntactically_valid(self):
        for name in ('PILOT_HOLD_SCRIPT','PILOT_SPEC','STOCK_HOST_VALIDATOR'):
            path=self.root/(name.lower()+'.cjs');path.write_text(self.ns[name])
            with self.subTest(name=name):
                result=subprocess.run(['node','--check',str(path)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_holder_failure_file_is_collected_as_evidence(self):
        root=self.root/'job';(root/'pilot-ready').mkdir(parents=True);(root/'custody-pilot.json').write_text('{}')
        (root/'pilot-ready/webkit.json.error').write_text('Error: missing host library')
        manifest=self.ns['collect_pilot_evidence'](root)
        self.assertIn('pilot-ready/webkit.json.error',[f['path'] for f in manifest['files']])

    def test_admitted_webkit_list_is_the_reviewed_pinned_list(self):
        # Reviewed fingerprint of deps["ubuntu24.04-x64"].webkit in playwright-core 1.63.0 (51 packages).
        packages=list(self.ns['PILOT_WEBKIT_PACKAGES'])
        self.assertEqual((len(packages),len(set(packages))),(51,51))
        self.assertEqual(hashlib.sha256(json.dumps(packages).encode()).hexdigest(),'d5bfa5eb129c4455d329e51e09a263bbffa87224f0a70476bbf9b9c899c8edd0')

    def test_pinned_webkit_list_parser(self):
        core=self.root/'core.js'
        core.write_text('x={"ubuntu22.04-x64": {webkit: ["old"]},\n "ubuntu24.04-x64": {\n tools: ["xvfb"],\n webkit: [\n "a1",\n "b2",\n "a1"\n ],\n lib2package:{}}}')
        self.assertEqual(self.ns['pinned_webkit_packages'](core),['a1','b2'])
        bundle=os.environ.get('FSGG_PLAYWRIGHT_CORE_BUNDLE')
        if bundle:
            self.assertEqual(hashlib.sha256(Path(bundle).read_bytes()).hexdigest(),self.ns['STOCK_LAUNCHER_INPUTS']['playwright-core/lib/coreBundle.js'])
            self.assertEqual(self.ns['pinned_webkit_packages'](bundle),list(self.ns['PILOT_WEBKIT_PACKAGES']))

    def test_one_case_exception_does_not_abort_later_cases(self):
        if os.geteuid()==0:self.skipTest('root can read a mode-0 file')
        summary=self.run_pilot({('normal','chromium'):'report-unreadable'}) # an OSError outside the group itself
        self.assertEqual(summary['cases']['chromium']['normal']['disposition'],'run-failed')
        self.assertIn('PermissionError',summary['cases']['chromium']['normal']['error'])
        manifest=json.loads((self.root/'rt/wasm-custody-pilot/pilot-evidence/manifest.json').read_text())
        self.assertEqual([Path(u['path']).name for u in manifest['unreadable']],['normal-report.json'])
        self.assertIn('custody-pilot.json',[f['path'] for f in manifest['files']])
        self.assertEqual(summary['cases']['webkit']['exit']['disposition'],'browser-exited-with-leader')
        summary=self.run_pilot({('normal','firefox'):'raise'})
        self.assertEqual(summary['cases']['firefox']['normal']['disposition'],'run-failed')
        self.assertIn('owner pipe broke',summary['cases']['firefox']['normal']['error'])
        self.assertEqual(summary['cases']['webkit']['exit']['disposition'],'browser-exited-with-leader')
        self.assertEqual(summary['disposition'],'incomplete')

    def test_disposition_counts_missing_cases_and_missing_scans(self):
        full={f:{c:{'disposition':self.ns['PILOT_EXPECTED'][c][0]} for c in ('normal','forced','exit','survivor')} for f in ('chromium','firefox','webkit')}
        scans={a:{'disposition':'support-complete'} for a in ('chromium-headless1243','chromium-full1243')}
        self.assertEqual(self.ns['pilot_disposition']({'cases':full,'libraryScan':scans}),'completed')
        partial=copy.deepcopy(full);del partial['webkit']['exit']
        summary={'cases':partial,'libraryScan':scans}
        self.assertEqual(self.ns['pilot_disposition'](summary),'incomplete');self.assertIn('webkit/exit: not run',summary['reasons'])
        summary={'cases':full,'libraryScan':{'chromium-full1243':scans['chromium-full1243']}}
        self.assertEqual(self.ns['pilot_disposition'](summary),'incomplete');self.assertIn('scan chromium-headless1243: not run',summary['reasons'])

    def test_every_case_deadline_is_capped_by_the_custody_phase(self):
        owner=self.pilot();root=self.root/'rt/wasm-custody-pilot'
        env=self.ns['fresh_environment'](root,{});self.ns['load_owner']=lambda r,d:owner
        identities={};receipts=[]
        provisioned=self.ns['prepare_browser_inputs'](root,env,self.ns['managed_executor'](owner,root,time.monotonic()+60,identities,'setup',receipts),owner.world['acquire'],time.monotonic()+60,identities,receipts)
        owner.case_calls.clear();short=time.monotonic()+3
        summary={'cases':{},'libraryScan':{}}
        self.ns['run_custody_pilot'](root,env,owner,identities,receipts,provisioned,short,summary,lambda:None)
        self.assertEqual(len(owner.case_calls),14)
        self.assertTrue(all(deadline<=short for _,deadline in owner.case_calls))

    def test_unavailable_containment_fails_before_acquisition_and_still_retains_evidence(self):
        self.pilot(owner_available=False)
        def forbidden(*args,**kwargs):raise AssertionError('acquisition before containment probe')
        self.ns['download']=forbidden
        with self.assertRaisesRegex(ValueError,'containment unavailable'):self.ns['pilot_sequence'](self.environ(),time.monotonic())
        root=self.root/'rt/wasm-custody-pilot'
        summary=json.loads((root/'pilot-evidence/custody-pilot.json').read_text())
        self.assertEqual(summary['disposition'],'failed');self.assertIn('containment unavailable',summary['firstCause'])
        self.assertFalse((root/'downloads').exists())

    def test_refused_dispatch_writes_nothing(self):
        with self.assertRaisesRegex(ValueError,'re-run refused'):self.ns['pilot_sequence'](self.environ(RUN_ATTEMPT='2'),time.monotonic())
        self.assertFalse((self.root/'rt/wasm-custody-pilot').exists())

    def test_evidence_is_capped_and_logs_truncated(self):
        root=self.root/'job';root.mkdir();(root/'custody-pilot.json').write_text('{}')
        group=root/'managed/001-custody';group.mkdir(parents=True)
        (group/'receipt.json').write_text('{}');(group/'stdout.log').write_bytes(b'x'*(2*1048576))
        self.ns['PILOT_EVIDENCE_BYTES']=1048576+100
        manifest=self.ns['collect_pilot_evidence'](root)
        self.assertEqual([t['bytes'] for t in manifest['truncated']],[2*1048576])
        self.assertLessEqual(manifest['totalBytes'],1048576+100)
        self.assertTrue(manifest['skipped'] or manifest['totalBytes']==2+2+1048576)
        for row in manifest['files']:
            self.assertEqual(hashlib.sha256((root/'pilot-evidence'/row['path']).read_bytes()).hexdigest(),row['sha256'])

    def test_parse_ldd_attributes_missing_libraries_per_target(self):
        targets=[Path('/b/chrome'),Path('/b/libEGL.so')]
        text='/b/chrome:\n\tlibnss3.so => not found\n\tlibc.so.6 => /lib/libc.so.6 (0x1)\n/b/libEGL.so:\n\tlibX11.so.6 => not found\n'
        self.assertEqual(self.ns['parse_ldd'](text,targets),{'/b/chrome':['libnss3.so'],'/b/libEGL.so':['libX11.so.6']})
        self.assertEqual(self.ns['parse_ldd']('\tlibz.so => not found\n',[Path('/b/one')]),{'/b/one':['libz.so']})

    def test_pilot_workflow_is_dispatch_only_bounded_and_uploads_one_artifact(self):
        text=self.workflow
        trigger=text.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual(re.findall(r'^  ([a-z_]+):$',trigger,re.M),['pull_request','workflow_dispatch'])
        self.assertNotRegex(text,r'(contents|actions|packages|id-token|pull-requests|issues): write|secrets\.|pull_request_target|workflow_run|schedule:')
        self.assertEqual(text.count('continue-on-error'),2) # the apt step and its post-step process check only
        static=text.split('  pilot-static-controls:',1)[1].split('  custody-pilot:',1)[0]
        pilot=text.split('  custody-pilot:',1)[1]
        self.assertNotIn('systemd-run',static);self.assertNotIn('wasm-custody-pilot.py\n',static.replace('ast.parse(open(sys.argv[1]).read())\' tests/composition/fable-game/wasm-custody-pilot.py',''))
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' }}",pilot)
        for required in ('runs-on: ubuntu-24.04','timeout-minutes: 40','contents: read','sudo -n systemd-run --quiet --wait --pipe --collect --service-type=exec',
                         '-p Delegate=yes','-p NoNewPrivileges=yes','-p KillMode=control-group','-p TimeoutStopSec=5','-p TasksMax=4096','-p MemoryMax=8G',
                         '-p RuntimeMaxSec=1800','--setenv=ADMITTED_REF="$ADMITTED_REF"','--setenv=ADMISSION="$ADMISSION"','ref: ${{ github.sha }}',
                         '--setenv=UNIT_NAME="$unit"','--setenv=HOST_EVIDENCE="$RUNNER_TEMP/wasm-custody-pilot-host"','include-hidden-files: true',
                         '-- /usr/bin/python3 -I tests/composition/fable-game/wasm-custody-pilot.py','retention-days: 30',
                         'path: ${{ runner.temp }}/wasm-custody-pilot/pilot-evidence/'):
            with self.subTest(required=required):self.assertIn(required,pilot)
        self.assertEqual(re.findall(r'uses: ([^\s]+)',pilot),['actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'])
        self.assertNotIn('${{ inputs.',pilot.split('    steps:',1)[1])
        self.assertIn(PILOT_URL,text)
        # The only host write is the pre-unit apt step, installing exactly the printed admitted list.
        steps=re.findall(r'^      - name: (.*)$',pilot,re.M)
        self.assertEqual(steps,['Check out the exact dispatched commit','Refuse unless this dispatch is admitted in source','Install and record the admitted WebKit host packages',
            'Check that no apt or dpkg process remains','Run the admitted pilot in a fresh delegated unit','Retain bounded pilot evidence','Report evidence artifact identity'])
        precheck=pilot.split('Refuse unless this dispatch is admitted in source',1)[1].split('      - name:',1)[0]
        self.assertIn('python3 -I tests/composition/fable-game/wasm-custody-pilot.py --check-admission',precheck);self.assertNotIn('if:',precheck)
        apt=pilot.split('Install and record the admitted WebKit host packages',1)[1].split('      - name:',1)[0]
        check=pilot.split('Check that no apt or dpkg process remains',1)[1].split('      - name:',1)[0]
        self.assertEqual(len(re.findall(r'apt-get .*install',text)),1);self.assertIn('apt-get',apt)
        self.assertIn('--print-webkit-packages >"$host/packages.txt"',apt);self.assertIn('"${packages[@]}"',apt)
        for evidence in ('dpkg-before.tsv','dpkg-after.tsv','dpkg-diff.txt','apt-sources.txt','update.log','update-exit.txt','install.log','install-exit.txt',
                         'update-attempted.txt','install-attempted.txt','step-complete.txt','apt-mirrors-before.txt','apt-mirrors-after.txt','fallback.txt'):
            self.assertIn(evidence,apt)
        self.assertIn('set +e',apt)
        self.assertIn("if: ${{ github.run_attempt == '1' }}",apt);self.assertIn('continue-on-error: true',apt);self.assertIn('timeout-minutes: 10',apt)
        # Admitted bounds: install under timeout -k 15 480 with retries and a 30 s HTTP timeout; update bounded too.
        self.assertIn('sudo -n env DEBIAN_FRONTEND=noninteractive timeout -k 15 480 apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y -q --no-install-recommends "${packages[@]}"',apt)
        self.assertIn('sudo -n timeout -k 10 60 apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update -q',apt)
        self.assertLessEqual(60+10+480+15,10*60-30) # bounded calls fit the 10-minute step with margin
        # The trap always writes the exit codes and the dpkg after-state, even on failure.
        self.assertIn('trap finish EXIT',apt)
        finish=apt.split('finish() {',1)[1].split('          }',1)[0]
        for written in ('update-exit.txt','install-exit.txt','dpkg-after.tsv','dpkg-diff.txt','step-complete.txt','apt-mirrors-after.txt','dpkg-settle.txt'):self.assertIn(written,finish)
        self.assertTrue(finish.lstrip().startswith('local rc=$?')) # the status that ended the step, captured first
        self.assertIn('''            cp /etc/apt/apt-mirrors.txt "$host/apt-mirrors-after.txt" 2>/dev/null || printf 'absent\\n' >"$host/apt-mirrors-after.txt"\n''',finish)
        loop='while pgrep -x dpkg >/dev/null 2>&1 && (( waited < 20 )); do sleep 1; waited=$((waited + 1)); done'
        self.assertIn(loop,finish);self.assertLess(finish.index(loop),finish.index('snapshot >"$host/dpkg-after.tsv"')) # dpkg settles before the after-state
        self.assertLessEqual(60+10+480+15+20,10*60-10) # bounded calls plus the dpkg settle fit the 10-minute step
        # Signal traps would defer until the foreground apt call ends and lose the evidence on cancel.
        self.assertEqual(re.findall(r'^\s*trap .*$',apt,re.M),['          trap finish EXIT'])
        self.assertIn('''update -q >"$host/update.log" 2>&1\n          printf '%s\\n' "$?" >"$host/update-exit.txt"\n''',apt)
        self.assertIn('''install -y -q --no-install-recommends "${packages[@]}" >"$host/install.log" 2>&1\n          printf '%s\\n' "$?" >"$host/install-exit.txt"\n''',apt)
        self.assertIn('''grep -Eq '^[a-z]+://archive\\.ubuntu\\.com/ubuntu/?([[:space:]]|$)' "$mirrors"''',apt)
        self.assertIn('"$host/dpkg-diff.txt" || true',finish) # diff exits 1 after any install
        self.assertLess(apt.index('update-attempted.txt'),apt.index('update -q'));self.assertLess(apt.index('install-attempted.txt'),apt.index(' install -y'))
        # Azure stays first; archive.ubuntu.com is only appended (recorded) when absent.
        self.assertIn("archive\\.ubuntu\\.com",apt);self.assertIn("printf 'http://archive.ubuntu.com/ubuntu/\\n' | sudo -n tee -a \"$mirrors\"",apt)
        self.assertNotIn('update -q &&',apt);self.assertLess(apt.index('update-exit.txt" '),apt.index(' install -y'))
        # Post-step apt termination check, after the apt step and before the unit.
        self.assertIn("if: ${{ always() && github.run_attempt == '1' }}",check);self.assertIn('post-step-check.txt',check)
        self.assertIn('/usr/lib/apt/methods/',check);self.assertIn('c!="awk"',check)
        hold=self.ns['PILOT_HOLD_SCRIPT'];self.assertIn('{detached:true,stdio:"ignore"}',hold);self.assertIn('holder.unref()',hold)
        self.assertIn('fs.writeFileSync(ready+".error"',hold);self.assertIn('fs.existsSync(ready+".error")',hold)
        self.assertEqual(text.count('sudo -n'),4) # apt update, apt install, mirror fallback append, systemd-run

    def test_pilot_is_closed_in_source_and_refuses_before_any_host_write(self):
        tree=ast.parse(self.code)
        nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(x,'id',None)=='PILOT_ADMISSION' for x in n.targets)]
        self.assertEqual(len(nodes),1);self.assertIsNone(nodes[0].value.value)
        closed={'__name__':'pilot_closed'};exec(compile(self.code,'actual-hosted-workflow','exec'),closed)
        with self.assertRaisesRegex(RuntimeError,'custody pilot closed'):closed['pilot_sequence'](self.environ(),time.monotonic())
        self.assertFalse((self.root/'rt/wasm-custody-pilot').exists())
        env={'PATH':'/usr/bin:/bin','ADMISSION':PILOT_URL,'ADMITTED_REF':'c'*40,'SHA':'c'*40,'RUN_ATTEMPT':'1'}
        result=subprocess.run([sys.executable,'-I',str(HERE/'wasm-custody-pilot.py'),'--check-admission'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,3,result.stderr);self.assertIn('not admitted in source',result.stderr)

    def test_admission_precheck_binds_source_input_ref_and_attempt(self):
        good={'ADMISSION':PILOT_URL,'ADMITTED_REF':'c'*40,'SHA':'c'*40,'RUN_ATTEMPT':'1'}
        self.assertTrue(self.ns['admission_precheck'](good,PILOT_URL))
        for admission,changes,message in [(None,{},'not admitted'),(PILOT_URL,{'ADMISSION':'x'},'input differs'),(PILOT_URL,{'ADMITTED_REF':'d'*40},'admitted_ref'),
                                          (PILOT_URL,{'RUN_ATTEMPT':'2'},'re-run refused')]:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):self.ns['admission_precheck']({**good,**changes},admission)

    def test_pilot_entry_leaves_installed_c_gates_closed(self):
        caller=WORKFLOW.read_text()
        self.assertEqual(len(re.findall(r'^        if: \$\{\{ false \}\}$',caller,re.M)),2)
        self.assertIn('RUNTIME_ADMITTED = False',self.code)
        with self.assertRaisesRegex(RuntimeError,'custody pilot remain unadmitted'):self.ns['custody_gate']({})
        body=ast.get_source_segment(self.code,next(n for n in ast.parse(self.code).body if isinstance(n,ast.FunctionDef) and n.name=='pilot_sequence'))
        for forbidden in ('installed_c','custody_gate','RUNTIME_ADMITTED','prepare_inputs','qualify_tools'):self.assertNotIn(forbidden,body)

    @unittest.skipUnless(OWNER_FILE,'set FSGG_MANAGED_GROUP_OWNER to the pinned owner file to validate pilot profiles')
    def test_every_pilot_call_is_valid_under_the_real_contract(self):
        source=Path(OWNER_FILE).read_bytes();self.assertEqual(hashlib.sha256(source).hexdigest(),self.ns['OWNER']['sha256'])
        spec=importlib.util.spec_from_file_location('pilot_owner_check',OWNER_FILE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        owner=self.pilot(validate=module.validate_profile)
        self.assertEqual(self.ns['pilot_sequence'](self.environ(),time.monotonic())['disposition'],'completed')
        self.assertEqual(len(owner.calls),20)


INSTALLED_WORKFLOW_FILE=HERE.parents[2]/'.github/workflows/wasm-installed-c.yml'
INSTALLED_URL='https://github.com/FS-GG/.github/issues/4710#issuecomment-0000000000' # test-only stand-in

class InstalledAdmissionTests(unittest.TestCase):
    """The held, separately admitted installed-C entry; nothing is downloaded, launched or uploaded."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(os.path.realpath(self.temp.name))
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'installed_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.addCleanup(setattr,sys,'dont_write_bytecode',sys.dont_write_bytecode)
        self.workflow=INSTALLED_WORKFLOW_FILE.read_text()

    def environ(self, **changes):
        sha='c'*40
        value={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main','SHA':sha,'ADMITTED_REF':sha,'CHECKOUT_HEAD':sha,
            'ADMISSION':INSTALLED_URL,'WORKFLOW_REF':'FS-GG/FS.GG.Templates/.github/workflows/wasm-installed-c.yml@refs/heads/main','WORKFLOW_SHA':sha,
            'RUN_ID':'9','RUN_ATTEMPT':'1','RUNNER_TEMP':str(self.root/'rt'),'UNIT_NAME':'fsgg-mg-templates-installed-9-1',
            'HOST_EVIDENCE':str(self.root/'rt/wasm-custody-pilot-host'),'GITHUB_WORKSPACE':str(self.root/'world/workspace')}
        value.update(changes);return value

    def admit(self, host='installed', validate=None):
        self.ns['INSTALLED_ADMISSION']=INSTALLED_URL
        (self.root/'world').mkdir();(self.root/'rt').mkdir()
        owner=FakeOwner(validate=validate)
        world=fixture_world(self.ns,self.root/'world',owner);owner.stdout=world['play']
        write_host_evidence(self.ns,self.root/'rt/wasm-custody-pilot-host',host)
        self.ns['load_owner']=lambda root,deadline:owner;self.ns['download']=world['acquire']
        return owner

    def test_held_in_source_refuses_before_any_acquisition(self):
        self.ns['INSTALLED_ADMISSION']=None # the held state, independent of the current source value
        def forbidden(*args,**kwargs):raise AssertionError('acquired while installed C is held')
        self.ns['download']=forbidden;self.ns['load_owner']=forbidden;self.ns['fresh_environment']=forbidden
        with self.assertRaisesRegex(RuntimeError,'installed C not admitted: INSTALLED_ADMISSION is unset'):
            self.ns['admitted_installed_sequence'](self.environ(),time.monotonic())
        self.assertFalse((self.root/'rt').exists())

    def test_all_runtime_gates_stay_literal_and_closed(self):
        tree=ast.parse(self.code)
        def literal(name):
            nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(x,'id',None)==name for x in n.targets)]
            self.assertEqual(len(nodes),1,name);return nodes[0].value.value
        # Admitted for exactly one run by #4710 comment 6359693961; a reset PR restores None.
        self.assertIs(literal('RUNTIME_ADMITTED'),False);self.assertEqual(literal('INSTALLED_ADMISSION'),'https://github.com/FS-GG/.github/issues/4710#issuecomment-6359693961')
        self.assertEqual(len(re.findall(r'^        if: \$\{\{ false \}\}$',WORKFLOW.read_text(),re.M)),2)
        self.ns['INSTALLED_ADMISSION']=None # held behaviour of the gate
        for admitted in (False,True):
            with self.subTest(admitted=admitted),self.assertRaisesRegex(RuntimeError,'installed C held'):self.ns['custody_gate']({},admitted=admitted)
        with self.assertRaisesRegex(RuntimeError,'installed C held'):self.ns['custody_gate']({})
        # Even when admitted, only the dispatch entry passes admitted=True; the PR path never does.
        self.ns['INSTALLED_ADMISSION']=INSTALLED_URL
        self.assertEqual(self.ns['custody_gate']({'x':1},admitted=True),{'x':1})
        with self.assertRaisesRegex(RuntimeError,'installed C held'):self.ns['custody_gate']({})
        hosted=ast.get_source_segment(self.code,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='hosted_sequence'))
        self.assertIn('custody_gate(provisioned)',hosted);self.assertNotIn('admitted',hosted)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        self.assertEqual(ast.unparse(main.body[0].test),'not RUNTIME_ADMITTED')

    def test_dispatch_validation_binds_admission_ref_workflow_unit_and_first_attempt(self):
        self.ns['INSTALLED_ADMISSION']=INSTALLED_URL
        source=self.ns['validate_installed_dispatch'](self.environ(),'c'*40,self.root/'rt/x')
        self.assertEqual((source['ADMISSION'],source['templateVersion']),(INSTALLED_URL,self.ns['TEMPLATE_VERSION']))
        for key,value in [('EVENT','pull_request'),('REPOSITORY','attacker/fork'),('REF','refs/heads/other'),('ADMITTED_REF','d'*40),('SHA','d'*40),
                          ('ADMISSION',PILOT_URL),('WORKFLOW_REF','FS-GG/FS.GG.Templates/.github/workflows/wasm-custody-pilot.yml@refs/heads/main'),
                          ('WORKFLOW_SHA','d'*40),('RUN_ATTEMPT','2'),('UNIT_NAME','fsgg-mg-templates-pilot-9-1'),('HOST_EVIDENCE',str(self.root/'other')),
                          ('GITHUB_WORKSPACE','relative')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_installed_dispatch'](self.environ(**{key:value}),'c'*40,self.root/'rt/x')
        with self.assertRaisesRegex(ValueError,'admitted_ref'):self.ns['validate_installed_dispatch'](self.environ(),'d'*40,self.root/'rt/x')
        with self.assertRaisesRegex(ValueError,'re-run refused'): # a consistent re-run is refused for its attempt, not its unit
            self.ns['validate_installed_dispatch'](self.environ(RUN_ATTEMPT='2',UNIT_NAME='fsgg-mg-templates-installed-9-2'),'c'*40,self.root/'rt/x')
        self.ns['INSTALLED_ADMISSION']=None
        with self.assertRaisesRegex(ValueError,'not admitted'):self.ns['validate_installed_dispatch'](self.environ(),'c'*40,self.root/'rt/x')

    def test_admitted_sequence_runs_provisioning_custody_gate_and_27_case_installed_c(self):
        owner=self.admit();start=time.monotonic()
        summary=self.ns['admitted_installed_sequence'](self.environ(),start)
        self.assertEqual(summary['disposition'],'passed')
        self.assertEqual(set(summary['unit']['matchesAdmission'].values()),{True})
        self.assertEqual((summary['hostPackages']['state'],summary['platformLabel']),('installed','ubuntu-24.04 + recorded packages'))
        root=self.root/'rt/wasm-installed-c';receipts=json.loads((root/'managed-receipts.json').read_text())
        self.assertEqual([r['phase'] for r in receipts],['setup']*19+['installed']*7)
        self.assertTrue(receipts[0]['executable'].endswith('systemctl'))
        families=summary['installedC']['families']
        self.assertEqual({f:(r['listed'],r['stats']['expected']) for f,r in families.items()},{f:(9,9) for f in ('chromium','firefox','webkit')})
        self.assertEqual(sum(r['stats']['expected'] for r in families.values()),27)
        for call in owner.calls:self.assertEqual(call['profile']['retirement']['onLeaderExit'],'require-empty')
        installed_deadlines={c['deadline'] for c,r in zip(owner.calls,receipts) if r['phase']=='installed'}
        self.assertEqual(len(installed_deadlines),1) # one installed-phase deadline, never renewed
        self.assertGreater(min(installed_deadlines)-start,1000) # the installed-C budget (1230 s), not the shared 900 s
        manifest=json.loads((root/'installed-evidence/manifest.json').read_text());files=[f['path'] for f in manifest['files']]
        for name in ('installed-run.json','installed-c.json','managed-receipts.json','host-packages/install-exit.txt','installed/qualification.json','source.json'):
            self.assertIn(name,files)
        self.assertLessEqual(manifest['totalBytes'],self.ns['INSTALLED_EVIDENCE_BYTES'])
        self.assertEqual(json.loads((root/'installed-run.json').read_text())['disposition'],'passed')

    def test_without_recorded_webkit_packages_refuses_before_provisioning(self):
        for host in ('failed','timeout','missing'):
            with self.subTest(host=host):
                shutil.rmtree(self.root/'world',ignore_errors=True);shutil.rmtree(self.root/'rt',ignore_errors=True)
                self.ns={'__name__':'installed_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
                owner=self.admit(host)
                def forbidden(*args,**kwargs):raise AssertionError('provisioning acquisition without WebKit packages')
                self.ns['prepare_inputs']=forbidden
                with self.assertRaisesRegex(ValueError,'WebKit host packages not installed'):
                    self.ns['admitted_installed_sequence'](self.environ(),time.monotonic())
                run=json.loads((self.root/'rt/wasm-installed-c/installed-evidence/installed-run.json').read_text())
                self.assertEqual(run['disposition'],'failed')

    def test_installed_workflow_is_dispatch_only_bounded_and_shares_the_pilot_host_step(self):
        text=self.workflow
        trigger=text.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual(re.findall(r'^  ([a-z_]+):$',trigger,re.M),['pull_request','workflow_dispatch'])
        self.assertNotRegex(text,r'(contents|actions|packages|id-token|pull-requests|issues): write|secrets\.|pull_request_target|workflow_run|schedule:')
        static=text.split('  installed-c-static-controls:',1)[1].split('  installed-c:',1)[0]
        job=text.split('\n  installed-c:\n',1)[1]
        self.assertNotIn('systemd-run',static);self.assertNotIn('apt-get',static)
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' }}",job)
        for required in ('runs-on: ubuntu-24.04','timeout-minutes: 60','contents: read','-p Delegate=yes','-p NoNewPrivileges=yes','-p KillMode=control-group',
                         '-p TasksMax=6144','-p MemoryMax=12G','-p RuntimeMaxSec=2400','--setenv=GITHUB_WORKSPACE="$GITHUB_WORKSPACE"',
                         'unit="fsgg-mg-templates-installed-${RUN_ID}-${RUN_ATTEMPT}"','-- /usr/bin/python3 -I tests/composition/fable-game/wasm-installed-c.py',
                         'path: ${{ runner.temp }}/wasm-installed-c/installed-evidence/','retention-days: 30','include-hidden-files: true'):
            with self.subTest(required=required):self.assertIn(required,job)
        self.assertEqual(re.findall(r'uses: ([^\s]+)',job),['actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'])
        self.assertNotIn('${{ inputs.',job.split('    steps:',1)[1])
        steps=re.findall(r'^      - name: (.*)$',job,re.M)
        self.assertEqual(steps[:3],['Check out the exact dispatched commit','Refuse unless this dispatch is admitted in source','Install and record the admitted WebKit host packages'])
        self.assertIn('python3 -I tests/composition/fable-game/wasm-installed-c.py --check-admission',job)
        precheck=job.split('Refuse unless this dispatch is admitted in source',1)[1].split('      - name:',1)[0]
        own='\n        shell: bash\n        run: python3 -I tests/composition/fable-game/wasm-installed-c.py --check-admission\n'
        self.assertTrue(precheck.startswith(own),precheck) # no if:, no continue-on-error
        self.assertTrue(all(line.startswith('      #') for line in precheck[len(own):].splitlines()),precheck) # then only the next step's comments
        self.assertEqual(re.findall(r'^    if: (.*)$',text,re.M),["${{ github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository }}","${{ github.event_name == 'workflow_dispatch' }}"])
        # The recorded WebKit host-package step and its post-step check are the accepted pilot's, byte for byte.
        pilot=PILOT_WORKFLOW_FILE.read_text()
        shared=pilot[pilot.index("      # The only admitted host write:"):pilot.index("      - name: Run the admitted pilot in a fresh delegated unit")]
        self.assertIn(shared,job)
        self.assertEqual(self.ns['INSTALLED_WORKFLOW'],'FS-GG/FS.GG.Templates/.github/workflows/'+INSTALLED_WORKFLOW_FILE.name+'@refs/heads/main')
        self.assertEqual(self.ns['INSTALLED_UNIT']['TasksMax'],'6144');self.assertEqual(self.ns['INSTALLED_UNIT']['RuntimeMaxUSec'],'40min')

    def test_held_precheck_refuses_before_the_host_step(self):
        env={'PATH':'/usr/bin:/bin','ADMISSION':INSTALLED_URL,'ADMITTED_REF':'c'*40,'SHA':'c'*40,'RUN_ATTEMPT':'1'}
        result=subprocess.run([sys.executable,'-I',str(HERE/'wasm-installed-c.py'),'--check-admission'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,3,result.stderr);self.assertIn('refused before any host write',result.stderr)

    def test_installed_budget_moves_the_spent_custody_reserve_to_installed(self):
        budget=self.ns['INSTALLED_BUDGET']
        self.assertEqual(budget['setup']+budget['installed']+2*budget['cleanup']+budget['collection']+budget['overhead'],budget['job'])
        self.assertEqual(budget['job'],self.ns['BUDGET']['job']);self.assertGreater(budget['installed'],self.ns['BUDGET']['installed'])
        self.assertEqual(self.ns['installed_deadline'](100,'setup',100),940)
        self.assertEqual(self.ns['installed_deadline'](100,'installed',940),2170) # min(940+1230, 100+2400-300)
        for phase,now in [('installed',2200),('custody',100)]:
            with self.subTest(phase=phase),self.assertRaises(ValueError):self.ns['installed_deadline'](100,phase,now)

    def test_unit_mismatch_or_lingering_apt_refuses_before_provisioning(self):
        for case in ('unit','lingering'):
            with self.subTest(case=case):
                shutil.rmtree(self.root/'world',ignore_errors=True);shutil.rmtree(self.root/'rt',ignore_errors=True)
                self.ns={'__name__':'installed_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
                owner=self.admit('lingering' if case=='lingering' else 'installed')
                if case=='unit':self.ns['INSTALLED_UNIT']={**self.ns['INSTALLED_UNIT'],'TasksMax':'1'}
                def forbidden(*args,**kwargs):raise AssertionError('provisioning after a failed precondition')
                self.ns['prepare_inputs']=forbidden
                with self.assertRaisesRegex(ValueError,'unit properties differ' if case=='unit' else 'apt or dpkg process still running'):
                    self.ns['admitted_installed_sequence'](self.environ(),time.monotonic())

    def test_installed_evidence_is_capped(self):
        root=self.root/'job';(root/'installed/browser/webkit').mkdir(parents=True);(root/'installed-run.json').write_text('{}')
        (root/'installed/browser/webkit/trace.zip').write_bytes(b'z'*4096);(root/'installed/guests.log').write_bytes(b'l'*(2*1048576))
        self.ns['INSTALLED_EVIDENCE_BYTES']=1048576+64
        manifest=self.ns['collect_installed_evidence'](root)
        self.assertLessEqual(manifest['totalBytes'],1048576+64)
        self.assertEqual([Path(s['path']).name for s in manifest['skipped']],['trace.zip'])
        self.assertEqual([t['bytes'] for t in manifest['truncated']],[2*1048576])

    @unittest.skipUnless(OWNER_FILE,'set FSGG_MANAGED_GROUP_OWNER to the pinned owner file to validate installed-C profiles')
    def test_every_installed_call_is_valid_under_the_real_contract(self):
        source=Path(OWNER_FILE).read_bytes();self.assertEqual(hashlib.sha256(source).hexdigest(),self.ns['OWNER']['sha256'])
        spec=importlib.util.spec_from_file_location('installed_owner_check',OWNER_FILE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        owner=self.admit(validate=module.validate_profile)
        self.assertEqual(self.ns['admitted_installed_sequence'](self.environ(),time.monotonic())['disposition'],'passed')
        self.assertEqual(len(owner.calls),26)


RESTORE_CONTROL_WORKFLOW=HERE.parents[2]/'.github/workflows/installed-c-restore-control.yml'
RESTORE_CONTROL=HERE/'installed-c-restore-control.py'
CHECKER=HERE/'verify-fable-reference-public.sh'

class RestoreControlTests(unittest.TestCase):
    """Run 39858275028 (NU1403): the ProviderTool restore keeps the SDK library-packs feed, and an
    always-run job executes the caller's and checker's exact restore commands from clean caches."""
    def setUp(self):
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'restore_control_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.tree=ast.parse(self.code)

    def body(self, name):
        return ast.get_source_segment(self.code,next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name==name))

    def test_provider_tool_restore_keeps_the_sdk_library_pack_feed(self):
        argv=self.ns['provider_tool_restore_argv']('/d/dotnet',Path('/w/P.fsproj'),Path('/r/nuget.config'))
        self.assertEqual(argv,['/d/dotnet','restore','/w/P.fsproj','--locked-mode','--configfile','/r/nuget.config','-p:NuGetAudit=false'])
        self.assertNotIn('DisableImplicitLibraryPacksFolder',self.code)
        self.assertEqual(self.ns['provider_tool_build_argv']('/d/dotnet',Path('/w/P.fsproj')),
            ['/d/dotnet','build','/w/P.fsproj','-c','Release','--no-restore','-p:UseSharedCompilation=false','-p:BuildInParallel=false'])
        self.assertEqual(self.ns['fable_install_argv']('/d/dotnet',Path('/t'),Path('/r/nuget.config')),
            ['/d/dotnet','tool','install','fable','--version',self.ns['TOOLS']['fable'],'--tool-path','/t/fable','--configfile','/r/nuget.config'])
        # The generated products keep their own discipline: their locks pin the nuget.org archive.
        restore=[l for l in CHECKER.read_text().splitlines() if l.strip().startswith('"$DOTNET_HOST_PATH" restore ')]
        self.assertEqual(len(restore),1);self.assertIn('-p:DisableImplicitLibraryPacksFolder=true',restore[0])

    def test_prepare_inputs_runs_exactly_the_shared_argv_and_sdk(self):
        body=self.body('prepare_inputs')
        for call in ('provision_sdk(get,tools,deadline)','closed_nuget_config(root)','execute(fable_install_argv(dotnet,tools,config),root,env)',
                'execute(provider_tool_restore_argv(dotnet,project,config),root,env)','execute(provider_tool_build_argv(dotnet,project),root,env)'):
            with self.subTest(call=call):self.assertEqual(body.count(call),1)
        self.assertNotIn('"restore"',body);self.assertNotIn('"build"',body);self.assertNotIn('releases.json',body)
        self.assertLess(body.index('provision_sdk('),body.index('provision_node_npm('))

    def test_control_job_always_runs_the_exact_commands(self):
        workflow=RESTORE_CONTROL_WORKFLOW.read_text()
        on=workflow[workflow.index('\non:\n'):workflow.index('\npermissions:')]
        self.assertIn('  pull_request:\n',on);self.assertNotIn('paths',on);self.assertNotIn('branches-ignore',on)
        jobs=workflow[workflow.index('\njobs:\n'):]
        self.assertNotRegex(jobs,r'\n    if:');self.assertNotIn('continue-on-error',jobs)
        self.assertIn('python3 -I tests/composition/fable-game/installed-c-restore-control.py "$RUNNER_TEMP/installed-c-restore-control"',jobs)
        self.assertIn('permissions:\n  contents: read\n',workflow);self.assertNotIn('secrets.',workflow)
        control=RESTORE_CONTROL.read_text()
        for name in ('fresh_environment','acquirer','download','provision_sdk','closed_nuget_config','fable_install_argv','provider_tool_restore_argv','provider_tool_build_argv'):
            with self.subTest(name=name):self.assertIn("caller['"+name+"']",control)
        self.assertNotIn("'restore'",control);self.assertNotIn('DisableImplicitLibraryPacksFolder',control)

    def test_control_extracts_the_checker_lines_verbatim(self):
        spec=importlib.util.spec_from_file_location('restore_control',RESTORE_CONTROL)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        lines=module.checker_lines();checker=CHECKER.read_text().splitlines()
        for prefix,rows in lines.items():
            for row in rows:
                with self.subTest(row=row):self.assertIn(row,[l.strip() for l in checker])
        self.assertEqual(len(lines['"$DOTNET_HOST_PATH" new ']),3)
        self.assertIn('-p:FsGgWasmPolicyExample="$enabled"',lines['"$DOTNET_HOST_PATH" restore '][0])


class ObservabilityTests(unittest.TestCase):
    """Installed-C run 2 precondition (FS-GG/.github#4710 comment 6352823677): per-group cgroup high-water,
    per-phase wall-clock, and bounded retries on the checker's idempotent GETs. Recording only."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(os.path.realpath(self.temp.name))
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'observability_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.tool=self.root/'tool';self.tool.write_bytes(b'#!/bin/sh\nexit 0\n');self.tool.chmod(0o700)
        self.identities={};self.ns['bind_identity'](self.identities,str(self.tool),'verified-archive-member')
        self.droot=self.root/'cg/unit.service';self.leaf=self.droot/'fsgg-mg-0';self.leaf.mkdir(parents=True)

    def cg(self, directory, **files):
        for name,value in files.items():(directory/name.replace('_','.')).write_text(value)

    def run_group(self, owner):
        receipts=[];execute=self.ns['managed_executor'](owner,self.root,time.monotonic()+60,self.identities,'setup',receipts)
        try:execute([str(self.tool)],self.root,{'PATH':'/usr/bin'})
        except RuntimeError:pass
        return receipts[0],json.loads((self.root/'managed-receipts.json').read_text())[0]

    def test_group_and_unit_high_water_is_recorded_for_the_group(self):
        self.cg(self.droot,pids_peak='12\n',memory_peak='5000\n',memory_current='100\n',pids_events='max 1\n',memory_events='low 0\nhigh 0\nmax 3\noom 0\noom_kill 2\n')
        self.cg(self.leaf,pids_peak='0\n',pids_events='max 0\n')
        events={'poll':lambda:self.cg(self.droot,memory_current='4096\n'),
                'before-remove':lambda:(self.cg(self.leaf,pids_peak='37\n',pids_events='max 0\n'),
                    self.cg(self.droot,pids_peak='40\n',memory_peak='9000\n',pids_events='max 1\n',memory_events='low 0\nhigh 0\nmax 3\noom 1\noom_kill 3\n'))}
        entry,written=self.run_group(FakeOwner(cgroup=(self.droot,self.leaf),events=events))
        self.assertEqual(entry['status'],'succeeded');self.assertEqual(written['highWater'],entry['highWater'])
        high=entry['highWater']
        self.assertEqual(high['group'],{'pidsPeak':37,'pidsEventsMax':0,'memoryPeakBytes':None,'memoryEventsMax':None,'memoryEventsOomKill':None,
            'memoryCurrentBytes':None,'memoryAnonBytes':None})
        unit={k:v for k,v in high['unit'].items() if not k.startswith(('memoryCurrentBytesAt','memoryAnonBytesAt','memoryCurrentGrowth','memoryAnonGrowth','memoryCurrentSince','memoryAnonSince'))}
        self.assertEqual(unit,{'pidsPeakCumulative':40,'memoryPeakBytesCumulative':9000,'memoryCurrentMaxBytesSampled':4096,
            'pidsEventsMaxDelta':0,'memoryEventsMaxDelta':0,'memoryEventsOomKillDelta':1})
        self.assertEqual((high['polls'],high['errors']),(1,[]))

    def test_high_water_is_recorded_for_failed_groups_and_never_affects_custody(self):
        self.cg(self.droot,pids_events='max 0\n',memory_events='oom_kill 0\n')
        events={'before-remove':lambda:self.cg(self.droot,pids_events='max 4\n',memory_events='oom_kill 1\n')}
        entry,_=self.run_group(FakeOwner(outcome='failed',cgroup=(self.droot,self.leaf),events=events))
        self.assertEqual(entry['status'],'failed')
        self.assertEqual((entry['highWater']['unit']['pidsEventsMaxDelta'],entry['highWater']['unit']['memoryEventsOomKillDelta']),(4,1))

    def test_observer_never_raises_or_reads_outside_the_delegated_root(self):
        state,control=self.ns['high_water_observer']()
        outside=self.root/'elsewhere';outside.mkdir();(outside/'pids.peak').write_text('99\n')
        for event,context in [('after-birth',{'delegatedRoot':7}),('poll',{'delegatedRoot':str(self.root/'missing')}),
                ('poll',{'delegatedRoot':None}),('before-remove',{'delegatedRoot':str(self.droot),'leaf':str(outside)}),
                ('before-remove',{'delegatedRoot':str(self.droot),'leaf':str(self.droot)+'-sibling/x'}),('unknown',{})]+[('poll',{'delegatedRoot':str(self.root/'missing')})]*6:
            with self.subTest(event=event):control(event,context) # must not raise
        self.assertIsNone(state['group']);self.assertEqual(len(state['errors']),4)
        record=self.ns['high_water_record'](state);self.assertIsNone(record['group'])
        self.assertEqual(self.ns['high_water_record']({'unitBefore':{'pidsEventsMax':'x'},'unitAfter':{'pidsEventsMax':1}})['unit']['pidsEventsMaxDelta'],None)
        self.assertNotIn('open(os.path.join(droot,"memory.current"),"w',self.code);self.assertNotIn('write_text',ast.get_source_segment(self.code,
            next(n for n in ast.parse(self.code).body if isinstance(n,ast.FunctionDef) and n.name=='high_water_observer')))

    @unittest.skipUnless(OWNER_FILE,'set FSGG_MANAGED_GROUP_OWNER to the pinned owner file to check its hook events')
    def test_the_pinned_owner_offers_the_hook_events_used(self):
        source=Path(OWNER_FILE).read_text();self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),self.ns['OWNER']['sha256'])
        spec=importlib.util.spec_from_file_location('hook_owner_check',OWNER_FILE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        import inspect
        self.assertIn('control',inspect.signature(module.run).parameters)
        for event in ('after-birth','poll','before-remove'):self.assertIn("hook('"+event+"', context())",source)
        self.assertIn("'leaf': leaf, 'delegatedRoot': droot",source)
        self.assertIn("stage('hook', lambda: hook('before-remove', context()))",source) # every launched outcome

    def test_phase_wall_clock_is_recorded_on_pass_and_on_failure(self):
        case=InstalledAdmissionTests('test_admitted_sequence_runs_provisioning_custody_gate_and_27_case_installed_c');case.setUp()
        self.addCleanup(case.doCleanups);case.admit()
        summary=self.ns_run(case)
        timing=summary['timing']
        self.assertEqual(timing['budgetSeconds'],case.ns['INSTALLED_BUDGET'])
        for key in ('setupStartedAt','setupSeconds','installedStartedAt','installedSeconds','checkerSeconds','sequenceSeconds'):
            with self.subTest(key=key):self.assertIsInstance(timing[key],float)
        self.assertEqual(set(timing['families']),{'chromium','firefox','webkit'})
        for row in timing['families'].values():self.assertEqual(set(row),{'listSeconds','testSeconds'})
        self.assertEqual(summary['installedC']['timing'],timing)
        root=case.root/'rt/wasm-installed-c'
        self.assertEqual(json.loads((root/'installed-run.json').read_text())['timing']['sequenceSeconds'],timing['sequenceSeconds'])
        self.assertTrue(all('highWater' in r for r in json.loads((root/'managed-receipts.json').read_text())))
        failing=InstalledAdmissionTests('test_admitted_sequence_runs_provisioning_custody_gate_and_27_case_installed_c');failing.setUp()
        self.addCleanup(failing.doCleanups);owner=failing.admit();owner.outcome='failed'
        with self.assertRaises((RuntimeError,ValueError)):failing.ns['admitted_installed_sequence'](failing.environ(),time.monotonic())
        stopped=json.loads((failing.root/'rt/wasm-installed-c/installed-run.json').read_text())['timing']
        self.assertIn('sequenceSeconds',stopped);self.assertIn('setupSecondsUntilStop',stopped);self.assertNotIn('setupSeconds',stopped)

    def ns_run(self, case):
        return case.ns['admitted_installed_sequence'](case.environ(),time.monotonic())

    def test_checker_gets_are_bounded_retried_and_still_hash_checked(self):
        text=CHECKER.read_text();start=text.index('if [[ "$mode" == wasm ]]; then\n  : "${DOTNET_HOST_PATH:?')
        block=text[start:text.index('\n  exit 0\nfi\n',start)]
        curls=[l.strip() for l in block.splitlines() if l.strip().startswith('curl ')]
        self.assertEqual(len(curls),2);self.assertNotIn('--retry 0',block)
        for line,target in zip(curls,('-o "$archive"','-o "$descriptor"')):
            with self.subTest(target=target):
                self.assertIn('--retry 3 --retry-all-errors --retry-max-time 60 --max-time 15 ',line);self.assertTrue(line.endswith(target))
                self.assertIn('--fail',line);self.assertIn('--max-filesize',line)
                for verb in (' -X',' --request',' -d ',' --data',' -T ',' --upload-file',' -F ',' --form',' -I ',' --head',' -G '):self.assertNotIn(verb,line) # GET only
                for resume in (' -C ',' -C-',' --continue-at'):self.assertNotIn(resume,line) # no resume: a retry restarts the file
        check=[l for l in block.splitlines() if 'reference-publication-check' in l];self.assertEqual(len(check),1)
        for flag in ('--archive "$archive"','--descriptor "$descriptor"','--sha256 "$sha"','--descriptor-sha256 "$descriptor_sha"'):self.assertIn(flag,check[0])
        self.assertLess(block.index('-o "$descriptor"'),block.index('reference-publication-check'))


class ObservabilityFollowUpTests(unittest.TestCase):
    """Admitter follow-ups on #744: memory at birth/removal with deltas, read-only observation,
    installed-phase failure timing, and the bounded tag read."""
    setUp=ObservabilityTests.setUp;cg=ObservabilityTests.cg;run_group=ObservabilityTests.run_group
    def test_memory_growth_and_change_since_the_previous_group(self):
        def stat(anon):return 'anon '+str(anon)+'\nfile 7\n'
        self.cg(self.droot,memory_current='1000\n',memory_stat=stat(300))
        steps=iter([('1000\n',stat(300)),('5000\n',stat(2300)),('1500\n',stat(400)),('2600\n',stat(900))])
        def set_next():
            current,anon=next(steps);self.cg(self.droot,memory_current=current,memory_stat=anon)
        owner=FakeOwner(cgroup=(self.droot,self.leaf),events={'after-birth':set_next,'before-remove':set_next})
        receipts=[];execute=self.ns['managed_executor'](owner,self.root,time.monotonic()+60,self.identities,'setup',receipts)
        execute([str(self.tool)],self.root,{'PATH':'/usr/bin'})
        later=self.ns['managed_executor'](owner,self.root,time.monotonic()+60,self.identities,'installed',receipts) # a new phase executor
        later([str(self.tool)],self.root,{'PATH':'/usr/bin'})
        first,second=(r['highWater']['unit'] for r in receipts)
        self.assertEqual((first['memoryCurrentBytesAtBirth'],first['memoryCurrentBytesAtRemove'],first['memoryCurrentGrowthBytes']),(1000,5000,4000))
        self.assertEqual((first['memoryAnonBytesAtBirth'],first['memoryAnonBytesAtRemove'],first['memoryAnonGrowthBytes']),(300,2300,2000))
        self.assertIsNone(first['memoryCurrentSincePreviousGroupBytes']);self.assertIsNone(first['memoryAnonSincePreviousGroupBytes'])
        self.assertEqual((second['memoryCurrentSincePreviousGroupBytes'],second['memoryAnonSincePreviousGroupBytes']),(1500-5000,400-2300))
        self.assertEqual((second['memoryCurrentGrowthBytes'],second['memoryAnonGrowthBytes']),(1100,500))

    def test_observation_only_reads_read_only_cgroup_files(self):
        self.cg(self.droot,pids_peak='3\n',memory_peak='10\n',memory_current='5\n',memory_stat='anon 4\n',pids_events='max 0\n',memory_events='oom_kill 0\n')
        self.cg(self.leaf,pids_peak='2\n',pids_events='max 0\n')
        def restore():
            for d in (self.leaf,self.droot):
                d.chmod(0o755)
                for f in d.iterdir():
                    if f.is_file():f.chmod(0o644)
        self.addCleanup(restore)
        for d in (self.leaf,self.droot):
            for f in d.iterdir():
                if f.is_file():f.chmod(0o444)
            d.chmod(0o555)
        state,control=self.ns['high_water_observer']()
        for event in ('after-birth','poll','before-retire','before-remove','after-cleanup'):control(event,{'delegatedRoot':str(self.droot),'leaf':str(self.leaf)})
        self.assertEqual(state['errors'],[]);self.assertEqual(state['group']['pidsPeak'],2);self.assertEqual(state['unitAfter']['memoryAnonBytes'],4)
        tree=ast.parse(self.code)
        for name in ('cgroup_counters','high_water_observer'):
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            opens=[c for c in ast.walk(fn) if isinstance(c,ast.Call) and getattr(c.func,'id',None)=='open']
            self.assertTrue(opens)
            for call in opens:
                with self.subTest(function=name,line=call.lineno):
                    self.assertEqual(len(call.args),1);self.assertEqual(call.keywords,[]) # default mode "r" only
            for call in ast.walk(fn):
                if isinstance(call,ast.Attribute):self.assertNotIn(call.attr,('write','write_text','write_bytes','unlink','rmdir','mkdir','chmod','kill'))

    def failing_installed_run(self, fail_on):
        case=InstalledAdmissionTests('test_admitted_sequence_runs_provisioning_custody_gate_and_27_case_installed_c');case.setUp()
        self.addCleanup(case.doCleanups);owner=case.admit();owner.fail_on=fail_on
        with self.assertRaises(RuntimeError):case.ns['admitted_installed_sequence'](case.environ(),time.monotonic())
        return json.loads((case.root/'rt/wasm-installed-c/installed-run.json').read_text())

    def test_installed_phase_failures_still_record_installed_and_checker_time(self):
        checker=lambda profile:'failed' if any(a.endswith('verify-fable-reference-public.sh') for a in profile['argv']) else None
        run=self.failing_installed_run(checker);timing=run['timing']
        self.assertEqual(run['disposition'],'failed')
        for key in ('setupSeconds','installedStartedAt','installedSeconds','checkerSeconds','sequenceSeconds'):
            with self.subTest(failure='checker',key=key):self.assertIsInstance(timing[key],float)
        self.assertNotIn('families',timing)
        browser=lambda profile:'failed' if len(profile['argv'])>2 and profile['argv'][2]=='test' and '--list' not in profile['argv'] else None
        timing=self.failing_installed_run(browser)['timing']
        for key in ('installedSeconds','checkerSeconds','sequenceSeconds'):
            with self.subTest(failure='first browser test',key=key):self.assertIsInstance(timing[key],float)
        self.assertEqual(set(timing['families']['chromium']),{'listSeconds','testSeconds'})
        self.assertNotIn('testSeconds',timing['families'].get('firefox',{}))

    def test_refused_groups_record_no_hook_reading(self):
        self.cg(self.droot,pids_peak='3\n')
        entry,_=self.run_group(FakeOwner(outcome='refused',cgroup=(self.droot,self.leaf)))
        self.assertEqual(entry['status'],'refused')
        self.assertEqual((entry['highWater']['group'],entry['highWater']['polls'],entry['highWater']['errors']),(None,0,[]))
        self.assertIsNone(entry['highWater']['unit']['pidsPeakCumulative'])

    def test_tag_read_is_bounded_and_retried_and_still_compared(self):
        text=CHECKER.read_text();start=text.index('if [[ "$mode" == wasm ]]; then\n  : "${DOTNET_HOST_PATH:?')
        block=text[start:text.index('\n  exit 0\nfi\n',start)]
        reads=[l.strip() for l in block.splitlines() if 'git ls-remote' in l]
        self.assertEqual(len(reads),1);self.assertTrue(reads[0].startswith('if refs_text="$(timeout -k 5 20 git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git '))
        self.assertIn('  for attempt in 1 2 3; do\n',block);self.assertIn("sleep $((attempt * 5))",block)
        self.assertIn("[[ \"$attempt\" -lt 3 ]] || { echo 'WASM public tag read failed after 3 bounded attempts' >&2; exit 1; }",block)
        self.assertLess(block.index('mapfile -t remote_refs <<<"$refs_text"'),block.index("WASM public immutable tag mismatch"))
        self.assertNotIn('push',reads[0]);self.assertNotIn('git fetch',block);self.assertNotIn('git clone',block)


WASM_EXAMPLE=HERE.parents[2]/'templates/fs-gg-fable-game/SvgFoundation/Examples/Wasm'
WASM_SDK_SHA='090658bd29c79500ed6f3f3defe89a14f7b8330b39586cd01880429258a99cb2'

class WasmReceiverPinTests(unittest.TestCase):
    """The receiver selects FS.GG.Wasm 0.7.0 (FS-GG/FS.GG.Game#727) coherently across template source,
    locks, guest build, asset materialization, the installed-C acquisition and the checker."""
    def test_receiver_pins_cohere_on_0_7_0(self):
        fsproj=(WASM_EXAMPLE.parents[1]/'SvgFoundation.fsproj').read_text()
        self.assertEqual(re.findall(r'Include="(FS\.GG\.Wasm\.[A-Za-z]+)" Version="([^"]+)"',fsproj),[('FS.GG.Wasm.Contracts','[0.7.0]'),('FS.GG.Wasm.Browser','[0.7.0]')])
        lock=json.loads((WASM_EXAMPLE/'packages.lock.json').read_text())
        rows={k:v for deps in lock['dependencies'].values() for k,v in deps.items() if k.startswith('FS.GG.Wasm.')}
        self.assertEqual({k:(v['requested'],v['resolved']) for k,v in rows.items()},{'FS.GG.Wasm.Browser':('[0.7.0, 0.7.0]','0.7.0'),'FS.GG.Wasm.Contracts':('[0.7.0, 0.7.0]','0.7.0')})
        # NuGet content hashes of the nuget.org 0.7.0 packages (signature excluded) and their dependency closure.
        self.assertEqual({k:v['contentHash'] for k,v in rows.items()},{
            'FS.GG.Wasm.Browser':'AG/nCETlW0BBTGRbb36RgOFtOzQlH4RWhIdVL9ReTs+w71pu2uCJhLPb6MmZyj5LZcBN0eHKk8eGlpCB9rZIQg==',
            'FS.GG.Wasm.Contracts':'39TdAGF23F03t4s16g9PVdhA/Gq5v1kbIbsMe1NsqIXREW/Wt65podyGXRBg/9iUJ7mlCouREmVa09+uwBK4ZA=='})
        self.assertEqual(rows['FS.GG.Wasm.Browser']['dependencies'],{'FS.GG.Wasm.Contracts':'[0.7.0]','FSharp.Core':'10.1.302'})
        self.assertEqual(rows['FS.GG.Wasm.Contracts']['dependencies'],{'FSharp.Core':'10.1.302'})
        self.assertIn('name = "fsgg-wasm-guest"\nversion = "0.7.0"',(WASM_EXAMPLE/'guest/rust/Cargo.lock').read_text())
        guests=(WASM_EXAMPLE/'build-guests.sh').read_text()
        self.assertEqual(guests.count(WASM_SDK_SHA),2);self.assertIn('sdk="$work/fsgg-wasm-sdk-0.7.0"',guests)
        materialize=(WASM_EXAMPLE/'materialize-assets.py').read_text()
        self.assertIn('modules.get("sdkSha256") != "'+WASM_SDK_SHA+'"',materialize)
        # The restore-path (nuget.org, repository-countersigned) Browser archive, not the producer original 1d5e9df2.
        self.assertIn('PACKAGE_SHA256 = "bfc28ac97df243aedaae8d913ff555967039b8aef824c48db970d50c14d198cd"',materialize)
        self.assertEqual(re.findall(r'FS\.GG\.Wasm\.\w+/([0-9.]+)',materialize),['0.7.0']*4)
        text,code=actual_hosted_code();ns={'__name__':'pins'};exec(compile(code,'actual-hosted-workflow','exec'),ns)
        self.assertEqual(ns['ENDPOINTS']['guest'][:2],('https://github.com/FS-GG/FS.GG.Game/releases/download/wasm/v0.7.0/fsgg-wasm-sdk-0.7.0.tar.gz',WASM_SDK_SHA))
        self.assertIn("refs['FS.GG.Wasm.Contracts']==refs['FS.GG.Wasm.Browser']=='[0.7.0]'",CHECKER.read_text())
        for stale in ('8091df6824981c0c37131524ffbcbae9bb8b36f672a20edc2efaddd35664f8c8','fsgg-wasm-sdk-0.3.0'):
            for path in (WASM_EXAMPLE/'build-guests.sh',WASM_EXAMPLE/'materialize-assets.py',WORKFLOW,CHECKER):
                with self.subTest(stale=stale,path=path.name):self.assertNotIn(stale,path.read_text())

    def test_installed_c_is_fenced_while_the_release_pins_are_split(self):
        # The guest SDK and checker already select 0.7.0; published 0.19.2 carries 0.3.0. Any admission
        # before the release pins move would spend a single-use run, so it is refused here.
        tree=ast.parse(actual_hosted_code()[1])
        literal=lambda name:next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(x,'id',None)==name for x in n.targets))
        if literal('TEMPLATE_VERSION')=='0.19.2':
            self.assertIsNone(literal('INSTALLED_ADMISSION'),'release pins still 0.19.2: move them with the 0.7.0 template release first')

    def world(self, bundle=None, build=None, extra=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        foundation=root/'SvgFoundation';(foundation/'obj').mkdir(parents=True)
        prefix='contentFiles/any/any/_content/FS.GG.Wasm.Browser/'
        bundle=bundle if bundle is not None else b'var x = 1;\nexport function run() { return x; }\n'
        output={'path':'module-worker.mjs','bytes':len(bundle),'sha256':hashlib.sha256(bundle).hexdigest()}
        build=build if build is not None else {'schema':'fsgg.wasm.worker-build/1','output':output,'composition':{'outputFiles':1,'externalImports':0}}
        members={'module-worker.mjs':bundle,'worker-client.mjs':b'export const client = () => new Worker(new URL("module-worker.mjs", base));\n',
                 'worker-build.json':json.dumps(build).encode(),'policy/Host.js':b'export const host = 1;\n',**(extra or {})}
        package=root/'packages/fs.gg.wasm.browser/0.7.0';package.mkdir(parents=True)
        archive=package/'fs.gg.wasm.browser.0.7.0.nupkg'
        with zipfile.ZipFile(archive,'w') as z:
            for name,body in members.items():z.writestr(prefix+name,body)
        for name,body in members.items():
            cached=package/(prefix+name);cached.parent.mkdir(parents=True,exist_ok=True);cached.write_bytes(body)
        (foundation/'obj/project.assets.json').write_text(json.dumps({'packageFolders':{str(root/'packages'):{}},'libraries':{
            'FS.GG.Wasm.Contracts/0.7.0':{'type':'package','path':'fs.gg.wasm.contracts/0.7.0'},'FS.GG.Wasm.Browser/0.7.0':{'type':'package','path':'fs.gg.wasm.browser/0.7.0'}}}))
        guest=foundation/'Examples/Wasm/guest';(guest/'rust/src').mkdir(parents=True);(guest/'policy.c').write_text('int x;');(guest/'rust/src/lib.rs').write_text('fn x(){}')
        guests=foundation/'obj/wasm-policy-guests';guests.mkdir()
        modules={}
        for name in ('c-normal.wasm','c-malformed.wasm','c-trap.wasm','c-loop.wasm','rust-normal.wasm'):
            (guests/name).write_bytes(name.encode());modules[name]=hashlib.sha256(name.encode()).hexdigest()
        (guests/'modules.json').write_text(json.dumps({'sdkSha256':WASM_SDK_SHA,'cSourceSha256':hashlib.sha256(b'int x;').hexdigest(),
            'rustSourceSha256':hashlib.sha256(b'fn x(){}').hexdigest(),'modules':modules}))
        spec=importlib.util.spec_from_file_location('materialize_fixture',WASM_EXAMPLE/'materialize-assets.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.PACKAGE_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest() # fixture archive bytes, not the public ones
        return module,foundation

    def test_self_contained_bundled_worker_is_materialized_and_recorded(self):
        module,foundation=self.world();module.materialize(foundation)
        manifest=json.loads((foundation/'obj/wasm-policy-public/wasm-package-assets.json').read_text())
        self.assertEqual(manifest['package'],'FS.GG.Wasm.Browser/0.7.0');self.assertEqual(manifest['productionReachable'],['module-worker.mjs','worker-client.mjs'])
        self.assertEqual(manifest['workerBuild']['composition'],{'outputFiles':1,'externalImports':0})
        self.assertTrue((foundation/'obj/wasm-policy-public/_content/FS.GG.Wasm.Browser/policy/Host.js').is_file()) # unused library modules still copied

    def test_worker_module_graph_or_build_drift_refuses(self):
        cases={
            'static import':(b'import { host } from "./policy/Host.js";\nexport const x = host;\n',None,'not self-contained'),
            'mid-line import':(b'var q=1;import{x}from"./policy/Host.js";\n',None,'not self-contained'),
            'dynamic import':(b'export const x = () => import("./policy/Host.js");\n',None,'not self-contained'),
            'commented dynamic import':(b'export const x = () => import /*x*/ ("./policy/Host.js");\n',None,'not self-contained'),
            'classic script':(b'importScripts("policy/Host.js");\n',None,'not self-contained'),
            'nested worker':(b'export const w = new Worker(new URL("./policy/Host.js", self.location));\n',None,'not self-contained'),
            'fetched code':(b'fetch("./policy/Host.js").then(r => r.text()).then(t => new Function(t)());\n',None,'not self-contained'),
            'import.meta':(b'export const u = import.meta.url;\n',None,'not self-contained'),
            'eval':(b'eval("1");\n',None,'not self-contained'),
        }
        for label,(bundle,build,message) in cases.items():
            with self.subTest(label=label):
                module,foundation=self.world(bundle=bundle)
                with self.assertRaisesRegex(ValueError,message):module.materialize(foundation)
        good=b'export const ok = 1;\n'
        drift={'wrong sha':{'schema':'fsgg.wasm.worker-build/1','output':{'path':'module-worker.mjs','bytes':len(good),'sha256':'0'*64},'composition':{'outputFiles':1,'externalImports':0}},
               'external imports':{'schema':'fsgg.wasm.worker-build/1','output':{'path':'module-worker.mjs','bytes':len(good),'sha256':hashlib.sha256(good).hexdigest()},'composition':{'outputFiles':1,'externalImports':2}},
               'several outputs':{'schema':'fsgg.wasm.worker-build/1','output':{'path':'module-worker.mjs','bytes':len(good),'sha256':hashlib.sha256(good).hexdigest()},'composition':{'outputFiles':3,'externalImports':0}}}
        for label,build in drift.items():
            with self.subTest(label=label):
                module,foundation=self.world(bundle=good,build=build)
                with self.assertRaisesRegex(ValueError,'differs from its build record'):module.materialize(foundation)
        module,foundation=self.world(bundle=good,extra={'worker-client.mjs':b'import "./policy/Host.js";\n'})
        with self.assertRaisesRegex(ValueError,'Production Worker graph differs'):module.materialize(foundation)
        module,foundation=self.world(bundle=good,extra={'worker-client.mjs':b'export const later = () => import("./policy/Host.js");\n'})
        with self.assertRaisesRegex(ValueError,'client loads further code'):module.materialize(foundation)
        # Quoted text is not code: a WASM import-section name in a string is accepted.
        module,foundation=self.world(bundle=b'const section = "import";\nexport const s = section;\n');module.materialize(foundation)


if __name__ == '__main__': unittest.main()
