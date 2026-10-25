#!/usr/bin/env python3
"""Pure acquisition/refusal controls; no network, package install or desktop."""
import ast
import copy
import importlib.util
import io
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('noble_acquisition_controls', HERE / 'current-reference-noble-acquisition.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


class Response(io.BytesIO):
    def __init__(self, body, status=200, uri=A.BASE+'pool/test.deb'):
        super().__init__(body)
        self.status, self.uri = status, uri
    def geturl(self):
        return self.uri


class Opener:
    def __init__(self, response):
        self.response, self.calls = response, 0
    def open(self, *args, **kwargs):
        self.calls += 1
        return self.response


class AcquisitionControls(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((HERE/'current-reference-noble-metadata-fixture.json').read_text())

    def test_actual_signed_metadata_rows_join_patched_sources(self):
        for package in self.fixture['packages']:
            row = A.select(package, self.fixture['binary'], self.fixture['sources'])
            self.assertEqual(row['version'], package['version'])
            self.assertTrue(any(x['path'].endswith('.dsc') for x in row['sourceFiles']))
            self.assertTrue(any('debian.tar' in x['path'] for x in row['sourceFiles']))
            self.assertTrue(any('.orig.tar' in x['path'] for x in row['sourceFiles']))

    def test_wrong_binary_or_patched_source_pin_refuses(self):
        for key in ['debSha256','sourceSha256','version','sourceUri']:
            package = copy.deepcopy(self.fixture['packages'][0])
            package[key] += 'wrong'
            with self.assertRaises(RuntimeError):
                A.select(package,self.fixture['binary'],self.fixture['sources'])
        sources = copy.deepcopy(self.fixture['sources'])
        for row in sources:
            row['Version'] = 'unpatched-upstream-version'
        with self.assertRaises(RuntimeError):
            A.select(self.fixture['packages'][0],self.fixture['binary'],sources)

    def test_complete_source_closure_not_only_dsc(self):
        package = self.fixture['packages'][0]
        selected = A.select(package,self.fixture['binary'],self.fixture['sources'])
        self.assertGreaterEqual(len(selected['sourceFiles']), 3)
        self.assertTrue(selected['depends'])

    def test_unsigned_prefix_never_parsed_as_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);key=root/'key';key.write_bytes(b'wrong')
            with patch.object(A.subprocess,'run',side_effect=AssertionError('gpg before pinned keyring')):
                with self.assertRaisesRegex(RuntimeError,'keyring differs'):
                    A.signed_release(root/'absent',key,'noble',A.Budget())

    def test_signed_plaintext_only_and_exact_signer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);key=root/'key';key.write_bytes(b'fixture-key')
            original_signer=A.SIGNER
            def gpg(command,**kwargs):
                Path(command[command.index('--output')+1]).write_text('Origin: Ubuntu\nSuite: noble\nCodename: noble\nSHA256:\n '+'a'*64+' 1 main/binary-amd64/Packages.xz\n')
                return type('Done',(),dict(returncode=0,stdout=('[GNUPG:] GOODSIG x\n[GNUPG:] VALIDSIG '+original_signer+' 2026-10-24 1 0 4 0 1 10 01 '+original_signer+'\n').encode(),stderr=b''))()
            with patch.object(A,'KEYRING_SHA256',A.digest(b'fixture-key')),patch.object(A.subprocess,'run',side_effect=gpg):
                self.assertIn('main/binary-amd64/Packages.xz',A.signed_release(root/'unsigned-input',key,'noble',A.Budget()))
                with self.assertRaisesRegex(RuntimeError,'identity differs'):
                    A.signed_release(root/'unsigned-input',key,'noble-updates',A.Budget())
            with patch.object(A,'KEYRING_SHA256',A.digest(b'fixture-key')),patch.object(A,'SIGNER','f'*40),patch.object(A.subprocess,'run',side_effect=gpg):
                with self.assertRaisesRegex(RuntimeError,'signature refused'):
                    A.signed_release(root/'unsigned-input',key,'noble',A.Budget())

    def test_http_status_before_digest_or_output(self):
        for status in [206,301,404,500]:
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'input';opener=Opener(Response(b'x',status))
                with self.assertRaisesRegex(RuntimeError,'HTTP status'):
                    A.fetch(A.BASE+'pool/test.deb',A.digest(b'x'),1,target,A.Budget(),opener)
                self.assertFalse(target.exists());self.assertEqual(opener.calls,1)

    def test_size_hash_and_original_partial_failure(self):
        for body,sha,size in [(b'xx',A.digest(b'x'),1),(b'x',A.digest(b'y'),1),(b'x',A.digest(b'xx'),2)]:
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'input';opener=Opener(Response(body))
                with self.assertRaises(RuntimeError):
                    A.fetch(A.BASE+'pool/test.deb',sha,size,target,A.Budget(),opener)
                self.assertTrue(target.exists());self.assertEqual(opener.calls,1)
                with self.assertRaisesRegex(RuntimeError,'already exists'):
                    A.fetch(A.BASE+'pool/test.deb',sha,size,target,A.Budget(),opener)
                self.assertEqual(opener.calls,1)

    def test_selected_origin_paths_only(self):
        for uri in ['https://example.invalid/x',A.BASE+'../x',A.BASE+'pool/a?x=1',A.BASE+'pool//x',A.BASE+'pool/%2e%2e/x']:
            with tempfile.TemporaryDirectory() as tmp,self.assertRaises(RuntimeError):
                A.fetch(uri,'a'*64,1,Path(tmp)/'x',A.Budget(),Opener(Response(b'x')))

    def test_original_deadline_and_population_bounds(self):
        now=[0];budget=A.Budget(1,lambda:now[0]);now[0]=2
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(RuntimeError,'deadline'):
            A.fetch(A.BASE+'pool/test.deb','a'*64,1,Path(tmp)/'x',budget,Opener(Response(b'x')))
        budget=A.Budget();budget.requests=A.MAX_REQUESTS
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(RuntimeError,'population'):
            A.fetch(A.BASE+'pool/test.deb','a'*64,1,Path(tmp)/'x',budget,Opener(Response(b'x')))

    def test_actual_ubuntu_empty_second_xz_stream_and_bounds(self):
        raw=lzma.compress(b'Package: fixture\nVersion: 1\n\n')+lzma.compress(b'')
        self.assertEqual(list(A.rows(raw))[0]['Package'],'fixture')
        for raw in [raw+b'unsigned',raw[:-1],lzma.compress(b'Package: x\nPackage: y\n\n')]:
            with self.assertRaises((RuntimeError,lzma.LZMAError)):
                list(A.rows(raw))
        with patch.object(A,'MAX_EXPANDED',4),self.assertRaises(RuntimeError):
            list(A.rows(lzma.compress(b'012345')))

    def test_redirect_and_http_library_errors_no_retry(self):
        with self.assertRaisesRegex(RuntimeError,'redirect refused'):
            A.NoRedirect().redirect_request(None,None,None,None,None,None)
        opener=Opener(Response(b'x',uri='https://example.invalid/x'))
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(RuntimeError,'origin differs'):
            A.fetch(A.BASE+'pool/test.deb',A.digest(b'x'),1,Path(tmp)/'x',A.Budget(),opener)
        self.assertEqual(opener.calls,1)

    def test_early_manifest_refusal_before_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(A,'fetch',side_effect=AssertionError('network reached')):
            with self.assertRaises((RuntimeError,KeyError,TypeError)):
                A.acquire({},Path(tmp)/'absent',Path(tmp)/'key')
            self.assertFalse((Path(tmp)/'absent').exists())

    def test_actual_registration_mutations_refuse(self):
        source=(HERE/'verify-external-reference-workflow.py').read_text()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='validate_current_at_registration')
        namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-registration','exec'),namespace)
        validate=namespace['validate_current_at_registration']
        workflow=(HERE.parents[2]/'.github/workflows/fable-external-reference-source.yml').read_text()
        self.assertTrue(validate(workflow))
        for old,new in [
            ("if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}",'if: always()'),
            ('timeout --kill-after=5s 240s prlimit --as=2147483648 --cpu=120','timeout 900s'),
            ('${{ runner.temp }}/current-noble-acquisition/acquisition.json','${{ runner.temp }}/wrong.json'),
            ('Refuse held current AT before acquisition or setup','missing guard'),
            ("      - 'tests/composition/fable-game/current-reference-noble-acquisition.py'",'')]:
            with self.subTest(old=old),self.assertRaises((AssertionError,ValueError)):
                validate(workflow.replace(old,new))


if __name__=='__main__':
    unittest.main()
