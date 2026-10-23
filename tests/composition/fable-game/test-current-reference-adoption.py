#!/usr/bin/env python3
"""Pure synthetic controls. No template engine, public archive or runtime proof."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('reference_harness', Path(__file__).with_name('verify-current-reference-adoption.py'))
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)
adopter = harness.adopter


class CurrentReference(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='current-reference-synthetic-')
        self.root = Path(self.temp.name)
        self.manifest = self.root / harness.MANIFEST.name
        self.manifest.write_bytes(harness.MANIFEST.read_bytes())
        self.historical = self.root / 'svg-complete-workspace-baselines.json'
        self.historical.write_bytes((ROOT / 'scripts' / self.historical.name).read_bytes())
        self.extension = json.loads(self.manifest.read_text())
        self.candidate = self.root / 'candidate'
        self.receiver = self.root / 'receiver'
        self.candidate.mkdir()
        self.receiver.mkdir()
        manifest, managed, _, _ = adopter.manifest_data(self.manifest)
        # Deliberately copied source with text substitutions, NOT dotnet new output.
        for logical in managed:
            if logical.startswith(('.agents/', '.claude/')):
                continue
            raw = (ROOT / 'templates/fs-gg-fable-game' / logical).read_bytes()
            destination = self.candidate / ('SyntheticReference403.slnx' if logical == 'FableGameWorkspace.slnx' else logical)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw.replace(b'FableGameWorkspaceNamespace', b'SyntheticReferenceNamespace403')
                                   .replace(b'FableGameWorkspace', b'SyntheticReference403')
                                   .replace(b'fablegameworkspace', b'syntheticreference403'))
            destination.chmod(0o755 if logical.endswith('.sh') else 0o644)
        skills = json.loads((ROOT / 'template/skill-manifest/skill-manifest.json').read_text())
        materialized = []
        for row in skills['skills']:
            supplied = row.get('supplied-by', '')
            if supplied.startswith('template/product-skills/fable-') and row['id'] != 'fable-bindings':
                path = self.candidate / row['resolvablePath']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / supplied / 'SKILL.md').read_bytes())
                materialized.append({'path': row['resolvablePath'], 'owner': 'generatedProduct'})
        path = self.candidate / '.agents/skills/skill-manifest.json'
        path.write_text(json.dumps(skills))
        path = self.candidate / '.fsgg/scaffold-provenance.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'syntheticFixture': True, 'producedPaths': materialized}))
        (self.receiver / 'SyntheticRetained403.slnx').write_bytes((self.candidate / 'SyntheticReference403.slnx').read_bytes().replace(b'SyntheticReference403', b'SyntheticRetained403'))
        (self.receiver / 'Domain').mkdir()
        (self.receiver / 'Domain/Room.fs').write_bytes((self.candidate / 'Domain/Room.fs').read_bytes().replace(b'SyntheticReferenceNamespace403', b'SyntheticRetainedNamespace403').replace(b'SyntheticReference403', b'SyntheticRetained403'))
        for logical, content in {
            'authored/save.json': b'owner save\n', 'authored/replay.json': b'owner replay\n',
            'authored/extension.fs': b'owner extension\n', '.config/local.json': b'owner configuration\n',
            'AGENTS.md': b'owner guidance\n', '.fsgg/scaffold-provenance.json': b'old lifecycle provenance\n',
            '.agents/skills/local/SKILL.md': b'local owner skill\n',
        }.items():
            path = self.receiver / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o600)
        self.inventory = self.root / 'inventory.json'
        self.review = self.root / 'review.diff'
        self.backup = self.root / 'backup'

    def tearDown(self):
        self.temp.cleanup()

    def write_extension(self):
        self.manifest.write_text(json.dumps(self.extension))

    def inventory_receiver(self):
        adopter.inventory(list(map(str, [self.candidate, self.receiver, self.manifest, self.inventory, self.review])))

    def apply_receiver(self):
        adopter.apply(list(map(str, [self.candidate, self.receiver, self.manifest, self.inventory, self.backup])))

    def tree(self):
        return adopter.tree_observation(self.receiver)[0]

    def test_historical_baselines_and_exact_current_cohort(self):
        current, managed, _, _ = adopter.manifest_data(self.manifest)
        historical, original, _, _ = adopter.manifest_data(self.historical)
        self.assertEqual(current['sourceArchives'], historical['sourceArchives'])
        self.assertEqual(current['baselineDigests'], historical['baselineDigests'])
        self.assertEqual([row['version'] for row in current['sourceArchives']], ['0.10.0', '0.11.0', '0.12.0', '0.13.0'])
        self.assertEqual(current['currentPublishedReference'], adopter.CURRENT_REFERENCE)
        self.assertEqual(set(managed) - set(original), set(self.extension['additionalManagedPaths']))
        for logical in ['SvgFoundation/FourDReference.fs', 'SvgFoundation/ExternalAuthorityReference.fs',
                        'SvgFoundation/Examples/FourD/LocalSaveReplayExample.fs',
                        'SvgFoundation/Examples/Wasm/WasmPolicyBrowser.fs',
                        'SvgFoundation/Examples/Wasm/guest/policy.c', 'Browser.Tests/wasm-policy.spec.ts']:
            self.assertIn(logical, managed)
            self.assertIn(logical, current['candidateCanonicalDigests'])

    def test_current_complete_reference_source_population_is_covered(self):
        _, managed, _, _ = adopter.manifest_data(self.manifest)
        source = ROOT / 'templates/fs-gg-fable-game'
        reference = {path.relative_to(source).as_posix()
                     for path in (source / 'SvgFoundation').rglob('*') if path.is_file()}
        # The template's unconditional modifier explicitly excludes these two.
        excluded = {'SvgFoundation/PreviewDocument.fs', 'SvgFoundation/PreviewFont.fs'}
        self.assertTrue(excluded <= reference)  # known-present measurement control
        self.assertTrue(reference - excluded <= set(managed))
        self.assertTrue(excluded.isdisjoint(managed))
        for logical in ['Browser.Tests/external-command-outcomes.spec.ts',
                        'Browser.Tests/soldier-reference.spec.ts', 'Browser.Tests/wasm-policy.spec.ts']:
            self.assertIn(logical, managed)

    def test_wrong_target_and_changed_historical_manifest_refuse(self):
        self.extension['currentPublishedReference']['version'] = '0.19.2'
        self.write_extension()
        with self.assertRaises(SystemExit):
            adopter.manifest_data(self.manifest)
        self.manifest.write_bytes(harness.MANIFEST.read_bytes())
        self.historical.write_bytes(self.historical.read_bytes() + b'\n')
        with self.assertRaises(SystemExit):
            adopter.manifest_data(self.manifest)

    def test_missing_or_forged_reference_hash_population_refuses(self):
        self.extension['candidateCanonicalDigests'].pop('SvgFoundation/FourDReference.fs')
        self.write_extension()
        with self.assertRaises(SystemExit):
            adopter.manifest_data(self.manifest)

    def test_missing_and_edited_candidate_reference_refuse_before_receiver_write(self):
        path = self.candidate / 'SvgFoundation/Examples/Wasm/guest/policy.c'
        raw = path.read_bytes()
        before = self.tree()
        path.unlink()
        with self.assertRaises(SystemExit):
            self.inventory_receiver()
        self.assertEqual(self.tree(), before)
        path.write_bytes(raw + b'\n// changed target\n')
        with self.assertRaises(SystemExit):
            self.inventory_receiver()
        self.assertEqual(self.tree(), before)

    def test_copied_receiver_harness_checks_full_target_and_recovery(self):
        before = self.tree()
        receipt = harness.exercise(self.candidate, self.receiver, self.root / 'controls', self.manifest)
        self.assertEqual(self.tree(), before)
        self.assertEqual(len(receipt['controls']), 5)
        self.assertEqual(receipt['currentPublishedReference']['version'], '0.19.3')
        self.assertIn('locked-build', receipt['requiredNext'])
        self.assertEqual((Path(receipt['adopted']) / 'authored/save.json').read_bytes(), b'owner save\n')
        self.assertEqual((Path(receipt['adopted']) / '.fsgg/scaffold-provenance.json').read_bytes(), b'old lifecycle provenance\n')

    def test_existing_and_new_managed_collisions_refuse_without_backup(self):
        for logical in ['Domain/Room.fs', 'SvgFoundation/FourDReference.fs']:
            path = self.receiver / logical
            previous = path.read_bytes() if path.exists() else None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((previous or b'') + b'\n// owner edit\n')
            before = self.tree()
            with self.assertRaises(SystemExit) as error:
                self.inventory_receiver()
            self.assertEqual(error.exception.code, 3)
            self.assertEqual(self.tree(), before)
            self.assertFalse(self.backup.exists())
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)

    def test_receiver_mode_candidate_mode_and_diff_stale_inventory_refuse(self):
        for change in ['receiver', 'candidate', 'diff']:
            with self.subTest(change=change):
                self.inventory_receiver()
                if change == 'receiver':
                    path = self.receiver / 'Domain/Room.fs'
                    path.chmod(0o600)
                elif change == 'candidate':
                    path = self.candidate / 'SvgFoundation/FourDReference.fs'
                    path.chmod(0o600)
                else:
                    self.review.write_text('forged review')
                before = self.tree()
                with self.assertRaises(SystemExit):
                    self.apply_receiver()
                self.assertFalse(self.backup.exists())
                self.assertEqual(self.tree(), before)

    def test_newer_edit_blocks_rollback_before_write(self):
        self.inventory_receiver()
        self.apply_receiver()
        (self.receiver / 'SvgFoundation/FourDReference.fs').write_bytes(b'new owner change\n')
        before = self.tree()
        with self.assertRaises(SystemExit) as error:
            adopter.restore(self.receiver, self.backup)
        self.assertEqual(error.exception.code, 3)
        self.assertEqual(self.tree(), before)

    def test_corrupt_backup_blocks_recovery_before_write(self):
        self.inventory_receiver()
        self.apply_receiver()
        (self.backup / 'files/Domain/Room.fs').write_bytes(b'corrupt before state')
        before = self.tree()
        with self.assertRaises(SystemExit):
            adopter.restore(self.receiver, self.backup)
        self.assertEqual(self.tree(), before)

    def test_reference_symlink_refuses(self):
        destination = self.receiver / 'SvgFoundation'
        destination.symlink_to(self.candidate / 'SvgFoundation', target_is_directory=True)
        before = self.tree()
        with self.assertRaises(SystemExit):
            self.inventory_receiver()
        self.assertEqual(self.tree(), before)

    def test_archive_hash_control_rejects_foreign_body(self):
        path = self.root / 'foreign.nupkg'
        path.write_bytes(b'foreign package; not public acceptance')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            harness.public_archive(path, adopter.CURRENT_REFERENCE['publicArchiveSha256'], '0.19.3')


if __name__ == '__main__':
    print('SYNTHETIC copied source and owner sentinels; no template engine/package/build/browser acceptance.')
    unittest.main(verbosity=2, buffer=True)
