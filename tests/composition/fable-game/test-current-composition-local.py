#!/usr/bin/env python3
"""Pure controls for the local ADR-0096 DOM-case runner; no SDK, browser, network or container runs."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('local_runner',HERE/'current-composition-local.py')
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
O=L.observations


class Controls(unittest.TestCase):
    def test_declared_tools_and_fable_identity_come_from_the_actual_hosted_caller(self):
        tools=L.pinned_tools()
        self.assertEqual((tools['sdk'],tools['node'],tools['npm'],tools['fable'],tools['playwright']),('10.0.401','24.20.0','11.19.0','5.18.0','1.63.0'))
        self.assertRegex(L.fable_sha(),r'^[0-9a-f]{64}$')

    def test_child_environment_is_closed_and_carries_no_credential(self):
        ambient={'PATH':'/usr/bin','GH_TOKEN':'secret','GITHUB_TOKEN':'secret','NUGET_API_KEY':'secret','HOME':'/home/real'}
        with tempfile.TemporaryDirectory() as tmp,mock.patch.dict(os.environ,ambient,clear=False):
            root=Path(tmp)
            env=L.closed_environment(root,{'PATH':'/usr/bin','environ':os.environ,'cpus':3,'platform':'ubuntu24.04-x64'})
            self.assertTrue(set(env).isdisjoint(O.CREDENTIAL_VARIABLES))
            self.assertNotIn('secret',' '.join(env.values()))
            self.assertEqual(env['HOME'],str(root/'home'));self.assertEqual(env['TMPDIR'],str(root/'tmp'))
            self.assertEqual(env['DOTNET_PROCESSOR_COUNT'],'3');self.assertEqual(env['PLAYWRIGHT_HOST_PLATFORM_OVERRIDE'],'ubuntu24.04-x64')
            self.assertIsNone(O.check_admission(env))
            # Every private store lives under the fresh root, never a shared cache.
            for name in ('NUGET_PACKAGES','NUGET_HTTP_CACHE_PATH','npm_config_cache','PLAYWRIGHT_BROWSERS_PATH','DOTNET_CLI_HOME'):
                self.assertTrue(Path(env[name]).is_relative_to(root),name)

    def test_container_phase_has_no_network_read_only_tools_and_exact_cpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            family_env={'FsGgExternalReferenceCandidate':'true','FsGgWasmPolicyExample':'false','PLAYWRIGHT_BROWSER_FAMILY':'webkit'}
            argv=L.container_prefix('localhost/fixture:1',root,2,family_env)
            self.assertEqual(argv[:3],['podman','run','--rm']);self.assertIn('--network=none',argv)
            self.assertEqual(argv[-2:],['localhost/fixture:1','/entry.sh'])
            self.assertTrue(any(a.startswith('--cpuset-cpus=') for a in argv))
            mounts=[argv[i+1] for i,a in enumerate(argv) if a=='-v']
            self.assertEqual(sum(m.endswith(':/opt/dotnet:ro') for m in mounts),1);self.assertEqual(sum(m.endswith(':/opt/node:ro') for m in mounts),1)
            self.assertTrue(any(m.endswith(':/receiver') for m in mounts) and any(m.endswith(':/browsers') for m in mounts))
            self.assertIn('PLAYWRIGHT_BROWSER_FAMILY=webkit',argv);self.assertIn('FsGgExternalReferenceCandidate=true',argv)
            self.assertFalse([a for a in argv if re.search(r'TOKEN|KEY|SECRET',a)])
            entry=root/'container-entry.sh';self.assertEqual(entry.stat().st_mode&0o777,0o700)
            self.assertIn('cd /receiver/Browser.Tests',entry.read_text())

    def test_refusals_precede_any_effect(self):
        before=os.sched_getaffinity(0)
        with tempfile.TemporaryDirectory() as tmp:
            fresh=str(Path(tmp)/'fresh')
            for argv,message in ((['--root',fresh,'--families','chromium,opera'],'closed browser families'),
                                 (['--root',fresh,'--families','chromium,chromium'],'closed browser families'),
                                 (['--root',fresh,'--cpus','4'],'at most 3 CPUs'),
                                 (['--root',tmp],'fresh'),
                                 (['--root',str(L.WORKSPACE/'.fresh-inside-checkout')],'outside the checkout')):
                with self.subTest(argv=argv),self.assertRaisesRegex(ValueError,message):L.main(argv)
            self.assertFalse(Path(fresh).exists())
        self.assertEqual(os.sched_getaffinity(0),before)

    def test_runner_is_not_wired_into_any_hosted_workflow_or_admission(self):
        text=(HERE/'current-composition-local.py').read_text()
        self.assertIn("'hostedRuntimeAdmission': False",text);self.assertIn("'whole4818Acceptance': False",text)
        self.assertIn("'durableSaveAcceptance': False",text);self.assertIn("'actualAT': False",text)
        self.assertIn("'actualProducerCustodyReadback': False",text);self.assertIn("'installedAcceptance': False",text)
        for workflow in (HERE.parents[2]/'.github/workflows').glob('*.yml'):
            # Only the pure controls run in CI; no workflow executes the runner or the image recipe.
            self.assertIsNone(re.search(r'(?:python3|bash)[^\n]*(?<!test-)current-composition-local(?:\.py|-image\.sh)',workflow.read_text()),workflow.name)

    def test_local_runner_cannot_open_the_hosted_receiver(self):
        workflow=(HERE.parents[2]/'.github/workflows/current-reference-composition.yml').read_text()
        self.assertIn('ADMISSION=None',workflow);self.assertIn('if: ${{ false }}',workflow)


if __name__=='__main__':unittest.main(verbosity=2)
