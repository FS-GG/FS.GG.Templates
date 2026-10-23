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
        self.assertIsNone(D5.ADMISSION);self.assertEqual(D5.OUTER_CALLER_CONTRACT,'d5')

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
            collect=lambda *a:{'failures':[]})
        env={'RUNNER_TEMP':str(self.root),'RUN_ID':'42','UNIT_NAME':'fsgg-mg-templates-d5-42-1','GITHUB_WORKSPACE':str(D5.HERE.parents[2]),'SCOPE':'rehearsal','PUBLIC_PINS':'{"schema":"synthetic"}'}
        with self.assertRaisesRegex(ValueError,'original synthetic setup failure'):D5.run_d5(fake,{'synthetic':True},env)
        self.assertEqual(events,['owner'])
        receipt=json.loads((root/'attempt.json').read_text())
        self.assertEqual(receipt['disposition'],'failed');self.assertEqual(receipt['retirement'],'unqualified')
        self.assertIn('original synthetic setup failure',receipt['firstCause'])

    def test_actual_lmt_recipe_preserves_canonical_source_basename_and_literal_argv(self):
        go=self.root/'go/bin/go';source=self.root/'download with spaces/main.go';output=self.root/'tools/lmt'
        args=D5.lmt_build_arguments(go,source,output)
        self.assertEqual(args,[str(go),'build','-trimpath','-ldflags',D5.LMT['ldflags'],'-o',str(output),str(source)])
        with self.assertRaises(ValueError):D5.lmt_build_arguments(go,source.with_name('lmt-main.go'),output)
        with self.assertRaises(ValueError):D5.lmt_build_arguments('relative-go',source,output)

    def test_dependency_missing_or_changed_refuses_before_import(self):
        with self.assertRaises(ValueError):D5.load_reader(self.root)
        p=self.root/D5.READER['path'];p.parent.mkdir(parents=True);p.write_text('raise RuntimeError("must not import")')
        with self.assertRaisesRegex(ValueError,'dependency unavailable'):D5.load_reader(self.root)

if __name__=='__main__':unittest.main()
