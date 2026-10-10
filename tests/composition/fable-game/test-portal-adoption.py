#!/usr/bin/env python3
"""Synthetic transaction controls; not genuine public retained adoption acceptance."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('adopter', ROOT/'scripts/apply-svg-complete-workspace.py')
adopter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adopter)


def full_tree(root):
    result = []
    for p in sorted(root.rglob('*')):
        mode = stat.S_IMODE(p.lstat().st_mode)
        value = os.readlink(p).encode() if p.is_symlink() else p.read_bytes() if p.is_file() else b''
        result.append((p.relative_to(root).as_posix(), mode, hashlib.sha256(value).hexdigest()))
    return result


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portal-synthetic-')
        self.root = Path(self.temp.name)
        self.workspace = self.root/'receiver'
        self.candidate = self.root/'candidate'
        self.archive = self.root/'synthetic-baseline-placeholder.nupkg'
        self.archive.write_bytes(b'synthetic; no public acquisition/installed acceptance')
        for folder, product, namespace in [(self.workspace,'Retained-Product','RetainedProduct'),(self.candidate,'Candidate-Product','CandidateProduct')]:
            (folder/'Domain').mkdir(parents=True)
            (folder/(product+'.slnx')).write_text('<Solution/>\n')
            (folder/'Domain/Room.fs').write_text('namespace '+namespace+'.Domain\nlet value = 1\n')
        payload = self.candidate/'PortalExample';payload.mkdir()
        for p in (ROOT/'templates/fs-gg-fable-game/PortalExample').iterdir():
            shutil.copy2(p,payload/p.name)
        shutil.copy2(ROOT/'scripts/apply-svg-complete-workspace.py',payload/'manage.py')
        (self.workspace/'authored').mkdir()
        (self.workspace/'authored/level.json').write_bytes(b'authored-data\n')
        (self.workspace/'authored/local.fs').write_bytes(b'module Authored\nlet value=42\n')
        (self.workspace/'.agents/skills/local').mkdir(parents=True)
        (self.workspace/'.agents/skills/local/SKILL.md').write_bytes(b'user-authored-skill\n')
        (self.workspace/'default.lock').write_bytes(b'preserve-default-lock\n')
        self.baseline_patch = patch.object(adopter,'portal_baseline',return_value={'synthetic':True,'publicAcceptance':False})
        self.baseline_patch.start()
        self.count = 0

    def tearDown(self):
        self.baseline_patch.stop();self.temp.cleanup()

    def command(self, name, args, code=0):
        with patch.object(sys,'argv',['adopter',name,*map(str,args)]),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            try:adopter.main();actual=0
            except SystemExit as e:actual=e.code
        self.assertEqual(actual,code)

    def inventory(self, remove=False, code=0):
        self.count+=1
        inventory=self.root/f'inventory-{self.count}.json';review=self.root/f'review-{self.count}.diff'
        args=[self.candidate,self.workspace,self.archive,inventory,review]+(['--remove'] if remove else [])
        self.command('portal-inventory',args,code)
        return inventory

    def apply(self, inventory, remove=False, code=0, backup=None):
        backup=backup or self.root/f'backup-{self.count}'
        self.command('portal-remove' if remove else 'portal-apply',[self.candidate,self.workspace,self.archive,inventory,backup],code)
        return backup

    def outside(self):return [r for r in full_tree(self.workspace) if not r[0].startswith('PortalExample')]

    def test_additive_noop_remove_foreign_and_recover(self):
        outside=self.outside();before=full_tree(self.workspace);backup=self.apply(self.inventory())
        self.assertEqual(self.outside(),outside)
        for rel in adopter.PORTAL_PATHS:
            self.assertEqual((self.workspace/rel).read_bytes(),(self.candidate/rel).read_bytes())
            self.assertEqual(stat.S_IMODE((self.workspace/rel).stat().st_mode),stat.S_IMODE((self.candidate/rel).stat().st_mode))
        noop=self.apply(self.inventory());self.assertFalse(noop.exists())
        (self.workspace/'PortalExample/foreign.txt').write_bytes(b'user-owned-foreign\n')
        adopted=full_tree(self.workspace);removed=self.apply(self.inventory(remove=True),remove=True)
        self.assertEqual((self.workspace/'PortalExample/foreign.txt').read_bytes(),b'user-owned-foreign\n')
        self.assertEqual(self.outside(),outside)
        self.command('portal-recover',[self.workspace,removed]);self.assertEqual(full_tree(self.workspace),adopted)
        (self.workspace/'PortalExample/foreign.txt').unlink()
        self.command('portal-recover',[self.workspace,backup]);self.assertEqual(full_tree(self.workspace),before)

    def test_fresh_owned_candidate_receiver_removal(self):
        shutil.copytree(self.candidate/'PortalExample',self.workspace/'PortalExample')
        backup=self.apply(self.inventory(remove=True),remove=True)
        self.assertFalse((self.workspace/'PortalExample/Program.fs').exists())
        self.command('portal-recover',[self.workspace,backup])
        self.assertEqual((self.workspace/'PortalExample/Program.fs').read_bytes(),(self.candidate/'PortalExample/Program.fs').read_bytes())

    def test_unowned_matching_destination_refuses_before_write(self):
        (self.workspace/'PortalExample').mkdir()
        shutil.copy2(self.candidate/'PortalExample/Program.fs',self.workspace/'PortalExample/Program.fs')
        before=full_tree(self.workspace);self.inventory(code=3);self.assertEqual(full_tree(self.workspace),before)

    def test_owned_edit_refuses_apply_and_remove(self):
        self.apply(self.inventory());(self.workspace/'PortalExample/Program.fs').write_text('authored changed file')
        before=full_tree(self.workspace);self.inventory(code=3);self.inventory(remove=True,code=3);self.assertEqual(full_tree(self.workspace),before)

    def test_stale_receiver_candidate_mode_and_review(self):
        for change in ['receiver','candidate-mode','review']:
            with self.subTest(change=change):
                inventory=self.inventory();data=json.loads(inventory.read_text())
                if change=='receiver':(self.workspace/'authored/level.json').write_bytes(b'new authored edit\n')
                elif change=='candidate-mode':(self.candidate/'PortalExample/README.md').chmod(0o600)
                else:Path(data['reviewDiff']).write_text('tampered diff')
                before=full_tree(self.workspace);backup=self.apply(inventory,code=3);self.assertFalse(backup.exists());self.assertEqual(full_tree(self.workspace),before)
                if change=='candidate-mode':(self.candidate/'PortalExample/README.md').chmod(0o644)

    def test_parent_and_candidate_symlinks_refuse(self):
        (self.workspace/'PortalExample').symlink_to(self.candidate/'PortalExample',target_is_directory=True)
        before=full_tree(self.workspace);self.inventory(code=2);self.assertEqual(full_tree(self.workspace),before)
        (self.workspace/'PortalExample').unlink();path=self.candidate/'PortalExample/Program.fs';raw=path.read_bytes();path.unlink();(self.root/'foreign.fs').write_bytes(raw);path.symlink_to(self.root/'foreign.fs')
        self.inventory(code=2)

    def test_forged_canonical_provenance_and_helper_refuse(self):
        path=self.candidate/'PortalExample/source-provenance.json';original=path.read_bytes();manifest=json.loads(original)
        manifest['canonicalFiles'][0]['producerPath']='foreign.fs';path.write_text(json.dumps(manifest));self.inventory(code=2);path.write_bytes(original)
        helper=self.candidate/'PortalExample/manage.py';helper.write_text('foreign helper');self.inventory(code=2)

    def test_wrong_receiver_refuses_inventory_apply_and_recovery(self):
        inventory=self.inventory();backup=self.apply(inventory);other=self.root/'other';shutil.copytree(self.workspace,other);before=full_tree(other)
        self.command('portal-recover',[other,backup],2);self.assertEqual(full_tree(other),before)
        self.command('portal-apply',[self.candidate,other,self.archive,inventory,self.root/'wrong-backup'],3);self.assertEqual(full_tree(other),before)

    def test_apply_interruption_rolls_back_early_and_late(self):
        for index in ['1','8']:
            before=full_tree(self.workspace)
            with patch.dict(os.environ,FSGG_PORTAL_FAIL_AFTER=index):backup=self.apply(self.inventory(),code=2)
            self.assertEqual(full_tree(self.workspace),before);self.assertEqual(json.loads((backup/'journal.json').read_text())['status'],'rolled-back')

    def test_recovery_interruption_resumes_verified_states(self):
        before=full_tree(self.workspace);backup=self.apply(self.inventory())
        with patch.dict(os.environ,FSGG_PORTAL_RECOVER_FAIL_AFTER='2'):
            with self.assertRaises(RuntimeError):self.command('portal-recover',[self.workspace,backup])
        self.assertEqual(json.loads((backup/'journal.json').read_text())['status'],'rolling-back')
        self.command('portal-recover',[self.workspace,backup]);self.assertEqual(full_tree(self.workspace),before)

    def test_late_conflict_preserves_foreign_edit_and_reports_unknown(self):
        inventory=self.inventory();original=adopter.write_json_durable;late=self.workspace/'PortalExample/verify-package-boundary.py'
        def conflict(path,value):
            original(path,value)
            if value.get('status')=='prepared':late.parent.mkdir(exist_ok=True);late.write_bytes(b'foreign concurrent edit\n')
        with patch.object(adopter,'write_json_durable',side_effect=conflict):backup=self.apply(inventory,code=3)
        self.assertEqual(late.read_bytes(),b'foreign concurrent edit\n')
        self.assertFalse((self.workspace/'PortalExample/Consumer.fsproj').exists())
        self.assertEqual(json.loads((backup/'journal.json').read_text())['status'],'prepared')
        late.unlink();self.command('portal-recover',[self.workspace,backup]);self.assertFalse(late.parent.exists())

    def test_conflict_after_first_write_preserves_edit_and_journal(self):
        inventory=self.inventory();original=adopter.os.replace;late=self.workspace/'PortalExample/verify-package-boundary.py'
        def conflict(source,destination):
            original(source,destination)
            if Path(destination)==self.workspace/'PortalExample/Consumer.fsproj':late.write_bytes(b'foreign during apply\n')
        with patch.object(adopter.os,'replace',side_effect=conflict):backup=self.apply(inventory,code=3)
        self.assertEqual(late.read_bytes(),b'foreign during apply\n')
        self.assertTrue((self.workspace/'PortalExample/Consumer.fsproj').is_file())
        self.assertEqual(json.loads((backup/'journal.json').read_text())['status'],'applying')
        late.unlink();self.command('portal-recover',[self.workspace,backup]);self.assertFalse(late.parent.exists())

    def test_corrupt_late_staged_object_refuses_before_any_write(self):
        inventory=self.inventory();before=full_tree(self.workspace);original=adopter.write_json_durable
        def corrupt(path,value):
            original(path,value)
            if value.get('status')=='prepared':(path.parent/'staged/PortalExample/verify-package-boundary.py').write_bytes(b'corrupt late staging')
        with patch.object(adopter,'write_json_durable',side_effect=corrupt):backup=self.apply(inventory,code=2)
        self.assertEqual(full_tree(self.workspace),before)
        self.assertEqual(json.loads((backup/'journal.json').read_text())['status'],'rolled-back')

    def test_corrupt_late_backup_refuses_before_restore_write(self):
        self.apply(self.inventory());backup=self.apply(self.inventory(remove=True),remove=True);before=full_tree(self.workspace)
        path=backup/'files/PortalExample/verify-package-boundary.py';path.write_bytes(b'corrupt late backup')
        self.command('portal-recover',[self.workspace,backup],2);self.assertEqual(full_tree(self.workspace),before)

    def test_escaping_and_duplicate_journal_paths_refuse(self):
        backup=self.apply(self.inventory());path=backup/'journal.json';original=path.read_bytes();before=full_tree(self.workspace)
        for logical in ['../foreign','PortalExample/Consumer.fsproj']:
            journal=json.loads(original);journal['paths'][-1]['logical']=logical;journal['paths'][-1]['destination']=logical;path.write_text(json.dumps(journal))
            self.command('portal-recover',[self.workspace,backup],2);self.assertEqual(full_tree(self.workspace),before)

    def test_authentic_archive_predicate_rejects_synthetic_bytes(self):
        self.baseline_patch.stop()
        with self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):adopter.portal_baseline(self.archive,self.workspace)
        self.baseline_patch.start()

    def test_candidate_inside_receiver_and_inventory_inside_receiver_refuse(self):
        self.command('portal-inventory',[self.candidate,self.workspace,self.archive,self.workspace/'inventory.json',self.root/'review.diff'],2)
        nested=self.workspace/'candidate';shutil.copytree(self.candidate,nested)
        self.command('portal-inventory',[nested,self.workspace,self.archive,self.root/'outside.json',self.root/'review.diff'],2)


class SvgRegression(unittest.TestCase):
    """Exercise unchanged SVG classifier/dispatcher and shared journal on synthetic trees."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='svg-synthetic-');self.root=Path(self.temp.name)
        self.candidate=self.root/'candidate';self.workspace=self.root/'workspace'
        for folder,name in [(self.candidate,'New'),(self.workspace,'Old')]:
            (folder/'Domain').mkdir(parents=True);(folder/(name+'.slnx')).write_text('<Solution/>\n');(folder/'Domain/Room.fs').write_text('namespace '+name+'.Domain\nlet value = 1\n')
        self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps({'schema':'fsgg.svg-complete-adoption-manifest/v1','managedPaths':['Domain/Room.fs','FableGameWorkspace.slnx'],'retiredPaths':[],'baselineDigests':{},'baselineSkillManifestRowDigests':{'fable-test':['a'*64]},'sourceCandidates':[{'version':'0.14.0','sourceHead':'b'*40,'nativeArchiveSha256':'c'*64}]}))
        self.inventory=self.root/'inventory.json';self.diff=self.root/'review.diff';self.backup=self.root/'backup'
    def tearDown(self):self.temp.cleanup()
    def command(self,name,args):
        with patch.object(sys,'argv',['adopter',name,*map(str,args)]),contextlib.redirect_stdout(io.StringIO()):adopter.main()
    def test_dispatch_apply_recover_no_svg_semantic_change(self):
        before=full_tree(self.workspace);self.command('complete-inventory',[self.candidate,self.workspace,self.manifest,self.inventory,self.diff]);self.command('complete-apply',[self.candidate,self.workspace,self.manifest,self.inventory,self.backup]);self.command('complete-recover',[self.workspace,self.backup]);self.assertEqual(full_tree(self.workspace),before)
    def test_svg_interruption_and_stale_inventory(self):
        before=full_tree(self.workspace);self.command('complete-inventory',[self.candidate,self.workspace,self.manifest,self.inventory,self.diff])
        with patch.dict(os.environ,FSGG_SVG_COMPLETE_FAIL_AFTER='1'),self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):self.command('complete-apply',[self.candidate,self.workspace,self.manifest,self.inventory,self.backup])
        self.assertEqual(full_tree(self.workspace),before)
        (self.workspace/'Domain/Room.fs').chmod(0o600)
        with self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):self.command('complete-apply',[self.candidate,self.workspace,self.manifest,self.inventory,self.root/'stale-backup'])
        self.assertFalse((self.root/'stale-backup').exists())
    def test_svg_corrupt_late_object_refuses_before_write(self):
        self.command('complete-inventory',[self.candidate,self.workspace,self.manifest,self.inventory,self.diff]);self.command('complete-apply',[self.candidate,self.workspace,self.manifest,self.inventory,self.backup]);before=full_tree(self.workspace);(self.backup/'files/FableGameWorkspace.slnx').write_bytes(b'corrupt')
        with self.assertRaises(SystemExit),contextlib.redirect_stderr(io.StringIO()):self.command('complete-recover',[self.workspace,self.backup])
        self.assertEqual(full_tree(self.workspace),before)


if __name__=='__main__':
    print('SYNTHETIC fixtures: public baseline predicate mocked for transaction cases; no public receiver/runtime acceptance.')
    unittest.main()
