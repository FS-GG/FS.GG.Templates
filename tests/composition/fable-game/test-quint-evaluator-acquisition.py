"""Pure acquisition controls: no network, subprocess, evaluator or model execution."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('acquisition',ROOT/'scripts/prepare-svg-quint-evaluator.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def release():
    return {'id':m.RELEASE,'tag_name':m.TAG,'html_url':f'https://github.com/{m.REPO}/releases/tag/{m.TAG}',
            'draft':False,'prerelease':False,'assets':[{'id':m.ASSET,'name':m.NAME,'size':m.SIZE,
            'state':'uploaded','digest':'sha256:'+m.ARCHIVE,'url':f'https://api.github.com/repos/{m.REPO}/releases/assets/{m.ASSET}',
            'browser_download_url':f'https://github.com/{m.REPO}/releases/download/{m.TAG}/{m.NAME}'}]}

def archive(name='quint_evaluator',kind=tarfile.REGTYPE,data=b'\x7fELFpure-fixture'):
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w:gz') as z:
        t=tarfile.TarInfo(name);t.type=kind;t.size=len(data) if kind==tarfile.REGTYPE else 0
        z.addfile(t,io.BytesIO(data) if t.size else None)
    return raw.getvalue(),data

class Controls(unittest.TestCase):
    def test_bounded_http_reads(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'x'*n
        class Opener:
            def open(self,request,timeout):
                self.request=request
                if timeout!=60:raise AssertionError('timeout drift')
                return Response()
        opener=Opener()
        with patch.object(m.urllib.request,'build_opener',return_value=opener):
            with self.assertRaises(ValueError):m.fetch('https://api.github.com/repos/quint-co/quint/releases/303596741','synthetic','application/vnd.github+json',10)
            self.assertEqual(opener.request.get_header('Authorization'),'Bearer synthetic')
    def test_workflow_acquisition_fence_and_native_commands(self):
        text=(ROOT/'.github/workflows/svg-preview-c.yml').read_text()
        start=text.index('      - name: Acquire pinned Rust evaluator for complete workspace')
        end=text.index('      - name: Qualify installed complete workspace across browser families')
        step=text[start:end]
        self.assertIn('GH_TOKEN: ${{ github.token }}',step)
        self.assertIn('QUINT_HOME: ${{ runner.temp }}/svg-preview-c-quint-home',step)
        self.assertIn('printf \'QUINT_HOME=%s\\n\' "$QUINT_HOME" >> "$GITHUB_ENV"',step)
        complete=text[end:text.index('      - name: Qualify the local container edge')]
        self.assertNotIn('GH_TOKEN',complete)
        self.assertIn('bash ./build.sh > "$RUNNER_TEMP/svg-preview-c-source/complete-chromium.log" 2>&1',complete)
        self.assertIn('for family in firefox webkit; do',complete)
        for path in ('scripts/prepare-svg-quint-evaluator.py','tests/composition/fable-game/test-quint-evaluator-acquisition.py'):
            self.assertEqual(text.count("      - '"+path+"'"),2)
    def test_metadata_exact(self):
        self.assertEqual(m.metadata(release())['id'],m.ASSET)
    def test_metadata_drift(self):
        for key,value in [('id',1),('tag_name','evaluator/v0.5.0'),('draft',True),('prerelease',True),('html_url','https://github.com/foreign/x')]:
            with self.subTest(key=key):
                r=release();r[key]=value
                with self.assertRaises(ValueError):m.metadata(r)
    def test_asset_drift(self):
        for key in ('id','name','size','state','digest','url','browser_download_url'):
            with self.subTest(key=key):
                r=release();r['assets'][0][key]='foreign'
                with self.assertRaises(ValueError):m.metadata(r)
        r=release();r['assets']*=2
        with self.assertRaises(ValueError):m.metadata(r)
    def checked_fixture(self,body,data):
        return patch.multiple(m,SIZE=len(body),ARCHIVE=m.sha(body),MEMBER_SIZE=len(data),MEMBER_SHA=m.sha(data))
    def test_archive_binary_positive_and_corrupt(self):
        body,data=archive()
        with self.checked_fixture(body,data):
            self.assertEqual(m.binary(body),data)
            with self.assertRaises(ValueError):m.binary(body+b'x')
            with patch.object(m,'MEMBER_SHA','0'*64):
                with self.assertRaises(ValueError):m.binary(body)
    def test_archive_member_refusals(self):
        for name,kind in [('../escape',tarfile.REGTYPE),('quint_evaluator',tarfile.SYMTYPE),('foreign',tarfile.REGTYPE)]:
            body,data=archive(name,kind)
            with self.checked_fixture(body,data):
                with self.assertRaises(ValueError):m.binary(body)
        body,data=archive(data=b'not-ELF')
        with self.checked_fixture(body,data):
            with self.assertRaises(ValueError):m.binary(body)
    def test_multiple_members(self):
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w:gz') as z:
            for name in ('quint_evaluator','extra'):
                t=tarfile.TarInfo(name);t.size=1;z.addfile(t,io.BytesIO(b'x'))
        body=raw.getvalue()
        with self.checked_fixture(body,b'x'):
            with self.assertRaises(ValueError):m.binary(body)
    def test_redirect_guards_and_token_stripping(self):
        handler=m.OfficialRedirect();r=urllib.request.Request('https://api.github.com/repos/quint-co/quint/releases/assets/385413317',headers={'Authorization':'Bearer synthetic'})
        x=handler.redirect_request(r,None,302,'Found',{},'https://release-assets.githubusercontent.com/blob?token=download')
        self.assertFalse(x.has_header('Authorization'))
        for url in ['http://github.com/x','https://foreign.example/x','https://user@github.com/x','https://github.com:444/x','https://github.com/x#fragment']:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):handler.redirect_request(r,None,302,'Found',{},url)
    def test_fresh_cache_guards(self):
        with tempfile.TemporaryDirectory() as d:
            runner=Path(d);producer=runner/'producer';producer.mkdir();home=runner/'cache'
            m.fresh(home,runner,producer)
            home.mkdir()
            with self.assertRaises(ValueError):m.fresh(home,runner,producer)
            link=runner/'link';link.symlink_to(home,target_is_directory=True)
            with self.assertRaises(ValueError):m.fresh(link,runner,producer)
            with self.assertRaises(ValueError):m.fresh(producer/'cache',runner,producer)
    def test_mock_prepare_custody_and_repeated_refusal(self):
        body,data=archive()
        with tempfile.TemporaryDirectory() as d,self.checked_fixture(body,data):
            runner=Path(d);producer=runner/'producer';producer.mkdir();quint=runner/'quint';quint.write_bytes(b'pinned-compiled-fixture')
            home=runner/'cache';evidence=runner/'evidence';calls=[]
            def get(url,token,accept,maximum):
                calls.append((url,token,accept,maximum))
                return json.dumps(release()).encode() if accept=='application/vnd.github+json' else body
            with patch.object(m,'QUINT_SHA',m.sha(quint.read_bytes())),patch.dict(os.environ,QUINT_HOME=str(home)):
                receipt=m.prepare(quint,home,evidence,runner,producer,'synthetic',get)
                self.assertEqual(len(calls),2);self.assertEqual(receipt['supportedCachePath'],str(home/'rust-evaluator-v0.6.0/quint_evaluator'))
                self.assertFalse(receipt['modelsExecuted']);self.assertFalse(receipt['qualificationPassed'])
                self.assertEqual((home/'rust-evaluator-v0.6.0/quint_evaluator').read_bytes(),data)
                self.assertEqual((home/'rust-evaluator-v0.6.0/quint_evaluator').stat().st_mode&0o777,0o700)
                with self.assertRaises(ValueError):m.prepare(quint,home,evidence,runner,producer,'synthetic',get)
                self.assertEqual(len(calls),2)
    def test_failure_does_not_create_cache(self):
        with tempfile.TemporaryDirectory() as d:
            runner=Path(d);producer=runner/'producer';producer.mkdir();q=runner/'quint';q.write_bytes(b'tool');h=runner/'cache';e=runner/'evidence'
            with patch.object(m,'QUINT_SHA',m.sha(q.read_bytes())),patch.dict(os.environ,QUINT_HOME=str(h)):
                with self.assertRaises(ValueError):m.prepare(q,h,e,runner,producer,'synthetic',lambda *a:json.dumps({'id':1}).encode())
                self.assertFalse(h.exists());self.assertFalse(e.exists())
    def test_wrong_tool_and_environment_refuse_before_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'producer';p.mkdir();q=r/'quint';q.write_bytes(b'foreign')
            def forbidden(*a):self.fail('network attempted')
            with self.assertRaises(ValueError):m.prepare(q,r/'cache',r/'evidence',r,p,'synthetic',forbidden)
            with patch.object(m,'QUINT_SHA',m.sha(q.read_bytes())),patch.dict(os.environ,QUINT_HOME=str(r/'wrong')):
                with self.assertRaises(ValueError):m.prepare(q,r/'cache',r/'evidence',r,p,'synthetic',forbidden)

if __name__=='__main__':unittest.main()
