#!/usr/bin/env python3
"""Pure/inert process controls. No APT, installation, guest, display or engine runs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('noble_transaction_controls',HERE/'current-reference-noble-transaction.py')
T=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(T)


def fixture():
    data=json.loads((HERE/'current-reference-noble-metadata-fixture.json').read_text())
    root=next(p for p in data['packages'] if p['name']=='ibus')
    return data,{'schema':'fsgg.current-reference-noble-package-request/1','packages':[root]}


def status(name='fixture',version='1',multi=False):
    return ('Package: '+name+'\nStatus: install ok installed\nArchitecture: amd64\nVersion: '+version+'\n'+('Multi-Arch: same\n' if multi else '')+'\n').encode()


class NoInstallControls(unittest.TestCase):
    def setUp(self):
        self.data,self.roots=fixture()
        self.body='Reading package lists... Done\nBuilding dependency tree... Done\n0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\nInst ibus (1.5.29-2 Ubuntu:24.04/noble [amd64])\nConf ibus (1.5.29-2 Ubuntu:24.04/noble [amd64])\n'

    def test_exact_installed_inventory_handles_real_multiarch_spelling(self):
        value=T.inventory(status()+status('libfixture','2',True))
        self.assertEqual({'fixture':'1','libfixture:amd64':'2'},value)
        self.assertEqual(b'fixture\t1\nlibfixture:amd64\t2\n',T.inventory_bytes(value))
        with self.assertRaises(RuntimeError):T.inventory(status()+status())

    def test_root_request_closed_bound_and_duplicate_fields(self):
        self.assertEqual(self.roots,T.request(json.dumps(self.roots).encode()))
        for raw in [b'',b'x'*65537,b'{"schema":1,"schema":2}',b'{}',json.dumps({**self.roots,'keymaps':{}}).encode()]:
            with self.assertRaises((RuntimeError,ValueError,TypeError)):T.request(raw)

    def test_wrong_runtime_refuses_before_native_tools(self):
        with patch.object(T,'read',return_value=b'ID=arch\nVERSION_ID="24.04"\n'),patch.object(T.subprocess,'Popen',side_effect=AssertionError('native tool reached')):
            with self.assertRaisesRegex(RuntimeError,'actual selected Noble'):T.runtime_guard()

    def test_actual_c068_fixture_is717_with_exact_protected_inventory(self):
        raw,value=T.base_fixture()
        self.assertEqual(717,len(value))
        self.assertEqual(T.BASE_SHA256,T.A.digest(T.inventory_bytes(value)))
        self.assertEqual(T.STATUS_FIXTURE_SHA256,T.A.digest(raw))

    def test_inventory_mismatch_refuses_as_exact_fixture_input_gap(self):
        with patch.object(T,'STATUS_FIXTURE_SHA256','0'*64):
            with self.assertRaisesRegex(RuntimeError,'status fixture differs'):T.base_fixture()

    def test_actual_signed_metadata_source_join_and_real_solver_projection(self):
        changes,final=T.frozen(self.body,{'fixture':'1'},self.roots,self.data['binary'],self.data['sources'])
        self.assertEqual('ibus',changes[0]['package']);self.assertEqual('1.5.29-2',final['ibus'])
        self.assertTrue(any(x['path'].endswith('.dsc') for x in changes[0]['sourceFiles']))
        self.assertTrue(any('debian.tar' in x['path'] for x in changes[0]['sourceFiles']))

    def test_missing_malformed_duplicate_unindexed_or_removal_is_not_solver_success(self):
        bad=['',self.body.replace('0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.','0 upgraded, 2 newly installed, 0 to remove and 0 not upgraded.'),self.body+'Remv fixture [1]\n',self.body+'Purg fixture [1]\n',self.body+self.body.split('Inst ')[1].join(['Inst ','']),self.body.replace('1.5.29-2','9.9.9'),self.body.replace('Inst ibus (','Inst unsupported-format ibus (')]
        for text in bad:
            with self.subTest(text=text[:80]),self.assertRaises(RuntimeError):
                T.frozen(text,{'fixture':'1'},self.roots,self.data['binary'],self.data['sources'])
        with self.assertRaises(RuntimeError):T.frozen('0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n',{'fixture':'1'},self.roots,self.data['binary'],self.data['sources'])

    def test_options_and_actual_commands_cannot_install_or_read_host_apt_configuration(self):
        opts=T.options(Path('/private'))
        for value in ['Dir::Etc::main=-','Dir::Etc::parts=-','Dir::Etc::sourceparts=-','Dir::Etc::preferences=-','Dir::State::status=/private/status','Acquire::By-Hash=no','APT::Sandbox::User=root']:
            self.assertIn(value,opts)
        self.assertNotIn('trusted=yes',' '.join(opts))

    def invoke(self,path,clock=None):
        commands=[];raw=status();base={'fixture':'1'}
        def observed(command,log,budget):
            commands.append(command)
            text=''.join(item.split('=',1)[0]+' \"'+item.split('=',1)[1]+'\";\n' for item in T.options(path) if item!='-o') if command[-1]=='dump' else 'update done\n' if command[-1]=='update' else self.body
            log.write_text(text)
            return text
        with patch.object(T,'runtime_guard',return_value=T.A.digest(raw)),patch.object(T,'base_fixture',return_value=(raw,base)),patch.object(T,'metadata',return_value=(self.data['binary'],self.data['sources'])),patch.object(T,'read',return_value=raw),patch.object(T,'BASE_COUNT',1),patch.object(T,'BASE_SHA256',T.A.digest(T.inventory_bytes(base))):
            result=T.plan(Path('/immutable-inputs'),self.roots,path,Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'),budget=clock,run=observed)
        return result,commands

    def test_real_plan_path_uses_only_update_and_simulate_and_never_claims_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'out';result,commands=self.invoke(root)
            self.assertEqual(3,len(commands));self.assertEqual('dump',commands[0][-1]);self.assertEqual('update',commands[1][-1]);self.assertIn('--simulate',commands[2]);self.assertIn('--no-install-recommends',commands[2])
            self.assertEqual('no-install-apt-simulation',result['actualSolver'])
            for key in ['installation','runtimeQualification','actualAT','nativeImeAcceptance']:self.assertIs(False,result[key])
            self.assertEqual('not-run',result['binaryAcquisition']);self.assertEqual('not-run',result['sourceArchiveAcquisition'])
            self.assertEqual(2,result['expectedFinalInventory']['packages'])

    def test_late_transaction_persistence_keeps_original_but_refuses_return(self):
        now=[0];clock=T.A.Budget(1,lambda:now[0]);real=Path.write_text
        def write(path,*args,**kwargs):
            result=real(path,*args,**kwargs)
            if path.name=='transaction.json':now[0]=2
            return result
        with tempfile.TemporaryDirectory() as tmp,patch.object(Path,'write_text',write):
            out=Path(tmp)/'out'
            with self.assertRaisesRegex(RuntimeError,'original deadline'):self.invoke(out,clock)
            self.assertTrue((out/'transaction.json').exists())
            with self.assertRaisesRegex(RuntimeError,'fresh transaction output'):self.invoke(out)

    def test_input_output_alias_refuses_before_runtime(self):
        with patch.object(T,'runtime_guard',side_effect=AssertionError('runtime reached')):
            with self.assertRaisesRegex(RuntimeError,'domains overlap'):
                T.plan(Path('/inputs'),self.roots,Path('/inputs/out'),Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'))

    def test_inert_child_failure_retains_partial_evidence_and_original_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'home').mkdir();(root/'tmp').mkdir();T.bootstrap(root)
            with self.assertRaisesRegex(RuntimeError,'original APT exit 7'):
                T.observed([sys.executable,'-I','-c','print("original inert failure");raise SystemExit(7)'],root/'child.log',T.A.Budget(5))
            self.assertIn('original inert failure',(root/'child.log').read_text())
            self.assertEqual('before-cleanup',json.loads((root/'partial-failure.json').read_text())['phase'])
            self.assertTrue(json.loads((root/'retirement.json').read_text())['originalFailurePreserved'])

    def test_launch_error_has_original_intent_and_partial_evidence_no_fake_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);T.bootstrap(root)
            with self.assertRaises(FileNotFoundError):
                T.observed(['/nonexistent-inert-fixture'],root/'child.log',T.A.Budget(5))
            self.assertTrue((root/'child.log.intent.json').exists())
            self.assertEqual('not-established',json.loads((root/'partial-failure.json').read_text())['childIdentity'])

    def test_original_apt_source_requires_config_before_commandline_and_host_parts(self):
        original=json.loads((HERE/'fixtures/apt-config-init-order.json').read_text())
        cli,init=original['files']
        self.assertIn('pkgInitConfig',cli['lines'][0]['text']);self.assertIn('CmdL.Parse',cli['lines'][1]['text'])
        self.assertLess(cli['lines'][0]['number'],cli['lines'][1]['number'])
        self.assertIn('APT_CONFIG',init['lines'][0]['text'])
        self.assertIn('Dir::Etc::parts',init['lines'][1]['text']);self.assertIn('Dir::Etc::main',init['lines'][2]['text'])
        self.assertEqual(sorted(r['number'] for r in init['lines']),[r['number'] for r in init['lines']])

    def test_private_bootstrap_is_present_in_environment_before_command_line_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'home').mkdir();(root/'tmp').mkdir();config=T.bootstrap(root)
            expected=['Dir::Etc::main "-";','Dir::Etc::parts "-";','Dir::Etc::netrc "-";']
            script='import os,pathlib; s=pathlib.Path(os.environ["APT_CONFIG"]).read_text(); expected='+repr(expected)+'; assert all(v in s for v in expected); assert "GH_TOKEN" not in os.environ; print("private-before-command-line")'
            with patch.dict(os.environ,{'APT_CONFIG':'/ambient-untrusted-config','GH_TOKEN':'inert-sentinel'}):
                result=T.observed([sys.executable,'-I','-c',script],root/'init.log',T.A.Budget(5))
            self.assertEqual('private-before-command-line\n',result)
            self.assertTrue(config.is_file())

    def test_actual_effective_config_must_match_private_controls_and_have_no_hooks(self):
        root=Path('/private')
        text=''.join(item.split('=',1)[0]+' "'+item.split('=',1)[1]+'";\n' for item in T.options(root) if item!='-o')
        T.effective_config(text,root)
        for bad in [text.replace('Dir::Etc::parts "-"','Dir::Etc::parts "/etc/apt/apt.conf.d"'),text+'APT::Update::Post-Invoke:: "ambient hook";\n',text+'Dir::Etc::main "-";\n','unknown-format']:
            with self.assertRaises(RuntimeError):T.effective_config(bad,root)

    def test_reporting_failure_cannot_skip_cleanup_or_replace_original_live_child_failure(self):
        real_write=Path.write_text;real_popen=T.subprocess.Popen;children=[]
        def writes(path,*args,**kwargs):
            if path.name in ('partial-failure.json','retirement.json'):raise OSError('inert report failure')
            return real_write(path,*args,**kwargs)
        def launch(*args,**kwargs):
            child=real_popen(*args,**kwargs);children.append(child);return child
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'home').mkdir();(root/'tmp').mkdir();T.bootstrap(root)
            with patch.object(Path,'write_text',writes),patch.object(T.subprocess,'Popen',side_effect=launch),patch.object(T,'MAX_LOG',1):
                with self.assertRaisesRegex(RuntimeError,'original APT output exceeded') as caught:
                    T.observed([sys.executable,'-I','-c','import time;print("too much",flush=True);time.sleep(60)'],root/'child.log',T.A.Budget(5))
            self.assertEqual(1,len(children));self.assertIsNotNone(children[0].returncode)
            self.assertTrue(any('secondary reporting failure' in n for n in caught.exception.__notes__))

    def test_launch_report_failure_preserves_original_launch_error(self):
        real_write=Path.write_text
        def writes(path,*args,**kwargs):
            if path.name=='partial-failure.json':raise OSError('inert report failure')
            return real_write(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);T.bootstrap(root)
            with patch.object(Path,'write_text',writes):
                with self.assertRaises(FileNotFoundError) as caught:
                    T.observed(['/nonexistent-inert-fixture'],root/'child.log',T.A.Budget(5))
            self.assertTrue(any('secondary reporting failure' in n for n in caught.exception.__notes__))


if __name__=='__main__':unittest.main()
