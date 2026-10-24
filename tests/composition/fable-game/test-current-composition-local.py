#!/usr/bin/env python3
"""Pure controls for the local ADR-0096 DOM-case runner; no SDK, browser, network or container runs."""
import hashlib
import importlib.util
import json
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
            self.assertTrue(any(a.startswith('--cpuset-cpus=') for a in argv));self.assertIn('--memory=8g',argv)
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
            # Only path triggers and the pure controls mention the runner; no workflow line executes it or the image recipe.
            for line in workflow.read_text().splitlines():
                if 'current-composition-local' in line and 'test-current-composition-local' not in line:
                    self.assertTrue(line.lstrip().startswith("- 'tests/composition/fable-game/"),workflow.name+': '+line)

    def test_hosted_original_operation_route_is_retired(self):
        self.assertFalse((HERE.parents[2]/'.github/workflows/current-reference-composition.yml').exists())
        self.assertFalse((HERE/'current-composition-managed.py').exists())


    # --- orchestration: the decisive sequence, with every process, download and git read faked ---------------------

    PLAN={'selection':{'externalReference':True,'wasmPolicyExample':False},
          'template':{'id':'Fixture.Template','version':'1.0.0','sha256':'t'*64},
          'rendering':{'version':'2.0.0','sourceCommit':'c'*40,'packages':[{'id':'Fixture.UI','sha256':'u'*64}]},
          'browsers':{'families':['chromium'],'workers':1,'retries':0,'cases':[{'file':'one.spec.ts','suite':[],'title':'case one'}]}}

    def run_main(self,root,*,listing_title='case one',report_status='expected',report_skipped=0,dirty='',extra=(),env=None,node='v24.20.0',stage='source-passed'):
        """Drive main() with fake processes; returns the recorded child calls."""
        plan=self.PLAN;calls=[];tests=root/'product/complete/Browser.Tests'
        def spec(title,results):
            return {'file':'one.spec.ts','title':title,'ok':True,'tests':[{'projectName':'chromium','status':report_status,'results':results}]}
        listing={'suites':[{'title':'one.spec.ts','specs':[spec(listing_title,[])]}]}
        report={'stats':{'expected':1,'unexpected':0,'skipped':report_skipped,'flaky':0},
                'suites':[{'title':'one.spec.ts','specs':[spec('case one',[{'status':'passed','retry':0}])]}]}
        def fake_run(argv,cwd,child_env,log,timeout):
            argv=[str(a) for a in argv];calls.append((argv,dict(child_env)))
            if argv[:3]==['dotnet','tool','install']:
                folder=root/'tools/fable';folder.mkdir(parents=True);(folder/'Fable.dll').write_bytes(b'fixture fable core')
            elif argv[0]=='bash':
                (root/'product').mkdir(exist_ok=True)
                (root/'product/current-source-stage.json').write_text(json.dumps({'disposition':stage,'browserExecuted':False}))
                for name in ('playwright','@playwright/test'):
                    (tests/'node_modules'/name).mkdir(parents=True)
                    (tests/'node_modules'/name/'cli.js').write_text('')
                (tests/'node_modules/playwright/package.json').write_text(json.dumps({'version':'1.63.0'}))
            elif '--workers=%d'%plan['browsers']['workers'] in argv:
                (tests/'test-results').mkdir(parents=True,exist_ok=True);(tests/'test-results/browser.json').write_text(json.dumps(report))
            return 0.1
        def fake_output(argv,**kwargs):
            argv=[str(a) for a in argv]
            if argv[:3]==['podman','image','inspect']:return 'sha256:fixtureimage\n'
            if argv[0]=='node':return node+'\n'
            if argv[0]=='npm':return '11.19.0\n'
            if argv[:2]==['dotnet','--version']:return '10.0.401\n'
            if argv[0]=='dotnet':return json.dumps(plan)
            raise AssertionError(argv)
        def fake_fetch(url,expected,maximum,destination):destination.write_bytes(b'archive')
        def fake_subprocess_run(argv,**kwargs):
            calls.append(([str(a) for a in argv],dict(kwargs['env'])))
            return subprocess.CompletedProcess(argv,0,stdout=json.dumps(listing),stderr='')
        def fake_git(*args):return dirty if args[0]=='status' else ('a'*40 if args[1]=='HEAD' else 'b'*40)
        build_core=root/'validator-artifacts/bin/FS.GG.Templates.ProviderTool/release/FS.GG.Templates.ProviderTool.dll'
        def build_then_run(argv,cwd,child_env,log,timeout):
            if str(argv[1])=='build':build_core.parent.mkdir(parents=True);build_core.write_bytes(b'owner')
            return fake_run(argv,cwd,child_env,log,timeout)
        patches=[mock.patch.object(L,'run',build_then_run),mock.patch.object(L,'fetch',fake_fetch),mock.patch.object(L,'git',fake_git),
                 mock.patch.object(L,'fable_sha',lambda:hashlib.sha256(b'fixture fable core').hexdigest()),
                 mock.patch.object(L.subprocess,'check_output',fake_output),mock.patch.object(L.subprocess,'run',fake_subprocess_run),
                 mock.patch.object(L.os,'sched_setaffinity',lambda *a:None),mock.patch.object(L,'container_prefix',lambda image,*a:['podman','run','--rm',image]),mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'',**(env or {})},clear=False)]
        for patch in patches:patch.start()
        try:
            try:L.main(['--root',str(root),'--cpus','1','--families','chromium',*extra])
            finally:
                for patch in reversed(patches):patch.stop()
        finally:
            self.calls=calls
        return calls

    def fresh_root(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);return Path(tmp.name)/'run'

    def test_sequence_lists_then_runs_each_family_with_the_typed_selection_and_no_ambient_credential(self):
        root=self.fresh_root()
        calls=self.run_main(root,env={'GH_TOKEN':'secret','GITHUB_TOKEN':'secret','GITHUB_ACTIONS':''})
        verbs=[argv[1] if argv[0] in ('dotnet','node') else argv[0] for argv,_ in calls]
        self.assertEqual(verbs[:3],['build','tool','bash'])  # typed owner, independent Fable, then the source stage
        listing=[c for c in calls if '--list' in c[0]];run=[c for c in calls if '--workers=1' in c[0]]
        self.assertEqual((len(listing),len(run)),(1,1));self.assertLess(calls.index(listing[0]),calls.index(run[0]))
        self.assertIn('--retries=0',run[0][0])
        for _,child_env in listing+run:
            self.assertEqual((child_env['FsGgExternalReferenceCandidate'],child_env['FsGgWasmPolicyExample'],child_env['PLAYWRIGHT_BROWSER_FAMILY']),('true','false','chromium'))
        for argv,child_env in calls:
            self.assertTrue(set(child_env).isdisjoint(O.CREDENTIAL_VARIABLES),argv[:2])
        summary=json.loads((root/'local-summary.json').read_text())
        self.assertEqual((summary['disposition'],summary['runtimeCases'],summary['dirty']),('dom-observed-local-reference-only',1,False))
        self.assertEqual(summary['families']['chromium'],{'passed':1,'retries':0,'skipped':0,'reportSha256':summary['families']['chromium']['reportSha256']})
        self.assertEqual((summary['playwrightVersion'],summary['head'],summary['tree']),('1.63.0','a'*40,'b'*40))
        for flag in ('hostedRuntimeAdmission','installedAcceptance','actualProducerCustodyReadback','durableSaveAcceptance','actualAT','whole4818Acceptance'):
            self.assertIs(summary[flag],False)

    def test_wrong_listing_or_unclean_report_refuses_before_or_after_the_run_and_records_the_first_cause(self):
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'listing identities'):self.run_main(root,listing_title='another case')
        self.assertFalse([c for c in self.calls if '--workers=1' in c[0]],'no case runs after a wrong listing')
        summary=json.loads((root/'local-summary.json').read_text())
        self.assertEqual(summary['disposition'],'failed');self.assertIn('listing identities',summary['firstCause'])
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'outcomes differ'):self.run_main(root,report_skipped=1)
        self.assertEqual(json.loads((root/'local-summary.json').read_text())['disposition'],'failed')
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'status differs'):self.run_main(root,report_status='unexpected')

    def test_container_launch_passes_only_the_runtime_environment_never_a_credential(self):
        root=self.fresh_root()
        calls=self.run_main(root,extra=['--container','localhost/fixture:1'],env={'GH_TOKEN':'secret','GITHUB_TOKEN':'secret','GITHUB_ACTIONS':'','ANTHROPIC_API_KEY':'secret'})
        launches=[c for c in calls if c[0][:2]==['podman','run']]
        self.assertEqual(len(launches),2)  # listing and run
        for argv,child_env in launches:
            self.assertLessEqual(set(child_env),{'PATH','HOME','XDG_RUNTIME_DIR'})
        self.assertEqual(json.loads((root/'local-summary.json').read_text())['containerImageId'],'sha256:fixtureimage')

    def test_declared_tool_versions_and_stage_disposition_gate_the_browser_phase(self):
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'declared tool versions differ'):self.run_main(root,node='v26.11.1')
        self.assertEqual(self.calls,[],'no process runs on the wrong toolchain')
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'source stage incomplete'):self.run_main(root,stage='failed')
        self.assertFalse([c for c in self.calls if '--list' in c[0] or '--workers=1' in c[0]],'no browser phase after an incomplete stage')

    def test_downloads_are_refused_unless_they_equal_the_typed_sha256_and_bound(self):
        class Response:
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,limit):return self.data[:limit]
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'archive';data=b'exact archive bytes';sha=hashlib.sha256(data).hexdigest()
            with mock.patch.object(L.urllib.request,'urlopen',lambda url,timeout:Response(data)):
                L.fetch('https://example.invalid/a',sha,1024,target);self.assertEqual(target.read_bytes(),data)
                target.unlink()
                with self.assertRaisesRegex(ValueError,'typed SHA-256'):L.fetch('https://example.invalid/a','0'*64,1024,target)
                with self.assertRaisesRegex(ValueError,'bound'):L.fetch('https://example.invalid/a',sha,4,target)
            self.assertFalse(target.exists(),'a refused download leaves no file')

    def test_timeout_kills_the_whole_process_group_not_only_the_direct_child(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            pid_file=Path(tmp)/'grandchild.pid'
            with self.assertRaisesRegex(RuntimeError,'timed out'):
                L.run(['sh','-c','sleep 60 & echo $! > "$1"; wait','sh',str(pid_file)],tmp,{'PATH':os.environ['PATH']},Path(tmp)/'log',1)
            pid=int(pid_file.read_text())
            def alive():
                try:return Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()[0]!='Z'
                except (FileNotFoundError,ProcessLookupError):return False
            deadline=time.monotonic()+5
            while alive() and time.monotonic()<deadline:time.sleep(0.05)
            self.assertFalse(alive(),'the grandchild survived the timeout')

    def test_producer_custody_flag_is_set_only_by_a_passing_join_and_a_successful_run(self):
        with self.assertRaisesRegex(ValueError,'go together'):L.main(['--root',str(self.fresh_root()),'--custody-evidence','/x'])
        root=self.fresh_root();self.run_main(root,env={'GITHUB_ACTIONS':''})
        self.assertIs(json.loads((root/'local-summary.json').read_text())['actualProducerCustodyReadback'],False)
        seen=[]
        def join(evidence,plan,feed,repository,work):seen.append((evidence,str(repository)));return {'custodySha256':'x'}
        root=self.fresh_root()
        with mock.patch.object(L.custody,'verify_producer_custody',join):
            self.run_main(root,extra=['--custody-evidence','/retained','--rendering-source','/rendering'])
        summary=json.loads((root/'local-summary.json').read_text())
        self.assertEqual(seen,[('/retained','/rendering')]);self.assertIs(summary['actualProducerCustodyReadback'],True);self.assertEqual(summary['producerCustody'],{'custodySha256':'x'})
        root=self.fresh_root()  # a refused join stops the run before the stage and leaves the flag false
        def refuse(*a):raise ValueError('custody manifest differs from the typed SHA-256')
        with mock.patch.object(L.custody,'verify_producer_custody',refuse),self.assertRaisesRegex(ValueError,'typed SHA-256'):
            self.run_main(root,extra=['--custody-evidence','/retained','--rendering-source','/rendering'])
        self.assertFalse([c for c in self.calls if c[0][0]=='bash'],'no stage after a refused custody join')
        refused=json.loads((root/'local-summary.json').read_text())
        self.assertEqual((refused['disposition'],refused['actualProducerCustodyReadback']),('failed',False))

    def test_dirty_checkout_and_hosted_runner_refuse_before_any_process(self):
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'clean checkout'):self.run_main(root,dirty=' M tests/x')
        self.assertEqual(self.calls,[]);self.assertFalse(root.exists())
        root=self.fresh_root()
        with self.assertRaisesRegex(ValueError,'hosted runner'):self.run_main(root,env={'GITHUB_ACTIONS':'true'})
        self.assertEqual(self.calls,[]);self.assertFalse(root.exists())
        root=self.fresh_root()
        calls=self.run_main(root,dirty=' M tests/x',extra=['--allow-dirty'],env={'GITHUB_ACTIONS':''})
        self.assertTrue(json.loads((root/'local-summary.json').read_text())['dirty'])

if __name__=='__main__':unittest.main(verbosity=2)
