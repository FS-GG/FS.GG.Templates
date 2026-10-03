#!/usr/bin/env python3
"""Offline checks of the live D.5 identity boundary; no installed-product claim."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "tests/composition/fable-game/verify-svg-release-d5-source.sh").read_text()
VERSION = next(line for line in SOURCE.splitlines() if line.startswith("sdd_version="))
INSTALL = SOURCE.split("dotnet tool install FS.GG.SDD.Cli", 1)[1].split("dotnet new install", 1)[0]
INSTALL = "dotnet tool install FS.GG.SDD.Cli" + INSTALL
RECEIPT = SOURCE.rsplit("python3 - ", 1)[1].split("\necho ", 1)[0]
RECEIPT = "python3 - " + RECEIPT


class CurrentSourceTests(unittest.TestCase):
    def test_exact_installed_identity_before_template_execution(self):
        self.assertEqual(VERSION, "sdd_version=2.1.0")
        for observed in ("2.1.0", "2.0.2", "2.1.01", "2.1.0\nunexpected"):
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as folder:
                out = Path(folder)
                tool = out / "tools/sdd/fsgg-sdd"
                tool.parent.mkdir(parents=True)
                tool.write_text('#!/bin/sh\nprintf "%s\\n" "$D5_FIXTURE_VERSION"\n')
                tool.chmod(0o755)
                script = "\n".join([
                    "set -euo pipefail", 'out="$1"', 'config="$out/NuGet.Config"',
                    VERSION, 'fail() { echo "$*" >&2; exit 1; }',
                    'dotnet() { printf "%s\\n" "$@" >"$out/install-args"; }',
                    INSTALL,
                ])
                env = dict(os.environ, D5_FIXTURE_VERSION=observed)
                run = subprocess.run(["bash", "-c", script, "test", folder],
                                     env=env, capture_output=True, text=True)
                args = (out / "install-args").read_text().splitlines()
                self.assertEqual(args[args.index("--version") + 1], "2.1.0")
                if observed == "2.1.0":
                    self.assertEqual(run.returncode, 0, run.stderr)
                else:
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn("installed SDD version mismatch", run.stderr)

    def test_receipt_uses_observed_identity_and_keeps_source_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            archive = out / "fixture.nupkg"
            archive.write_bytes(b"offline receipt fixture, not a published package")
            script = '\n'.join([
                "set -euo pipefail", 'out="$1"', 'package="$out/fixture.nupkg"',
                "package_version=0.18.0", "installed_sdd_version=2.1.0", RECEIPT,
            ])
            run = subprocess.run(["bash", "-c", script, "test", folder],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            receipt = json.loads((out / "qualification.json").read_text())
            self.assertEqual(receipt["sdd"]["version"], "2.1.0")
            self.assertEqual(receipt["templates"]["candidateSha256"],
                             hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(receipt["status"], "source-candidate-only")
            self.assertEqual(receipt["templates"]["publication"], "pending")
            self.assertTrue(receipt["defaultActivation"].startswith("pending-"))


if __name__ == "__main__":
    unittest.main()
