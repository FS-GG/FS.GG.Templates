#!/usr/bin/env python3
"""Actual preflight, archive, lifecycle and refusal-preservation controls; no product run."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("current_d5", HERE / "d5-current-public.py")
D5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D5)


class CurrentPublicTests(unittest.TestCase):
    def test_closed_current_tuple_refuses_mixed_or_historical_identities(self):
        D5.validate(copy.deepcopy(D5.PINS))
        for role in ("templates", "sdd", "wizard", "overlay"):
            for key in ("version", "sourceCommit", "sha256"):
                changed = copy.deepcopy(D5.PINS); changed[role][key] = "historical"
                with self.subTest(role=role, key=key), self.assertRaises(ValueError): D5.validate(changed)
        changed = copy.deepcopy(D5.PINS); changed["unexpected"] = True
        with self.assertRaises(ValueError): D5.validate(changed)

    def test_actual_case_caller_keeps_rehearsal_partial_and_full_matrix_complete(self):
        command = ["python3", str(HERE / "d5-current-public.py"), "cases"]
        rehearsal = subprocess.run(command + ["rehearsal"], capture_output=True, text=True, check=True)
        self.assertEqual({tuple(row.split('\t')[1:]) for row in rehearsal.stdout.splitlines()},
                         {("provider", "omitted", "omitted"), ("wizard", "omitted", "omitted")})
        full = subprocess.run(command + ["full"], capture_output=True, text=True, check=True)
        rows = [row.split('\t') for row in full.stdout.splitlines()]
        self.assertEqual(len(rows), 42); self.assertEqual(len({row[0] for row in rows}), 42)
        for route in ("provider", "wizard"):
            for lane in ("none", "sdd", "typed-sdd", "spec-kit"):
                self.assertEqual({row[3] for row in rows if row[1:3] == [route, lane]},
                                 {"player", "studio", "tactical", "arcade", "complete"})
        self.assertNotEqual(subprocess.run(command + ["unknown"], capture_output=True).returncode, 0)

    def test_actual_shell_preflight_never_launches_acquisition_or_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); pins = root / "pins.json"; output = root / "must-not-exist"
            bins = root / "bin"; bins.mkdir(); sentinel = root / "workload-launched"
            for name in ("curl", "dotnet", "git", "npm", "go", "unshare"):
                script = bins / name; script.write_text('#!/bin/sh\necho launched >>"$SENTINEL"\nexit 91\n'); script.chmod(0o700)
            env = {**os.environ, "PATH": str(bins) + os.pathsep + os.environ["PATH"], "SENTINEL": str(sentinel)}
            for raw, succeeds in ((json.dumps(D5.PINS), True),
                                  (json.dumps({**D5.PINS, "wizard": D5.PINS["sdd"]}), False),
                                  ('{"schema":"x","schema":"y"}', False), ('not-json', False)):
                pins.write_text(raw)
                result = subprocess.run(["bash", str(HERE / "verify-svg-release-d5-current-public.sh"), str(pins), str(output), "--preflight-only"], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                self.assertFalse(output.exists()); self.assertFalse(sentinel.exists())

    def test_raw_and_provider_omission_and_complete_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); foundation = root / "SvgFoundation"; foundation.mkdir()
            (foundation / "SvgFoundation.fsproj").write_text("project")
            D5.check_tree(root, "omitted", "omitted", raw=True)
            (root / ".fsgg").mkdir(); (root / ".fsgg/sdd.yml").write_text("typed lifecycle")
            provenance = {"generator": {"id": "FS.GG.SDD.Artifacts", "version": "2.4.0"},
                          "effectiveParameters": [{"key": "lifecycle", "value": "typed-sdd"}]}
            path = root / ".fsgg/scaffold-provenance.json"; path.write_text(json.dumps(provenance))
            D5.check_tree(root, "omitted", "omitted")
            provenance["effectiveParameters"][0]["value"] = "sdd"; path.write_text(json.dumps(provenance))
            with self.assertRaises(ValueError): D5.check_tree(root, "omitted", "omitted")
            with self.assertRaises(ValueError): D5.check_tree(root, "sdd", "complete")

    def test_authority_owner_snapshot_detects_mutation_and_new_owner_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); authority = root / "readiness/d5-default/typed-authority.json"
            authority.parent.mkdir(parents=True); authority.write_text("existing authority")
            (root / "AGENTS.md").write_text("owned guidance")
            original = D5.owner_snapshot(root)
            self.assertEqual(D5.owner_snapshot(root), original)
            (root / "AGENTS.md").write_text("modified")
            self.assertNotEqual(D5.owner_snapshot(root), original)
            (root / "AGENTS.md").write_text("owned guidance")
            (root / ".fsgg").mkdir(); (root / ".fsgg/new-owner.json").write_text("new")
            self.assertNotEqual(D5.owner_snapshot(root), original)

    def test_actual_preserved_caller_refuses_published_wrong_profile_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); authority = root / "readiness/d5-default/typed-authority.json"
            authority.parent.mkdir(parents=True); authority.write_text("existing")
            before = root / "snapshot.json"; before.write_text(json.dumps(D5.owner_snapshot(root)))
            command = ["python3", str(HERE / "d5-current-public.py"), "preserved", str(root), str(before)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            refused = root / "readiness/d5-refused/typed-authority.json"; refused.parent.mkdir(); refused.write_text("bad")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0); self.assertIn("refused authority was published", result.stderr)

    def test_current_authority_requires_producer_profile_and_real_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root / "readiness/d5-default/typed-authority.json"
            path.parent.mkdir(parents=True); model = path.parent / "model.qnt"; model.write_text("actual model bytes")
            authority = {"backend": "quint-specification-v1", "profileIdentity": "fsgg-quint-profile/2",
                         "packageIdentity": "FS.GG.SDD.Artifacts/2.4.0",
                         "artifacts": [{"path": str(model.relative_to(root)), "sha256": hashlib.sha256(model.read_bytes()).hexdigest()}]}
            path.write_text(json.dumps(authority)); D5.check_authority(root)
            for field, bad in (("packageIdentity", "FS.GG.SDD.Artifacts/2.0.2"), ("profileIdentity", "fsgg-quint-profile/1")):
                altered = {**authority, field: bad}; path.write_text(json.dumps(altered))
                with self.subTest(field=field), self.assertRaises(ValueError): D5.check_authority(root)
            path.write_text(json.dumps(authority)); model.write_text("tampered")
            with self.assertRaises(ValueError): D5.check_authority(root)

    def test_archive_uses_maintained_nuspec_and_template_identity_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "fixture.nupkg"
            with ZipFile(archive, "w") as package:
                pin = D5.PINS["templates"]
                package.writestr("fixture.nuspec", '<package><metadata><id>FS.GG.Workspace.Template</id><version>0.19.3</version><repository commit="' + pin["sourceCommit"] + '"/></metadata></package>')
                for name, default in (("fs-gg-fable-game", "typed-sdd"), ("fs-gg-fable-game-legacy", "sdd")):
                    package.writestr(f"content/templates/{name}/.template.config/template.json", json.dumps({"symbols": {
                        "lifecycle": {"defaultValue": default, "choices": [{"choice": x} for x in D5.LIFECYCLES]},
                        "bundle": {"defaultValue": "player", "choices": [{"choice": x} for x in D5.BUNDLES]}}}))
            # This synthetic archive is only a parser control; production CLI first
            # requires the immutable published tuple and cannot admit this fixture.
            pins = copy.deepcopy(D5.PINS); pins["templates"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            D5.archive_identity(archive, "templates", pins)
            pins["templates"]["sourceCommit"] = "a" * 40
            with self.assertRaises(ValueError): D5.archive_identity(archive, "templates", pins)


if __name__ == "__main__": unittest.main()
