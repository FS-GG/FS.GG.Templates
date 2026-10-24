#!/usr/bin/env python3
"""Pure fixed-call controls. All SDK/packages/receipts are synthetic; no child runs."""
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import textwrap
import types
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('retained_rehearsal', HERE/'retained-reference-rehearsal.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)
LOADER = importlib.util.spec_from_file_location('actual_rehearsal_caller', HERE/'wasm-installed-c.py')
loader = importlib.util.module_from_spec(LOADER); LOADER.loader.exec_module(loader)
OWNER_FILE = os.environ.get('FSGG_MANAGED_GROUP_OWNER')


def synthetic_package(package, version):
    prefix = 'content/templates/fs-gg-fable-game/'
    files = {package+'.nuspec':f'<package><metadata><id>{package}</id><version>{version}</version></metadata></package>'.encode()}
    if package == 'FS.GG.Workspace.Template':
        files.update({prefix+'.template.config/template.json': b'{"sources":[],"symbols":{}}',
                      prefix+'Domain/Room.fs': b'namespace FableGameWorkspaceNamespace.Domain\n',
                      prefix+'global.json': json.dumps({'sdk':{'version':'10.0.400' if version=='0.13.0' else '10.0.401','rollForward':'disable'}}).encode(),
                      prefix+'Domain/packages.lock.json': b'{"version":1}\n',
                      prefix+'.config/dotnet-tools.json':json.dumps({'version':1,'isRoot':True,'tools':{'fable':{'version':'5.13.0' if version=='0.13.0' else '5.18.0','commands':['fable']}}}).encode()})
    else:
        base='tools/net10.0/any/'
        files.update({base+'DotnetToolSettings.xml': b'<DotNetCliTool><Commands><Command Name="fsgg-sdd" Runner="dotnet" EntryPoint="FS.GG.SDD.Cli.dll"/></Commands></DotNetCliTool>',
                      base+'FS.GG.SDD.Cli.dll':b'SYNTHETIC SDD DLL; NEVER EXECUTE',
                      base+'FS.GG.SDD.Cli.runtimeconfig.json':json.dumps({'runtimeOptions':{'tfm':'net10.0','rollForward':'Major','framework':{'name':'Microsoft.NETCore.App','version':'10.0.0'}}}).encode(),
                      base+'FS.GG.SDD.Cli.deps.json':b'{}', 'skills/example/SKILL.md':b'# Synthetic shipped skill\n'})
    return files


class World:
    def __init__(self, root, canonical, fail=None):
        self.root=root; self.canonical=canonical; self.fail=fail; self.calls=[];self.environments=[];self.profiles=[]
        self.caller=loader.actual_caller()
        self.caller["time"]=types.SimpleNamespace(monotonic=lambda:100.5,time=lambda:0)
        self.packages={'target':synthetic_package('FS.GG.Workspace.Template','0.19.3'),
                       'baseline':synthetic_package('FS.GG.Workspace.Template','0.13.0'),
                       'sdd':synthetic_package('FS.GG.SDD.Cli','2.0.2')}
        self.owner=types.SimpleNamespace(Refused=canonical.Refused,GroupFailed=canonical.GroupFailed,run=self.owner_run)
        self.caller['load_owner']=lambda root,deadline:self.owner
        self.caller['probe_containment']=lambda owner,root:{'available':True,'synthetic':True}
        self.caller['host_image']=self.host_image
        self.caller['provision_sdk']=self.sdk
        self.caller['download']=self.download

    def host_image(self, name):
        path=self.root/'host'/Path(name).name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            path.write_bytes(('#!'+str(self.root/'host/bash')+'\n').encode() if path.name=='ldd' else b'SYNTHETIC EXECUTABLE/LIBRARY; NEVER EXECUTE')
            path.chmod(0o700)
        return str(path),m.sha(path)

    def sdk(self, get, tools, deadline):
        get('dotnet-releases.json','https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json',None,8388608)
        get('dotnet.tar.gz',m.SDK_URL,m.SDK_SHA512,536870912,'sha512')
        root=tools/'dotnet';root.mkdir()
        for relative in ['dotnet','host/fxr/10.0.12/libhostfxr.so']+['shared/Microsoft.NETCore.App/10.0.12/'+name for name in ['libhostpolicy.so','libcoreclr.so','libSystem.Globalization.Native.so','libSystem.Security.Cryptography.Native.OpenSsl.so']]:
            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'SYNTHETIC SDK MEMBER; NEVER EXECUTE');path.chmod(0o700)
        return root/'dotnet'

    def download(self,url,path,maximum,deadline,expected=None,algorithm='sha256'):
        if self.fail=='download':raise ValueError('original synthetic download failure')
        if path.name in m.FILENAMES.values():
            key=next(key for key,name in m.FILENAMES.items() if name==path.name)
            if key=='provider':path.write_text('source: FS.GG.Workspace.Template::0.13.0\n')
            else:
                with zipfile.ZipFile(path,'w') as archive:
                    for name,data in self.packages[key].items():archive.writestr(name,data)
        elif path.name=='dotnet-releases.json':
            path.write_text(json.dumps({'releases':[{'sdks':[{'version':'10.0.401','files':[{'rid':'linux-x64','name':'dotnet-sdk-linux-x64.tar.gz','url':m.SDK_URL,'hash':m.SDK_SHA512}]}]}]}))
        else:path.write_bytes(b'SYNTHETIC SDK BODY; NOT A REAL PACKAGE')
        return {'url':url,'bytes':path.stat().st_size,'digest':m.sha(path),'synthetic':True}

    def materialize(self, key, target, product):
        prefix='content/templates/fs-gg-fable-game/'
        for name,data in self.packages[key].items():
            if not name.startswith(prefix) or '/.template.config/' in name:continue
            path=target/name[len(prefix):];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data.replace(b'FableGameWorkspaceNamespace',product.encode()).replace(b'FableGameWorkspace',product.encode()))

    def response(self, argv, env):
        if Path(argv[0]).name=='systemctl':return '\n'.join(key+'='+value for key,value in {**m.UNIT,'CPUQuotaPerSecUSec':'2s','InvocationID':'a'*32,'ControlGroup':'/system.slice/unit.service','MainPID':'42'}.items())+'\n'
        if Path(argv[0]).name=='ldd':return 'libfixture.so => '+self.host_image('libfixture.so')[0]+' (0x1234)\n'
        if argv[1:]==['--version']:return '10.0.401\n'
        if argv[1:]==['--info']:return 'SYNTHETIC SDK INFO\n'
        if argv[1:]==['--list-runtimes']:return 'Microsoft.NETCore.App 10.0.12 [synthetic]\n'
        if argv[1:3]==['tool','install']:
            store=self.root/'tools/sdd/.store/fs.gg.sdd.cli/2.0.2/fs.gg.sdd.cli/2.0.2'
            for name,data in self.packages['sdd'].items():
                path=store/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            return ''
        if argv[-1:] == ['--version'] and argv[1].endswith('FS.GG.SDD.Cli.dll'):return '2.0.2\n'
        if argv[1:3]==['new','install']:
            hive=Path(env['DOTNET_CLI_HOME'])/'.templateengine';hive.mkdir(parents=True,exist_ok=True);m.write(hive/'packages.json',{'Packages':[{'Details':{'PackageId':'FS.GG.Workspace.Template','Version':'0.19.3'},'MountPointUri':argv[3]}]});return ''
        if argv[1:3]==['new','fs-gg-fable-game']:
            if self.fail=='materialize':raise ValueError('original synthetic materialization failure')
            self.materialize('target',self.root/'candidate','Reference4816Current');return ''
        if 'scaffold' in argv:
            hive=Path(env['DOTNET_CLI_HOME'])/'.templateengine';hive.mkdir(parents=True,exist_ok=True);m.write(hive/'packages.json',{'Packages':[{'Details':{'PackageId':'FS.GG.Workspace.Template','Version':'0.13.0'},'MountPointUri':str(self.root/'downloads'/m.FILENAMES['baseline'])}]})
            self.materialize('baseline',self.root/'retained','Reference4816Retained')
            path=self.root/'retained/.config/dotnet-tools.json';value=json.loads(path.read_text())
            value['tools'].update({'fs.gg.sdd.cli':{'version':'2.0.2','commands':['fsgg-sdd']},'fs.gg.coord.cli':{'version':'0.90.0','commands':['fsgg-coord-engine']}});path.write_text(json.dumps(value))
            path=self.root/'retained/.fsgg/scaffold-provenance.json';path.write_text('{"effectiveParameters":[{"key":"lifecycle","value":"typed-sdd"}]}');return ''
        if len(argv)>3 and Path(argv[3]).name=='verify-current-reference-adoption.py':
            target=self.root/'transaction/adopted';shutil.copytree(self.root/'retained',target);m.write(self.root/'transaction/transaction-controls.json',{'synthetic':True})
            (target/'global.json').write_bytes((self.root/'candidate/global.json').read_bytes())
            path=target/'.config/dotnet-tools.json';value=json.loads(path.read_text());value['tools']['fable']={'version':'5.18.0','commands':['fable']};path.write_text(json.dumps(value));return ''
        if argv[1:2]==['restore']:
            if self.fail=='restore':raise ValueError('original synthetic restore failure')
            return 'SYNTHETIC LOCKED RESTORE\n'
        raise AssertionError('unrecognized fixed call '+repr(argv))

    def owner_run(self, profile, env, deadline, out_dir, control):
        # Real canonical validation; no canonical run/probe/native hook ever executes.
        _,digest=self.canonical.validate_profile(profile)
        self.profiles.append((profile,deadline));self.calls.append(profile['argv']);self.environments.append(dict(env))
        out=Path(out_dir);out.mkdir(parents=True)
        receipt={'outcome':'succeeded','cleanup':'observed-empty-removed','custody':'contained','profileSha256':digest,'owner':{'sha256':self.caller['OWNER']['sha256']},'firstCause':None,'synthetic':True}
        try:
            if self.fail=='cleanup':raise ValueError('original synthetic cleanup uncertainty')
            result=self.response(profile['argv'],env)
        except ValueError as error:
            receipt.update(outcome='failed',firstCause=str(error),cleanup='unknown' if self.fail=='cleanup' else 'observed-empty-removed');m.write(out/'receipt.json',receipt);(out/'stdout.log').write_text('');(out/'stderr.log').write_text(str(error));raise self.canonical.GroupFailed(receipt)
        (out/'stdout.log').write_text(result);(out/'stderr.log').write_text('');m.write(out/'receipt.json',receipt)
        return receipt


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not OWNER_FILE:
            raise RuntimeError('FSGG_MANAGED_GROUP_OWNER must point to the exact pinned owner source; no silent contract-test skip')
        path=Path(OWNER_FILE)
        if path.stat().st_size!=45315:raise RuntimeError('canonical owner size differs')
        if m.sha(path)!='d846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0':raise RuntimeError('canonical owner source pin differs')
        cls.canonical=m.load_file('retained_real_contract',path)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='retained-rehearsal-synthetic-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'retained-reference-123-1'
        self.env={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main','SHA':'a'*40,'ADMITTED_REF':'a'*40,'CHECKOUT_HEAD':'a'*40,'WORKFLOW_SHA':'a'*40,'WORKFLOW_REF':m.WORKFLOW,'RUN_ID':'123','RUN_ATTEMPT':'1','UNIT_NAME':'fsgg-mg-templates-retained-123-1','ADMISSION':'https://github.com/FS-GG/.github/issues/4816#issuecomment-123','RUNNER_TEMP':str(self.base),'GITHUB_WORKSPACE':str(m.WORKSPACE)}

    def drive(self,fail=None):
        world=World(self.root,self.canonical,fail)
        admission=m.validate_admission(self.env,self.env['ADMISSION'])
        with patch.object(m,'validate_admission',return_value=admission),patch.object(m,'load_file',return_value=types.SimpleNamespace(actual_caller=lambda:world.caller)),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100.5)),patch.object(m,'operational_start',return_value={'properties':{'InvocationID':'a'*32,'ControlGroup':'/system.slice/unit.service','MainPID':'42'}}),patch.object(m,'acquisition_capacity',return_value={'synthetic':True}):
            original=m.template_registration
            def synthetic_registration(home,root,version,expected):
                body=root/'downloads'/m.FILENAMES['baseline' if version=='0.13.0' else 'target']
                return original(home,root,version,m.sha(body))
            with patch.object(m,'template_registration',side_effect=synthetic_registration):
                result=m.run_rehearsal(self.env,100)
        return result,world

    def test_hold_precedes_io_loader_and_execution(self):
        with patch.object(m,'ADMISSION',None),patch.object(m,'load_file',side_effect=AssertionError('loader reached')),self.assertRaisesRegex(ValueError,'held'):
            m.run_rehearsal(self.env,100)
        self.assertFalse(self.root.exists())

    def test_selected_source_admission_binds_exact_owning_literal(self):
        admission=m.ADMISSION or 'https://github.com/FS-GG/.github/issues/4816#issuecomment-124'
        selected={**self.env,'ADMISSION':admission}
        self.assertEqual(m.validate_admission(selected,admission)['ADMISSION'],admission)
        with self.assertRaisesRegex(ValueError,'admission input differs'):
            m.validate_admission({**selected,'ADMISSION':admission+'0'},admission)
        with patch.object(m,'ADMISSION',admission),patch.dict(os.environ,selected,clear=True),patch.object(m.sys,'argv',['rehearsal','--check-admission']),patch.object(m,'run_rehearsal',side_effect=AssertionError('runtime reached')):
            self.assertEqual(m.main(),0)

    def test_admission_binds_exact_source_without_future_self_sha(self):
        self.assertEqual(m.validate_admission(self.env,self.env['ADMISSION'])['SHA'],'a'*40)
        for key,bad in [('REF','refs/heads/other'),('CHECKOUT_HEAD','b'*40),('WORKFLOW_SHA','b'*40),('ADMITTED_REF','b'*40),('RUN_ATTEMPT','2'),('EVENT','pull_request'),('WORKFLOW_REF',m.WORKFLOW+'other'),('UNIT_NAME','other')]:
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_admission({**self.env,key:bad},self.env['ADMISSION'])
        with self.assertRaises(ValueError):m.validate_admission(self.env,'https://github.com/FS-GG/.github/issues/4710#issuecomment-123')

    def test_future_admitted_source_shape_can_pass_precheck_without_running(self):
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.dict(os.environ,self.env,clear=True),patch.object(m.sys,'argv',['rehearsal','--check-admission']),patch.object(m,'run_rehearsal',side_effect=AssertionError('runtime reached')):
            self.assertEqual(m.main(),0)

    def test_every_fixed_call_validates_real_contract_and_preserves_boundaries(self):
        result,world=self.drive();self.assertEqual(result['disposition'],'passed');self.assertTrue(result['membersQualified'])
        self.assertGreater(len(world.profiles),15)
        for profile,deadline in world.profiles:
            self.assertEqual(profile['retirement']['onLeaderExit'],'require-empty');self.assertEqual(profile['root'],str(self.root));self.assertTrue(Path(profile['cwd']).is_relative_to(self.root))
            self.assertFalse(any('\n' in arg for arg in profile['argv']));self.assertLessEqual(deadline,1600)
        calls=world.calls
        target_homes=[env['DOTNET_CLI_HOME'] for argv,env in zip(calls,world.environments) if argv[1:2]==['new']]
        old_homes=[env['DOTNET_CLI_HOME'] for argv,env in zip(calls,world.environments) if 'scaffold' in argv]
        self.assertEqual(set(target_homes),{str(self.root/'target-home')});self.assertEqual(old_homes,[str(self.root/'retained-home')])
        registrations=json.loads((self.root/'template-registrations.json').read_text());self.assertEqual(registrations['retained-create']['version'],'0.13.0');self.assertEqual(registrations['target-create']['version'],'0.19.3')
        self.assertEqual(sum(argv[1:2]==['restore'] for argv in calls),1)
        self.assertEqual(sum('scaffold' in argv for argv in calls),1)
        self.assertFalse(any('5.13.0' in argv or '10.0.400' in argv for argv in calls))
        self.assertFalse(any('fable' in argv or 'build' in argv or 'npm' in argv for argv in calls))
        receipts=json.loads((self.root/'managed-receipts.json').read_text());self.assertEqual([row['index'] for row in receipts],list(range(1,len(receipts)+1)))
        self.assertTrue((self.root/'retained-evidence/manifest.json').is_file())

    def test_setup_failure_blocks_materialization_and_restore(self):
        with self.assertRaisesRegex(ValueError,'original synthetic download failure'):self.drive('download')
        result=json.loads((self.root/'retained-evidence/rehearsal.json').read_text());self.assertIn('original synthetic download failure',result['firstCause']);self.assertFalse((self.root/'candidate').exists())
        receipts=json.loads((self.root/'managed-receipts.json').read_text());self.assertEqual(len(receipts),1)

    def test_materialization_failure_blocks_restore_and_retains_original_receipt(self):
        with self.assertRaisesRegex(RuntimeError,'original synthetic materialization failure'):self.drive('materialize')
        result=json.loads((self.root/'retained-evidence/rehearsal.json').read_text());self.assertIn('original synthetic materialization failure',result['firstCause'])
        self.assertFalse((self.root/'transaction').exists());self.assertFalse((self.root/'locks-before.json').exists())

    def test_restore_failure_retains_transaction_and_first_cause(self):
        with self.assertRaisesRegex(RuntimeError,'original synthetic restore failure'):self.drive('restore')
        result=json.loads((self.root/'retained-evidence/rehearsal.json').read_text());self.assertIn('original synthetic restore failure',result['firstCause']);self.assertTrue((self.root/'locks-before.json').exists());self.assertTrue((self.root/'locks-after.json').exists())

    def test_expired_phase_and_unexpected_sdk_refuse_before_execution(self):
        with self.assertRaises(ValueError):m.phase_deadline(100,'setup',821)
        self.assertEqual(m.phase_deadline(100,'setup',110),820)
        for args in [('dotnet.tar.gz',m.SDK_URL,'0'*128,536870912,'sha512'),('dotnet.tar.gz',m.SDK_URL.replace('401','400'),m.SDK_SHA512,536870912,'sha512')]:
            with self.assertRaises(ValueError):m.verify_sdk_selection(*args)
        m.verify_sdk_selection('dotnet.tar.gz',m.SDK_URL,m.SDK_SHA512,536870912,'sha512')

    def test_official_metadata_unique_tuple_and_ambiguity_control(self):
        selected={'rid':'linux-x64','name':'dotnet-sdk-linux-x64.tar.gz','url':m.SDK_URL,'hash':m.SDK_SHA512}
        body={'releases':[{'sdks':[{'version':'10.0.401','files':[selected]},
                                  {'version':'10.0.400','files':[{'rid':'linux-x64','name':'old.tar.gz','url':'old','hash':'old'}]}]}]}
        m.sdk_metadata(json.dumps(body))
        body['releases'][0]['sdks'][0]['files'].append({**selected,'hash':'f'*128})
        with self.assertRaises(ValueError):m.sdk_metadata(json.dumps(body))
        with self.assertRaises(ValueError):m.sdk_metadata('{"releases":[]}')

    def test_global_and_symlink_overlap_guards(self):
        self.root.mkdir();(self.root/'global.json').write_text('{}')
        with self.assertRaises(ValueError):m.no_global_before_create(self.root/'fresh')
        alias=self.base/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):m.normalized_roots(alias/'output',m.WORKSPACE)

    def test_generation_guard_rejects_postactions_and_changed_product(self):
        path=self.base/'package.zip'
        with zipfile.ZipFile(path,'w') as source:source.writestr('content/templates/fs-gg-fable-game/.template.config/template.json','{"sources":[],"symbols":{},"postActions":[]}')
        with zipfile.ZipFile(path) as source,self.assertRaises(ValueError):m.baseline_template(source)
        path.unlink()
        with zipfile.ZipFile(path,'w') as source:
            for name,data in synthetic_package('FS.GG.Workspace.Template','0.13.0').items():source.writestr(name,data)
        world=World(self.root,self.canonical);self.root.mkdir();world.materialize('baseline',self.root/'old','Old')
        with zipfile.ZipFile(path) as source:self.assertGreater(m.generation_join({},source,self.root/'old','Old','Old')['archiveProductFilesChecked'],0)
        (self.root/'old/Domain/Room.fs').write_text('foreign')
        with zipfile.ZipFile(path) as source,self.assertRaises(ValueError):m.generation_join({},source,self.root/'old','Old','Old')

    def test_collection_failure_is_distinct_and_never_passes(self):
        original=m.collect
        def incomplete(root,deadline):
            result=original(root,deadline);result['failures'].append({'synthetic':'collection failure'});return result
        with patch.object(m,'collect',side_effect=incomplete),self.assertRaisesRegex(RuntimeError,'collection incomplete'):self.drive()
        result=json.loads((self.root/'retained-evidence/collection-terminal.json').read_text());self.assertEqual(result['disposition'],'failed');self.assertIsNone(result['firstCause']);self.assertEqual(result['executionDisposition'],'passed');self.assertIn('collection',result['additionalFailures'][0])
        manifest=json.loads((self.root/'retained-evidence/manifest.json').read_text())
        for row in manifest['files']:
            path=self.root/'retained-evidence'/row['path'];self.assertEqual(m.sha(path),row['sha256']);self.assertEqual(path.stat().st_size,row['bytes'])

    def test_cleanup_uncertainty_blocks_dependent_steps_and_preserves_receipt(self):
        with self.assertRaisesRegex(RuntimeError,'original synthetic cleanup uncertainty'):self.drive('cleanup')
        receipt=json.loads(next((self.root/'managed').rglob('receipt.json')).read_text())
        self.assertEqual(receipt['cleanup'],'unknown')
        self.assertFalse((self.root/'downloads').exists())
        result=json.loads((self.root/'retained-evidence/rehearsal.json').read_text())
        self.assertEqual(result['executionDisposition'],'failed')

    def test_compiled_sdd_runtime_and_installed_member_mismatch_refuse(self):
        path=self.base/'sdd.zip';files=synthetic_package('FS.GG.SDD.Cli','2.0.2')
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in files.items():archive.writestr(name,data)
        with zipfile.ZipFile(path) as archive:entry,members=m.sdd_payload(archive)
        tool=self.base/'tools';store=tool/'store'
        for name,data in files.items():
            target=store/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        actual,_=m.installed_sdd(tool,entry,members);self.assertTrue(actual.is_file())
        actual.write_bytes(b'changed DLL')
        with self.assertRaises(ValueError):m.installed_sdd(tool,entry,members)
        value=json.loads(files['tools/net10.0/any/FS.GG.SDD.Cli.runtimeconfig.json']);value['runtimeOptions']['tfm']='net9.0';files['tools/net10.0/any/FS.GG.SDD.Cli.runtimeconfig.json']=json.dumps(value).encode()
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in files.items():archive.writestr(name,data)
        with zipfile.ZipFile(path) as archive,self.assertRaises(ValueError):m.sdd_payload(archive)

    def test_evidence_cap_is_enforced_and_receipt_is_retained(self):
        self.root.mkdir();m.write(self.root/'rehearsal.json',{'synthetic':True});(self.root/'locks-before.json').write_text('x'*50)
        with patch.object(m,'EVIDENCE_CAP',32):result=m.collect(self.root,m.time.monotonic()+5)
        self.assertTrue(result['failures']);self.assertLessEqual(result['totalBytes'],32);self.assertTrue((self.root/'retained-evidence/manifest.json').exists())

    def test_registration_readback_rejects_wrong_version_and_archive(self):
        self.root.mkdir();home=self.root/'home';registry=home/'.templateengine/packages.json';registry.parent.mkdir(parents=True)
        archive=self.root/'template.nupkg';archive.write_bytes(b'synthetic archive')
        row={'Details':{'PackageId':'FS.GG.Workspace.Template','Version':'0.13.0'},'MountPointUri':str(archive)}
        m.write(registry,{'Packages':[row]})
        self.assertEqual(m.template_registration(home,self.root,'0.13.0',m.sha(archive))['version'],'0.13.0')
        with self.assertRaises(ValueError):m.template_registration(home,self.root,'0.19.3',m.sha(archive))
        with self.assertRaises(ValueError):m.template_registration(home,self.root,'0.13.0','0'*64)
        m.write(registry,{'Packages':[row,row]})
        with self.assertRaises(ValueError):m.template_registration(home,self.root,'0.13.0',m.sha(archive))

    def test_collection_does_not_walk_restore_or_generated_trees(self):
        self.root.mkdir();m.write(self.root/'rehearsal.json',{'synthetic':True})
        for relative in ['transaction/adopted/.nuget/packages/library/huge.json','transaction/adopted/obj/project.assets.json','transaction/rollback/obj/generated.json','transaction/apply-backup/files/private.json']:
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('do not retain')
        m.write(self.root/'transaction/transaction-controls.json',{'synthetic':True})
        m.write(self.root/'transaction/apply-backup/journal.json',{'synthetic':'required journal'})
        result=m.collect(self.root,m.time.monotonic()+5)
        paths={row['path'] for row in result['files']}
        self.assertIn('transaction/apply-backup/journal.json',paths)
        self.assertTrue(all('/.nuget/' not in path and '/obj/' not in path and '/files/' not in path for path in paths))

    def test_acquisition_capacity_refusal_retains_partial_snapshot(self):
        self.root.mkdir();facts={'complete':False,'ancestors':[{'path':'synthetic'}]}
        def unavailable(owner,path,exclude_memory_under=None,facts=None):facts.update(complete=False,ancestors=[{'path':'synthetic'}]);raise ValueError('capacity unavailable')
        with patch.object(m,'capacity_snapshot',side_effect=unavailable),self.assertRaisesRegex(ValueError,'capacity unavailable'):
            m.acquisition_capacity(object(),self.root,{'cgroupPath':'/synthetic/unit'})
        self.assertEqual(json.loads((self.root/'capacity-before-acquisition.json').read_text()),facts)

    def test_effective_ancestor_capacity_and_unit_memory_exclusion(self):
        data={'/proc/meminfo':'MemTotal: 33554432 kB\nMemAvailable: 20971520 kB\n','/proc/sys/kernel/random/boot_id':'boot-synthetic'}
        for directory in ['/cg/parent','/cg/parent/unit','/cg/parent/unit/fsgg-supervisor']:
            data[directory+'/cpu.max']='max 100000'
            data[directory+'/memory.current']=str(1*1073741824)
            data[directory+'/memory.max']='max';data[directory+'/memory.high']='max'
        for directory in ['/cg','/cg/parent','/cg/parent/unit','/cg/parent/unit/fsgg-supervisor']:
            data[directory+'/cgroup.controllers']='cpu memory pids'
            data[directory+'/cgroup.subtree_control']='cpu memory pids'
        data['/cg/parent/cpu.max']='400000 100000';data['/cg/parent/memory.max']=str(20*1073741824)
        data['/cg/parent/unit/cpu.max']='200000 100000';data['/cg/parent/unit/memory.max']=str(8*1073741824)
        def read(path):
            if path not in data:raise FileNotFoundError(path)
            return data[path]
        owner=types.SimpleNamespace(_read=read,_cgroup2_mount=lambda:('/cg','/'),_cgroup_dir=lambda *args:'/cg/parent/unit/fsgg-supervisor')
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}):
            facts=m.capacity_snapshot(owner,self.base,exclude_memory_under=Path('/cg/parent/unit'));m.require_capacity(facts)
            self.assertEqual(facts['effectiveCPUs'],2);self.assertEqual(facts['availableMemoryBytes'],19*1073741824)
            with self.assertRaises(ValueError):m.require_capacity(m.capacity_snapshot(owner,self.base))
            data['/cg/parent/cpu.max']='100000 100000'
            with self.assertRaises(ValueError):m.require_capacity(m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit')))
            data['/cg/parent/cpu.max']='400000 100000';data['/cg/parent/memory.current']=str(19*1073741824)
            with self.assertRaises(ValueError):m.require_capacity(m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit')))
            del data['/cg/parent/memory.current'];partial={}
            with self.assertRaises(ValueError):m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'),partial)
            self.assertFalse(partial['complete']);self.assertTrue(partial['ancestors'])

    def inherited_cpu_fixture(self):
        data={'/proc/meminfo':'MemTotal: 33554432 kB\nMemAvailable: 20971520 kB\n','/proc/sys/kernel/random/boot_id':'boot-synthetic'}
        for directory in ['/cg','/cg/parent','/cg/parent/unit','/cg/parent/unit/fsgg-supervisor']:
            data[directory+'/cgroup.controllers']='cpu memory pids'
            data[directory+'/cgroup.subtree_control']='cpu memory pids'
            if directory!='/cg':
                data[directory+'/cpu.max']='max 100000'
                data[directory+'/memory.current']=str(1073741824)
                data[directory+'/memory.max']='max';data[directory+'/memory.high']='max'
        data['/cg/parent/memory.max']=str(20*1073741824)
        data['/cg/parent/unit/memory.max']=str(8*1073741824)
        data['/cg/parent/unit/cpu.max']='200000 100000'
        data['/cg/parent/unit/cgroup.subtree_control']='memory pids'
        data['/cg/parent/unit/fsgg-supervisor/cgroup.controllers']='memory pids'
        data['/cg/parent/unit/fsgg-supervisor/cgroup.subtree_control']=''
        del data['/cg/parent/unit/fsgg-supervisor/cpu.max']
        def read(path):
            if path not in data:raise FileNotFoundError(path)
            value=data[path]
            if isinstance(value,BaseException):raise value
            return value
        owner=types.SimpleNamespace(_read=read,_cgroup2_mount=lambda:('/cg','/'),_cgroup_dir=lambda *args:'/cg/parent/unit/fsgg-supervisor')
        return data,owner

    def test_missing_undelegated_child_cpu_inherits_real_ancestor_quota(self):
        data,owner=self.inherited_cpu_fixture()
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}):
            facts=m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'));m.require_capacity(facts)
        self.assertEqual(facts['effectiveCPUs'],2)
        self.assertEqual(facts['ancestors'][0]['cpuAccounting'],'inherited-from-ancestors')
        self.assertEqual(facts['availableMemoryBytes'],19*1073741824)
        self.assertEqual(facts['cpuControllerReads']['/cg/parent/unit']['cgroup.subtree_control'],'memory pids')

    def pids_only_fixture(self):
        data,owner=self.inherited_cpu_fixture()
        data['/cg/parent/unit/cgroup.subtree_control']='pids'
        data['/cg/parent/unit/fsgg-supervisor/cgroup.controllers']='pids'
        for name in ('memory.current','memory.max','memory.high'):
            del data['/cg/parent/unit/fsgg-supervisor/'+name]
        return data,owner

    def test_pids_only_child_inherits_cpu_and_memory_without_losing_unit_bounds(self):
        data,owner=self.pids_only_fixture()
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}):
            facts=m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'));m.require_capacity(facts)
        self.assertEqual(facts['effectiveCPUs'],2)
        self.assertEqual(facts['availableMemoryBytes'],19*1073741824)
        self.assertEqual(facts['ancestors'][0]['memoryAccounting'],'inherited-from-ancestors')

    def test_pids_only_memory_missing_partial_delegated_or_unreadable_refuses(self):
        leaf='/cg/parent/unit/fsgg-supervisor'
        changes=[(leaf+'/memory.current','0'),
                 ('/cg/parent/unit/cgroup.subtree_control','memory pids'),
                 (leaf+'/memory.max',PermissionError('synthetic unreadable')),
                 ('/cg/parent/unit/memory.max',None),
                 ('/cg/parent/unit/memory.high','corrupt'),
                 ('/cg/parent/unit/memory.max','-1')]
        for path,value in changes:
            data,owner=self.pids_only_fixture()
            if value is None:del data[path]
            else:data[path]=value
            if path=='/cg/parent/unit/cgroup.subtree_control':data[leaf+'/cgroup.controllers']='memory pids'
            facts={}
            with self.subTest(path=path,value=str(value)),patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}),self.assertRaises((ValueError,PermissionError)):
                m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'),facts)
            self.assertFalse(facts['complete']);self.assertTrue(facts['ancestors'])

    def test_selected_unit_memory_family_is_mandatory_even_when_excluded(self):
        data,owner=self.pids_only_fixture()
        data['/cg/parent/cgroup.subtree_control']='cpu pids'
        data['/cg/parent/unit/cgroup.controllers']='cpu pids'
        for name in ('memory.current','memory.max','memory.high'):del data['/cg/parent/unit/'+name]
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}),self.assertRaisesRegex(ValueError,'selected unit memory accounting unavailable'):
            m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'))

    def test_pids_only_memory_missing_cannot_hide_disappeared_group(self):
        data,owner=self.pids_only_fixture();original=owner._read;reads=[]
        def read(path):
            if path=='/cg/parent/unit/fsgg-supervisor/cgroup.controllers':
                reads.append(path)
                if len(reads)>1:raise FileNotFoundError('synthetic group disappeared after controller snapshot')
            return original(path)
        owner._read=read;facts={}
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}),self.assertRaises(FileNotFoundError):
            m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'),facts)
        self.assertFalse(facts['complete']);self.assertIn('memoryInheritanceReadback',facts['ancestors'][0])

    def test_pids_only_memory_still_enforces_outer_headroom(self):
        data,owner=self.pids_only_fixture();data['/cg/parent/memory.current']=str(11*1073741824)
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}):
            facts=m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'))
            self.assertEqual(facts['availableMemoryBytes'],9*1073741824)
            with self.assertRaisesRegex(ValueError,r'8GiB\+2GiB'):m.require_capacity(facts)

    def test_inherited_child_still_refuses_one_cpu_ancestor(self):
        data,owner=self.inherited_cpu_fixture();data['/cg/parent/cpu.max']='100000 100000'
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}):
            facts=m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'))
            self.assertEqual(facts['effectiveCPUs'],1)
            with self.assertRaisesRegex(ValueError,'CPU capacity below'):m.require_capacity(facts)

    def test_missing_cpu_while_delegated_refuses_with_partial_facts(self):
        data,owner=self.inherited_cpu_fixture()
        data['/cg/parent/unit/cgroup.subtree_control']='cpu memory pids'
        data['/cg/parent/unit/fsgg-supervisor/cgroup.controllers']='cpu memory pids'
        facts={}
        with patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}),self.assertRaisesRegex(ValueError,'delegated CPU accounting unavailable'):
            m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'),facts)
        self.assertFalse(facts['complete']);self.assertTrue(facts['cpuControllerReads'])

    def test_inheritance_evidence_unavailable_corrupt_or_contradictory_refuses(self):
        changes=[('/cg/parent/unit/fsgg-supervisor/cgroup.controllers',PermissionError('synthetic unreadable')),
                 ('/cg/parent/unit/fsgg-supervisor/cgroup.controllers',FileNotFoundError('synthetic disappeared')),
                 ('/cg/parent/unit/fsgg-supervisor/cgroup.controllers','cpu memory pids'),
                 ('/cg/parent/unit/cgroup.controllers','memory pids'),
                 ('/cg/parent/unit/fsgg-supervisor/cgroup.subtree_control','cpu'),
                 ('/cg/parent/unit/fsgg-supervisor/cgroup.controllers','memory memory pids'),
                 ('/cg/cgroup.controllers',FileNotFoundError('synthetic root facts absent')),
                 ('/cg/parent/unit/cpu.max','corrupt')]
        for path,value in changes:
            data,owner=self.inherited_cpu_fixture();data[path]=value;facts={}
            with self.subTest(path=path,value=str(value)),patch.object(m.os,'sched_getaffinity',return_value={0,1,2,3}),self.assertRaises((ValueError,PermissionError,FileNotFoundError)):
                m.capacity_snapshot(owner,self.base,Path('/cg/parent/unit'),facts)
            self.assertFalse(facts['complete']);self.assertTrue(facts['cpuControllerReads'])

    def post_fixture(self):
        directory=m.outer_path(self.env);directory.mkdir()
        source=m.validate_admission(self.env,self.env['ADMISSION'])
        m.outer_write(directory,'preflight.json',{'source':source,'disposition':'passed','startedMonotonic':10,'deadlineMonotonic':1000,'capacity':{'boot':'boot-synthetic'}})
        group=self.base/'cgroup';group.mkdir();status=group.stat();(group/'cgroup.events').write_text('populated 0\n')
        props={'Id':self.env['UNIT_NAME']+'.service','InvocationID':'a'*32,'ControlGroup':'/system.slice/test.service','MainPID':'42424242'}
        initial={'properties':props,'source':source,'boot':'boot-synthetic','mainStartTicks':123,'cgroupPath':str(group),'cgroupDev':status.st_dev,'cgroupInode':status.st_ino}
        m.outer_write(directory,'initial-unit.json',initial);m.outer_write(directory,'client-exit.json',{'source':source,'clientExit':'23','wrapperExit':'23'})
        def read(path):
            if path=='/proc/sys/kernel/random/boot_id':return 'boot-synthetic'
            if path.startswith('/proc/'):raise FileNotFoundError(path)
            return Path(path).read_text()
        return directory,group,initial,types.SimpleNamespace(_read=read,_stat=lambda pid:None)

    def test_post_unit_joins_original_terminal_state_and_preserves_failed_client(self):
        directory,group,initial,owner=self.post_fixture()
        props={**initial['properties'],'MainPID':'0','LoadState':'loaded','ActiveState':'failed','SubState':'failed'}
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':0,'properties':props}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100)):
            result=m.post_unit(self.env)
        self.assertEqual(result['disposition'],'original-unit-terminal-empty');self.assertEqual(result['originalClientExit'],'23');self.assertEqual(result['boot'],'boot-synthetic');self.assertEqual(result['observations'][0]['cgroupInode'],initial['cgroupInode'])

    def test_post_unit_changed_identity_and_missing_initial_are_unknown(self):
        directory,group,initial,owner=self.post_fixture()
        props={**initial['properties'],'InvocationID':'b'*32,'MainPID':'0','LoadState':'loaded','ActiveState':'inactive'}
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':0,'properties':props}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100)):
            with self.assertRaises(ValueError):m.post_unit(self.env)
            self.assertEqual(json.loads((directory/'post-unit.json').read_text())['disposition'],'Unknown')
            (directory/'initial-unit.json').unlink()
            with self.assertRaises(ValueError):m.post_unit(self.env)
            result=json.loads((directory/'post-unit.json').read_text());self.assertEqual(result['originalClientExit'],'23');self.assertEqual(result['disposition'],'Unknown')

    def test_post_unit_absence_and_late_read_have_distinct_results(self):
        directory,group,initial,owner=self.post_fixture();(group/'cgroup.events').unlink();group.rmdir()
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':1,'properties':{'LoadState':'not-found'}}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100)):
            self.assertEqual(m.post_unit(self.env)['disposition'],'original-unit-absent')
        clock=iter([100,9999,10000])
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':1,'properties':{'LoadState':'not-found'}}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:next(clock))):
            with self.assertRaises(ValueError):m.post_unit(self.env)
        self.assertEqual(json.loads((directory/'post-unit.json').read_text())['disposition'],'Unknown')

    def test_initial_identity_survives_capacity_refusal_before_owner_acquisition(self):
        directory,group,initial,owner=self.post_fixture()
        pre=json.loads((directory/'preflight.json').read_text());pre['deadlineMonotonic']=10000;m.outer_write(directory,'preflight.json',pre)
        props={**initial['properties'],'ControlGroup':'/cgroup','MainPID':str(os.getpid())}
        owner._cgroup2_mount=lambda:(str(self.base),'/');owner._cgroup_dir=lambda *args:str(group);owner._stat=lambda pid:{'start':123}
        def missing(owner,path,exclude_memory_under=None,facts=None):facts.update(complete=False);raise ValueError('capacity missing')
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':0,'properties':props}),patch.object(m,'capacity_snapshot',side_effect=missing),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100)):
            with self.assertRaisesRegex(ValueError,'capacity missing'):m.operational_start(self.env)
        recorded=json.loads((directory/'initial-unit.json').read_text());self.assertFalse(recorded['capacityPassed']);self.assertEqual(recorded['properties']['InvocationID'],'a'*32);self.assertEqual(recorded['mainStartTicks'],123)

    def clock_fixture(self,start):
        keys=('EVENT','REPOSITORY','REF','SHA','WORKFLOW_REF','WORKFLOW_SHA','RUN_ID','RUN_ATTEMPT','UNIT_NAME')
        path=self.base/'retained-reference-123-1-clock.json'
        m.write(path,{'scope':'first-workflow-step','startedMonotonic':start,'boot':'synthetic','source':{key:self.env[key] for key in keys}})
        return path

    def test_actual_first_step_writer_is_exclusive_and_precedes_both_checkouts(self):
        workflow=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text()
        self.assertLess(workflow.index('Anchor the original first-step clock'),workflow.index('uses: actions/checkout'))
        code=textwrap.dedent(workflow.split("python3 -I -B <<'PY'\n",1)[1].split('          PY\n',1)[0])
        with patch.dict(os.environ,self.env,clear=True),patch('time.monotonic',return_value=100),patch.object(Path,'read_text',return_value='synthetic\n'):
            exec(compile(code,'actual-workflow-first-step','exec'),{})
            with self.assertRaises(FileExistsError):exec(compile(code,'actual-workflow-first-step','exec'),{})
        with patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:200)):
            clock=m.original_clock(self.env,'synthetic')
        self.assertEqual(clock['startedMonotonic'],100);self.assertEqual(clock['scope'],'first-workflow-step')
        self.assertEqual((self.base/'retained-reference-123-1-clock.json').stat().st_mode&0o777,0o600)

    def test_delayed_preflight_cannot_renew_original_outer_budget(self):
        self.clock_fixture(0)
        owner=types.SimpleNamespace(_read=lambda path:'synthetic')
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=owner),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:300)),patch.object(m,'capacity_snapshot',side_effect=AssertionError('late capacity reached')),patch.object(m,'read_unit',side_effect=AssertionError('late unit read reached')):
            with self.assertRaisesRegex(ValueError,'setup consumed'):m.outer_preflight(self.env)
        record=json.loads((m.outer_path(self.env)/'preflight.json').read_text())
        self.assertEqual(record['deadlineMonotonic'],2100);self.assertEqual(record['startedMonotonic'],0);self.assertEqual(record['preflightStartedMonotonic'],300);self.assertEqual(record['disposition'],'refused')
        self.assertFalse(self.root.exists())

    def test_missing_or_changed_first_step_clock_refuses(self):
        with self.assertRaisesRegex(ValueError,'unavailable'):m.original_clock(self.env,'synthetic')
        path=self.clock_fixture(0)
        with self.assertRaisesRegex(ValueError,'boot/scope'):m.original_clock(self.env,'another-boot')
        clock=json.loads(path.read_text());clock['source']['SHA']='b'*40;m.write(path,clock)
        with self.assertRaisesRegex(ValueError,'source differs'):m.original_clock(self.env,'synthetic')
        clock['source']['SHA']=self.env['SHA'];clock['startedMonotonic']=float('nan');m.write(path,clock)
        with self.assertRaisesRegex(ValueError,'malformed'):m.original_clock(self.env,'synthetic')

    def test_outer_collision_refuses_without_launch_and_retains_capacity(self):
        self.clock_fixture(m.time.monotonic())
        facts={'complete':True,'effectiveCPUs':2,'availableMemoryBytes':10*1073741824,'diskFreeBytes':20*1073741824,'boot':'synthetic'}
        def capacity(owner,path,facts=None,**kwargs):facts.update({'complete':True,'effectiveCPUs':2,'availableMemoryBytes':10*1073741824,'diskFreeBytes':20*1073741824,'boot':'synthetic'})
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=types.SimpleNamespace(_read=lambda path:'synthetic')),patch.object(m,'capacity_snapshot',side_effect=capacity),patch.object(m,'read_unit',return_value={'exit':0,'properties':{'LoadState':'loaded'}}):
            with self.assertRaisesRegex(ValueError,'collision'):m.outer_preflight(self.env)
        result=json.loads((m.outer_path(self.env)/'preflight.json').read_text());self.assertEqual(result['disposition'],'refused');self.assertEqual(result['capacity']['effectiveCPUs'],2);self.assertFalse(self.root.exists())

    def test_workflow_and_ci_wiring_preserve_all_historical_holds(self):
        workflow=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text()
        self.assertIn('  workflow_dispatch:',workflow);self.assertNotIn('  pull_request:',workflow)
        for field in ['-p CPUQuota=200%','-p TasksMax=512','-p MemoryMax=8G','-p RuntimeMaxSec=1800','-p NoNewPrivileges=yes','-p KillMode=control-group','include-hidden-files: true','timeout-minutes: 35']:self.assertIn(field,workflow)
        self.assertLess(workflow.index('--check-admission'),workflow.index('sudo -n systemd-run'))
        composition=(m.WORKSPACE/'.github/workflows/composition.yml').read_text()
        self.assertLess(composition.index('python3 tests/composition/fable-game/test-retained-reference-rehearsal.py'),composition.index('actions/setup-dotnet@v6'))
        self.assertIn('ref: ac22206560f3eddfea524ce8f752ff1d0dfeec4e',composition)
        caller=loader.actual_caller();self.assertIsNone(caller['INSTALLED_ADMISSION']);self.assertIsNone(caller['PILOT_ADMISSION']);self.assertFalse(caller['RUNTIME_ADMITTED'])
        if m.ADMISSION is not None:self.assertRegex(m.ADMISSION,r'^https://github.com/FS-GG/\.github/issues/4816#issuecomment-[0-9]+$')
        self.assertEqual(sum(m.BUDGET.values()),1800)
        tree=ast.parse((HERE/'retained-reference-rehearsal.py').read_text());function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_rehearsal')
        body=ast.get_source_segment((HERE/'retained-reference-rehearsal.py').read_text(),function)
        for forbidden in ["['prepare_inputs']","['qualify_tools']","['installed_c']","['admitted_installed_sequence']"]:self.assertNotIn(forbidden,body)


class CrossCallerControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='d5-caller-synthetic-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.admission='https://github.com/FS-GG/.github/issues/4849#issuecomment-1'
        self.contract=m.caller_contract('d5',self.admission)
        self.env={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main',
                  'SHA':'a'*40,'ADMITTED_REF':'a'*40,'CHECKOUT_HEAD':'a'*40,'WORKFLOW_SHA':'a'*40,
                  'WORKFLOW_REF':self.contract['workflow'],'RUN_ID':'123','RUN_ATTEMPT':'1',
                  'UNIT_NAME':'fsgg-mg-templates-d5-123-1','ADMISSION':self.admission,'RUNNER_TEMP':str(self.base)}

    def test_closed_namespaces_do_not_grant_foreign_admission(self):
        self.assertEqual(m.validate_admission(self.env,self.admission,self.contract)['ADMISSION'],self.admission)
        with self.assertRaises(ValueError):m.validate_admission(self.env,self.admission)
        with self.assertRaises(ValueError):m.validate_admission(self.env,None,self.contract)
        with self.assertRaises(ValueError):m.validate_admission({**self.env,'ADMISSION':self.admission+'2'},self.admission+'2',self.contract)
        for key,value in [('namespace','retained-reference'),('unitPrefix','arbitrary-'),('cap',2**40)]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):m.outer_path(self.env,{**self.contract,key:value})
        self.assertEqual(m.outer_path(self.env,self.contract).name,'current-d5-123-1-outer')
        self.assertEqual(m.outer_path(self.env).name,'retained-reference-123-1-outer')

    def test_original_clock_is_scoped_to_actual_caller_without_renewal(self):
        keys=('EVENT','REPOSITORY','REF','SHA','WORKFLOW_REF','WORKFLOW_SHA','RUN_ID','RUN_ATTEMPT','UNIT_NAME')
        value={'scope':'first-workflow-step','startedMonotonic':100,'boot':'synthetic','source':{k:self.env[k] for k in keys}}
        self.env.update(SELECTED_UTC='2026-10-23T23:59:59Z',LATEST_START_UTC='2026-10-24T00:04:59Z',OBSERVER_DEADLINE_UTC='2026-10-24T00:39:59Z')
        value.update(observedUTC='2026-10-24T00:00:00Z',rootSelection={k:self.env[k] for k in ('SELECTED_UTC','LATEST_START_UTC','OBSERVER_DEADLINE_UTC')},observerDeadlineMonotonic=2499,disposition='accepted')
        path=self.base/'current-d5-123-1-clock.json';path.write_text(json.dumps(value))
        with patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:101)):
            self.assertEqual(m.original_clock(self.env,'synthetic',self.contract)['startedMonotonic'],100)
            with self.assertRaises(ValueError):m.original_clock(self.env,'synthetic')
            value['source']['UNIT_NAME']='fsgg-mg-templates-retained-123-1';path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):m.original_clock(self.env,'synthetic',self.contract)

    def test_d5_evidence_is_bounded_and_cannot_select_foreign_paths(self):
        root=self.base/'current-d5-123-1';root.mkdir();(root/'author.json').write_text('{"synthetic":true}')
        (root/'d5-evidence-inputs.json').write_text('["author.json"]')
        result=m.collect(root,m.time.monotonic()+5,self.contract)
        self.assertEqual([r['path'] for r in result['files']],['author.json'])
        self.assertTrue((root/'d5-evidence/author.json').exists());self.assertFalse((root/'retained-evidence').exists())
        for index,value in enumerate(['../outside','/outside']):
            other=self.base/str(index);other.mkdir();(other/'d5-evidence-inputs.json').write_text(json.dumps([value]))
            with self.assertRaises(ValueError):m.collect(other,m.time.monotonic()+5,self.contract)

    def test_d5_post_unit_joins_same_outer_namespace_and_failed_original_client(self):
        directory=m.outer_path(self.env,self.contract);directory.mkdir()
        source=m.validate_admission(self.env,self.admission,self.contract)
        group=self.base/'absent-cgroup'
        initial={'source':source,'boot':'synthetic','cgroupPath':str(group),'mainStartTicks':10,
                 'properties':{'Id':self.env['UNIT_NAME']+'.service','InvocationID':'a'*32,'ControlGroup':'/synthetic','MainPID':'7'}}
        (directory/'preflight.json').write_text(json.dumps({'source':source,'deadlineMonotonic':2100}))
        (directory/'initial-unit.json').write_text(json.dumps(initial))
        (directory/'client-exit.json').write_text(json.dumps({'source':source,'clientExit':'7'}))
        def read(path):
            if path=='/proc/sys/kernel/random/boot_id':return 'synthetic'
            raise FileNotFoundError(path)
        owner=types.SimpleNamespace(_read=read)
        with patch.object(m,'probe_owner',return_value=owner),patch.object(m,'read_unit',return_value={'exit':1,'properties':{'LoadState':'not-found'}}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:101)):
            result=m.post_unit(self.env,self.contract)
        self.assertEqual(result['disposition'],'original-unit-absent');self.assertEqual(result['originalClientExit'],'7')
        self.assertFalse(m.outer_path(self.env).exists())


EARLIER_PUBLIC_NUSPECS = {'0.10.0': b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">\n  <metadata>\n    <id>FS.GG.Workspace.Template</id>\n    <version>0.10.0</version>\n    <title>FS.GG workspace templates</title>\n    <authors>FS-GG</authors>\n    <license type="expression">MIT</license>\n    <licenseUrl>https://licenses.nuget.org/MIT</licenseUrl>\n    <readme>README.md</readme>\n    <projectUrl>https://github.com/FS-GG/FS.GG.Templates</projectUrl>\n    <description>dotnet new workspace templates for FS.GG.SDD: governance, production-shaped F# console workspaces, and neutral F# ASP.NET Core plus TypeScript web workspaces.</description>\n    <tags>dotnet-new templates fsgg sdd governance console web typescript aspnetcore</tags>\n    <packageTypes>\n      <packageType name="Template" />\n    </packageTypes>\n    <repository type="git" url="https://github.com/FS-GG/FS.GG.Templates" commit="565ad45d2dda386e9d1673071cc0b424cfd02be6" />\n  </metadata>\n</package>', '0.11.0': b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">\n  <metadata>\n    <id>FS.GG.Workspace.Template</id>\n    <version>0.11.0</version>\n    <title>FS.GG workspace templates</title>\n    <authors>FS-GG</authors>\n    <license type="expression">MIT</license>\n    <licenseUrl>https://licenses.nuget.org/MIT</licenseUrl>\n    <readme>README.md</readme>\n    <projectUrl>https://github.com/FS-GG/FS.GG.Templates</projectUrl>\n    <description>dotnet new workspace templates for FS.GG.SDD: governance, production-shaped F# console workspaces, and neutral F# ASP.NET Core plus TypeScript web workspaces.</description>\n    <tags>dotnet-new templates fsgg sdd governance console web typescript aspnetcore</tags>\n    <packageTypes>\n      <packageType name="Template" />\n    </packageTypes>\n    <repository type="git" url="https://github.com/FS-GG/FS.GG.Templates" commit="6a66e0a31c33feab4c8f650709b585df6ac3d4c4" />\n  </metadata>\n</package>', '0.12.0': b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd">\n  <metadata>\n    <id>FS.GG.Workspace.Template</id>\n    <version>0.12.0</version>\n    <title>FS.GG workspace templates</title>\n    <authors>FS-GG</authors>\n    <license type="expression">MIT</license>\n    <licenseUrl>https://licenses.nuget.org/MIT</licenseUrl>\n    <readme>README.md</readme>\n    <projectUrl>https://github.com/FS-GG/FS.GG.Templates</projectUrl>\n    <description>dotnet new workspace templates for FS.GG.SDD: governance, production-shaped F# console workspaces, and neutral F# ASP.NET Core plus TypeScript web workspaces.</description>\n    <tags>dotnet-new templates fsgg sdd governance console web typescript aspnetcore</tags>\n    <packageTypes>\n      <packageType name="Template" />\n    </packageTypes>\n    <repository type="git" url="https://github.com/FS-GG/FS.GG.Templates" commit="7146224843419a10613b0f23c781b38bc88514b8" />\n  </metadata>\n</package>'}

class EarlierWorld(World):
    """Actual fixed earlier caller with synthetic runtime images/receipts only."""
    def __init__(self,root,canonical,fail=None):
        super().__init__(root,canonical,fail)
        prefix='content/templates/fs-gg-fable-game/'
        for version in m.EARLIER_VERSIONS:
            files=synthetic_package('FS.GG.Workspace.Template',version)
            files['FS.GG.Workspace.Template.nuspec']=EARLIER_PUBLIC_NUSPECS[version]
            files[prefix+'global.json']=b'{"sdk":{"version":"10.0.400","rollForward":"disable"}}'
            files[prefix+'.config/dotnet-tools.json']=b'{"version":1,"isRoot":true,"tools":{"fable":{"version":"5.13.0","commands":["fable"]}}}'
            if fail=='source-'+version:files['FS.GG.Workspace.Template.nuspec']+=b' '
            self.packages[version]=files

    def download(self,url,path,maximum,deadline,expected=None,algorithm='sha256'):
        selected=next((v for v in m.EARLIER_VERSIONS if path.name=='fs.gg.workspace.template.'+v+'.nupkg'),None)
        if selected:
            with zipfile.ZipFile(path,'w') as archive:
                for name,data in self.packages[selected].items():archive.writestr(name,data)
            return {'url':url,'bytes':path.stat().st_size,'digest':m.sha(path),'synthetic':True}
        return super().download(url,path,maximum,deadline,expected,algorithm)

    def response(self,argv,env):
        if Path(argv[0]).name=='systemctl':return super().response(argv,env).replace('RuntimeMaxUSec=30min','RuntimeMaxUSec=51min')
        if argv[1:3]==['new','install']:
            archive=Path(argv[3]);version=next((v for v in m.EARLIER_VERSIONS if v in archive.name),'0.19.3')
            home=Path(env['DOTNET_CLI_HOME'])/'.templateengine';home.mkdir(parents=True,exist_ok=True)
            m.write(home/'packages.json',{'Packages':[{'Details':{'PackageId':'FS.GG.Workspace.Template','Version':version},'MountPointUri':str(archive)}]});return ''
        if argv[1:3]==['new','fs-gg-fable-game']:
            destination=Path(argv[argv.index('-o')+1]);key='target' if destination.name=='candidate' else destination.name
            if self.fail=='generate-'+key:raise ValueError('original earlier generation failure '+key)
            self.materialize(key,destination,argv[argv.index('-n')+1]);return ''
        if len(argv)>3 and Path(argv[3]).name=='verify-current-reference-adoption.py':
            source=Path(argv[argv.index('--receiver')+1]);out=Path(argv[argv.index('--output')+1]);target=out/'adopted';shutil.copytree(source,target)
            m.write(out/'transaction-controls.json',{'controls':['SYNTHETIC TRANSACTION; existing separate copied-fixture suite covers real helper']})
            (target/'global.json').write_bytes((self.root/'candidate/global.json').read_bytes())
            data=json.loads((target/'.config/dotnet-tools.json').read_text());data['tools']['fable']={'version':'5.18.0','commands':['fable']};m.write(target/'.config/dotnet-tools.json',data);return ''
        if argv[1:2]==['restore']:
            version=next(v for v in m.EARLIER_VERSIONS if 'V'+v.replace('.','') in argv[2])
            if self.fail=='restore-'+version:raise ValueError('original earlier restore failure '+version)
            return 'SYNTHETIC EARLIER LOCKED RESTORE\n'
        return super().response(argv,env)


class EarlierControls(unittest.TestCase):
    setUpClass=Controls.__dict__["setUpClass"]
    setUp=Controls.setUp
    # Reuse only fixture setup/canonical source qualification, not inherited tests.
    def drive_earlier(self,fail=None):
        self.root=self.base/'retained-earlier-three-123-1';world=EarlierWorld(self.root,self.canonical,fail)
        env={**self.env,'UNIT_NAME':'fsgg-mg-templates-earlier-three-123-1'}
        admission=m.validate_admission(env,env['ADMISSION'],m.caller_contract('earlier-three',env['ADMISSION']))
        original_registration=m.template_registration
        def registration(home,root,version,expected):
            archive=root/'downloads'/('fs.gg.workspace.template.'+version+'.nupkg')
            return original_registration(home,root,version,m.sha(archive))
        with patch.object(m,'validate_admission',return_value=admission),patch.object(m,'load_file',return_value=types.SimpleNamespace(actual_caller=lambda:world.caller)),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100.5)),patch.object(m,'original_clock',return_value={'startedMonotonic':100}),patch.object(m,'operational_start',return_value={'boot':'synthetic','properties':{'InvocationID':'a'*32,'ControlGroup':'/system.slice/unit.service','MainPID':'42'}}),patch.object(m,'acquisition_capacity',return_value={'synthetic':True}),patch.object(m,'template_registration',side_effect=registration),patch.object(m,'earlier_sandbox_prerequisite',return_value='SYNTHETIC only; focused real-probe controls are separate'):
            result=m.run_earlier_three(env)
        return result,world

    def test_earlier_hold_precedes_io(self):
        with patch.object(m,'EARLIER_ADMISSION',None),patch.object(m,'load_file',side_effect=AssertionError('loader reached')),self.assertRaisesRegex(ValueError,'no source admission'):m.run_earlier_three(self.env)
        self.assertFalse((self.base/'retained-earlier-three-123-1').exists())

    def test_earlier_fixed_profiles_and_old_defaults(self):
        self.assertEqual(sum(seconds for _,seconds in m.EARLIER_PHASES),3000)
        self.assertEqual(m.scope_limits(m.caller_contract('earlier-three',None)),(3060,3300))
        for name in ('retained','d5','composition'):self.assertEqual(m.scope_limits(m.caller_contract(name,None)),(1800,2100))
        self.assertEqual(sum(m.BUDGET.values()),1800)
        self.assertEqual(m.earlier_deadline(100,'0.12.0-restore',101),581)
        with self.assertRaises(ValueError):m.earlier_deadline(100,'0.12.0-restore',2800)
        with self.assertRaises(ValueError):m.earlier_steps(self.root,'sdk',{},'0.13.0')

    def test_earlier_actual_three_call_order_independent_hives_and_profiles(self):
        result,world=self.drive_earlier();self.assertEqual(list(result['cohorts']),list(m.EARLIER_VERSIONS));self.assertEqual(result['disposition'],'passed')
        self.assertFalse(result['whole4816Acceptance']);self.assertEqual(result['browserCases'],0)
        creates=[(argv,env) for argv,env in zip(world.calls,world.environments) if argv[1:3]==['new','fs-gg-fable-game']]
        self.assertEqual(len(creates),4);self.assertEqual(len({env['DOTNET_CLI_HOME'] for _,env in creates}),4)
        for (argv,_),version in zip(creates[1:],m.EARLIER_VERSIONS):
            self.assertEqual('--svgFoundation' in argv,version!='0.10.0');self.assertEqual(argv[argv.index('--lifecycle')+1],'none')
        restores=[argv for argv in world.calls if argv[1:2]==['restore']];self.assertEqual(len(restores),3)
        self.assertFalse(any('scaffold' in argv or '0.13.0' in ' '.join(argv) for argv in world.calls))
        self.assertFalse(any('build' in argv or 'npm' in argv or 'fable' in argv for argv in world.calls))
        for profile,until in world.profiles:
            self.assertEqual(profile['retirement']['onLeaderExit'],'require-empty');self.assertLessEqual(until,2800)
            self.assertTrue(Path(profile['cwd']).is_relative_to(self.root))
        receipts=json.loads((self.root/'managed-receipts.json').read_text());self.assertEqual([row['index'] for row in receipts],list(range(1,len(receipts)+1)))
        evidence=self.root/'earlier-three-evidence';index=json.loads((evidence/'manifest.json').read_text())
        for row in index['files']:
            path=evidence/row['path'];self.assertEqual(m.sha(path),row['sha256']);self.assertEqual(path.stat().st_size,row['bytes'])
        for version in m.EARLIER_VERSIONS:
            self.assertEqual(json.loads((self.root/('locks-'+version+'-before.json')).read_text()),json.loads((self.root/('locks-'+version+'-after.json')).read_text()))
            self.assertTrue((evidence/'transactions'/version/'transaction-controls.json').is_file())

    def test_earlier_source_mismatch_blocks_all_generation(self):
        with self.assertRaisesRegex(ValueError,'NuSpec bytes differ'):self.drive_earlier('source-0.11.0')
        self.assertFalse((self.root/'candidate').exists());self.assertFalse((self.root/'receivers').exists())
        first=json.loads((self.root/'earlier-three-evidence/rehearsal.json').read_text())['firstCause'];self.assertIn('NuSpec bytes differ',first)

    def test_earlier_second_generation_failure_blocks_later_and_keeps_first(self):
        with self.assertRaisesRegex(RuntimeError,'original earlier generation failure'):self.drive_earlier('generate-0.11.0')
        record=json.loads((self.root/'earlier-three-evidence/rehearsal.json').read_text());self.assertEqual(record['cohorts']['0.10.0']['disposition'],'materialized-adopted-locked-restore-passed');self.assertNotIn('0.12.0',record['cohorts'])
        self.assertFalse((self.root/'receivers/0.12.0').exists())

    def test_earlier_second_restore_failure_preserves_after_and_blocks_third(self):
        with self.assertRaisesRegex(RuntimeError,'original earlier restore failure'):self.drive_earlier('restore-0.11.0')
        self.assertTrue((self.root/'locks-0.11.0-after.json').is_file());self.assertFalse((self.root/'receivers/0.12.0').exists())

    def test_earlier_real_public_nuspec_fixture_and_edited_metadata_refusal(self):
        for version in m.EARLIER_VERSIONS:
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                archive.writestr('fixture.nuspec',EARLIER_PUBLIC_NUSPECS[version]);archive.writestr('content/templates/fs-gg-fable-game/.template.config/template.json','{"sources":[],"symbols":{}}')
            stream.seek(0)
            with zipfile.ZipFile(stream) as archive:self.assertEqual(m.earlier_metadata(archive,version)['repositoryCommit'],m.EARLIER_SOURCES[version][0])
        self.assertEqual(set(m.earlier_inputs(m.WORKSPACE)),set(m.EARLIER_VERSIONS))

    def test_earlier_reporting_failure_preserves_first_and_attempts_terminal(self):
        self.root.mkdir();summary={'disposition':'failed','executionDisposition':'failed','firstCause':'owner first','additionalFailures':[],'phases':{}};primary=ValueError('owner first');events=[]
        with patch.object(m,'write',side_effect=OSError('secondary index failure')),patch.object(m,'collection_terminal',side_effect=lambda *args:events.append('terminal')):
            m.finish_earlier(self.root,summary,[],primary,100,m.caller_contract('earlier-three',None))
        self.assertEqual(events,['terminal']);self.assertEqual(summary['firstCause'],'owner first');self.assertIn('index failure',str(primary.__notes__))

    def test_earlier_actual_late_original_clock_refuses_before_capacity_or_unit(self):
        env={**self.env,'UNIT_NAME':'fsgg-mg-templates-earlier-three-123-1','SELECTED_UTC':'2026-10-24T01:59:59Z','LATEST_START_UTC':'2026-10-24T02:04:59Z','OBSERVER_DEADLINE_UTC':'2026-10-24T02:59:59Z'};contract=m.caller_contract('earlier-three',env['ADMISSION'])
        keys=('EVENT','REPOSITORY','REF','SHA','WORKFLOW_REF','WORKFLOW_SHA','RUN_ID','RUN_ATTEMPT','UNIT_NAME')
        m.write(self.base/'retained-earlier-three-123-1-clock.json',{'scope':'first-workflow-step','startedMonotonic':100,'boot':'synthetic','source':{k:env[k] for k in keys},'rootSelection':{k:env[k] for k in ('SELECTED_UTC','LATEST_START_UTC','OBSERVER_DEADLINE_UTC')},'observedUTC':'2026-10-24T02:04:59Z','observerDeadlineMonotonic':3400,'disposition':'accepted'})
        with patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:306)),patch.object(m,'probe_owner',return_value=types.SimpleNamespace(_read=lambda p:'synthetic')),patch.object(m,'capacity_snapshot',side_effect=AssertionError('capacity reached')),patch.object(m,'read_unit',side_effect=AssertionError('unit reached')),self.assertRaisesRegex(ValueError,'original setup consumed'):
            m.outer_preflight(env,contract)
        pre=json.loads((self.base/'retained-earlier-three-123-1-outer/preflight.json').read_text());self.assertEqual(pre['deadlineMonotonic'],3400);self.assertEqual(pre['disposition'],'refused')

    def test_earlier_workflow_separates_original_budget_and_fixed_held_route(self):
        source=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text()
        original,earlier=source.split('  earlier-three:\n',1)
        self.assertIn('timeout-minutes: 35',original);self.assertIn('RuntimeMaxSec=1800',original)
        self.assertIn('timeout-minutes: 55',earlier);self.assertIn('RuntimeMaxSec=3060',earlier)
        self.assertIn('retained-reference-rehearsal.py --earlier-three --check-admission',earlier)
        self.assertLess(earlier.index('Anchor the original'),earlier.index('actions/checkout'))
        self.assertIn('default: retained-13',source);self.assertNotIn('baseline_version:',source)


class EarlierClockControls(unittest.TestCase):
    def setUp(self):
        import datetime,textwrap
        self.temp=tempfile.TemporaryDirectory(prefix='earlier-clock-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.env={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main','SHA':'a'*40,'ADMITTED_REF':'a'*40,'CHECKOUT_HEAD':'a'*40,'WORKFLOW_REF':m.WORKFLOW,'WORKFLOW_SHA':'a'*40,'RUN_ID':'42','RUN_ATTEMPT':'1','UNIT_NAME':'fsgg-mg-templates-earlier-three-42-1','RUNNER_TEMP':str(self.root),'ADMISSION':m.EARLIER_ADMISSION,'SELECTED_UTC':'2026-10-24T01:59:59Z','LATEST_START_UTC':'2026-10-24T02:04:59Z','OBSERVER_DEADLINE_UTC':'2026-10-24T02:59:59Z'}
        source=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text();self.producer=textwrap.dedent(source.split("python3 -I -B <<'PY_EARLIER_CLOCK'\n",1)[1].split('          PY_EARLIER_CLOCK',1)[0]);self.now=datetime.datetime(2026,10,24,2,0,tzinfo=datetime.timezone.utc)
    def produce(self,now=None):
        import datetime
        value=self.now if now is None else now
        class SyntheticUTC(datetime.datetime):
            @classmethod
            def now(cls,tz=None):return value
        with patch.dict(os.environ,self.env,clear=True),patch.object(datetime,'datetime',SyntheticUTC),patch('time.monotonic',return_value=100):exec(compile(self.producer,'actual-earlier-first-clock','exec'),{})
        return json.loads((self.root/'retained-earlier-three-42-1-clock.json').read_text())
    def test_actual_producer_reader_projection_and_literal_cutoff_join(self):
        clock=self.produce();m.validate_earlier_original_clock(clock,self.env);self.assertEqual(clock['observerDeadlineMonotonic'],3699)
        self.assertIn(m.EARLIER_CONDITIONAL_CUTOFF_UTC,self.producer)
        with patch.object(m.time,'monotonic',return_value=150):self.assertEqual(m.original_clock(self.env,clock['boot'],m.caller_contract('earlier-three',m.EARLIER_ADMISSION)),clock)
        self.assertEqual(clock['observerDeadlineMonotonic'],3699)
    def test_late_queue_retains_original_refusal_without_checkout(self):
        import datetime
        with self.assertRaisesRegex(ValueError,'window refused'):self.produce(now=self.now+datetime.timedelta(seconds=300))
        record=json.loads((self.root/'retained-earlier-three-42-1-clock.json').read_text());self.assertEqual(record['disposition'],'refused');self.assertIn('window refused',record['firstCause'])
        source=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text().split('  earlier-three:\n',1)[1]
        self.assertIn("always() && steps.clock.outcome != 'skipped'",source);self.assertIn('1-clock.json',source)
    def test_wrong_intervals_cutoff_and_old_grants_refuse(self):
        for change in ({'LATEST_START_UTC':'2026-10-24T02:05:00Z'},{'OBSERVER_DEADLINE_UTC':'2026-10-24T02:39:59Z'},{'SELECTED_UTC':''},{'SELECTED_UTC':'2026-10-24T03:31:00Z','LATEST_START_UTC':'2026-10-24T03:36:00Z','OBSERVER_DEADLINE_UTC':'2026-10-24T04:31:00Z'}):
            with self.subTest(change=change),self.assertRaises(ValueError):m.earlier_root_times({**self.env,**change})
        contract=m.caller_contract('earlier-three',m.EARLIER_ADMISSION)
        for old in (m.ADMISSION,'https://github.com/FS-GG/.github/issues/4849#issuecomment-6378268333'):
            with self.assertRaises(ValueError):m.validate_admission({**self.env,'ADMISSION':old},m.EARLIER_ADMISSION,contract)
    def test_projection_source_boot_and_input_tamper_refuse(self):
        clock=self.produce()
        value=json.loads(json.dumps(clock));value['observerDeadlineMonotonic']+=1
        with self.assertRaises(ValueError):m.validate_earlier_original_clock(value,self.env)
        with self.assertRaises(ValueError):m.validate_earlier_original_clock(clock,{**self.env,'LATEST_START_UTC':'2026-10-24T02:04:58Z'})
        with patch.object(m.time,'monotonic',return_value=150),self.assertRaises(ValueError):m.original_clock(self.env,'other-boot',m.caller_contract('earlier-three',m.EARLIER_ADMISSION))
    def test_literal_supported_probe_images_and_cleared_environment(self):
        seen=[];identities={};summary={}
        caller={'host_image':lambda path:(path,'a'*64 if path.endswith('unshare') else 'b'*64),'bind_identity':lambda ids,path,basis,**kw:ids.update({path:{'basis':basis,'images':kw.get('images',['b'*64])}})}
        result=m.earlier_sandbox_prerequisite(caller,lambda *a:seen.append(a) or 'synthetic',identities,self.root,summary)
        self.assertEqual(result,'synthetic');self.assertEqual(seen,[(['/usr/bin/unshare','--user','--map-root-user','--net','--','/usr/bin/true'],self.root,{'LANG':'C.UTF-8','TZ':'UTC'})]);self.assertEqual(identities['/usr/bin/unshare']['images'],['a'*64,'b'*64]);self.assertEqual(summary['sandboxPrerequisite']['disposition'],'managed-literal-probe-passed')
    def test_actual_earlier_probe_failure_blocks_bulk_acquisition_and_preserves_cause(self):
        actual_d5=m.load_file('clock-test-d5-source',HERE/'d5-managed-runtime.py');events=[];root=self.root/'retained-earlier-three-42-1'
        def fresh(path,env):path.mkdir();return {}
        def run(argv,cwd,env,**kw):events.append(argv);raise ValueError('original synthetic unshare denied')
        caller={'fresh_environment':fresh,'load_owner':lambda *a:object(),'probe_containment':lambda *a:None,'managed_executor':lambda *a:run,'host_image':lambda path:(path,'a'*64 if path.endswith('unshare') else 'b'*64),'bind_identity':lambda ids,path,basis,**kw:ids.update({path:{'synthetic':True}})}
        def loader(name,path):return actual_d5 if name=='earlier_supported_sandbox' else types.SimpleNamespace(actual_caller=lambda:caller)
        env={**self.env,'GITHUB_WORKSPACE':str(m.WORKSPACE)}
        with patch.object(m,'load_file',side_effect=loader),patch.object(m,'validate_admission',return_value={'synthetic':True}),patch.object(m,'operational_start',return_value={'boot':'synthetic'}),patch.object(m,'original_clock',return_value={'startedMonotonic':100}),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100.5)),patch.object(m,'unit_properties',return_value={}),patch.object(m,'acquisition_capacity',return_value={}),self.assertRaisesRegex(ValueError,'original synthetic unshare denied'):m.run_earlier_three(env)
        self.assertEqual(len(events),1);self.assertEqual(events[0][0],'/usr/bin/unshare');self.assertFalse((root/'tools').exists());self.assertFalse((root/'downloads').exists())
        summary=json.loads((root/'earlier-three-evidence/rehearsal.json').read_text());self.assertIn('original synthetic unshare denied',summary['firstCause']);self.assertEqual(summary['sandboxPrerequisite']['disposition'],'started')


class HostedUsernsStepControls(unittest.TestCase):
    """Earlier-three hosted AppArmor prerequisite step: scope, order and nothing else changed."""
    def setUp(self):
        workflow=(m.WORKSPACE/'.github/workflows/retained-reference-rehearsal.yml').read_text()
        self.workflow=workflow
        self.job=workflow.split('  earlier-three:\n',1)[1]
        self.original=workflow.split('  earlier-three:\n',1)[0]

    def test_single_hosted_guarded_sysctl_between_capacity_and_unit_in_earlier_three_only(self):
        self.assertEqual(self.workflow.count('sysctl -w'),1)
        self.assertNotIn('sysctl',self.original.split('jobs:',1)[1])
        capacity=self.job.index('id: capacity');step=self.job.index('id: userns')
        unit=self.job.index('- name: Run the fixed rehearsal in a fresh delegated unit')
        self.assertLess(capacity,step);self.assertLess(step,unit)
        body=self.job[step:unit]
        for token in ('set -euo pipefail','test "${RUNNER_ENVIRONMENT:-}" = github-hosted','mkdir -m 700',
                      'key=kernel.apparmor_restrict_unprivileged_userns','sudo -n sysctl -w "$key=0"','grep -qx "$key = 0"'):
            self.assertIn(token,body)
        self.assertLess(body.index('before.txt'),body.index('sysctl -w'));self.assertLess(body.index('sysctl -w'),body.index('after.txt'))
        self.assertNotIn('continue-on-error',self.job[step-400:unit])
        self.assertNotIn('if:',body.split('run:',1)[0])

    def test_unit_properties_unchanged_and_userns_evidence_uploaded(self):
        unit=self.job.split('- name: Run the fixed rehearsal in a fresh delegated unit',1)[1]
        for token in ('-p NoNewPrivileges=yes','-p Delegate=yes','-p TasksMax=512','-p MemoryMax=8G','-p RuntimeMaxSec=3060','-p CPUQuota=200%'):
            self.assertIn(token,unit)
        self.assertEqual(unit.count('sysctl'),0)
        self.assertIn('retained-earlier-three-${{ github.run_id }}-1-userns/',self.job.split('- name: Retain bounded original rehearsal evidence',1)[1])



if __name__=='__main__':
    print('SYNTHETIC fixed-call graph, archive bodies, executables and receipts; real canonical profile validation only. No native member or runtime executes.')
    unittest.main(verbosity=2,buffer=True)
