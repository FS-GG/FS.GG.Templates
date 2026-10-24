#!/usr/bin/env python3
"""Pure mechanical DTO/report controls; synthetic selections, no runtime executes."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('observations',HERE/'current-composition-observations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Controls(unittest.TestCase):
    def setUp(self):
        # Deliberately synthetic, independent of the typed owner's real selection.
        self.plan={'template':{'sha256':'fixture-template'},'rendering':{'version':'fixture-version','sourceCommit':'fixture-source','custodySha256':'fixture-custody','packages':[{'id':'Fixture.UI','sha256':'fixture-ui','lockContentHash':'fixture-lock'}]},'game':{'id':'Fixture.Game','version':'fixture-game','lockContentHash':'fixture-game-lock'},'browsers':{'families':['fixture-family'],'cases':[{'file':'one.spec.ts','suite':[],'title':'literal (one)'},{'file':'two.spec.ts','suite':['nested'],'title':'literal two'}]}}
        def row(file,title):return {'file':file,'title':title,'ok':True,'tests':[{'projectName':'fixture-family','status':'expected','results':[{'status':'passed','retry':0}]}]}
        self.report={'stats':{'expected':2,'unexpected':0,'skipped':0,'flaky':0},'suites':[{'title':'one.spec.ts','specs':[row('one.spec.ts','literal (one)')]},{'title':'two.spec.ts','suites':[{'title':'nested','specs':[row('two.spec.ts','literal two')]}]}]}

    def test_exact_report_and_escaped_selector(self):
        self.assertTrue(m.validate_report(self.report,self.plan,'fixture-family'))
        selector=m.selector(self.plan)
        self.assertIsNotNone(re.search(selector,'one.spec.ts literal (one)'))
        self.assertIsNone(re.search(selector,'one.spec.ts literal one'))
        self.assertIsNone(re.search(selector,'one.spec.ts literal (one) extra'))

    def test_missing_duplicate_and_same_count_wrong_identities_refuse(self):
        for change in ['missing','duplicate','file','suite','title']:
            report=copy.deepcopy(self.report)
            if change=='missing':report['suites'].pop()
            elif change=='duplicate':report['suites'][1]=copy.deepcopy(report['suites'][0])
            elif change=='file':report['suites'][0]['specs'][0]['file']='other.spec.ts'
            elif change=='suite':report['suites'][1]['suites'][0]['title']='wrong'
            else:report['suites'][0]['specs'][0]['title']='another'
            with self.subTest(change=change),self.assertRaises(ValueError):m.validate_report(report,self.plan,'fixture-family')

    def test_failed_skipped_flaky_wrong_family_and_retries_refuse(self):
        for change in ['unexpected','skipped','flaky','family','retry','multiple-results','case-status']:
            report=copy.deepcopy(self.report);test=report['suites'][0]['specs'][0]['tests'][0]
            if change in ('unexpected','skipped','flaky'):report['stats'][change]=1
            elif change=='family':test['projectName']='another'
            elif change=='retry':test['results'][0]['retry']=1
            elif change=='multiple-results':test['results'].append(copy.deepcopy(test['results'][0]))
            else:test['status']='unexpected'
            with self.subTest(change=change),self.assertRaises(ValueError):m.validate_report(report,self.plan,'fixture-family')
        with self.assertRaises(ValueError):m.validate_report(self.report,self.plan,'unselected')

    def test_inputs_follow_typed_values_without_local_policy(self):
        self.assertTrue(m.validate_inputs(self.plan,'fixture-version','fixture-source','fixture-template'))
        for args in [('wrong','fixture-source','fixture-template'),('fixture-version','wrong','fixture-template'),('fixture-version','fixture-source','wrong')]:
            with self.subTest(args=args),self.assertRaises(ValueError):m.validate_inputs(self.plan,*args)

    def test_locked_graph_joins_all_selected_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'SvgFoundation').mkdir();path=root/'SvgFoundation/packages.lock.json'
            lock={'dependencies':{'fixture-tfm':{'Fixture.UI':{'resolved':'fixture-version','contentHash':'fixture-lock'},'Fixture.Game':{'resolved':'fixture-game','contentHash':'fixture-game-lock'}}}}
            path.write_text(json.dumps(lock));self.assertTrue(m.validate_locked_graph(self.plan,root))
            for key in ['resolved','contentHash']:
                changed=copy.deepcopy(lock);changed['dependencies']['fixture-tfm']['Fixture.Game'][key]='wrong';path.write_text(json.dumps(changed))
                with self.subTest(key=key),self.assertRaises(ValueError):m.validate_locked_graph(self.plan,root)

    def test_actual_selected_graph_refuses_project_fallback_or_other_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'SvgFoundation/obj').mkdir(parents=True);path=root/'SvgFoundation/obj/project.assets.json'
            assets={'libraries':{'Fixture.UI/fixture-version':{'type':'package'},'Fixture.Game/fixture-game':{'type':'package'}},'packageFolders':{str(root/'.nuget/packages'): {}}}
            path.write_text(json.dumps(assets));self.assertTrue(m.validate_assets(self.plan,root))
            assets['libraries']['Fixture.Game/fixture-game']['type']='project';path.write_text(json.dumps(assets))
            with self.assertRaisesRegex(ValueError,'package-backed'):m.validate_assets(self.plan,root)
            assets['libraries']['Fixture.Game/fixture-game']['type']='package';assets['packageFolders']={str(root/'other-cache'):{}};path.write_text(json.dumps(assets))
            with self.assertRaisesRegex(ValueError,'cache differs'):m.validate_assets(self.plan,root)

    def test_public_archive_and_custody_observations_join_typed_plan(self):
        observed={'custodySha256':'fixture-custody','records':[{'id':'Fixture.UI','state':'matched','rawSha256':'fixture-ui'}]}
        self.assertTrue(m.validate_public_readback(self.plan,observed))
        for change in ['custody','hash','state','duplicate']:
            value=copy.deepcopy(observed)
            if change=='custody':value['custodySha256']='wrong'
            elif change=='hash':value['records'][0]['rawSha256']='wrong'
            elif change=='state':value['records'][0]['state']='started'
            else:value['records'].append(copy.deepcopy(value['records'][0]))
            with self.subTest(change=change),self.assertRaises(ValueError):m.validate_public_readback(self.plan,value)

    def test_actual_current_shell_refuses_before_typed_owner_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/'must-remain-absent'
            result=subprocess.run(['bash',str(HERE/'verify-external-reference-candidate.sh'),str(root/'no-rendering-source'),str(root/'no-custody'),'fixture-version',str(output),'a'*40,'current-public-composition',str(root/'no-template.nupkg'),'b'*64],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('current composition needs the local ADR-0096 verification gate',result.stderr)
            self.assertFalse(output.exists())

    def test_actual_workflow_watches_and_bounds_mechanical_controls(self):
        workflow=(HERE.parents[2]/'.github/workflows/fable-external-reference-source.yml').read_text()
        for path in ('current-composition-observations.py','test-current-composition-observations.py'):
            self.assertIn("      - 'tests/composition/fable-game/"+path+"'",workflow)
        static=workflow.split('  static:',1)[1].split('  candidate:',1)[0]
        self.assertIn('timeout --kill-after=5s 150s prlimit --as=1073741824 --cpu=120 python3 -B tests/composition/fable-game/test-current-composition-observations.py',static)
        self.assertNotIn('actions/setup-dotnet',static)

    def test_browser_processes_receive_the_typed_selection_not_only_the_build(self):
        plan={'selection':{'externalReference':True,'wasmPolicyExample':False}}
        self.assertEqual(m.browser_environment(plan),{'FsGgExternalReferenceCandidate':'true','FsGgWasmPolicyExample':'false'})
        plan['selection']['externalReference']=False
        self.assertEqual(m.browser_environment(plan)['FsGgExternalReferenceCandidate'],'false')
        for bad in ('true',None,1):
            with self.subTest(bad=bad),self.assertRaises(ValueError):m.browser_environment({'selection':{'externalReference':bad,'wasmPolicyExample':False}})
        # The shipped specs read this variable (or the fsproj) to register the four command-outcome cases.
        self.assertEqual(m.browser_environment({'selection':{'externalReference':True,'wasmPolicyExample':False}})['FsGgExternalReferenceCandidate'],'true')

    def test_local_verification_gate_is_the_only_entry_and_refuses_credentials_and_runners(self):
        marker={'FSGG_CURRENT_COMPOSITION_LOCAL_VERIFICATION':m.LOCAL_VERIFICATION}
        self.assertIsNone(m.check_admission(dict(marker)))
        self.assertFalse(hasattr(m,'CURRENT_COMPOSITION_ADMISSION'),'the retired hosted admission constant must not return')
        for name in m.CREDENTIAL_VARIABLES:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'credentials'):m.check_admission({**marker,name:'x'})
        with self.assertRaisesRegex(ValueError,'hosted'):m.check_admission({**marker,'GITHUB_ACTIONS':'true'})
        for wrong in ('','true','adr-0096'):
            with self.subTest(wrong=wrong),self.assertRaisesRegex(ValueError,'needs the local ADR-0096 verification gate'):m.check_admission({'FSGG_CURRENT_COMPOSITION_LOCAL_VERIFICATION':wrong})
        # The retired hosted route has no workflow, no managed caller and no admission variable left to reach the stage.
        self.assertFalse((HERE.parents[2]/'.github/workflows/current-reference-composition.yml').exists())
        self.assertFalse((HERE/'current-composition-managed.py').exists())
        for workflow in (HERE.parents[2]/'.github/workflows').glob('*.yml'):
            self.assertNotIn('FSGG_CURRENT_COMPOSITION',workflow.read_text(),workflow.name)

    def test_current_entry_refuses_before_owner_root_or_acquisition(self):
        with self.assertRaisesRegex(ValueError,'needs the local ADR-0096 verification gate'):m.check_admission({})
        shell=(HERE/'verify-external-reference-candidate.sh').read_text()
        self.assertLess(shell.index('--check-admission'),shell.index('mkdir -p'))
        self.assertLess(shell.index('--check-admission'),shell.index('current-composition-plan >'))
        self.assertIn('external-reference-template-package.py" inspect',shell)
        self.assertIn('external-reference-template-package.py" rendering',shell)
        self.assertIn('current-d5-receiver-check',shell)
        self.assertIsNone(re.search(r'--package(?![-\w])',shell))  # not an option of `dotnet new <template>`; the custom hive scopes the one installed package
        self.assertIn("packet['whole4818Acceptance']=False",shell)


if __name__=='__main__':unittest.main(verbosity=2)
