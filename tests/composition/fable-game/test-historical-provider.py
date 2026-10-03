"""Historical archive/source custody and actual source-wrapper refusal controls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("historical_provider", HERE / "historical-provider.py")
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


class HistoricalProviderTests(unittest.TestCase):
    def subject(self, directory, package_id="FS.GG.Workspace.Template", version="0.13.0", revision="a" * 40):
        archive = directory / "subject.nupkg"
        with ZipFile(archive, "w") as package:
            package.writestr("subject.nuspec", f'<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"><metadata><id>{package_id}</id><version>{version}</version><repository type="git" commit="{revision}"/></metadata></package>')
        return archive

    def test_exact_join_uses_immutable_source_and_preserves_descriptor_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = self.subject(root)
            descriptor = b"historical owner bytes\n"
            urls = []
            def download(url):
                urls.append(url)
                return descriptor
            output = root / "provider.yml"
            provider.acquire(archive, "0.13.0", "a" * 40, provider.sha(archive.read_bytes()), provider.sha(descriptor), output, download)
            self.assertEqual(output.read_bytes(), descriptor)
            self.assertEqual(urls, ["https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/" + "a" * 40 + "/providers/fable-game.providers.yml"])

    def test_archive_identity_source_and_hash_refuse_before_network_or_output(self):
        for changes, archive_sha in [({}, "0" * 64), ({"package_id": "Foreign.Template"}, None),
                                     ({"version": "0.18.0"}, None), ({"revision": "b" * 40}, None)]:
            with self.subTest(changes=changes, archive_sha=archive_sha), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive = self.subject(root, **changes)
                def download(url):
                    self.fail("Rejected archive reached descriptor download")
                with self.assertRaises(ValueError):
                    provider.acquire(archive, "0.13.0", "a" * 40, archive_sha or provider.sha(archive.read_bytes()), "1" * 64, root / "output", download)
                self.assertFalse((root / "output").exists())

    def test_wrong_descriptor_refuses_without_output_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = self.subject(root)
            args = (archive, "0.13.0", "a" * 40, provider.sha(archive.read_bytes()), provider.sha(b"owner"))
            with self.assertRaisesRegex(ValueError, "descriptor hash"):
                provider.acquire(*args, root / "output", lambda url: b"foreign")
            self.assertFalse((root / "output").exists())
            (root / "output").write_bytes(b"authored")
            with self.assertRaisesRegex(ValueError, "existing output"):
                provider.acquire(*args, root / "output", lambda url: self.fail("Existing output reached network"))
            self.assertEqual((root / "output").read_bytes(), b"authored")

    def test_current_source_identity_gate_precedes_effects(self):
        source = (HERE / "verify-svg-preview-c-source.sh").read_text()
        # Execute the real beginning, stopping before its first source preparation effect.
        gate = source[source.index("sdd_version="):source.index("# shellcheck source=")]
        for observed in ("2.1.0", "1.7.0", "2.1.00", "2.1.0\nunexpected"):
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                fake = root / "dotnet"
                fake.write_text('#!/usr/bin/env python3\nimport os,pathlib,sys\na=sys.argv[1:]\nassert a[:3]==["tool","install","FS.GG.SDD.Cli"]\nassert a[a.index("--version")+1]=="2.1.0"\np=pathlib.Path(a[a.index("--tool-path")+1]);p.mkdir(parents=True)\nf=p/"fsgg-sdd";f.write_text("#!/bin/sh\\nprintf \'%s\\\\n\' \'"+os.environ["OBSERVED"]+"\'\\n");f.chmod(0o755)\n')
                fake.chmod(0o755)
                result = subprocess.run(["bash", "-c", 'set -euo pipefail\nout="$1"\n' + gate + '\ntouch "$out/template-effects"', "fixture", str(root / "out")],
                                        env={**os.environ, "PATH": str(root) + ":" + os.environ["PATH"], "OBSERVED": observed}, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, observed == "2.1.0", result.stderr)
                self.assertEqual((root / "out/template-effects").exists(), observed == "2.1.0")

    def test_actual_selectors_emit_report_and_retain_nonzero_status(self):
        for name in ("verify-svg-preview-c-public.sh", "verify-svg-preview-c-source.sh", "verify-svg-typed-receivers.sh"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                out = Path(folder)
                historical = out / "historical.providers.yml"
                historical.write_text((ROOT / "providers/fable-game.providers.yml").read_text() + "\n# exact historical fixture input\n")
                fake = out / "producer"
                fake.write_text('#!/bin/sh\nprintf \'{"outcome":"blocked","diagnostics":[{"id":"actual-refusal"}]}\\n\'\nexit 23\n')
                fake.chmod(0o755)
                source = (HERE / name).read_text()
                function = "scaffold() {" + source.split("scaffold() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
                if "typed-receivers" in name:
                    function = "pin_provider() {" + source.split("pin_provider() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n" + function
                setup = 'set -euo pipefail\nroot="$1"\nout="$2"\nsdd="$out/producer"\ncli="$sdd"\ntemplate="$out/archive.nupkg"\ncurrent_package="$template"\nhistorical_provider="$out/historical.providers.yml"\n'
                invoke = next(line for line in source.splitlines() if line.startswith('scaffold "$out/clean"')) if "typed-receivers" in name else next(line for line in source.splitlines() if line.startswith("scaffold sdd-none none;")).split(";", 1)[0]
                result = subprocess.run(["bash", "-c", setup + function + invoke, "fixture", str(ROOT), str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertIn('"id":"actual-refusal"', result.stderr)
                receiver = out / ("clean" if "typed-receivers" in name else "sdd-none")
                selected = (receiver / ".fsgg/providers.yml").read_text()
                self.assertEqual("# exact historical fixture input" in selected, "source.sh" not in name)

    def test_new_source_receipt_records_observed_cli_without_historical_route_label(self):
        source = (HERE / "verify-svg-preview-c-source.sh").read_text()
        receipt_command = next(line for line in source.splitlines() if line.startswith("jq -n "))
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "archive.nupkg").write_bytes(b"source receipt fixture")
            for family in ("chromium", "firefox", "webkit"):
                (out / (family + "-present.json")).write_text("{}")
            setup = 'set -euo pipefail\nout="$1"\ntemplate="$out/archive.nupkg"\ntemplate_version=0.18.0\ninstalled_sdd_version=2.1.0\nbrowser_evidence_sha=fixture\n'
            result = subprocess.run(["bash", "-c", setup + receipt_command, "fixture", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((out / "qualification.json").read_text())
            self.assertEqual(receipt["routes"]["sdd21"]["version"], "2.1.0")
            self.assertNotIn("sdd17", receipt["routes"])
            self.assertFalse(receipt["publication"])


if __name__ == "__main__":
    unittest.main()
