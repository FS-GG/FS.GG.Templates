#!/usr/bin/env python3
"""Glue controls for the offline producer-custody join; synthetic evidence, no network.

The producer's own `release-custody.py` is the real binder and is exercised by the recorded run on the
actual retained acquisition. These controls stand in a stub binder ONLY to prove this module's own
checks: receipt, hashes, census, typed joins and that a binder refusal is never swallowed.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import io
import os
import stat
import unittest
from unittest import mock
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('custody',HERE/'current-composition-custody.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
sha=lambda b:hashlib.sha256(b).hexdigest()
STUB=('MODE=%r\nimport sys\nfrom pathlib import Path\n'
      'ok=MODE=="ok"\n'
      'print("payload entries exact \u00b7 feed signature=" + ("present (excluded)" if ok else "absent"))\n'
      'sys.exit(0 if ok else 1)\n')


class Controls(unittest.TestCase):
    def build(self,*,binder='ok',attempts=1,extra_member=None,version='1.0.0',manifest_commit=None,zip_custody=None,rename=None,symlink=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        names=['Fixture.UI.1.0.0.nupkg','Fixture.Input.1.0.0.nupkg']+['Other%d.1.0.0.nupkg'%i for i in range(17)]
        unsigned={n:('unsigned '+n).encode() for n in names}
        feed=root/'feed';feed.mkdir()
        signed={n:unsigned[n]+b' +signature' for n in names[:2]}
        for n,d in signed.items():(feed/n).write_bytes(d)
        repo=root/'rendering';(repo/'scripts').mkdir(parents=True);(repo/'eng/release').mkdir(parents=True)
        plan_bytes=b'{"plan":true}';(repo/'eng/release/plan.json').write_bytes(plan_bytes)
        (repo/'scripts/release-custody.py').write_text(STUB%binder)
        git=lambda *a:subprocess.run(['git','-C',str(repo),*a],check=True,capture_output=True)
        git('init','-q');git('add','-A');git('-c','user.name=t','-c','user.email=t@t','commit','-q','-m','x')
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        manifest={'schema':C.SCHEMA,'version':version,'source':{'commit':manifest_commit or commit},'releasePlanSha256':sha(plan_bytes),
                  'archives':[{'file':n,'sha256':sha(unsigned[n])} for n in names]}
        custody=json.dumps(manifest).encode()
        evidence=root/'evidence';evidence.mkdir()
        with zipfile.ZipFile(evidence/'rendering-packet.zip','w') as z:
            for n,d in unsigned.items():
                if rename and n=='Other16.1.0.0.nupkg':n=rename
                if symlink and n=='Other16.1.0.0.nupkg':
                    info=zipfile.ZipInfo(n);info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,d);continue
                z.writestr(n,d)
            z.writestr('release-custody.json',zip_custody or custody)
            if extra_member:z.writestr(extra_member,b'x')
        (evidence/'release-custody.json').write_bytes(custody)
        zbytes=(evidence/'rendering-packet.zip').read_bytes()
        receipt={'attempts':attempts,'exit':0,'disposition':'matched','bytes':len(zbytes),'zipSha256':sha(zbytes),'custodySha256':sha(custody)}
        (evidence/'receipt.json').write_text(json.dumps(receipt))
        plan={'rendering':{'version':'1.0.0','sourceCommit':commit,'custodySha256':sha(custody),
                           'packages':[{'id':'Fixture.UI','sha256':sha(signed[names[0]])},{'id':'Fixture.Input','sha256':sha(signed[names[1]])}]}}
        return dict(evidence=evidence,plan=plan,feed=feed,repository=repo,work=root/'work'),root

    def verify(self,args):return C.verify_producer_custody(args['evidence'],args['plan'],args['feed'],args['repository'],args['work'])

    def test_matching_evidence_returns_the_facts_that_justify_the_flag(self):
        args,_=self.build();facts=self.verify(args)
        self.assertEqual((facts['acquisitionAttempts'],facts['archivesVerified'],len(facts['payloadJoin'])),(1,19,2))
        self.assertEqual(facts['custodySha256'],args['plan']['rendering']['custodySha256'])
        self.assertIn('adds only the feed signature entry',facts['equality'])

    def test_each_join_refuses_when_broken(self):
        cases={
          'second attempt':dict(attempts=2),'extra member':dict(extra_member='stray.txt'),'traversal member':dict(extra_member='../escape.nupkg'),
          'nested member':dict(extra_member='dir/inner.nupkg'),
          # Census stays at 20, so only the name/type guard can refuse these.
          'renamed traversal':dict(rename='../escape.nupkg'),'renamed nested':dict(rename='dir/inner.nupkg'),'symlink member':dict(symlink=True),
          'binder refuses':dict(binder='refuse'),'wrong version':dict(version='9.9.9'),
        }
        for name,kwargs in cases.items():
            with self.subTest(name):
                args,_=self.build(**kwargs)
                with self.assertRaises(ValueError):self.verify(args)
        args,_=self.build();args['plan']['rendering']['custodySha256']='0'*64
        with self.assertRaisesRegex(ValueError,'typed SHA-256'):self.verify(args)
        args,_=self.build();args['plan']['rendering']['sourceCommit']='f'*40
        with self.assertRaises((ValueError,subprocess.CalledProcessError)):self.verify(args)
        # The manifest names another commit than the typed one, while the typed commit exists: only the manifest/typed join can refuse.
        args,_=self.build(manifest_commit='e'*40)
        with self.assertRaisesRegex(ValueError,'different version or source'):self.verify(args)
        # The zip's custody member differs from the retained, typed-hash-checked manifest: the binder would verify the wrong bytes.
        args,_=self.build(zip_custody=b'{"schema":"other"}')
        with self.assertRaisesRegex(ValueError,'custody member differs'):self.verify(args)
        args,_=self.build();receipt=json.loads((args['evidence']/'receipt.json').read_text());receipt['custodySha256']='0'*64;(args['evidence']/'receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'typed SHA-256'):self.verify(args)
        args,_=self.build();(args['feed']/'Fixture.UI.1.0.0.nupkg').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'published archive differs'):self.verify(args)
        args,_=self.build();(args['evidence']/'rendering-packet.zip').write_bytes(b'not the retained bytes')
        with self.assertRaisesRegex(ValueError,'differs from its receipt'):self.verify(args)

    def test_the_signed_and_unsigned_hashes_are_never_equated(self):
        args,_=self.build()
        manifest=json.loads((args['evidence']/'release-custody.json').read_text())
        row=[r for r in manifest['archives'] if r['file']=='Fixture.UI.1.0.0.nupkg'][0]
        # Publish the unsigned custody bytes under the typed hash: every earlier check passes, so only the signed/unsigned guard can refuse.
        (args['feed']/'Fixture.UI.1.0.0.nupkg').write_bytes(b'unsigned Fixture.UI.1.0.0.nupkg')
        args['plan']['rendering']['packages'][0]['sha256']=row['sha256']
        with self.assertRaisesRegex(ValueError,'unexpectedly byte-identical'):self.verify(args)

    def test_a_compare_that_does_not_show_the_feed_signature_is_refused(self):
        args,_=self.build(binder='ok')
        real=C.binder
        def unsigned(script,*a):
            out=real(script,*a);return out.replace('feed signature=present (excluded)','feed signature=absent') if a[0]=='compare' else out
        with mock.patch.object(C,'binder',unsigned),self.assertRaisesRegex(ValueError,'plus the feed signature'):self.verify(args)

    def test_children_get_no_ambient_credential_or_global_git_config(self):
        args,_=self.build();seen=[]
        real=subprocess.run
        def spy(argv,**kw):seen.append(kw.get('env'));return real(argv,**kw)
        with mock.patch.dict(os.environ,{'GH_TOKEN':'secret','NUGET_API_KEY':'secret'}),mock.patch.object(C.subprocess,'run',spy):self.verify(args)
        self.assertTrue(seen and all(env is not None and 'GH_TOKEN' not in env and 'NUGET_API_KEY' not in env for env in seen))

    def test_module_makes_no_network_call_and_runner_sets_the_flag_only_from_it(self):
        text=(HERE/'current-composition-custody.py').read_text()
        for forbidden in ('urllib','requests','socket','"gh"',"'gh'","'curl'"):self.assertNotIn(forbidden,text)
        runner=(HERE/'current-composition-local.py').read_text()
        self.assertIn("summary['actualProducerCustodyReadback'] = 'producerCustody' in summary",runner)
        self.assertEqual(runner.count("'actualProducerCustodyReadback': False"),1)


if __name__=='__main__':unittest.main(verbosity=2)
