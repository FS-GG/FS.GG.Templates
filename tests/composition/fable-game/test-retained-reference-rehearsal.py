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
        with patch.object(m,'validate_admission',return_value=admission),patch.object(m,'load_file',return_value=types.SimpleNamespace(actual_caller=lambda:world.caller)),patch.object(m,'time',types.SimpleNamespace(monotonic=lambda:100.5)),patch.object(m,'operational_start',return_value={'properties':{'InvocationID':'a'*32,'ControlGroup':'/system.slice/unit.service','MainPID':'42'}}):
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

    def test_effective_ancestor_capacity_and_unit_memory_exclusion(self):
        data={'/proc/meminfo':'MemTotal: 33554432 kB\nMemAvailable: 20971520 kB\n','/proc/sys/kernel/random/boot_id':'boot-synthetic'}
        for directory in ['/cg/parent','/cg/parent/unit','/cg/parent/unit/fsgg-supervisor']:
            data[directory+'/cpu.max']='max 100000'
            data[directory+'/memory.current']=str(1*1073741824)
            data[directory+'/memory.max']='max';data[directory+'/memory.high']='max'
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

    def test_outer_collision_refuses_without_launch_and_retains_capacity(self):
        facts={'complete':True,'effectiveCPUs':2,'availableMemoryBytes':10*1073741824,'diskFreeBytes':20*1073741824,'boot':'synthetic'}
        def capacity(owner,path,facts=None,**kwargs):facts.update({'complete':True,'effectiveCPUs':2,'availableMemoryBytes':10*1073741824,'diskFreeBytes':20*1073741824,'boot':'synthetic'})
        with patch.object(m,'ADMISSION',self.env['ADMISSION']),patch.object(m,'probe_owner',return_value=object()),patch.object(m,'capacity_snapshot',side_effect=capacity),patch.object(m,'read_unit',return_value={'exit':0,'properties':{'LoadState':'loaded'}}):
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


if __name__=='__main__':
    print('SYNTHETIC fixed-call graph, archive bodies, executables and receipts; real canonical profile validation only. No native member or runtime executes.')
    unittest.main(verbosity=2,buffer=True)
