#!/usr/bin/env python3
"""Synthetic input controls; preflight cannot install, build or query a feed."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import ast
import copy
import hashlib
import io
import json
import re
import time
import zipfile
import stat
import tarfile
import signal
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

class PublicReferencePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.effect = self.root / 'effect'
        stub = self.root / 'dotnet'; stub.write_text('#!/bin/sh\ntouch "' + str(self.effect) + '"\nexit 99\n'); stub.chmod(0o700)
        self.env = {**os.environ, 'DOTNET_HOST_PATH': str(stub), 'QUINT_BIN': str(stub)}

    def args(self, mode='templates'):
        args = ['--mode', mode, '--template-version', '0.18.1', '--sha256', 'a'*64,
                '--descriptor-sha256', 'b'*64, '--source-revision', 'c'*40,
                '--tag-revision', 'c'*40, '--sdd-version', '2.1.0', '--sdd-sha256', 'd'*64,
                '--sdd-source-revision', 'e'*40, '--evidence-dir', str(self.root/'fresh'), '--preflight-only']
        if mode == 'full': args += ['--wizard-version', '0.16.0', '--wizard-sha256', 'f'*64, '--wizard-source-revision', 'a'*40]
        return args

    def wasm_args(self):
        return ['--mode', 'wasm', '--template-version', '0.19.0', '--sha256', 'a'*64,
                '--descriptor-sha256', 'b'*64, '--source-revision', 'c'*40,
                '--tag-revision', 'c'*40, '--evidence-dir', str(self.root/'fresh'), '--preflight-only']

    def run_preflight(self, args, expected):
        result = subprocess.run(['bash', str(HERE/'verify-fable-reference-public.sh'), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, expected, result.stderr)
        self.assertFalse(self.effect.exists()); self.assertFalse((self.root/'fresh').exists())

    def test_templates_only_is_independent_of_wizard(self): self.run_preflight(self.args(), True)
    def test_full_requires_selected_successor_inputs(self): self.run_preflight(self.args('full'), True)
    def test_historical_version_refused(self): self.run_preflight([a.replace('0.18.1', '0.18.0') for a in self.args()], False)
    def test_old_wizard_refused(self): self.run_preflight([a.replace('0.16.0', '0.15.0') for a in self.args('full')], False)
    def test_templates_mode_refuses_wizard_claim(self): self.run_preflight(self.args()+['--wizard-version', '0.16.0'], False)
    def test_unknown_mode_refused(self): self.run_preflight(self.args('unknown'), False)
    def test_missing_full_wizard_refused(self):
        args = self.args(); args[1] = 'full'; self.run_preflight(args, False)
    def test_different_tag_source_refused(self): self.run_preflight([a.replace('c'*40, 'b'*40) if i and self.args()[i-1]=='--tag-revision' else a for i,a in enumerate(self.args())], False)
    def test_source_newline_refused(self): self.run_preflight([a+'\n' if a=='c'*40 else a for a in self.args()], False)
    def test_duplicate_version_refused(self): self.run_preflight(self.args()+['--template-version', '0.18.1'], False)

    def test_wasm_direct_preflight_has_no_sdd_wizard_or_runtime_effect(self): self.run_preflight(self.wasm_args(), True)
    def test_wasm_requires_closed_successor(self): self.run_preflight([a.replace('0.19.0','0.18.1') for a in self.wasm_args()], False)
    def test_historical_route_cannot_claim_successor(self): self.run_preflight([a.replace('0.18.1','0.19.0') for a in self.args()], False)
    def test_wasm_refuses_sdd_scope(self): self.run_preflight(self.wasm_args()+['--sdd-version','2.1.0'], False)
    def test_wasm_refuses_wizard_scope(self): self.run_preflight(self.wasm_args()+['--wizard-version','0.16.0'], False)
    def test_wasm_requires_exact_tag_source(self):
        args=self.wasm_args(); args[args.index('--tag-revision')+1]='f'*40; self.run_preflight(args, False)
    def test_wasm_source_newline_refused(self): self.run_preflight([a+'\n' if a=='c'*40 else a for a in self.wasm_args()], False)
    def test_wasm_archive_digest_required(self):
        args=self.wasm_args(); args[args.index('--sha256')+1]='a'*63; self.run_preflight(args, False)
    def test_wasm_preflight_requires_new_evidence(self):
        (self.root/'fresh').mkdir()
        result=subprocess.run(['bash',str(HERE/'verify-fable-reference-public.sh'),*self.wasm_args()],env=self.env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0); self.assertFalse(self.effect.exists())


WORKFLOW=HERE.parents[2]/'.github/workflows/fable-reference-public.yml'

def actual_hosted_code():
    text=WORKFLOW.read_text()
    matches=re.findall(r"          python3 - <<'HOSTED_WASM'\n(.*?)\n          HOSTED_WASM",text,re.S)
    if len(matches)!=1: raise AssertionError('exactly one actual hosted caller required')
    code='\n'.join(line[10:] for line in matches[0].splitlines())
    ast.parse(code)
    return text,code

class HostedWasmCallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.text,self.code=actual_hosted_code()
        self.ns={'__name__':'fielding_test'};exec(compile(self.code,'actual-hosted-workflow','exec'),self.ns)
        self.env={'EVENT':'pull_request','REPOSITORY':'FS-GG/FS.GG.Templates','HEAD_REPOSITORY':'FS-GG/FS.GG.Templates',
          'PR_HEAD':'a'*40,'WORKFLOW_REF':'FS-GG/FS.GG.Templates/.github/workflows/fable-reference-public.yml@refs/pull/1/merge',
          'WORKFLOW_SHA':'b'*40,'RUN_ID':'1','RUN_ATTEMPT':'1','IMAGE_OS':'Linux','IMAGE_VERSION':'X64'}

    def test_exact_same_repo_source_reaches_preparation(self):
        self.assertEqual(self.ns['validate_source'](self.env,'a'*40,self.root)['WORKFLOW_SHA'],'b'*40)
    def test_wrong_or_missing_source_bindings_refuse(self):
        for key,value in [('EVENT','workflow_dispatch'),('HEAD_REPOSITORY','attacker/fork'),('PR_HEAD','a'*39),('WORKFLOW_REF','other/path@ref'),('WORKFLOW_SHA','')]:
            env={**self.env,key:value}
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):self.ns['validate_source'](env,'a'*40,self.root)
        with self.assertRaises(ValueError):self.ns['validate_source'](self.env,'c'*40,self.root)
    def test_legacy_dispatch_is_separate_and_no_elevated_permission(self):
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' }}",self.text)
        self.assertIn('options: [templates, full]',self.text)
        self.assertIn('persist-credentials: false',self.text)
        self.assertNotRegex(self.text,r'(contents|actions|packages|id-token): write|secrets\.|pull_request_target:|continue-on-error')
    def test_budget_preserves_later_stages_and_never_renews(self):
        budget=self.ns['BUDGET'];self.assertEqual(sum(budget[k] for k in ('setup','custody','installed','collection','overhead'))+3*budget['cleanup'],2400)
        self.assertEqual(self.ns['phase_deadline'](100,'setup',100),940)
        self.assertEqual(self.ns['phase_deadline'](100,'installed',2100),2200)
        with self.assertRaises(ValueError):self.ns['phase_deadline'](100,'installed',2400)
        with self.assertRaises(ValueError):self.ns['phase_deadline'](100,'other',100)
    def test_fixed_checker_has_no_sdd_wizard_inputs(self):
        argv=self.ns['fixed_checker_argv'](self.root,self.root/'installed')
        self.assertIn('wasm',argv);self.assertIn('0.19.0',argv)
        self.assertEqual(argv.count(self.ns['PUBLISHED']),2)
        self.assertNotIn('--sdd-version',argv);self.assertNotIn('--wizard-version',argv)
    def test_unknown_managed_contract_cannot_acquire_or_start_c(self):
        with self.assertRaisesRegex(RuntimeError,'managed-group candidate/profile contract not yet bound'):self.ns['main']()
    def test_final_environment_is_fresh_and_does_not_inherit_credentials_or_profile(self):
        env=self.ns['fresh_environment'](self.root/'job',{'GH_TOKEN':'sensitive','MOZ_DISABLE_CONTENT_SANDBOX':'1'})
        self.assertNotIn('GH_TOKEN',env);self.assertNotIn('MOZ_DISABLE_CONTENT_SANDBOX',env)
        self.assertEqual(env['DOTNET_PROCESSOR_COUNT'],'2')
        self.assertEqual(list((self.root/'job/checker-packages').iterdir()),[])
        with self.assertRaises(ValueError):self.ns['fresh_environment'](self.root/'job',{})
    def transport(self,body,url='https://api.nuget.org/test'):
        response=io.BytesIO(body);response.geturl=lambda:url
        return lambda *args,**kwargs:response
    def test_actual_download_transport_good_bytes_and_changed_bytes(self):
        expected=hashlib.sha256(b'actual').hexdigest()
        row=self.ns['download']('https://api.nuget.org/test',self.root/'download',64,time.monotonic()+10,expected,transport=self.transport(b'actual'))
        self.assertEqual(row['bytes'],6);self.assertEqual(row['digest'],expected)
        with self.assertRaisesRegex(ValueError,'digest differs'):self.ns['download']('https://api.nuget.org/test',self.root/'bad',64,time.monotonic()+10,expected,transport=self.transport(b'changed'))
    def test_actual_download_refuses_wrong_origin_redirect_bound_and_expiry(self):
        cases=[('http://api.nuget.org/test',b'x','https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://unknown.invalid/test',b'x','https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x','https://unknown.invalid/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x'*11,'https://api.nuget.org/test',10,time.monotonic()+10),
            ('https://api.nuget.org/test',b'x','https://api.nuget.org/test',10,time.monotonic()-1)]
        for i,(url,body,final,cap,deadline) in enumerate(cases):
            with self.subTest(i=i),self.assertRaises(ValueError):self.ns['download'](url,self.root/str(i),cap,deadline,transport=self.transport(body,final))
    def package(self,path,wrong=False):
        with zipfile.ZipFile(path,'w') as z:
            for role,key,version in [('Client','vite','7.3.6'),('Browser.Tests','@playwright/test','1.63.0')]:
                if wrong and role=='Browser.Tests':version='1.62.0'
                prefix='content/templates/fs-gg-fable-game/'+role+'/'
                z.writestr(prefix+'package.json','{}')
                z.writestr(prefix+'package-lock.json',json.dumps({'packages':{'':{'devDependencies':{key:version}},'node_modules/'+key:{'resolved':'https://registry.npmjs.org/example/-/example.tgz','integrity':'sha512-abc'}}}))
    def test_actual_package_seed_uses_only_downloaded_modern_locks(self):
        archive=self.root/'package';self.package(archive)
        out=self.ns['seed_from_package'](archive,self.root/'seed',time.monotonic()+10)
        self.assertEqual(sorted(p.name for p in out.iterdir()),['Browser.Tests','Client'])
        self.assertEqual(sorted(p.name for p in (out/'Client').iterdir()),['package-lock.json','package.json'])
    def test_wrong_browser_lock_blocks_acquisition(self):
        archive=self.root/'package';self.package(archive,True)
        with self.assertRaisesRegex(ValueError,'dependency version differs'):self.ns['seed_from_package'](archive,self.root/'seed',time.monotonic()+10)
    def test_actual_tool_failures_collected_and_block_dependent_stages(self):
        outputs={'--version':'wrong','--list-runtimes':'Microsoft.NETCore.App 10.0.11 [/tool]'}
        def inert(argv,cwd,env):return outputs.get(argv[-1],'wrong')
        env={'DOTNET_HOST_PATH':'/qualified/dotnet','FSGG_WASM_FABLE_CORE':'/qualified/fable.dll','FSGG_WASM_WASI_ROOT':'/qualified/wasi'}
        with self.assertRaisesRegex(ValueError,'tool prerequisites failed'):self.ns['qualify_tools'](self.root,env,inert)
        retained=json.loads((self.root/'actual-tool-findings.json').read_text())
        self.assertGreaterEqual(len(retained['failures']),6)
    def test_private_download_refuses_late_eof_and_covers_open_with_one_wall_timer(self):
        clock=[1.0]
        class Late(io.BytesIO):
            def read(self,n):clock[0]=11.0;return b''
        response=Late();response.geturl=lambda:'https://api.nuget.org/test'
        with patch.object(self.ns['time'],'monotonic',lambda:clock[0]),self.assertRaisesRegex(ValueError,'deadline'):
            self.ns['download']('https://api.nuget.org/test',self.root/'late',64,10.0,transport=lambda *a,**k:response)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        previous=signal.getsignal(signal.SIGALRM);entered=[]
        def blocked_open(*args,**kwargs):
            entered.append(True);signal.getsignal(signal.SIGALRM)(signal.SIGALRM,None)
        with self.assertRaisesRegex(TimeoutError,'wall deadline'):
            self.ns['download']('https://api.nuget.org/test',self.root/'never-opened',64,time.monotonic()+10,transport=blocked_open)
        self.assertTrue(entered);self.assertFalse((self.root/'never-opened').exists())
        self.assertEqual(signal.getsignal(signal.SIGALRM),previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))

    def test_private_seed_refuses_population_and_oversized_lock_before_decompression(self):
        path=self.root/'over-populated.zip'
        with zipfile.ZipFile(path,'w') as z:
            for n in range(2048):z.writestr(str(n),b'')
        with patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('unbounded CRC')),patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('decompression before population')),self.assertRaises(ValueError):
            self.ns['seed_from_package'](path,self.root/'no-seed',time.monotonic()+10)
        self.assertFalse((self.root/'no-seed').exists())
        path=self.root/'oversized-lock.zip';self.package(path)
        # Rewrite exact selected lock with a declared payload beyond the closed limit.
        with zipfile.ZipFile(path) as z:entries={i.filename:z.read(i) for i in z.infolist()}
        key='content/templates/fs-gg-fable-game/Client/package-lock.json';entries[key]=b'x'*1048577
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,raw in entries.items():z.writestr(name,raw)
        with patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('decompression before selected byte cap')),self.assertRaisesRegex(ValueError,'lock byte'):
            self.ns['seed_from_package'](path,self.root/'no-large-seed',time.monotonic()+10)
        self.assertFalse((self.root/'no-large-seed').exists())

    def tar_fixture(self, entries):
        path=self.root/'fixture.tar.gz'
        with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as source:
            for name,kind,body,target in entries:
                item=tarfile.TarInfo(name);item.type=kind;item.mode=0o755;item.size=len(body);item.linkname=target
                source.addfile(item,io.BytesIO(body))
        return path

    def test_private_tar_streams_finite_regular_files_and_links_without_getmembers(self):
        path=self.tar_fixture([('bin/',tarfile.DIRTYPE,b'',''),('bin/tool',tarfile.REGTYPE,b'inert',''),('bin/link',tarfile.SYMTYPE,b'','tool')])
        with patch.object(tarfile.TarFile,'getmembers',side_effect=AssertionError('unbounded header list')):
            row=self.ns['unpack_tar'](path,self.root/'tar-root',100,time.monotonic()+10,10)
        self.assertEqual(row['members'],3);self.assertEqual(row['expandedBytes'],5)
        self.assertEqual(os.readlink(self.root/'tar-root/bin/link'),'tool')

    def test_private_tar_rejects_member_population_and_extended_metadata_early(self):
        path=self.tar_fixture([('a',tarfile.REGTYPE,b'x',''),('b',tarfile.REGTYPE,b'x','')])
        with self.assertRaisesRegex((ValueError,RuntimeError),'population'):
            self.ns['unpack_tar'](path,self.root/'tar-partial',100,time.monotonic()+10,1)
        self.assertFalse((self.root/'tar-partial/b').exists())
        path=self.tar_fixture([('pax',tarfile.XHDTYPE,b'x'*1048577,'')])
        with self.assertRaisesRegex(RuntimeError,'metadata byte'):
            self.ns['unpack_tar'](path,self.root/'pax-refused',2097152,time.monotonic()+10,10)
        self.assertFalse((self.root/'pax-refused').exists())

    def archive_fixture(self, entries):
        path=self.root/'fixture.zip'
        if path.exists():path.unlink()
        rows=[]
        with zipfile.ZipFile(path,'w') as z:
            for name,mode,body in entries:
                i=zipfile.ZipInfo(name);i.create_system=3;i.external_attr=mode<<16;z.writestr(i,body)
                rows.append({'name':name,'mode':mode,'bytes':len(body),'link':body.decode() if stat.S_ISLNK(mode) else None})
        expected={'members':len(rows),'logicalBytes':sum(r['bytes'] for r in rows),'symlinks':sum(r['link'] is not None for r in rows),'layoutSha256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        # Explicit inert archive source adapter; production never learns this fixture as authority.
        self.ns['BROWSER_ARCHIVES']={'fixture':{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.ns['BROWSER_LAYOUTS']={'fixture':expected}
        return path,expected

    def test_private_extractor_preserves_relative_library_link_and_executable_mode(self):
        path,_=self.archive_fixture([('lib/',0o40755,b''),('lib/real.so',0o100644,b'library'),('lib/alias.so',0o120777,b'real.so'),('browser',0o100755,b'inert-no-execution')])
        root=self.root/'fresh';record=self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
        self.assertEqual(os.readlink(root/'lib/alias.so'),'real.so')
        self.assertEqual((root/'lib/alias.so').read_bytes(),b'library')
        self.assertEqual(stat.S_IMODE((root/'browser').stat().st_mode),0o755)
        self.assertEqual(record['state'],'extracted-data-not-registered-not-qualified')

    def test_private_extractor_refuses_traversal_special_duplicate_and_links_before_writes(self):
        cases=[
          [('../outside',0o100644,b'x')], [('/absolute',0o100644,b'x')],
          [('a//b',0o100644,b'x')], [('bad\\name',0o100644,b'x')],
          [('device',0o20644,b'')], [('setuid',0o104755,b'x')],
          [('dup',0o100644,b'a'),('dup',0o100644,b'b')],
          [('alias',0o120777,b'../outside')], [('alias',0o120777,b'missing')],
          [('alias',0o120777,b'real'),('alias/child',0o100644,b'x'),('real',0o100644,b'x')],
          [('a',0o120777,b'b'),('b',0o120777,b'a')]]
        for index,entries in enumerate(cases):
            with self.subTest(index=index):
                path,_=self.archive_fixture(entries);root=self.root/f'refused-{index}'
                with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
                self.assertFalse(root.exists())

    def test_private_extractor_refuses_changed_layout_and_raw_bytes(self):
        path,expected=self.archive_fixture([('inert',0o100644,b'x')])
        self.ns['BROWSER_LAYOUTS']['fixture']={**expected,'layoutSha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'layout differs'):self.ns['extract_browser_archive']('fixture',path,self.root/'bad-layout',time.monotonic()+10)
        self.assertFalse((self.root/'bad-layout').exists())
        self.ns['BROWSER_LAYOUTS']['fixture']=expected;path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,self.root/'bad-raw',time.monotonic()+10)
        self.assertFalse((self.root/'bad-raw').exists())

    def test_private_extractor_refuses_expired_original_deadline_and_existing_root(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')])
        with self.assertRaisesRegex(ValueError,'deadline'):self.ns['extract_browser_archive']('fixture',path,self.root/'expired',time.monotonic()-1)
        root=self.root/'occupied';root.mkdir()
        with self.assertRaises(ValueError):self.ns['extract_browser_archive']('fixture',path,root,time.monotonic()+10)
        self.assertEqual(list(root.iterdir()),[])

    def test_private_extractor_refuses_filesystem_symlink_ancestor(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')])
        real=self.root/'real';real.mkdir();alias=self.root/'alias';alias.symlink_to(real,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ancestor'):self.ns['extract_browser_archive']('fixture',path,alias/'fresh',time.monotonic()+10)
        self.assertEqual(list(real.iterdir()),[])

    def test_private_extractor_retains_partial_data_and_refuses_late_terminal_read(self):
        path,_=self.archive_fixture([('inert',0o100644,b'x')]);clock=[1.0]
        original=zipfile.ZipFile.open
        class LateEof:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def read(self,n):
                result=self.stream.read(n)
                if not result:clock[0]=20.0
                return result
        def opened(source,*args,**kwargs):return LateEof(original(source,*args,**kwargs))
        root=self.root/'partial'
        with patch.object(self.ns['time'],'monotonic',lambda:clock[0]),patch.object(zipfile.ZipFile,'open',opened),self.assertRaisesRegex(ValueError,'deadline'):
            self.ns['extract_browser_archive']('fixture',path,root,10.0)
        self.assertEqual((root/'inert').read_bytes(),b'x')
        self.assertEqual(stat.S_IMODE((root/'inert').stat().st_mode),0o600)

    def test_private_layout_enforces_cardinality_byte_and_link_caps(self):
        path,expected=self.archive_fixture([('inert',0o100644,b'x')])
        for key,value in [('members',2),('logicalBytes',2),('symlinks',1)]:
            with self.subTest(key=key),zipfile.ZipFile(path) as z,self.assertRaises(ValueError):
                self.ns['inspect_browser_layout'](z,{**expected,key:value},time.monotonic()+10)

    def test_browser_archive_inputs_refuse_changed_raw_bytes_before_install(self):
        calls=[]
        def changed(name,url,expected,maximum):
            calls.append((url,expected,maximum));p=self.root/name;p.write_bytes(b'changed');return p
        with self.assertRaisesRegex(ValueError,'raw bytes differ'):self.ns['browser_archive_inputs'](changed)
        self.assertEqual(len(calls),1)
        self.assertNotIn('"install","chromium"',self.code)

    def test_release_build_precedes_browser_and_provisioned_is_not_qualified(self):
        self.assertLess(self.code.index('"--locked-mode"'),self.code.index('"Release"'))
        self.assertLess(self.code.index('"Release"'),self.code.index('browser_inputs=browser_archive_inputs(get)'))
        self.assertIn('provisioned-not-qualified',self.code)
        self.assertIn('observedAt',self.code)


    def test_public_url_rejects_authority_controls_before_transport(self):
        good=['https://api.nuget.org/test','https://api.nuget.org:443/test']
        for url in good:self.assertEqual(self.ns['public_url'](url),url)
        for url in ['https://api.nuget.org:444/test','https://api.nuget.org:/test','https://user@api.nuget.org/test','https://user:secret@api.nuget.org/test','https://api.nuget.org/%0aheader','https://api.nuget.org/test\n','https://api.nuget.org\\@other.invalid/test','https://api.nuget.org/test#fragment','https://api.nuget.org.evil.invalid/test']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.ns['public_url'](url)
    def test_per_hop_redirect_refuses_unselected_intermediate_before_open(self):
        request=self.ns['urllib'].request.Request('https://api.nuget.org/start')
        handler=self.ns['ClosedRedirect']();contacts=[]
        # Execute the actual inherited redirect flow; the fake opener records any next request.
        class Opener:
            def open(self,req,*args,**kwargs):contacts.append(req.full_url);return io.BytesIO(b'body')
        handler.parent=Opener()
        headers={'location':'https://unknown.invalid/then-back-to-allowed'}
        response=io.BytesIO(b'')
        with self.assertRaises(ValueError):handler.http_error_302(request,response,302,'found',headers)
        self.assertEqual(contacts,[])
    def test_per_hop_redirect_good_chain_cap_and_auth_refusal(self):
        request=self.ns['urllib'].request.Request('https://api.nuget.org/start')
        handler=self.ns['ClosedRedirect']()
        for i in range(5):
            request=handler.redirect_request(request,None,302,'found',{},'https://raw.githubusercontent.com/next'+str(i))
            self.assertEqual(request.get_method(),'GET')
            self.assertFalse(request.has_header('Authorization'))
        with self.assertRaisesRegex(ValueError,'hop cap'):handler.redirect_request(request,None,302,'found',{},'https://api.nuget.org/end')
        handler=self.ns['ClosedRedirect']();request=self.ns['urllib'].request.Request('https://api.nuget.org/start',headers={'Authorization':'secret'})
        with self.assertRaisesRegex(ValueError,'auth-free'):handler.redirect_request(request,None,302,'found',{},'https://api.nuget.org/end')
    def test_initial_origin_is_checked_before_opener_creation_and_proxy_disabled(self):
        with patch.object(self.ns['urllib'].request,'build_opener') as make:
            with self.assertRaises(ValueError):self.ns['open_public']('https://unknown.invalid/',10)
            make.assert_not_called()
            self.ns['open_public']('https://api.nuget.org/test',10)
            handlers=make.call_args.args
            self.assertEqual(handlers[0].proxies,{})
            self.assertIsInstance(handlers[1],self.ns['ClosedRedirect'])
    def test_new_actions_are_immutable_and_admission_not_assert_dependent(self):
        job=self.text.split('  wasm-installed-c:',1)[1]
        uses=re.findall(r'uses: ([^\s]+)',job)
        self.assertEqual(uses,['actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'])
        tree=ast.parse(self.code)
        self.assertFalse(any(isinstance(node,ast.Assert) for node in ast.walk(tree)))
        self.assertIn('sys.flags.optimize != 0',self.code)


    def test_original_acquisition_failure_survives_independent_report_failure(self):
        def fail(*args,**kwargs):raise RuntimeError('original acquisition failure')
        with patch.object(Path,'write_text',side_effect=OSError('report failure')):
            with self.assertRaisesRegex(RuntimeError,'original acquisition failure') as caught:
                self.ns['prepare_inputs'](self.root,self.root,{},fail,fail,time.monotonic()+10)
        self.assertTrue(any('independent download reporting failure' in note for note in caught.exception.__notes__))


    def test_stock_boundary_metadata_cannot_claim_universal_signal_safety(self):
        selected=self.ns['stock_boundary_metadata']()
        self.assertEqual(self.ns['validate_stock_boundary_metadata'](selected),selected)
        for key,value in [('chromiumSelection','sandbox-enabled'),('firefoxSelection','content-sandbox-disabled'),('canonicalSignalBoundary','all-transitive-signals-pidfd-safe'),('qualification','passed')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_stock_boundary_metadata']({**selected,key:value})
    def test_actual_stock_selection_preserves_weaker_chromium_and_enabled_firefox(self):
        env={'FSGG_WASM_FIREFOX_PROFILE':'content-sandbox-enabled'}
        argv={'chromium':['--headless','--no-sandbox','--remote-debugging-pipe','--no-startup-window','--user-data-dir=/owned/profile'],
              'firefox':['-no-remote','-headless','-profile','/owned/profile','-juggler-pipe','-silent'],
              'webkit':['--inspector-pipe','--headless','--no-startup-window']}
        for family,args in argv.items():self.assertEqual(self.ns['check_stock_launch_selection'](family,args,env)['fullCanonicalAdmission'],'pending')
        for key,value in [('MOZ_DISABLE_CONTENT_SANDBOX','1'),('PLAYWRIGHT_EXECUTABLE_PATH','/system/browser'),('PLAYWRIGHT_BROWSER_CHANNEL','chrome'),('NODE_OPTIONS','--require=/other'),('PW_TEST_CONNECT_WS_ENDPOINT','ws://other')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['check_stock_launch_selection']('chromium',argv['chromium'],{**env,key:value})
        with self.assertRaises(ValueError):self.ns['check_stock_launch_selection']('chromium',[a for a in argv['chromium'] if a!='--no-sandbox'],env)
    def test_actual_stock_source_guard_rejects_changed_config_and_launcher(self):
        template=self.root/'template.zip'
        self.package(template)
        with self.assertRaises((ValueError,KeyError)):self.ns['inspect_stock_sources'](template,self.root/'node_modules')
        template=self.root/'stock.zip';source_map=self.ns['STOCK_INPUTS'];npm_map=self.ns['STOCK_LAUNCHER_INPUTS']
        # Execute the actual final byte guard using inert declared source adapters; this
        # fixture proves rejection/fielding, never authentic stock/browser qualification.
        raw=b'fixture';digest=hashlib.sha256(raw).hexdigest()
        with zipfile.ZipFile(template,'w') as z:
            for name in source_map:z.writestr('content/templates/fs-gg-fable-game/'+name,raw)
        for name in npm_map:
            path=self.root/'node_modules'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.ns['STOCK_INPUTS']={name:digest for name in source_map}
        self.ns['STOCK_LAUNCHER_INPUTS']={name:digest for name in npm_map}
        observations=self.ns['inspect_stock_sources'](template,self.root/'node_modules');self.assertEqual(len(observations),7)
        (self.root/'node_modules'/next(iter(npm_map))).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'launcher source differs'):self.ns['inspect_stock_sources'](template,self.root/'node_modules')

if __name__ == '__main__': unittest.main()
