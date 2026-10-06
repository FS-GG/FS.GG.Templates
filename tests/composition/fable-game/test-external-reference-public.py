#!/usr/bin/env python3
"""Synthetic archives establish refusal behavior; they are not published proof."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('public_input', HERE / 'external-reference-public.py')
public = importlib.util.module_from_spec(spec); spec.loader.exec_module(public)


class PublicInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'fixture.nupkg'
        self.identity = 'FS.GG.UI.Scene'
        self.payload = {'fixture.nuspec': f'<package><metadata><id>{self.identity}</id><version>0.32.1</version><repository commit="{public.SOURCE}"/><dependencies><group><dependency id="FSharp.Core" version="10.1.401"/></group></dependencies></metadata></package>'.encode(), 'fable/Source.fs': b'// synthetic only\n'}
        self.row = {'payloadEntries': {n: hashlib.sha256(b).hexdigest() for n, b in self.payload.items()}, 'dependencies': [{'id': 'FSharp.Core', 'version': '10.1.401'}]}
        self.write()

    def write(self, signature=b'synthetic signature', extra=None):
        with ZipFile(self.path, 'w') as z:
            for n, b in self.payload.items(): z.writestr(n, b)
            if signature is not None: z.writestr('.signature.p7s', signature)
            if extra: z.writestr(*extra)
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def check(self, expected=None, row=None, identity=None):
        return public.validate_archive(self.path, identity or self.identity, expected or self.sha, row or self.row)

    def test_exact_signed_payload_and_source_pass(self):
        self.assertTrue(self.check()['payloadMatched'])

    def test_changed_signature_refused_by_raw_identity(self):
        original = self.sha; self.write(signature=b'different signer bytes')
        with self.assertRaisesRegex(ValueError, 'raw archive identity'): self.check(expected=original)

    def test_rehashed_changed_payload_still_refused(self):
        self.payload['fable/Source.fs'] = b'changed payload'; self.write()
        with self.assertRaisesRegex(ValueError, 'custody payload'): self.check()

    def test_wrong_source_cannot_be_admitted_by_rehashing_truth(self):
        self.payload['fixture.nuspec'] = self.payload['fixture.nuspec'].replace(public.SOURCE.encode(), b'0' * 40); self.write()
        self.row['payloadEntries'] = {n: hashlib.sha256(b).hexdigest() for n, b in self.payload.items()}
        with self.assertRaisesRegex(ValueError, 'package/source'): self.check()

    def test_unknown_package_identity_refused(self):
        with self.assertRaisesRegex(ValueError, 'package/source'): self.check(identity='unknown')

    def test_dependency_truth_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError, 'dependency'): self.check(row={**self.row, 'dependencies': []})

    def test_unsigned_archive_refused(self):
        self.write(signature=None)
        with self.assertRaisesRegex(ValueError, 'signature absent'): self.check()

    def test_unsafe_path_refused_without_extraction(self):
        self.write(extra=('../escape', b'x'))
        with self.assertRaisesRegex(ValueError, 'unsafe'): self.check()
        self.assertFalse((self.root.parent / 'escape').exists())

    def test_symlink_refused(self):
        target = self.path; self.path = self.root / 'link'; self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'regular archive'): self.check()

    def test_wrong_custody_refused_before_network_or_output(self):
        custody = self.root / 'custody'; custody.write_text('{}'); output = self.root / 'fresh'
        with self.assertRaisesRegex(ValueError, 'custody identity'): public.acquire(custody, output)
        self.assertFalse(output.exists())

    def test_signed_raw_hash_is_not_lock_content_hash(self):
        original = self.root / 'original.nupkg'
        with ZipFile(original, 'w') as z:
            for n, b in self.payload.items(): z.writestr(n, b)
        lock_hash = base64.b64encode(hashlib.sha512(original.read_bytes()).digest()).decode()
        self.assertNotEqual(self.check()['rawSha512'], lock_hash)
        self.assertEqual(self.check()['lockContentHash'], public.LOCK_HASH[self.identity])
        self.assertNotEqual(self.check()['rawSha512'], self.check()['lockContentHash'])

    def test_mode_and_identity_refused_before_receiver_effect(self):
        script = HERE / 'verify-external-reference-candidate.sh'
        for version, source, mode in [('0.32.1', public.SOURCE, 'unknown'), ('0.31.0', public.SOURCE, 'public'), ('0.32.1', '0' * 40, 'public')]:
            output = self.root / 'not-created'
            run = subprocess.run(['bash', str(script), '/missing', '/missing', version, str(output), source, mode], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0); self.assertFalse(output.exists())

    def test_release_c_source_pin_uses_actual_default_and_refuses_ambiguity(self):
        import re
        source = (HERE / 'verify-svg-preview-c-source.sh').read_text()
        match = re.search(r"<<'PYSOURCEPIN'\n(.*?)\nPYSOURCEPIN", source, re.S)
        self.assertIsNotNone(match)
        for xml, expected in [('<Project><PropertyGroup><FsGgSvgInputVersion>0.32.1</FsGgSvgInputVersion></PropertyGroup></Project>', '0.32.1'), ('<Project><FsGgSvgInputVersion>0.31.0</FsGgSvgInputVersion></Project>', '0.31.0'), ('<Project/>', None), ('<Project><FsGgSvgInputVersion>main</FsGgSvgInputVersion></Project>', None), ('<Project><FsGgSvgInputVersion>0.32.1</FsGgSvgInputVersion><FsGgSvgInputVersion>0.31.0</FsGgSvgInputVersion></Project>', None)]:
            path = self.root / 'pin.fsproj'; path.write_text(xml)
            result = subprocess.run(['python3', '-', str(path)], input=match.group(1), text=True, capture_output=True)
            if expected is None: self.assertNotEqual(result.returncode, 0)
            else: self.assertEqual((result.returncode, result.stdout.strip()), (0, expected))

    def test_public_route_keeps_locked_resolution_and_candidate_branch(self):
        source = (HERE / 'verify-external-reference-candidate.sh').read_text()
        public_block = source.split('if [[ "$input_mode" == public ]]; then\n  python3 -', 1)[1].split('\nelse\n  export FsGgSvgInputVersion', 1)[0]
        self.assertIn('--locked-mode --configfile', public_block)
        self.assertNotIn('--force-evaluate', public_block)
        self.assertIn("'.nupkg.metadata'", public_block)
        self.assertIn('dotnet restore "$out/complete/SvgFoundation/SvgFoundation.fsproj" --force-evaluate', source)
        config = source.split('if [[ "$input_mode" == public ]]; then\n  printf', 1)[1].split('\nelse', 1)[0]
        self.assertIn('https://api.nuget.org/v3/index.json', config)
        self.assertNotIn('value="$out/feed"', config)

    def test_shipped_locks_use_original_content_hashes_and_current_defaults(self):
        root = HERE.parents[2] / 'templates/fs-gg-fable-game'
        count = 0
        for path in root.rglob('packages.lock.json'):
            for rows in json.loads(path.read_text())['dependencies'].values():
                for identity, row in rows.items():
                    if identity in public.LOCK_HASH:
                        self.assertEqual(row['resolved'], '0.32.1')
                        self.assertEqual(row['contentHash'], public.LOCK_HASH[identity]); count += 1
        self.assertEqual(count, 9)


if __name__ == '__main__': unittest.main()
