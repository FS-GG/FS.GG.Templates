#!/usr/bin/env python3
"""Focused public identity refusal checks; no network or product execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location("pins", Path(__file__).with_name("d5-public-pins.py"))
pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins)


class PublicPinsTests(unittest.TestCase):
    def setUp(self):
        self.good = {"schema": "fsgg.svg-release-d5.public-pins/1", "mode": "templates",
                     "templates": {"version": "0.15.0", "sha256": "a" * 64,
                                   "sourceCommit": "b" * 40, "providerSha256": "c" * 64},
                     "sdd": {"version": "2.0.2", "sha256": "d" * 64, "sourceCommit": "e" * 40}}

    def test_both_modes(self):
        pins.validate(self.good)
        self.good.update(mode="full", wizard={"version": "0.12.0", "sha256": "f" * 64,
                                              "sourceCommit": "a" * 40})
        pins.validate(self.good)

    def test_historical_and_incomplete_pins_refuse(self):
        for key, field, value in [("templates", "version", "0.14.0"),
                                  ("templates", "sha256", "pending"),
                                  ("templates", "sourceCommit", "main"),
                                  ("templates", "providerSha256", ""),
                                  ("sdd", "version", "1.4.0-preview.1")]:
            changed = copy.deepcopy(self.good)
            changed[key][field] = value
            with self.subTest(key=key, field=field), self.assertRaises(ValueError):
                pins.validate(changed)
        self.good["mode"] = "full"
        with self.assertRaises(ValueError):
            pins.validate(self.good)
        self.good["wizard"] = {"version": "0.11.2", "sha256": "f" * 64, "sourceCommit": "a" * 40}
        with self.assertRaises(ValueError):
            pins.validate(self.good)

    def test_nuspec_source_mismatch_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "test.nupkg"
            with ZipFile(archive, "w") as z:
                z.writestr("test.nuspec", '<package><metadata><id>FS.GG.Workspace.Template</id>'
                           '<version>0.15.0</version><repository commit="' + "b" * 40 + '"/></metadata></package>')
                for name, default in [("fs-gg-fable-game", "typed-sdd"), ("fs-gg-fable-game-legacy", "sdd")]:
                    z.writestr(f'content/{name}/.template.config/template.json', json.dumps({"symbols": {
                        "lifecycle": {"defaultValue": default, "choices": [{"choice": lane} for lane in
                            ["none", "sdd", "typed-sdd", "spec-kit"]]}}}))
            pins.archive_identity(archive, "FS.GG.Workspace.Template", self.good["templates"])
            self.good["templates"]["sourceCommit"] = "a" * 40
            with self.assertRaises(ValueError):
                pins.archive_identity(archive, "FS.GG.Workspace.Template", self.good["templates"])

    def test_script_preflight_never_launches_workload(self):
        script = Path(__file__).with_name("verify-svg-release-d5-public-default.sh")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pins.json"
            output = Path(folder) / "unused-output"
            path.write_text(json.dumps(self.good))
            command = ["bash", str(script), str(path), str(output), "--preflight-only"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(output.exists())
            self.good["templates"]["sha256"] = "pending-publication"
            path.write_text(json.dumps(self.good))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exact public archive sha256 required", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
