#!/usr/bin/env python3
"""Synthetic actual-consumer controls; no process owner/CLR/network/unit runs."""
import sys
sys.dont_write_bytecode = True
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

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('d5_managed', HERE/'d5-managed-runtime.py')
D5 = importlib.util.module_from_spec(spec);spec.loader.exec_module(D5)


class SyntheticOwner:
    OWNER_SHA256 = D5.OWNER['sha256']
    OWNER_PATH = '/synthetic/canonical-owner.py'
    class GroupFailed(Exception):
        def __init__(self, receipt): self.receipt = receipt
    @staticmethod
    def validate_profile(profile):
        # Synthetic owner contract double only; real schema validation remains canonical.
        return profile, hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


class ManagedConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.cwd = self.root/'receiver';self.cwd.mkdir()
        self.core = self.root/'sdd.dll';self.core.write_bytes(b'synthetic installed core')
        self.arguments = ['typed-sdd','author','--work','d5-refused','--root',str(self.cwd),'--bindings','models/refused.bindings.json']
        self.argv = ['/synthetic/dotnet',str(self.core),*self.arguments]
        self.env = {'HOME':str(self.root/'home')};self.receipts=[];self.calls=[]
        self.directory = self.root/'managed-001';self.directory.mkdir()
        self.profile = {'schema':'fsgg.managed-group-profile/1','name':'installed-001-dotnet','root':str(self.root),
                        'executable':{'path':self.argv[0],'sha256':'a'*64},'leaderImages':['a'*64],
                        'argv':self.argv,'cwd':str(self.cwd),'environmentKeys':sorted(self.env),
                        'containment':'cgroup2-delegated','limits':{},'retirement':{'onLeaderExit':'require-empty'}}
        self.receipt = {'schema':'fsgg.managed-group-receipt/1','contract':'fsgg.managed-group-contract/1',
                        'owner':{'sha256':D5.OWNER['sha256'],'path':SyntheticOwner.OWNER_PATH},'profile':self.profile,
                        'invocationId':'b'*32,'bootId':'synthetic','leader':{'pid':7,'start':10,'pidfdInode':12,'image':'admitted','imageSha256':'a'*64,'noNewPrivileges':'1','cmdline':self.argv},
                        'profileSha256':SyntheticOwner.validate_profile(self.profile)[1],
                        'launch':{'attempted':True,'launched':True},'exit':{'code':1,'signal':None},
                        'outcome':'failed','refusal':None,'firstCause':'RuntimeError: command failed with exit 1',
                        'additionalFailures':[],'cleanup':'observed-empty-removed','custody':'contained',
                        'escaped':[],'residualInRoot':[],'createdCgroups':[],
                        'retirement':{'leaderReaped':True,'leafRemoved':True,'populatedAfter':False},'streams':{}}
        for name, body in [('stdout',b'{"synthetic":"not semantic acceptance"}\n'),('stderr',b'')]:
            path=self.directory/(name+'.log');path.write_bytes(body)
            self.receipt['streams'][name]={'eof':True,'capped':False,'sinkError':None,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        self.persist()

    def persist(self): (self.directory/'receipt.json').write_text(json.dumps(self.receipt))
    def execute(self, argv, cwd, env, inputs):
        self.calls.append((argv,cwd,env,inputs))
        self.receipts.append({'status':'failed','executable':argv[0],'outDir':str(self.directory),'inputs':{str(self.core):D5.sha(self.core)}})
        raise RuntimeError('canonical executor retained original failure') from SyntheticOwner.GroupFailed(self.receipt)
    def consume(self, execute=None, arguments=None):
        return D5.wrong_profile(execute or self.execute,SyntheticOwner,self.receipts,self.argv,self.core,
                                self.arguments if arguments is None else arguments,self.cwd,self.env)

    def test_actual_refusal_consumer_retains_original_failed_receipt(self):
        original=copy.deepcopy(self.receipt)
        result=self.consume()
        self.assertEqual(result,self.directory/'stdout.log')
        self.assertEqual(D5.read_json(self.directory/'receipt.json'),original)
        self.assertEqual(self.receipt['outcome'],'failed')
        self.assertEqual(self.calls[0][3],[self.core])
        # Transport acceptance cannot make malformed/missing semantic JSON qualified.
        self.assertNotIn('passed', result.read_text())

    def test_cleanup_birth_stream_caps_escape_and_wrong_exit_are_not_expected(self):
        changes=[('cleanup','unknown'),('custody','escaped-retired'),('additionalFailures',['late cleanup failure']),
                 ('firstCause','RuntimeError: original deadline exhausted'),('escaped',[{'pid':7}]),
                 ('residualInRoot',[{'pid':7}]),('exit',{'code':None,'signal':9}),('exit',{'code':0,'signal':None}),
                 ('exit',{'code':True,'signal':None}),('launch',{'attempted':True,'launched':False}),
                 ('retirement',{'leaderReaped':False,'leafRemoved':True,'populatedAfter':False}),
                 ('createdCgroups',[{'removed':False}]),('leader',None),('invocationId',''),('bootId',None)]
        original=copy.deepcopy(self.receipt)
        for key,value in changes:
            with self.subTest(key=key,value=value):
                self.receipt=copy.deepcopy(original);self.receipt[key]=value;self.persist()
                with self.assertRaises(ValueError):self.consume()
        for field,value in [('eof',False),('capped',True),('sinkError','failed'),('sha256','0'*64),('bytes',-1)]:
            with self.subTest(field=field):
                self.receipt=copy.deepcopy(original);self.receipt['streams']['stdout'][field]=value;self.persist()
                with self.assertRaises(ValueError):self.consume()

    def test_original_receipt_and_command_identity_are_causal(self):
        original=copy.deepcopy(self.receipt)
        self.receipt['profile']['argv']=['other'];self.receipt['profileSha256']=SyntheticOwner.validate_profile(self.receipt['profile'])[1];self.persist()
        with self.assertRaises(ValueError):self.consume()
        self.receipt=copy.deepcopy(original);self.persist();(self.directory/'stdout.log').write_text('tampered')
        with self.assertRaises(ValueError):self.consume()
        (self.directory/'receipt.json').unlink()
        with self.assertRaises(ValueError):self.consume()

    def test_success_unrelated_exception_and_missing_index_do_not_pass(self):
        with self.assertRaises(ValueError):self.consume(lambda *a,**k:'unexpected success')
        def unrelated(*a,**k):raise RuntimeError('unrelated')
        with self.assertRaises(ValueError):self.consume(unrelated)
        def with_note(*a,**k):
            error=RuntimeError('wrapped');error.add_note('index reporting failed')
            raise error from SyntheticOwner.GroupFailed(self.receipt)
        with self.assertRaises(ValueError):self.consume(with_note)
        def unindexed(*a,**k):raise RuntimeError('wrapped') from SyntheticOwner.GroupFailed(self.receipt)
        with self.assertRaises(ValueError):self.consume(unindexed)

    def test_only_exact_typed_refused_plan_is_forwarded(self):
        for args in [self.arguments+['--backend','fsharp'],self.arguments[:-1],['typed-sdd','author','--work']]:
            with self.assertRaises(ValueError):self.consume(arguments=args)
        self.assertEqual(self.calls,[])

    def test_delegation_preserves_deadline_identity_and_receipt_list(self):
        marker=object();seen=[]
        def factory(*args):seen.append(args);return marker
        identities={}
        got=D5.managed_transport({'managed_executor':factory},SyntheticOwner,self.root,123.5,identities,'backend',self.receipts)
        self.assertIs(got,marker)
        self.assertEqual(seen[0],(SyntheticOwner,self.root,123.5,identities,'installed',self.receipts))
        with self.assertRaises(ValueError):D5.managed_transport({'managed_executor':factory},SyntheticOwner,self.root,123.5,identities,'unknown',self.receipts)

    def test_original_phase_clock_never_renews(self):
        self.assertEqual(D5.phase_deadline(10,'setup',20),730)
        self.assertEqual(D5.phase_deadline(10,'backend',1500),1570)
        for start,phase,now in [(10,'setup',730),(10,'backend',1570),(10,'backend',9),(float('nan'),'setup',20)]:
            with self.assertRaises(ValueError):D5.phase_deadline(start,phase,now)

    def test_entry_and_direct_shell_fail_before_effects(self):
        sent=self.root/'sentinel';bins=self.root/'bin';bins.mkdir()
        for name in ('dotnet','curl','go','sudo','unshare','npm','git'):
            p=bins/name;p.write_text('#!/bin/sh\necho launched >>"$SENTINEL"\nexit 91\n');p.chmod(0o700)
        env={**os.environ,'PATH':str(bins)+':'+os.environ['PATH'],'SENTINEL':str(sent),'ADMISSION':'https://github.com/FS-GG/.github/issues/4849#issuecomment-1'}
        for flags in [['--check-admission'],['--outer-preflight'],['--post-unit'],['--record-client-exit'],['--run'],['--admission',env['ADMISSION']]]:
            result=subprocess.run([sys.executable,str(HERE/'d5-managed-runtime.py'),*flags],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,3)
        self.assertFalse(sent.exists())
        self.assertEqual(D5.ADMISSION,'https://github.com/FS-GG/.github/issues/4849#issuecomment-6387729342');self.assertEqual(D5.OUTER_CALLER_CONTRACT,'d5')

    def test_exact_admission_join_refuses_branches_retries_and_mixed_heads(self):
        admission='https://github.com/FS-GG/.github/issues/4849#issuecomment-1';head='a'*40
        env={'ADMISSION':admission,'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates',
             'REF':'refs/heads/main','RUN_ATTEMPT':'1','SHA':head,'ADMITTED_REF':head,'CHECKOUT_HEAD':head,
             'WORKFLOW_SHA':head,'WORKFLOW_REF':D5.WORKFLOW,'RUN_ID':'42','UNIT_NAME':'fsgg-mg-templates-d5-42-1'}
        self.assertEqual(D5.admission_join(env,admission),env)
        for key,value in [('REF','refs/heads/topic'),('RUN_ATTEMPT','2'),('CHECKOUT_HEAD','b'*40),('WORKFLOW_SHA','b'*40),('UNIT_NAME','other'),('EVENT','pull_request')]:
            with self.subTest(key=key):
                bad={**env,key:value}
                with self.assertRaises(ValueError):D5.admission_join(bad,admission)
        with self.assertRaises(ValueError):D5.admission_join(env,None)

    def test_first_setup_failure_stops_actual_fixed_caller_and_never_claims_pass(self):
        import types
        events=[]
        root=self.root/'current-d5-42-1'
        def fresh(path,environ):path.mkdir();return {'HOME':str(path/'home')}
        def owner(*args):events.append('owner');raise ValueError('original synthetic setup failure')
        caller={'fresh_environment':fresh,'load_owner':owner}
        pins={'schema':'synthetic'}
        fake=types.SimpleNamespace(
            validate_admission=lambda *a:{'synthetic':True},
            operational_start=lambda *a:{'boot':'synthetic'},normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
            load_file=lambda name,path:types.SimpleNamespace(actual_caller=lambda:caller) if name=='d5_actual_loader' else types.SimpleNamespace(PINS=pins),
            original_clock=lambda *a:{'startedMonotonic':D5.time.monotonic()},
            collect=lambda *a:{'failures':[]},collection_terminal=lambda *a:None)
        env={'RUNNER_TEMP':str(self.root),'RUN_ID':'42','UNIT_NAME':'fsgg-mg-templates-d5-42-1','GITHUB_WORKSPACE':str(D5.HERE.parents[2]),'SCOPE':'rehearsal','PUBLIC_PINS':'{"schema":"synthetic"}'}
        with self.assertRaisesRegex(ValueError,'original synthetic setup failure'):D5.run_d5(fake,{'synthetic':True},env)
        self.assertEqual(events,['owner'])
        receipt=json.loads((root/'attempt.json').read_text())
        self.assertEqual(receipt['disposition'],'failed');self.assertEqual(receipt['retirement'],'unqualified')
        self.assertIn('original synthetic setup failure',receipt['firstCause'])

    def test_actual_collection_finalizer_indexes_success_and_first_failure_without_rewriting_attempt(self):
        import types
        reader=D5.load_reader(D5.HERE.parents[2]);contract=reader.caller_contract('d5',None)
        for name,fail in [('success',False),('first-failure',True)]:
            root=self.root/name;root.mkdir()
            summary={'disposition':'receiver-checks-complete','executionDisposition':'receiver-checks-complete',
                     'firstCause':None,'additionalFailures':[],'phases':{}}
            def collect(*args):
                if fail:raise ValueError('original synthetic collector failure')
                return reader.collect(*args)
            fake=types.SimpleNamespace(collect=collect,collection_terminal=reader.collection_terminal)
            if fail:
                with self.assertRaisesRegex(ValueError,'original synthetic collector failure'):
                    D5.finish_collection(fake,contract,root,summary,[],None,D5.time.monotonic())
            else:D5.finish_collection(fake,contract,root,summary,[],None,D5.time.monotonic())
            original=json.loads((root/'attempt.json').read_text())
            self.assertEqual((root/'d5-evidence/attempt.json').read_bytes(),(root/'attempt.json').read_bytes())
            self.assertIsNone(original['firstCause'])
            terminal=root/'d5-evidence/collection-terminal.json';value=json.loads(terminal.read_text())
            if fail:self.assertIn('original synthetic collector failure',value['firstCause']);self.assertEqual(value['disposition'],'failed')
            else:
                self.assertIsNone(value['firstCause'])
                self.assertEqual((root/'d5-evidence/attempt.json').read_bytes(),(root/'attempt.json').read_bytes())
            manifest=json.loads((root/'d5-evidence/manifest.json').read_text())
            row=next(r for r in manifest['files'] if r['path']=='collection-terminal.json')
            self.assertEqual(row['sha256'],D5.sha(terminal));self.assertEqual(row['bytes'],terminal.stat().st_size)

    def test_actual_entry_preserves_setup_primary_and_indexes_secondary_collection_failure(self):
        import types
        actual=D5.load_reader(D5.HERE.parents[2]);contract=actual.caller_contract('d5',None)
        root=self.root/'current-d5-43-1'
        def fresh(path,environ):path.mkdir();return {'HOME':str(path/'home')}
        def owner(*args):raise ValueError('first synthetic setup failure')
        def collect(*args):raise ValueError('secondary synthetic collection failure')
        fake=types.SimpleNamespace(validate_admission=lambda *a:{'synthetic':True},
            operational_start=lambda *a:{'boot':'synthetic'},normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
            load_file=lambda name,path:types.SimpleNamespace(actual_caller=lambda:{'fresh_environment':fresh,'load_owner':owner}) if name=='d5_actual_loader' else types.SimpleNamespace(PINS={'synthetic':True}),
            original_clock=lambda *a:{'startedMonotonic':D5.time.monotonic()},collect=collect,collection_terminal=actual.collection_terminal)
        env={'RUNNER_TEMP':str(self.root),'RUN_ID':'43','UNIT_NAME':'fsgg-mg-templates-d5-43-1','GITHUB_WORKSPACE':str(D5.HERE.parents[2]),'SCOPE':'rehearsal','PUBLIC_PINS':'{"synthetic":true}'}
        with self.assertRaisesRegex(ValueError,'first synthetic setup failure'):D5.run_d5(fake,contract,env)
        terminal=json.loads((root/'d5-evidence/collection-terminal.json').read_text())
        self.assertIn('first synthetic setup failure',terminal['firstCause'])
        self.assertIn('secondary synthetic collection failure',terminal['additionalFailures'][0])
        original=json.loads((root/'attempt.json').read_text());self.assertEqual(original['additionalFailures'],[])

    def test_terminal_write_failure_is_explicit_unknown_and_preserves_primary(self):
        import contextlib,io,types
        def terminal(*args):raise OSError('synthetic terminal write failed')
        fake=types.SimpleNamespace(collect=lambda *a:{'failures':[]},collection_terminal=terminal)
        for name,primary in [('first',None),('secondary',ValueError('original setup failure'))]:
            root=self.root/name;root.mkdir();summary={'disposition':'failed' if primary else 'receiver-checks-complete',
                'executionDisposition':'failed' if primary else 'receiver-checks-complete',
                'firstCause':str(primary) if primary else None,'additionalFailures':[],'phases':{}}
            stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                if primary is None:
                    with self.assertRaisesRegex(OSError,'synthetic terminal write failed'):
                        D5.finish_collection(fake,{},root,summary,[],primary,D5.time.monotonic())
                else:D5.finish_collection(fake,{},root,summary,[],primary,D5.time.monotonic())
            self.assertIn('terminal collection report Unknown',stderr.getvalue())
            if primary:self.assertIn('original setup failure',str(primary));self.assertIn('Unknown',primary.__notes__[0])

    def test_actual_lmt_recipe_preserves_canonical_source_basename_and_literal_argv(self):
        go=self.root/'go/bin/go';source=self.root/'download with spaces/main.go';output=self.root/'tools/lmt'
        args=D5.lmt_build_arguments(go,source,output)
        self.assertEqual(args,[str(go),'build','-trimpath','-ldflags',D5.LMT['ldflags'],'-o',str(output),str(source)])
        with self.assertRaises(ValueError):D5.lmt_build_arguments(go,source.with_name('lmt-main.go'),output)
        with self.assertRaises(ValueError):D5.lmt_build_arguments('relative-go',source,output)

    def test_rehearsal_source_scope_does_not_grant_full_matrix(self):
        self.assertEqual(D5.runtime_scope({'SCOPE':'rehearsal'}),'rehearsal')
        for value in ('full','',None):
            with self.assertRaises(ValueError):D5.runtime_scope({'SCOPE':value})

    def test_actual_entry_refuses_full_before_unit_or_private_root(self):
        import types
        def unexpected(*args):raise AssertionError('full scope reached unit')
        reader=types.SimpleNamespace(validate_admission=lambda *args:{'synthetic':True},operational_start=unexpected)
        with self.assertRaisesRegex(ValueError,'rehearsal only'):D5.run_d5(reader,{}, {'SCOPE':'full'})

    def test_actual_sandbox_probe_uses_literal_backend_argv_and_cleared_environment(self):
        seen=[];identities={}
        caller={'host_image':lambda path:(path,'a'*64 if path.endswith('unshare') else 'b'*64),
                'bind_identity':lambda store,path,basis,**kw:store.update({path:kw.get('images',[path])})}
        result=D5.probe_backend_sandbox(caller,lambda *args:seen.append(args) or 'synthetic',identities,self.root)
        self.assertEqual(result,'synthetic')
        self.assertEqual(seen,[(['/usr/bin/unshare','--user','--map-root-user','--net','--','/usr/bin/true'],self.root,{'LANG':'C.UTF-8','TZ':'UTC'})])
        self.assertEqual(set(identities),{'/usr/bin/unshare','/usr/bin/true'})
        self.assertEqual(identities['/usr/bin/unshare'],['a'*64,'b'*64])

    def test_actual_entry_sandbox_refusal_prevents_all_sdk_asset_acquisition(self):
        import types
        root=self.root/'current-d5-44-1';events=[]
        owner=types.SimpleNamespace(OWNER_SHA256=D5.OWNER['sha256'])
        def fresh(path,environ):path.mkdir();return {'HOME':str(path/'home')}
        def run(argv,cwd,env):events.append(('probe',argv,env));raise ValueError('original synthetic namespace denied')
        caller={'fresh_environment':fresh,'load_owner':lambda *a:owner,'probe_containment':lambda *a:None,
                'managed_executor':lambda *a:run,'host_image':lambda path:(path,'synthetic'),
                'bind_identity':lambda *a,**kw:None,'provision_sdk':lambda *a:events.append('UNEXPECTED SDK')}
        fake=types.SimpleNamespace(validate_admission=lambda *a:{'synthetic':True},
            operational_start=lambda *a:{'boot':'synthetic'},normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
            load_file=lambda name,path:types.SimpleNamespace(actual_caller=lambda:caller) if name=='d5_actual_loader' else types.SimpleNamespace(PINS={'synthetic':True}),
            original_clock=lambda *a:{'startedMonotonic':D5.time.monotonic()},unit_properties=lambda *a:{'synthetic':True},
            acquisition_capacity=lambda *a:events.append('capacity'),collect=lambda *a:{'failures':[]},collection_terminal=lambda *a:None)
        env={'RUNNER_TEMP':str(self.root),'RUN_ID':'44','UNIT_NAME':'fsgg-mg-templates-d5-44-1','GITHUB_WORKSPACE':str(D5.HERE.parents[2]),'SCOPE':'rehearsal','PUBLIC_PINS':'{"synthetic":true}'}
        with patch.object(D5,'sandbox_parent_data',return_value={'synthetic':'parent only'}),self.assertRaisesRegex(ValueError,'original synthetic namespace denied'):D5.run_d5(fake,{},env)
        self.assertEqual(events[0],'capacity');self.assertEqual(len(events),2)
        self.assertEqual(events[1][1][0],'/usr/bin/unshare')
        self.assertIn('original synthetic namespace denied',json.loads((root/'attempt.json').read_text())['firstCause'])

    def test_dependency_missing_or_changed_refuses_before_import(self):
        with self.assertRaises(ValueError):D5.load_reader(self.root)
        p=self.root/D5.READER['path'];p.parent.mkdir(parents=True);p.write_text('raise RuntimeError("must not import")')
        with self.assertRaisesRegex(ValueError,'dependency unavailable'):D5.load_reader(self.root)

class SandboxParentControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='d5-parent-pure-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_read_only_fixture_bounds_and_file_links(self):
        target=self.root/'fixture';target.write_bytes(b'closed fixture')
        self.assertEqual(D5.sandbox_read(target),b'closed fixture')
        with self.assertRaisesRegex(ValueError,'byte cap'):D5.sandbox_read(target,3)
        link=self.root/'link';link.symlink_to(target)
        with self.assertRaises(OSError):D5.sandbox_read(link)
        with self.assertRaises(FileNotFoundError):D5.sandbox_read(self.root/'missing')
        with self.assertRaisesRegex(ValueError,'read-only'):D5.sandbox_prctl(4) # rejects SET before loading libc

    def test_unshare_image_complete_hash_metadata_and_changed_image_refusal(self):
        import types,stat
        body=b'synthetic ELF image'
        info=types.SimpleNamespace(st_mode=stat.S_IFREG|0o755,st_uid=0,st_gid=0,st_size=len(body),st_dev=1,st_ino=2,st_mtime_ns=3)
        with patch.object(D5.os,'stat',return_value=info),patch.object(D5,'sandbox_read',return_value=body) as read,\
             patch.object(D5.os,'getxattr',return_value=b'fixture-capability'),patch.object(D5.os.path,'realpath',return_value='/usr/bin/unshare'):
            value=D5.sandbox_image()
        self.assertEqual(value['sha256'],hashlib.sha256(body).hexdigest())
        self.assertEqual(value['fileCapabilities']['hex'],b'fixture-capability'.hex());self.assertIn('Unknown',value['version'])
        read.assert_called_once_with('/usr/bin/unshare',8388608)
        changed=types.SimpleNamespace(**{**vars(info),'st_ino':99})
        with patch.object(D5.os,'stat',side_effect=[info,changed]),patch.object(D5,'sandbox_read',return_value=body),self.assertRaisesRegex(ValueError,'changed'):
            D5.sandbox_image()
        with patch.object(D5.os,'stat',return_value=info),patch.object(D5,'sandbox_read',return_value=b'short'),self.assertRaisesRegex(ValueError,'completely read'):
            D5.sandbox_image()

    def test_actual_collector_closed_paths_parent_scope_and_partial_unknowns(self):
        seen=[]
        def read(path,maximum=16384):
            seen.append(str(path))
            if path=='/proc/self/status':return b'Uid: 1001 1001 1001 1001\nCapEff: 0000\nNoNewPrivs: 1\nSeccomp: 2\nName: not retained\n'
            if path=='/proc/self/mountinfo':return b'1 2 0:1 / /proc rw - proc proc rw\n3 2 0:2 / / rw - ext4 root rw\n'
            if path=='/proc/self/attr/current':raise PermissionError('synthetic LSM label unreadable')
            if path=='/proc/sys/kernel/unprivileged_userns_clone':raise FileNotFoundError('synthetic absent')
            return b'fixture'
        with patch.object(D5,'sandbox_read',side_effect=read),patch.object(D5,'sandbox_prctl',return_value=1),\
             patch.object(D5,'sandbox_image',return_value={'sha256':'a'*64}),\
             patch.object(D5.os,'getresuid',return_value=(1001,1001,1001)),patch.object(D5.os,'getresgid',return_value=(1001,1001,1001)),\
             patch.object(D5.os,'getgroups',return_value=[1001]),patch.object(D5.os,'uname',return_value=('Linux','fixture','kernel','v','x86_64')),\
             patch.object(D5.os,'readlink',return_value='fixture:[1]'),patch.object(D5.os,'stat',return_value=type('Stat',(),{'st_uid':1001,'st_gid':1001,'st_mode':0o400,'st_dev':1,'st_ino':2})()):
            value=D5.optional_sandbox_parent(D5.time.monotonic()+10)
        self.assertEqual(value['status'],'observed');data=value['data']
        self.assertIn('not post-exec/post-CLONE',data['childState'])
        self.assertEqual(data['files']['/proc/self/status']['value'],{'Uid':'1001 1001 1001 1001','CapEff':'0000','NoNewPrivs':'1','Seccomp':'2'})
        self.assertEqual(data['files']['/proc/self/attr/current']['status'],'Unknown')
        self.assertEqual(data['files']['/proc/sys/kernel/unprivileged_userns_clone']['status'],'Unknown')
        self.assertEqual(len(data['procMounts']['value']),1)
        self.assertNotIn('/proc/sys/kernel/randomize_va_space',seen)
        self.assertEqual(data['unshareImage']['value']['sha256'],'a'*64)

    def test_expired_optional_clock_does_not_read_or_renew(self):
        with patch.object(D5,'sandbox_read',side_effect=AssertionError('expired read')),patch.object(D5,'sandbox_prctl',side_effect=AssertionError('expired syscall')),patch.object(D5,'sandbox_image',side_effect=AssertionError('expired image')):
            value=D5.optional_sandbox_parent(0)['data']
        self.assertEqual(value['dumpable']['status'],'Unknown')
        self.assertIn('deadline expired',value['dumpable']['reason'])

    def test_actual_entry_optional_failure_overflow_and_missing_metadata_preserve_original_streams_terminal_upload(self):
        import types
        reader=D5.load_reader(D5.HERE.parents[2]);contract=reader.caller_contract('d5',None)
        workflow=(D5.HERE.parents[2]/'.github/workflows/svg-release-d5-current-public.yml').read_text()
        upload=workflow.split('- name: Retain bounded original D5 evidence',1)[1]
        self.assertIn("always() && steps.clock.outcome != 'skipped'",upload)
        self.assertNotIn('steps.receipt.outcome',upload)
        cases=[('exception',OSError('optional synthetic read failed')),('overflow',json.loads('{"value":1e999}')),
               ('nan',{'value':float('nan')}),('oversize',{'value':'x'*131073}),
               ('missing',{'files':{'label':{'status':'Unknown','reason':'missing'}}}),('normal',{'synthetic':'parent only'})]
        for ordinal,(name,observation) in enumerate(cases):
            with self.subTest(name=name):
                root=self.root/('current-d5-'+str(90+ordinal)+'-1');events=[]
                def fresh(path,environ):
                    path.mkdir();(path/'input-downloads.json').write_text('[]');(path/'executable-identities.json').write_text('{}')
                    return {'HOME':str(path/'home')}
                def run(argv,cwd,env):
                    events.append(('probe',argv,env));group=root/'managed'/'probe';group.mkdir(parents=True)
                    (group/'stderr.log').write_text('unshare: write failed /proc/self/uid_map: Operation not permitted\n')
                    (group/'stdout.log').write_text('');(group/'receipt.json').write_text('{"outcome":"failed"}')
                    raise ValueError('original synthetic uid_map denied')
                caller={'fresh_environment':fresh,'load_owner':lambda *a:types.SimpleNamespace(OWNER_SHA256=D5.OWNER['sha256']),
                    'probe_containment':lambda *a:None,'managed_executor':lambda *a:run,'host_image':lambda path:(path,'synthetic'),
                    'bind_identity':lambda *a,**kw:None,'provision_sdk':lambda *a:events.append('UNEXPECTED SDK')}
                fake=types.SimpleNamespace(validate_admission=lambda *a:{'synthetic':True},operational_start=lambda *a:{'boot':'synthetic'},
                    normalized_roots=lambda *a:None,no_global_before_create=lambda *a:None,
                    load_file=lambda name,path:types.SimpleNamespace(actual_caller=lambda:caller) if name=='d5_actual_loader' else types.SimpleNamespace(PINS={'synthetic':True}),
                    original_clock=lambda *a:{'startedMonotonic':D5.time.monotonic()},unit_properties=lambda *a:{'synthetic':True},
                    acquisition_capacity=lambda *a:events.append('capacity'),collect=reader.collect,collection_terminal=reader.collection_terminal)
                env={'RUNNER_TEMP':str(self.root),'RUN_ID':str(90+ordinal),'UNIT_NAME':'synthetic','GITHUB_WORKSPACE':str(D5.HERE.parents[2]),'SCOPE':'rehearsal','PUBLIC_PINS':'{"synthetic":true}'}
                options={'side_effect':observation} if isinstance(observation,Exception) else {'return_value':observation}
                with patch.object(D5,'sandbox_parent_data',**options),self.assertRaisesRegex(ValueError,'original synthetic uid_map denied'):
                    D5.run_d5(fake,contract,env)
                value=json.loads((root/'d5-evidence'/'attempt.json').read_text())
                self.assertIn('original synthetic uid_map denied',value['firstCause'])
                self.assertEqual(value['sandboxParentObservation']['status'],'Unknown' if ordinal<4 else 'observed')
                self.assertEqual((root/'managed/probe/stderr.log').read_bytes(),(root/'d5-evidence/managed/probe/stderr.log').read_bytes())
                terminal=json.loads((root/'d5-evidence/collection-terminal.json').read_text())
                self.assertIn('original synthetic uid_map denied',terminal['firstCause']);self.assertEqual(terminal['additionalFailures'],[])
                manifest=json.loads((root/'d5-evidence/manifest.json').read_text());self.assertEqual(manifest['failures'],[])
                self.assertEqual(events[0],'capacity');self.assertEqual(len(events),2)
                self.assertEqual(events[1][1],['/usr/bin/unshare','--user','--map-root-user','--net','--','/usr/bin/true'])
                self.assertEqual(events[1][2],{'LANG':'C.UTF-8','TZ':'UTC'})


class RootClockControls(unittest.TestCase):
    def setUp(self):
        import datetime,textwrap
        self.temp=tempfile.TemporaryDirectory(prefix='d5-root-clock-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.reader=D5.load_reader(D5.HERE.parents[2])
        self.env={'EVENT':'workflow_dispatch','REPOSITORY':'FS-GG/FS.GG.Templates','REF':'refs/heads/main',
            'SHA':'a'*40,'WORKFLOW_REF':D5.WORKFLOW,'WORKFLOW_SHA':'a'*40,'RUN_ID':'42','RUN_ATTEMPT':'1','UNIT_NAME':'fsgg-mg-templates-d5-42-1',
            'RUNNER_TEMP':str(self.root),'SELECTED_UTC':'2026-10-23T23:59:59Z','LATEST_START_UTC':'2026-10-24T00:04:59Z','OBSERVER_DEADLINE_UTC':'2026-10-24T00:39:59Z'}
        workflow=(D5.HERE.parents[2]/'.github/workflows/svg-release-d5-current-public.yml').read_text()
        code=workflow.split("python3 -I -B <<'PY_CLOCK'\n",1)[1].split('          PY_CLOCK',1)[0]
        self.producer=textwrap.dedent(code);self.actual=datetime.datetime(2026,10,24,0,0,0,tzinfo=datetime.timezone.utc)

    def produce(self,env=None,now=None):
        import datetime
        from unittest.mock import patch
        actual=self.actual if now is None else now
        class NativeUTC(datetime.datetime):
            @classmethod
            def now(cls,tz=None):return actual
        with patch.dict(os.environ,self.env if env is None else env,clear=True),patch.object(datetime,'datetime',NativeUTC),patch('time.monotonic',return_value=100):
            exec(compile(self.producer,'actual-D5-first-clock','exec'),{})
        return json.loads((self.root/'current-d5-42-1-clock.json').read_text())

    def test_actual_producer_and_reader_preserve_fixed_projection(self):
        clock=self.produce();self.reader.validate_d5_original_clock(clock,self.env)
        self.assertEqual(clock['observerDeadlineMonotonic'],2499)
        from unittest.mock import patch
        contract=self.reader.caller_contract('d5',D5.ADMISSION)
        with patch.object(self.reader.time,'monotonic',return_value=150):
            self.assertEqual(self.reader.original_clock(self.env,clock['boot'],contract),clock)
        self.assertEqual(clock['observerDeadlineMonotonic'],2499) # no projection from later now

    def test_actual_producer_refuses_late_queue_and_preserves_refusal_clock(self):
        import datetime
        with self.assertRaisesRegex(ValueError,'window refused'):self.produce(now=self.actual+datetime.timedelta(seconds=300))
        clock=json.loads((self.root/'current-d5-42-1-clock.json').read_text());self.assertEqual(clock['disposition'],'refused')
        self.assertIn('window refused',clock['firstCause'])

    def test_replacement_unused_selection_accepts_later_source_window_without_renewal(self):
        import datetime
        env={**self.env,'SELECTED_UTC':'2026-10-24T00:30:00Z','LATEST_START_UTC':'2026-10-24T00:35:00Z','OBSERVER_DEADLINE_UTC':'2026-10-24T01:10:00Z'}
        clock=self.produce(env,datetime.datetime(2026,10,24,0,30,1,tzinfo=datetime.timezone.utc))
        self.reader.validate_d5_original_clock(clock,env)
        self.assertEqual(clock['observerDeadlineMonotonic'],2499)

    def test_wrong_missing_intervals_and_expired_selection_refuse(self):
        for updates in [{'LATEST_START_UTC':'2026-10-24T00:05:00Z'},{'SELECTED_UTC':''},
            {'SELECTED_UTC':'2026-10-25T06:00:01Z','LATEST_START_UTC':'2026-10-25T06:05:01Z','OBSERVER_DEADLINE_UTC':'2026-10-25T06:40:01Z'}]:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):self.reader.d5_root_times({**self.env,**updates})

    def test_tampered_projection_input_crosssource_run_boot_and_missing_clock_refuse(self):
        clock=self.produce()
        for key,value in [('observerDeadlineMonotonic',2500),('observedUTC','2026-10-23T23:59:58Z'),('rootSelection',{}),('disposition','refused')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):self.reader.validate_d5_original_clock({**clock,key:value},self.env)
        from unittest.mock import patch
        contract=self.reader.caller_contract('d5',D5.ADMISSION)
        for key,value in [('SHA','b'*40),('RUN_ID','43')]:
            with self.subTest(key=key):
                with patch.object(self.reader.time,'monotonic',return_value=150):
                    with self.assertRaises(ValueError):self.reader.original_clock({**self.env,key:value},clock['boot'],contract)
        with self.assertRaises(ValueError):self.reader.original_clock(self.env,'other-boot',contract)
        (self.root/'current-d5-42-1-clock.json').unlink()
        with self.assertRaises(ValueError):self.reader.original_clock(self.env,clock['boot'],contract)

    def test_before_selected_utc_refuses_in_actual_producer(self):
        import datetime
        with self.assertRaisesRegex(ValueError,'window refused'):self.produce(now=self.actual-datetime.timedelta(seconds=2))

class HostedUsernsStepControls(unittest.TestCase):
    """The A/B-proven hosted prerequisite step: scope, order and nothing else changed."""
    def setUp(self):
        self.workflow=(D5.HERE.parents[2]/'.github/workflows/svg-release-d5-current-public.yml').read_text()
        self.receiver=self.workflow.split('  receiver:\n',1)[1]

    def test_only_one_hosted_guarded_sysctl_between_capacity_and_unit(self):
        import re
        self.assertEqual(self.workflow.count('sysctl -w'),1)
        self.assertEqual(re.findall(r'sudo -n sysctl -w ("\$key=0")',self.workflow),['"$key=0"'])
        self.assertIn('key=kernel.apparmor_restrict_unprivileged_userns',self.workflow)
        capacity=self.receiver.index('id: capacity');step=self.receiver.index('id: userns')
        unit=self.receiver.index('- name: Fixed D5 sequence in the canonical delegated unit')
        self.assertLess(capacity,step);self.assertLess(step,unit)
        body=self.receiver[step:unit]
        self.assertIn('test "${RUNNER_ENVIRONMENT:-}" = github-hosted',body)
        self.assertLess(body.index('before.txt'),body.index('sysctl -w'));self.assertLess(body.index('sysctl -w'),body.index('after.txt'))
        self.assertIn('grep -qx "$key = 0"',body)
        self.assertIn('set -euo pipefail',body);self.assertIn('mkdir -m 700',body)
        self.assertNotIn('continue-on-error',self.receiver[step-400:unit])
        self.assertNotIn('if:',body.split('run:',1)[0])

    def test_unit_properties_and_literal_probe_stay_unchanged_and_userns_evidence_is_uploaded(self):
        unit=self.receiver.split('- name: Fixed D5 sequence in the canonical delegated unit',1)[1]
        for token in ('-p NoNewPrivileges=yes','-p Delegate=yes','-p TasksMax=512','-p MemoryMax=8G','-p RuntimeMaxSec=1800','-p CPUQuota=200%'):
            self.assertIn(token,unit)
        self.assertIn("current-d5-${{ github.run_id }}-1-userns/",self.workflow.split('- name: Retain bounded original D5 evidence',1)[1])
        self.assertEqual(unit.count('sysctl'),0)


if __name__=='__main__':unittest.main()
