#!/usr/bin/env python3
"""Pure controls of hosted snapshot provisioning; no apt, privilege, network or install runs here."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('noble_install_controls', HERE / 'current-reference-noble-install.py')
I = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(I)
WORKFLOW = (HERE.parents[2] / '.github/workflows/fable-external-reference-source.yml').read_text()


def committed():
    return I.N.read_manifest(I.COMMITTED.read_text())


def fakes(manifest, root_rows):
    versions = {**dict(root_rows), **{r['name']: r['version'] for r in manifest['packages']}}
    hashes = {r['name']: r['debSha256'] for r in manifest['packages']}
    return (lambda name: versions[name.removesuffix(':amd64')] if name.removesuffix(':amd64') in versions else versions[name],
            lambda name, version: hashes[name], lambda value: True)


class SnapshotProvisioningControls(unittest.TestCase):
    def test_roots_are_the_32_reviewed_exact_rows_and_agree_with_the_manifest(self):
        rows = I.roots()
        self.assertEqual(32, len(rows))
        self.assertEqual(32, len({name for name, _ in rows}))
        self.assertTrue(all(version for _, version in rows))
        manifest = committed()
        self.assertEqual(11, I.check_manifest_against_roots(manifest, rows))
        self.assertEqual(['ibus-data'], [r['name'] for r in manifest['packages'] if r['name'] not in {n for n, _ in rows} and r['name'].removesuffix(':amd64') not in {n for n, _ in rows}])
        for index in range(len(manifest['packages'])):
            bad = copy.deepcopy(manifest)
            row = bad['packages'][index]
            if row['name'].removesuffix(':amd64') in dict(rows):
                row['version'] += '+x'
                with self.assertRaisesRegex(I.Refused, 'differs from root'):
                    I.check_manifest_against_roots(bad, rows)

    def test_source_is_keyring_pinned_snapshot_with_no_host_sources_or_recommends(self):
        rows = I.roots()
        with tempfile.TemporaryDirectory() as tmp:
            keyring = Path(tmp) / 'keyring.gpg'; keyring.write_bytes(b'fixture keyring')
            with patch.object(I.A, 'KEYRING_SHA256', I.N.sha(b'fixture keyring')):
                private = Path(tmp) / 'p'; private.mkdir()
                pinned = I.prepare_private(private, keyring)
            text = (private / 'sources.d/snapshot.sources').read_text()
            self.assertIn('Signed-By: %s' % pinned, text)
            self.assertIn('URIs: https://snapshot.ubuntu.com/ubuntu/20261024T000000Z/', text)
            self.assertIn('Suites: noble noble-updates noble-security', text)
            self.assertNotIn('Trusted', text)
            self.assertEqual(b'fixture keyring', pinned.read_bytes())
            options = ' '.join(I.apt_options(private))
            for key in ['Dir::Etc::sourcelist=', 'Dir::Etc::sourceparts=', 'Dir::Etc::preferences=', 'Dir::State::lists=', 'Dir::Cache::archives=']:
                self.assertIn(key + str(private), options)
            for simulate in [True, False]:
                argv = I.install_argv(private, rows, simulate)
                self.assertIn('--no-install-recommends', argv)
                self.assertEqual(('--simulate' in argv), simulate)
                self.assertEqual(['%s=%s' % row for row in rows], [a for a in argv if '=' in a and not a.startswith(('Dir::', 'Acquire::', 'APT::'))])

    def test_wrong_keyring_bytes_refuse_before_any_source_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            keyring = Path(tmp) / 'keyring.gpg'; keyring.write_bytes(b'ambient keyring')
            private = Path(tmp) / 'p'; private.mkdir()
            with self.assertRaisesRegex(I.Refused, 'keyring differs'):
                I.prepare_private(private, keyring)
            self.assertFalse((private / 'sources.d').exists())

    def test_install_is_held_by_the_none_gate_before_any_command_or_manifest_read(self):
        with patch.object(I.subprocess, 'run', side_effect=AssertionError('command reached')), \
             patch.dict(os.environ, FSGG_CURRENT_PUBLIC_AT_ADMISSION='inert-control-only', FSGG_CURRENT_NATIVE_INPUT_FACILITY=I.COMMITTED.read_text()):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(RuntimeError, 'held'):
                    I.main(['--install', '--private', str(Path(tmp) / 'p')])
                self.assertFalse((Path(tmp) / 'p').exists())

    def test_admitted_install_still_refuses_a_missing_or_damaged_manifest_before_apt(self):
        spec = importlib.util.spec_from_file_location('noble_install_caller_controls', HERE / 'current-reference-at-caller.py')
        caller = importlib.util.module_from_spec(spec); spec.loader.exec_module(caller)
        raw = I.COMMITTED.read_text()
        for label, payload in {'missing': '', 'truncated': raw[:-40], 'dropped-role': raw.replace('"xdotool":', '"renamed":', 1)}.items():
            with patch.object(caller.observer, 'CURRENT_PUBLIC_AT_ADMISSION', 'inert-control-only'), \
                 patch.object(I, 'load', side_effect=lambda name, path, _l=I.load: caller if 'caller' in name else _l(name, path)), \
                 patch.dict(os.environ, FSGG_CURRENT_PUBLIC_AT_ADMISSION='inert-control-only', FSGG_CURRENT_NATIVE_INPUT_FACILITY=payload), \
                 patch.object(I.subprocess, 'run', side_effect=AssertionError('command reached')):
                with tempfile.TemporaryDirectory() as tmp, self.assertRaises((RuntimeError, ValueError), msg=label):
                    I.main(['--install', '--private', str(Path(tmp) / 'p')])

    def test_readback_accepts_the_reviewed_tuple_and_refuses_every_single_difference(self):
        rows = I.roots(); manifest = committed()
        query, download, verify = fakes(manifest, rows)
        result = I.readback(manifest, rows, query, download, verify)
        self.assertEqual({'roots': 32, 'packages': 12, 'files': 39}, result)
        refusals = 0
        versions = {**dict(rows), **{r['name']: r['version'] for r in manifest['packages']}}
        for name, _ in rows:
            with self.assertRaisesRegex(I.Refused, 'root version differs'):
                I.readback(manifest, rows, lambda n, t=name: 'tampered' if n == t else query(n), download, verify)
            refusals += 1
        for row in manifest['packages']:
            with self.assertRaisesRegex(I.Refused, 'package version differs'):
                I.readback(manifest, [], lambda n, t=row['name']: 'tampered' if n == t else query(n), download, verify)
            refusals += 1
            with self.assertRaisesRegex(I.Refused, 'archive hash differs'):
                I.readback(manifest, [], query, lambda n, v, t=row['name']: '0' * 64 if n == t else download(n, v), verify)
            refusals += 1
        def failing(value):
            raise RuntimeError('native input: facility file bytes differ')
        with self.assertRaisesRegex(RuntimeError, 'bytes differ'):
            I.readback(manifest, rows, query, download, failing)
        refusals += 1
        self.assertEqual(32 + 12 + 12 + 1, refusals)
        print('snapshot readback refusals:', refusals)

    def test_real_verifier_refuses_a_tampered_installed_file_in_the_readback(self):
        import types, stat
        manifest = committed(); rows = [*manifest['objects'].values(), *manifest['dataFiles']]
        installed = {r['path']: ('installed:' + r['path']).encode() for r in rows}
        pinned = {installed[r['path']]: r['sha256'] for r in rows}
        info = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_size=64)
        read = lambda path: b'ID=ubuntu\nVERSION_ID="24.04"\n' if path == '/etc/os-release' else installed[path]
        real = I.N.sha
        with patch.object(I.N, 'sha', lambda raw: pinned.get(raw) or real(raw)):
            verify = lambda value: I.N.verify_files(value, read, lambda p: info)
            query, download, _ = fakes(manifest, I.roots())
            self.assertEqual(39, I.readback(manifest, I.roots(), query, download, verify)['files'])
            bad = copy.deepcopy(manifest); bad['objects']['xkbcomp']['sha256'] = '0' * 64
            with self.assertRaisesRegex(RuntimeError, 'bytes differ'):
                I.readback(bad, I.roots(), query, download, verify)

    def test_simulation_refuses_removals_and_counts_downgrades(self):
        summary = '3 upgraded, 4 newly installed, 0 to remove and 1 not upgraded.\n'
        good = 'Inst libfoo [1.0] (0.9 Ubuntu:24.04/noble [amd64])\nInst bar (1.0 Ubuntu:24.04/noble [amd64])\n' + summary
        with patch.object(I, 'version_less', lambda new, old: new < old):
            self.assertEqual({'install': 2, 'downgrades': ['libfoo'], 'removals': 0}, I.classify_simulation(good))
            for bad in ['Remv orca [46]\n' + summary, good.replace('3 upgraded', 'x upgraded'), 'no summary']:
                with self.assertRaises(I.Refused):
                    I.classify_simulation(bad)

    def test_workflow_provisioning_is_gated_ordered_and_leaves_the_none_gate_alone(self):
        steps = re.findall(r'^      - (?:name|uses): (.+)$', WORKFLOW.split('  candidate:', 1)[1], re.M)
        names = [s for s in steps]
        guard = names.index('Refuse held current AT before acquisition or setup')
        install = names.index('Install declared Noble snapshot roots and read them back against the facility manifest')
        legacy = names.index('Provision external reference assistive technology')
        acquire = names.index('Acquire declared current Noble inputs without installation')
        self.assertTrue(guard < acquire < install < legacy)
        body = WORKFLOW.split('      - name: Install declared Noble snapshot roots', 1)[1].split('      - name: Provision external reference assistive technology', 1)[0]
        self.assertIn("if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}", body)
        self.assertIn('current-reference-noble-install.py --install', body)
        self.assertIn('snapshot-provisioning.json', body)
        self.assertNotIn('apt-get install', body)
        self.assertNotIn('sudo', body)
        legacy_if = WORKFLOW.split('      - name: Provision external reference assistive technology\n', 1)[1].split('\n', 1)[0]
        self.assertEqual("        if: ${{ !inputs.preflight-only && inputs.rendering-input-source != 'current-public-composition' }}", legacy_if)
        self.assertIn('current-reference-noble-install.py --simulate', WORKFLOW.split('  candidate:', 1)[0])
        orca = (HERE / 'external-reference-orca.py').read_text()
        self.assertRegex(orca, r'(?m)^CURRENT_PUBLIC_AT_ADMISSION = None$')
        self.assertIn("      current-public-at-admission:", WORKFLOW)


if __name__ == '__main__':
    unittest.main()
