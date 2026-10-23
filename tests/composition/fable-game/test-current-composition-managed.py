#!/usr/bin/env python3
"""Pure held DOM caller controls; no toolchain, owner runtime or browser executes."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
M=load('managed_dom',HERE/'current-composition-managed.py')
O=load('dom_observations',HERE/'current-composition-observations.py')
L=load('actual_dom_loader',HERE/'wasm-installed-c.py')

class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_hold_precedes_dependency_import_and_actual_cli_effects(self):
        self.assertIsNone(M.ADMISSION);self.assertIsNone(O.CURRENT_COMPOSITION_ADMISSION)
        with patch.object(M,'dependencies',side_effect=AssertionError('dependency reached')),self.assertRaisesRegex(ValueError,'HELD'):M.main(['--run'])
        result=subprocess.run(['python3','-B',str(HERE/'current-composition-managed.py'),'--run'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,3);self.assertIn('HELD',result.stderr)

    def test_closed_third_contract_and_preserved_defaults(self):
        reader,d5=M.dependencies()
        self.assertEqual(reader.caller_contract('retained',None)['namespace'],'retained-reference')
        self.assertEqual(reader.caller_contract('d5',None)['issue'],'4849')
        selected=reader.caller_contract('composition',None)
        self.assertEqual(selected['issue'],'4818');self.assertEqual(selected['workflow'],M.WORKFLOW)
        self.assertEqual(selected['unitPrefix'],'fsgg-mg-templates-composition-')
        with self.assertRaises(ValueError):reader.caller_contract('arbitrary',None)
        self.assertEqual(d5.READER['sha256'],M.READER_SHA)

    def test_composition_admission_is_bound_to_own_issue_source_workflow_and_unit(self):
        reader,_=M.dependencies();url='https://github.com/FS-GG/.github/issues/4818#issuecomment-123';contract=reader.caller_contract('composition',url)
        env={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main','SHA':'a'*40,'ADMITTED_REF':'a'*40,'CHECKOUT_HEAD':'a'*40,'WORKFLOW_SHA':'a'*40,'WORKFLOW_REF':M.WORKFLOW,'RUN_ID':'42','RUN_ATTEMPT':'1','UNIT_NAME':'fsgg-mg-templates-composition-42-1','ADMISSION':url}
        self.assertEqual(reader.validate_admission(env,url,contract)['SHA'],'a'*40)
        for key,value in [('RUN_ATTEMPT','2'),('WORKFLOW_REF',reader.WORKFLOW),('ADMITTED_REF','b'*40),('UNIT_NAME','fsgg-mg-templates-d5-42-1'),('ADMISSION','https://github.com/FS-GG/.github/issues/4816#issuecomment-123')]:
            with self.subTest(key=key),self.assertRaises(ValueError):reader.validate_admission({**env,key:value},url,contract)
        with self.assertRaises(ValueError):reader.selected_contract({**contract,'issue':'4816'})

    def test_actual_fixed_setup_failure_blocks_build_and_preserves_primary_and_collection(self):
        reader,collection=M.dependencies();contract=reader.caller_contract('composition',None);events=[]
        root=self.root/'current-composition-42-1'
        def fresh(path,environ):path.mkdir();return {'HOME':str(path/'home')}
        def fail(*args):events.append('owner');raise ValueError('original synthetic owner refusal')
        caller={'fresh_environment':fresh,'load_owner':fail}
        fake=types.SimpleNamespace(validate_admission=lambda *a:{'synthetic':True},operational_start=lambda *a:{'boot':'synthetic'},normalised_roots=lambda *a:None,normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
            load_file=lambda *a:types.SimpleNamespace(actual_caller=lambda:caller),original_clock=lambda *a:{'startedMonotonic':M.time.monotonic()},collect=reader.collect,collection_terminal=reader.collection_terminal)
        env={'GITHUB_WORKSPACE':str(HERE.parents[2]),'RUNNER_TEMP':str(self.root),'RUN_ID':'42','UNIT_NAME':'synthetic'}
        with self.assertRaisesRegex(ValueError,'original synthetic owner refusal'):M.run_composition(fake,collection,contract,env)
        self.assertEqual(events,['owner']);attempt=json.loads((root/'composition-evidence/attempt.json').read_text())
        self.assertEqual(attempt['executionDisposition'],'failed');self.assertIn('original synthetic owner refusal',attempt['firstCause']);self.assertFalse(attempt['completeCompositionAcceptance'])
        index=json.loads((root/'composition-evidence/manifest.json').read_text())
        for row in index['files']:
            path=root/'composition-evidence'/row['path'];self.assertEqual(M.sha(path),row['sha256']);self.assertEqual(path.stat().st_size,row['bytes'])

    def test_current_success_disposition_cannot_claim_full_producer_custody(self):
        source=(HERE/'current-composition-managed.py').read_text()
        self.assertIn("disposition='dom-observed-producer-custody-reference-only'",source)
        self.assertIn("'actualProducerCustodyReadback':False",source);self.assertIn("'completeCompositionAcceptance':False",source)

    def test_original_phase_budget_never_renews(self):
        self.assertEqual(sum(M.BUDGET.values()),1800)
        self.assertEqual(M.deadline(0,'build',800),1380)
        with self.assertRaises(ValueError):M.deadline(0,'build',1380)
        with self.assertRaises(ValueError):M.deadline(100,'browser',99)

    def test_exact_source_stage_args_have_no_command_or_dll_fallback(self):
        args=M.source_arguments('/bin/bash',self.root,HERE.parents[2],{'rendering':{'version':'synthetic','sourceCommit':'a'*40},'template':{'sha256':'b'*64}},self.root/'template')
        self.assertEqual(args[-1],'current-source-stage');self.assertEqual(args[-4],'current-public-composition')
        self.assertNotIn('--force',args)
        source=(HERE/'current-composition-managed.py').read_text()
        self.assertNotIn("['prepare_inputs']",source);self.assertNotIn("['qualify_tools']",source)
        for forbidden in ('rustup','wasi-sdk','subprocess.Popen','os.kill','systemd-run'):self.assertNotIn(forbidden,source)

    def test_actual_provider_argv_builds_owned_output_before_typed_cli(self):
        calls=[];folder=self.root/'validator-artifacts/bin/FS.GG.Templates.ProviderTool/release'
        def run(argv,cwd,inputs=()):
            calls.append(argv)
            if argv[1]=='build':
                folder.mkdir(parents=True)
                for name in ('FS.GG.Templates.ProviderTool.dll','FS.GG.Templates.ProviderTool.deps.json','FS.GG.Templates.ProviderTool.runtimeconfig.json'):(folder/name).write_text('synthetic only')
            if argv[-1]=='current-composition-plan':return '{"synthetic":true}'
            return ''
        caller=L.actual_caller();core,plan=M.qualified_provider(caller,run,'/synthetic/dotnet',self.root,HERE.parents[2],self.root/'NuGet.config')
        self.assertEqual(plan,{'synthetic':True});self.assertEqual(calls[0][1],'restore');self.assertEqual(calls[1][1],'build');self.assertEqual(calls[2][-1],'current-composition-plan')
        self.assertIn('--artifacts-path',calls[0]);self.assertIn('--artifacts-path',calls[1]);self.assertEqual(core.parent,folder)
        self.assertTrue((self.root/'provider-member-identities.json').is_file())

    def test_provider_restore_failure_blocks_compile_and_cli(self):
        calls=[]
        def fail(argv,*args,**kwargs):calls.append(argv);raise ValueError('original restore refusal')
        with self.assertRaisesRegex(ValueError,'original restore'):M.qualified_provider(L.actual_caller(),fail,'/synthetic/dotnet',self.root,HERE.parents[2],self.root/'config')
        self.assertEqual(len(calls),1);self.assertFalse((self.root/'current-composition-plan.json').exists())

    def test_actual_managed_browser_argv_validates_pinned_canonical_profile(self):
        canonical=load('dom_real_contract',Path(os.environ['FSGG_MANAGED_GROUP_OWNER']))
        self.assertEqual(M.sha(Path(os.environ['FSGG_MANAGED_GROUP_OWNER'])),'d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0')
        caller=L.actual_caller();node=self.root/'node';node.write_text('synthetic not executed');node.chmod(0o700);identities={};caller['bind_identity'](identities,str(node),'caller-authored');profiles=[]
        def owner_run(profile,env,deadline,out_dir,control):
            _,digest=canonical.validate_profile(profile);profiles.append(profile);out=Path(out_dir);out.mkdir(parents=True);(out/'stdout.log').write_text('{}')
            return {'outcome':'succeeded','cleanup':'observed-empty-removed','custody':'contained','profileSha256':digest,'owner':{'sha256':caller['OWNER']['sha256']}}
        owner=types.SimpleNamespace(run=owner_run,Refused=canonical.Refused,GroupFailed=canonical.GroupFailed)
        receipts=[];execute=caller['managed_executor'](owner,self.root,12345,identities,'installed',receipts)
        for family in ('chromium','firefox','webkit'):
            caller['managed_playwright'](execute,str(node),self.root,family,{},True,'current-composition.generated.config.ts')
            caller['managed_playwright'](execute,str(node),self.root,family,{},False,'current-composition.generated.config.ts')
        self.assertEqual(len(profiles),6);self.assertTrue(all(p['retirement']['onLeaderExit']=='require-empty' for p in profiles));self.assertTrue(all(p['limits']['memoryMaxBytes'] is None for p in profiles))
        self.assertIn('--list',profiles[0]['argv']);self.assertEqual(profiles[1]['argv'][-3:],['--workers=1','--retries=0','--max-failures=1'])
        with self.assertRaises(ValueError):caller['managed_playwright'](execute,str(node),self.root,'unknown',{},False,'current-composition.generated.config.ts')

    def test_listing_rejects_substitution_duplicates_wrong_family_and_run_results(self):
        plan={'browsers':{'families':['synthetic'],'cases':[{'file':'one.spec.ts','suite':['nested'],'title':'one'}]}}
        report={'suites':[{'title':'one.spec.ts','suites':[{'title':'nested','specs':[{'file':'one.spec.ts','title':'one','tests':[{'projectName':'synthetic','results':[]}]}]}]}]}
        self.assertTrue(O.validate_listing(report,plan,'synthetic'))
        for change in ('title','project','results','duplicate'):
            value=copy.deepcopy(report);row=value['suites'][0]['suites'][0]['specs'][0]
            if change=='title':row['title']='wrong'
            elif change=='project':row['tests'][0]['projectName']='other'
            elif change=='results':row['tests'][0]['results']=[{'status':'passed'}]
            else:value['suites'][0]['suites'][0]['specs'].append(copy.deepcopy(row))
            with self.subTest(change=change),self.assertRaises(ValueError):O.validate_listing(value,plan,'synthetic')

    def test_actual_browser_sequence_is_list_then_test_per_family_and_failure_gated(self):
        tests=self.root/'product/complete/Browser.Tests/test-results';tests.mkdir(parents=True);calls=[]
        plan={'browsers':{'families':['chromium','firefox','webkit'],'cases':[{'file':'one.spec.ts','suite':[],'title':'one'}]}}
        def report(family,listed):
            test={'projectName':family,'status':'expected','results':[] if listed else [{'status':'passed','retry':0}]}
            return {'stats':{'expected':1,'unexpected':0,'skipped':0,'flaky':0},'suites':[{'title':'one.spec.ts','specs':[{'file':'one.spec.ts','title':'one','ok':True,'tests':[test]}]}]}
        def run(argv,cwd,env):
            listed='--list' in argv;family=env['PLAYWRIGHT_BROWSER_FAMILY'];calls.append((family,listed))
            value=report(family,listed)
            if listed:return json.dumps(value)
            (tests/'browser.json').write_text(json.dumps(value));return ''
        results=M.browser_sequence(L.actual_caller(),run,'/synthetic/node',self.root,{},plan,O)
        self.assertEqual(calls,[(family,listed) for family in plan['browsers']['families'] for listed in (True,False)])
        self.assertEqual(sum(row['passed'] for row in results.values()),3)
        calls.clear()
        def bad(argv,cwd,env):calls.append(argv);return '{"suites":[]}'
        with self.assertRaisesRegex(ValueError,'listing identities'):M.browser_sequence(L.actual_caller(),bad,'/synthetic/node',self.root,{},plan,O)
        self.assertEqual(len(calls),1);self.assertIn('--list',calls[0])

    def test_staged_typed_raw_feed_is_not_fabricated_custody_readback(self):
        source=self.root/'input';source.mkdir();raw=b'synthetic public archive; never execute';(source/'Fixture.1.nupkg').write_bytes(raw)
        plan={'rendering':{'version':'1','custodySha256':'reference-only','packages':[{'id':'Fixture','sha256':hashlib.sha256(raw).hexdigest()}]}}
        result=O.staged_public_feed(plan,source,self.root/'feed');self.assertFalse(result['actualCustodyReadback']);self.assertTrue(O.validate_public_readback(plan,result))
        (source/'Fixture.1.nupkg').write_bytes(b'changed')
        with self.assertRaises(ValueError):O.staged_public_feed(plan,source,self.root/'bad')

    def test_reporting_index_and_terminal_failures_preserve_original_and_attempt_terminal(self):
        reader,collection=M.dependencies();contract=reader.caller_contract('composition',None)
        for primary in (ValueError('original setup refusal'),None):
            with self.subTest(primary=primary):
                root=self.root/('primary' if primary else 'index');root.mkdir();events=[]
                summary={'disposition':'success','executionDisposition':'complete','firstCause':str(primary) if primary else None,'additionalFailures':[]}
                fake=types.SimpleNamespace(collect=lambda *a:events.append('collect') or {'failures':[]},collection_terminal=lambda *a:events.append('terminal'))
                original=M.write
                def fail(path,value):
                    if path.name=='managed-receipts.json':raise OSError('index denied')
                    return original(path,value)
                with patch.object(M,'write',side_effect=fail):
                    if primary:M.finish_composition(fake,contract,root,summary,[],primary,M.time.monotonic())
                    else:
                        with self.assertRaisesRegex(OSError,'index denied'):M.finish_composition(fake,contract,root,summary,[],None,M.time.monotonic())
                self.assertIn('terminal',events);self.assertEqual(summary['disposition'],'failed')
                if primary:self.assertEqual(summary['firstCause'],'original setup refusal');self.assertIn('index denied',str(primary.__notes__))
        summary={'additionalFailures':[]};fake.collection_terminal=lambda *a:(_ for _ in ()).throw(OSError('terminal denied'))
        with self.assertRaisesRegex(OSError,'terminal denied'):M.finish_composition(fake,contract,self.root,summary,[],None,M.time.monotonic())
        self.assertEqual(summary['collectionDisposition'],'Unknown')

    def test_closed_inventory_retains_failed_compiler_log_and_excludes_native_assets(self):
        reader,_=M.dependencies();contract=reader.caller_contract('composition',None)
        product=self.root/'product';product.mkdir();(product/'fable-build.log').write_bytes(b'original compiler failed')
        cache=product/'complete/.nuget/packages';cache.mkdir(parents=True);(cache/'secret.json').write_text('never retain')
        (self.root/'tools').mkdir();(self.root/'tools/private.json').write_text('never retain')
        summary={'disposition':'failed','executionDisposition':'failed','firstCause':'compiler original','additionalFailures':[]}
        M.finish_composition(reader,contract,self.root,summary,[],ValueError('compiler original'),M.time.monotonic())
        evidence=self.root/'composition-evidence';self.assertEqual((evidence/'product/fable-build.log').read_bytes(),b'original compiler failed')
        index=json.loads((evidence/'manifest.json').read_text())
        for row in index['files']:
            path=evidence/row['path'];self.assertEqual(M.sha(path),row['sha256']);self.assertEqual(path.stat().st_size,row['bytes'])
        self.assertFalse(any('secret' in row['path'] or 'private' in row['path'] for row in index['files']))
        (product/'fable-build.log').unlink();(product/'fable-build.log').symlink_to(cache/'secret.json')
        with self.assertRaisesRegex(ValueError,'path refused'):M.evidence_inventory(self.root)

    def test_failed_browser_keeps_invalid_raw_bytes_before_validation_and_original_error(self):
        tests=self.root/'product/complete/Browser.Tests/test-results';tests.mkdir(parents=True)
        plan={'browsers':{'families':['chromium'],'cases':[]}}
        observation=types.SimpleNamespace(validate_listing=lambda *a:None,validate_report=lambda *a:(_ for _ in ()).throw(ValueError('semantic refusal')))
        def browser(*args,**kwargs):
            if kwargs.get('list_only'):return '{}'
            (tests/'browser.json').write_bytes(b'not JSON: original failed report');raise ValueError('original DOM failure')
        with self.assertRaisesRegex(ValueError,'original DOM failure'):M.browser_sequence({'managed_playwright':browser},None,'synthetic',self.root,{},plan,observation)
        self.assertEqual((self.root/'chromium-report.json').read_bytes(),b'not JSON: original failed report')
        def invalid(*args,**kwargs):
            if kwargs.get('list_only'):return '{}'
            (tests/'browser.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'semantic refusal'):M.browser_sequence({'managed_playwright':invalid},None,'synthetic',self.root,{},plan,observation)
        self.assertEqual((self.root/'chromium-report.json').read_bytes(),b'{}')

    def test_actual_entry_owner_failure_survives_index_and_terminal_failure(self):
        reader,collection=M.dependencies();contract=reader.caller_contract('composition',None);events=[]
        def fresh(path,environ):path.mkdir();return {}
        def fail(*args):raise ValueError('first owner failure')
        def terminal(*args):events.append('terminal');raise OSError('terminal inaccessible')
        caller={'fresh_environment':fresh,'load_owner':fail}
        fake=types.SimpleNamespace(validate_admission=lambda *a:{},operational_start=lambda *a:{'boot':'synthetic'},normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
            load_file=lambda *a:types.SimpleNamespace(actual_caller=lambda:caller),original_clock=lambda *a:{'startedMonotonic':M.time.monotonic()},collect=reader.collect,collection_terminal=terminal)
        original=M.write
        def index_fail(path,value):
            if path.name=='managed-receipts.json':raise OSError('secondary index inaccessible')
            return original(path,value)
        env={'GITHUB_WORKSPACE':str(HERE.parents[2]),'RUNNER_TEMP':str(self.root),'RUN_ID':'42','UNIT_NAME':'synthetic'}
        with patch.object(M,'write',side_effect=index_fail),self.assertRaisesRegex(ValueError,'first owner failure') as caught:M.run_composition(fake,collection,contract,env)
        self.assertEqual(events,['terminal']);self.assertIn('secondary index inaccessible',str(caught.exception.__notes__));self.assertIn('terminal inaccessible',str(caught.exception.__notes__))
        self.assertFalse(json.loads((self.root/'current-composition-42-1/composition-evidence/attempt.json').read_text())['completeCompositionAcceptance'])

    def test_actual_provider_compile_failure_retains_partial_log_without_cli(self):
        calls=[];product=self.root/'product';product.mkdir()
        def run(argv,*args,**kwargs):
            calls.append(argv)
            if argv[1]=='build':
                (product/'fable-build.log').write_text('first compiler failure bytes');raise ValueError('compiler failed')
            return ''
        with self.assertRaisesRegex(ValueError,'compiler failed'):M.qualified_provider(L.actual_caller(),run,'synthetic',self.root,HERE.parents[2],self.root/'config')
        self.assertEqual(len(calls),2);self.assertIn('product/fable-build.log',M.evidence_inventory(self.root));self.assertFalse((self.root/'current-composition-plan.json').exists())

    def test_inventory_rejects_oversize_metadata_without_copying(self):
        product=self.root/'product';product.mkdir()
        with (product/'fable-build.log').open('wb') as handle:handle.truncate(16777217)
        with self.assertRaisesRegex(ValueError,'member cap'):M.evidence_inventory(self.root)
        (product/'fable-build.log').unlink();(self.root/'arbitrary-tree').mkdir();(self.root/'arbitrary-tree/private.json').write_text('exclude');(self.root/'arbitrary-secret.json').write_text('exclude')
        self.assertEqual(M.evidence_inventory(self.root),[])

    def test_workflow_has_real_preflight_watch_hold_and_original_bounds(self):
        w=(HERE.parents[2]/'.github/workflows/current-reference-composition.yml').read_text()
        self.assertLess(w.index('Hold manual runtime'),w.index('actions/checkout'))
        self.assertIn('if: ${{ false }}',w);self.assertIn('test-current-composition-managed.py',w)
        for item in ('timeout-minutes: 35','RuntimeMaxSec=1800','TimeoutStopSec=5','MemoryMax=8G','CPUQuota=200%','TasksMax=512','current-composition-','ac22206560f3eddfea524ce8f752ff1d0dfeec4e'):self.assertIn(item,w)
        s=(HERE/'verify-external-reference-candidate.sh').read_text();self.assertLess(s.index("CURRENT_CONFIG\n  exit 0"),s.index('npx playwright install chromium'))

if __name__=='__main__':unittest.main(verbosity=2)
