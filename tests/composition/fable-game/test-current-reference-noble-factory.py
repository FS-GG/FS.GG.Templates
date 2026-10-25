#!/usr/bin/env python3
"""Pure archive and inert-child factory controls; no package/display/guest execution."""
import hashlib
import gzip
import lzma
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('factory_controls',HERE/'current-reference-noble-factory.py')
F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)


def deb(rows):
    body=io.BytesIO()
    with tarfile.open(fileobj=body,mode='w') as archive:
        for name,kind,content in rows:
            row=tarfile.TarInfo(name);row.uid=0;row.mode=0o755
            if kind=='dir':row.type=tarfile.DIRTYPE;archive.addfile(row)
            elif kind=='link':row.type=tarfile.SYMTYPE;row.linkname=content;archive.addfile(row)
            else:
                data=content.encode();row.size=len(data);archive.addfile(row,io.BytesIO(data))
    return ar(body.getvalue(),'data.tar')


def ar(raw,name):
    name+='/'
    head=(name.ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(len(raw)).ljust(10)+'`\n').encode()
    return b'!<arch>\n'+head+raw+(b'\n' if len(raw)%2 else b'')


class FactoryControls(unittest.TestCase):
    def archive(self,rows):
        raw=deb(rows);self.path.write_bytes(raw)
        return F.archive_records(self.path,hashlib.sha256(raw).hexdigest())
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'package.deb'
    def test_actual_debian_dot_root_and_file_are_read_without_extraction(self):
        rows=self.archive([('.', 'dir',''),('./usr/bin/tool','file','fixed')])
        self.assertEqual({'/usr/bin/tool'},set(rows));self.assertEqual(F.N.sha(b'fixed'),rows['/usr/bin/tool']['sha256'])
        self.assertFalse((self.root/'usr').exists())
    def test_path_traversal_duplicate_and_non_directory_root_refuse(self):
        for rows in [[('../tool','file','bad')],[('/usr/tool','file','bad')],[('./usr/tool','file','a'),('usr/tool','file','b')],[('.','file','bad')]]:
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):self.archive(rows)
    def test_digest_truncation_and_multiple_data_members_refuse(self):
        raw=deb([('./usr/tool','file','fixed')]);self.path.write_bytes(raw)
        with self.assertRaises(RuntimeError):F.archive_records(self.path,'0'*64)
        with self.assertRaises(RuntimeError):F.ar_data(raw[:-1])
        with self.assertRaises(RuntimeError):F.ar_data(raw+raw[8:])
    def test_compressed_streams_are_complete_bounded_and_cannot_hide_trailing_frames(self):
        _,raw=F.ar_data(deb([('./usr/bin/tool','file','fixed')]))
        for name,encode in [('data.tar.gz',gzip.compress),('data.tar.xz',lzma.compress)]:
            body=ar(encode(raw),name);self.path.write_bytes(body)
            rows=F.archive_records(self.path,F.N.sha(body));self.assertIn('/usr/bin/tool',rows)
            bad=ar(encode(raw)+b'undeclared-trailing-bytes',name);self.path.write_bytes(bad)
            with self.assertRaises(RuntimeError):F.archive_records(self.path,F.N.sha(bad))
        bad=ar(raw,'data.tar.unknown');self.path.write_bytes(bad)
        with self.assertRaises(RuntimeError):F.archive_records(self.path,F.N.sha(bad))

    def test_exact_data_exception_cannot_widen_ar_acquisition_limit(self):
        self.assertEqual('1a3fac02f9bb69ad32e68e0f9e00fc98cccf2bacf5c9d2f034676a821c266c7c',F.IBUS_DATA_SHA256)
        self.assertEqual(128*1024**2,F.T.A.MAX_FILE);self.assertEqual(512*1024**2,F.T.A.MAX_TOTAL)
    def test_phase_clock_preserves_overall_completion_reserve_and_refuses_absent(self):
        with patch.dict(F.os.environ,{},clear=True),self.assertRaises(RuntimeError):F.phase_clock(120)
        with patch.dict(F.os.environ,{'FSGG_AT_DEADLINE_MONOTONIC':'200'},clear=True),patch.object(F.time,'monotonic',return_value=100),patch.object(F,'ENTRY_STARTED',90):
            self.assertEqual((185,200),F.phase_clock(120))
            self.assertEqual((110,125),F.phase_clock(20))
    def test_actual_unsealed_entry_refuses_before_any_sibling_import(self):
        # Default local TMPDIR may be deeper than the hosted /tmp/tmpXYZ path.
        with tempfile.TemporaryDirectory(dir='/tmp') as short:
            for root in (self.root,Path(short)):
                with self.subTest(root=root):
                    path=root/'current-reference-noble-factory.py';path.write_bytes((HERE/path.name).read_bytes())
                    (root/'current-reference-noble-transaction.py').write_text("raise AssertionError('UNTRUSTED IMPORT EXECUTED')\n")
                    result=subprocess.run([sys.executable,'-I','-B',str(path),'install-readback'],capture_output=True,timeout=5)
                    self.assertNotEqual(0,result.returncode)
                    self.assertIn(b'fixed root-sealed factory controller path required before imports',result.stderr)
                    self.assertNotIn(b'UNTRUSTED IMPORT EXECUTED',result.stderr)

    def test_legacy_baked_driver_refuses_before_guest_or_installation(self):
        with patch.object(F.os,'geteuid',return_value=1000),self.assertRaises(RuntimeError):F.qualified_scope('a'*64,'install-readback')
    def test_nested_budget_cannot_renew_original_clock_after_delayed_construction(self):
        with patch.object(F.time,'monotonic',return_value=105):
            budget=F.OriginalBudget(110);self.assertEqual(5,budget.remaining())
        with patch.object(F.time,'monotonic',return_value=111),self.assertRaises(RuntimeError):F.OriginalBudget(110)

    def test_private_output_refuses_traversal_intermediate_alias_and_existing_output_without_writes(self):
        base=self.root/'runner';base.mkdir();foreign=self.root/'foreign';foreign.mkdir()
        (base/'link').symlink_to(foreign,target_is_directory=True)
        for path in [base/'..'/'foreign'/'native-at-facility',base/'link'/'native-at-facility',foreign/'native-at-facility',base/'wrong-name']:
            with self.subTest(path=path),self.assertRaises(RuntimeError):F.private_output(path,base)
            self.assertFalse(path.exists())
        out=base/'native-at-facility';self.assertEqual(out,F.private_output(out,base));out.mkdir()
        with self.assertRaises(RuntimeError):F.private_output(out,base)

    def test_aggregate_rss_includes_original_supervisor_and_refuses_missing_or_drifted_birth(self):
        leader={'pid':42,'start':1,'ppid':2,'sid':42,'rss':100}
        child={'pid':43,'start':2,'ppid':42,'sid':43,'rss':4*1024**3-100}
        with patch.object(F.O,'proc',return_value=leader):runner=F.Owned(self.root,time.monotonic()+5)
        runner.children=[{'name':'inert','leader':child,'known':{},'outputLimit':128*1024**2}]
        with patch.object(Path,'stat',return_value=types.SimpleNamespace(st_size=0)),patch.object(F.O,'census',return_value=([child],[],[])):
            with patch.object(F.O,'proc',return_value=leader):runner.health()
            with patch.object(F.O,'proc',return_value={**leader,'rss':101}),self.assertRaises(RuntimeError):runner.health()
            for current in (None,{**leader,'start':99},{**leader,'rss':-1}):
                with self.subTest(current=current),patch.object(F.O,'proc',return_value=current),self.assertRaises(RuntimeError):runner.health()
        with patch.object(F.O,'proc',return_value=None),self.assertRaises(RuntimeError):F.Owned(self.root,time.monotonic()+5)

    def test_exact_decoder_output_limit_reaches_health_guard_without_widening_default(self):
        runner=F.Owned(self.root,time.monotonic()+5)
        runner.children=[{'name':'decoder','leader':{'pid':42,'start':1},'known':{},'outputLimit':136*1024**2}]
        with patch.object(F.O,'census',return_value=([],[],[])),patch.object(Path,'stat',return_value=types.SimpleNamespace(st_size=135925760)):
            runner.health()
            runner.children[0]['outputLimit']=128*1024**2
            with self.assertRaises(RuntimeError):runner.health()
        with patch.object(F.O,'census',return_value=([],[],[])),patch.object(Path,'stat',return_value=types.SimpleNamespace(st_size=136*1024**2+1)),self.assertRaises(RuntimeError):
            runner.children[0]['outputLimit']=136*1024**2;runner.health()

    def test_partial_reporting_failure_cannot_skip_cleanup_or_mask_original(self):
        runner=F.Owned(self.root,time.monotonic()+5)
        item=runner.launch([sys.executable,'-I','-B','-c','import time; time.sleep(10)'],'inert','source-control')
        cause=RuntimeError('original source failure');write=Path.write_text
        def broken(path,*args,**kwargs):
            if path.name in ('partial-failure.json','retirement.json'):raise OSError('injected reporting write')
            return write(path,*args,**kwargs)
        with patch.object(Path,'write_text',broken),self.assertRaises(RuntimeError) as observed:runner.finish(cause)
        self.assertIs(cause,observed.exception);self.assertIsNotNone(item['child'].poll())
        self.assertTrue(any('report' in note for note in cause.__notes__))
        # A failed later output must not replay cleanup of the already retired birth.
        with patch.object(F.O,'cleanup',side_effect=AssertionError('cleanup replay')),self.assertRaises(RuntimeError):runner.finish(cause)
    def test_binary_and_keymap_stdout_matches_observer_without_merging_stderr_diagnostics(self):
        runner=F.Owned(self.root,time.monotonic()+5)
        raw=runner.command([sys.executable,'-I','-B','-c',"import sys; sys.stdout.write('actual output'); sys.stderr.write('diagnostic')"],
            'inert-map','source-control',stdout_only=True)
        self.assertEqual(b'actual output',raw);self.assertEqual(b'diagnostic',(self.root/'inert-map.stderr.log').read_bytes())
        self.assertEqual('observed-empty',runner.finish()['retirement'])

    def test_original_child_exit_remains_distinct_from_retirement(self):
        runner=F.Owned(self.root,time.monotonic()+5)
        with self.assertRaises(RuntimeError):runner.command([sys.executable,'-I','-B','-c','raise SystemExit(7)'],'inert','source-control')
        packet=runner.finish();self.assertEqual(7,packet['actors'][0]['originalExitBeforeCleanup'])
        self.assertEqual('observed-empty',packet['retirement']);self.assertFalse(packet['runtimeAT'])
    def test_service_policy_drift_is_retained_and_primary_exception_preserved(self):
        policy=F.ServicePolicy();policy.path=self.root/'policy'
        cause=RuntimeError('original installation failure')
        with self.assertRaises(RuntimeError) as observed:
            with policy:
                policy.path.write_text('changed')
                raise cause
        self.assertIs(cause,observed.exception);self.assertTrue(policy.path.exists())
        self.assertTrue(any('service-policy' in note for note in cause.__notes__))
    def test_closed_json_refuses_duplicate_properties(self):
        self.path.write_text('{"x":1,"x":2}')
        with self.assertRaises(RuntimeError):F.load(self.path)


if __name__=='__main__':unittest.main()
