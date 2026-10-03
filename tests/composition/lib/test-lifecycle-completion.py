#!/usr/bin/env python3
"""Pure causal controls for partial replay, conditional failure and persisted test settings."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
WORK='typed-sdd-p4-templates'


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.model=self.root/'work-model.json';self.model.write_text('updated')
        self.old=hashlib.sha256(b'old').hexdigest()
        self.partial={'outcome':'blocked','refresh':{'status':'partially-blocked','refreshedViewIds':['work-model'],
              'blockedViewIds':['analysis','summary','ship','ship-verdict','verify','governance-handoff']},
              'diagnostics':[{'id':'refresh.staleView','severity':'warning','artifact':f'readiness/{WORK}/analysis.json'},
                             {'id':'refresh.unrenderableSummary','severity':'error','artifact':f'readiness/{WORK}/summary.md'}]}
    def shell(self,body,*args,env=None):
        script='set -uo pipefail\nLANE_REPO_ROOT="$1"\n. "$1/tests/composition/lib/lifecycle-matrix.sh"\n'+body
        return subprocess.run(['bash','-c',script,'fixture',str(ROOT),*map(str,args)],capture_output=True,text=True,env=env)
    def refresh(self,record,digest=None):
        p=self.root/'refresh.json';p.write_text(json.dumps(record))
        return self.shell('if assert_completion_refresh "$2" "$3" "$4" "$5" "$6"; then echo ACCEPT; else exit 27; fi',p,self.model,digest or self.old,WORK,1 if record['refresh']['status']=='partially-blocked' else 0)
    def test_known_partial_requires_updated_work_model(self):
        self.assertEqual(0,self.refresh(self.partial).returncode)
        self.assertNotEqual(0,self.refresh(self.partial,hashlib.sha256(self.model.read_bytes()).hexdigest()).returncode)
    def test_unrelated_block_diagnostics_artifacts_views_and_missing_model_refuse(self):
        mutations=[lambda p:p['diagnostics'][0].update(id='refresh.unreadableSource'),
                   lambda p:p['diagnostics'][0].update(artifact=f'work/{WORK}/plan.md'),
                   lambda p:p['refresh']['blockedViewIds'].append('authoritative-spec'),
                   lambda p:p['refresh'].update(refreshedViewIds=['agent-commands']),
                   lambda p:p.update(outcome='succeeded')]
        for mutate in mutations:
            p=copy.deepcopy(self.partial);mutate(p);self.assertNotEqual(0,self.refresh(p).returncode)
    def test_current_refresh_positive_and_contradictory_block_refuse(self):
        p={'outcome':'succeeded','diagnostics':[],'refresh':{'status':'refreshed-current'}}
        self.assertEqual(0,self.refresh(p).returncode)
        p['outcome']='blocked';self.assertNotEqual(0,self.refresh(p).returncode)
    def completion(self,fail='',badpredicate='',typed=False,partial=False):
        work=self.root/('case-'+(fail or badpredicate or 'positive'))
        (work/'.fsgg').mkdir(parents=True)
        env=dict(os.environ,FAIL_STAGE=fail,BAD_STAGE=badpredicate,PARTIAL_REFRESH='1' if partial else '',FSGG_COMPOSITION_DIAGNOSTICS=str(work/'retained'))
        # Fake command emits real phase shapes but can lie about exit status; helper must check both.
        stub=self.root/'fsgg-sdd';stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args=sys.argv[1:]
if args==['--version']:print('2.1.0');sys.exit(0)
command=args[0];root=pathlib.Path(args[args.index('--root')+1])
phase='migrate' if command=='typed-sdd' else command
if phase=='evidence' and '--sync-observed-run' in args:phase='evidence-sync'
if phase=='refresh':
 (root/'readiness/typed-sdd-p4-templates/work-model.json').write_text('updated-actual-fixture-model')
 report={'outcome':'succeeded','diagnostics':[],'refresh':{'status':'refreshed-current'}}
 if os.getenv('PARTIAL_REFRESH'):
  report={'outcome':'blocked','refresh':{'status':'partially-blocked','refreshedViewIds':['work-model'],'blockedViewIds':['analysis']},'diagnostics':[{'id':'refresh.staleView','severity':'warning','artifact':'readiness/typed-sdd-p4-templates/analysis.json'}]}
elif phase=='migrate':report={'outcome':'succeeded','classification':'Migrated'}
elif phase=='plan':report={'outcome':'succeeded'}
else:
 status={'analyze':'implementationReady','evidence-sync':'evidenceReady','evidence':'evidenceReady','verify':'verificationReady','ship':'shipReady'}[phase]
 key='analysis' if phase=='analyze' else 'evidence' if phase.startswith('evidence') else 'verification' if phase=='verify' else 'ship'
 report={'outcome':'succeeded','diagnostics':[],key:{'status':status if phase!=os.getenv('BAD_STAGE') else 'blocked'}}
print(json.dumps(report));sys.exit(23 if phase==os.getenv('FAIL_STAGE') else 1 if phase=='refresh' and os.getenv('PARTIAL_REFRESH') else 0)
''');stub.chmod(0o755);env['PATH']=str(self.root)+os.pathsep+env['PATH']
        script='''if assert_generated_lifecycle_completion console sdd "$2" "$3" "$4"; then echo TERMINAL-PASS; else exit 29; fi'''
        return self.shell(script,work,self.root,'typed-sdd' if typed else 'sdd',env=env),work
    def test_refresh_crash_with_current_or_partial_json_refuses_before_analyze(self):
        for partial in (False,True):
            import shutil
            shutil.rmtree(self.root/'case-refresh',ignore_errors=True)
            r,work=self.completion(fail='refresh',partial=partial)
            self.assertNotEqual(0,r.returncode);self.assertNotIn('reached shipReady',r.stdout)
            self.assertFalse((work/'retained/sdd.completion-analyze.json').exists())
            self.assertEqual(23,json.loads((work/'retained/sdd.completion-refresh.json.execution.json').read_text())['exitCode'])
    def test_expected_partial_exit_one_completes_all_terminal_gates(self):
        r,_=self.completion(partial=True);self.assertEqual(0,r.returncode,r.stderr)
        self.assertIn('reached shipReady',r.stdout)
    def test_all_terminal_completion_commands_propagate_failed_status_under_if(self):
        for stage in ('analyze','evidence-sync','evidence','verify','ship'):
            r,work=self.completion(fail=stage);self.assertNotEqual(0,r.returncode,r.stdout)
            self.assertNotIn('reached shipReady',r.stdout)
            report=next((work/'retained').glob(f'sdd.completion-{stage}.json.execution.json'))
            proof=json.loads(report.read_text());self.assertEqual(23,proof['exitCode']);self.assertIn('fsgg-sdd',proof['argv'][0])
    def test_terminal_predicate_refuses_success_exit_with_blocked_state(self):
        r,_=self.completion(badpredicate='ship');self.assertNotEqual(0,r.returncode);self.assertNotIn('reached shipReady',r.stdout)
    def test_typed_migration_status_cannot_be_masked_by_success_json(self):
        r,_=self.completion(fail='migrate',typed=True);self.assertNotEqual(0,r.returncode);self.assertNotIn('reached shipReady',r.stdout)
    def test_positive_completion_runs_all_terminal_gates(self):
        r,work=self.completion();self.assertEqual(0,r.returncode,r.stderr);self.assertIn('reached shipReady',r.stdout)
        self.assertEqual(6,len(list((work/'retained').glob('*.execution.json'))))
    def test_real_git_candidate_tracks_fixture_and_excludes_caches(self):
        root=self.root/'git-positive';(root/f'work/{WORK}').mkdir(parents=True)
        (root/f'work/{WORK}/lifecycle-evidence.junit.xml').write_text('<testsuite/>')
        for name in ('.fsgg/cache/secret.bin','.fsgg/lifecycle-test-state.abc/settings.json','bin/built.dll','nested/obj/artifact','node_modules/fixture/index.js'):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('excluded')
        env=dict(os.environ,FSGG_COMPOSITION_DIAGNOSTICS=str(self.root/'git-reports'))
        result=self.shell('if initialize_completion_candidate "$2" "$3" "$4" sdd; then echo GIT-PASS; else exit 41; fi',root,WORK,self.root,env=env)
        self.assertEqual(0,result.returncode,result.stderr)
        tracked=subprocess.check_output(['git','-C',str(root),'ls-files'],text=True).splitlines()
        self.assertEqual([f'work/{WORK}/lifecycle-evidence.junit.xml'],tracked)
        self.assertEqual(40,len(subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()))
        missing=self.root/'git-missing';missing.mkdir()
        result=self.shell('if initialize_completion_candidate "$2" "$3" "$4" sdd; then echo WRONG-PASS; else exit 41; fi',missing,WORK,self.root,env=env)
        self.assertNotEqual(0,result.returncode);self.assertNotIn('WRONG-PASS',result.stdout)

    def matrix(self,failure=''):
        root=self.root/'matrix';root.mkdir()
        stub=self.root/'fsgg-sdd';stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args=sys.argv[1:]
if args==['--version']:print('2.1.0');sys.exit(0)
root=pathlib.Path(args[args.index('--root')+1]);command=args[0]
if command=='scaffold':
 lane=args[args.index('--param')+1].split('=')[1] if '--param' in args else 'sdd'
 (root/'.fsgg/scaffold-provenance.json').write_text(json.dumps({'effectiveParameters':[{'key':'lifecycle','value':lane}],'requiredMinimumCliVersion':'2.1.0'}))
 report={'outcome':'succeeded','scaffold':{'providerName':'console','providerInvoked':True}}
elif command=='typed-sdd':
 if args[1]=='author':
  for name in ['work/matrix-spec/specification.fsx','work/matrix-spec/spec.md','readiness/matrix-spec/specification.normalized.json','readiness/matrix-spec/typed-authority.json','.agents/skills/fs-gg-sdd-typed-author/SKILL.md','.claude/skills/fs-gg-sdd-typed-author/SKILL.md']:
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
 report={'outcome':'blocked' if os.getenv('FAIL_STAGE')=='inspect-predicate' and args[1]=='inspect' else 'succeeded'}
elif command=='refresh':report={'outcome':'noChange','refresh':{'status':'early-stage'}}
elif command=='upgrade':report={'outcome':'noChange','upgrade':{'residualDrift':False}}
print(json.dumps(report))
''');stub.chmod(0o755)
        env=dict(os.environ,PATH=str(self.root)+os.pathsep+os.environ['PATH'],FAIL_STAGE=failure)
        script=''' . "$1/tests/composition/lib/lane-package.sh"
assert_lifecycle_trees_equivalent() { return 0; }
assert_generated_lifecycle_completion() { echo completion-$2; [[ "${FAIL_STAGE:-}" != completion ]]; }
assert_generated_product_restore_build_test() { echo build-$2; [[ "${FAIL_STAGE:-}" != build ]]; }
if assert_provider_lifecycle_matrix console "$2/archive.nupkg" "$2/receivers"; then echo PARENT-PASS; else exit 43; fi
'''
        return self.shell(script,root,env=env)
    def test_real_matrix_conditional_caller_reaches_pass_only_for_positive_children(self):
        r=self.matrix();self.assertEqual(0,r.returncode,r.stderr);self.assertIn('PASS lifecycle matrix',r.stdout)
    def test_real_matrix_completion_build_and_typed_predicate_fail_before_pass(self):
        for failure in ('completion','build','inspect-predicate'):
            # Each fixture needs a fresh root; remove the prior synthetic receiver tree only.
            import shutil
            shutil.rmtree(self.root/'matrix',ignore_errors=True)
            r=self.matrix(failure);self.assertNotEqual(0,r.returncode,r.stderr)
            self.assertNotIn('PASS lifecycle matrix',r.stdout);self.assertNotIn('PARENT-PASS',r.stdout)
            if failure=='inspect-predicate':self.assertNotIn('completion-',r.stdout)

    def product(self,name,fail=''):
        work=self.root/name;(work/'.fsgg').mkdir(parents=True);(work/'Product.slnx').write_text('fixture')
        env=dict(os.environ,FAIL_STAGE=fail,PATH=str(self.root)+os.pathsep+os.environ['PATH'])
        stub=self.root/'dotnet';stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
if sys.argv[1]==os.getenv('FAIL_STAGE'):sys.exit(31)
if sys.argv[1]=='test':
 data=pathlib.Path(os.environ['XDG_DATA_HOME']);config=pathlib.Path(os.environ['XDG_CONFIG_HOME'])
 assert data.is_absolute() and config.is_absolute()
 settings=data/'Generated Product/game-shell-settings.json';settings.parent.mkdir(parents=True,exist_ok=True)
 previous=settings.read_text() if settings.exists() else 'W';settings.write_text('Q')
 pathlib.Path('observed-settings.json').write_text(json.dumps({'previous':previous,'data':str(data),'config':str(config)}))
''');stub.chmod(0o755)
        r=self.shell('if assert_generated_product_restore_build_test rendering sdd "$2"; then echo PRODUCT-PASS; else exit 37; fi',work,env=env)
        return r,work
    def test_restore_build_test_failures_cannot_reach_parent_pass_under_if(self):
        for stage in ('restore','build','test'):
            r,_=self.product(stage,stage);self.assertNotEqual(0,r.returncode);self.assertNotIn('PRODUCT-PASS',r.stdout)
    def test_each_product_has_its_own_persistent_data_and_config(self):
        observed=[]
        for name in ('none','sdd','typed-sdd','spec-kit','omitted'):
            r,work=self.product(name);self.assertEqual(0,r.returncode,r.stderr)
            observed.append(json.loads((work/'observed-settings.json').read_text()))
        self.assertEqual(['W']*5,[x['previous'] for x in observed])
        self.assertEqual(5,len({x['data'] for x in observed}));self.assertEqual(5,len({x['config'] for x in observed}))
        self.assertTrue(all((Path(x['data'])/'Generated Product/game-shell-settings.json').read_text()=='Q' for x in observed))

if __name__=='__main__':unittest.main()
