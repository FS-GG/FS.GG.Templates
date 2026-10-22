"""Historical archive/source custody and actual source-wrapper refusal controls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
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
            setup = 'set -euo pipefail\nout="$1"\ntemplate="$out/archive.nupkg"\ntemplate_version=0.18.0\nrendering_version=0.32.1\ninstalled_sdd_version=2.1.0\nbrowser_evidence_sha=fixture\n'
            result = subprocess.run(["bash", "-c", setup + receipt_command, "fixture", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((out / "qualification.json").read_text())
            self.assertEqual(receipt["routes"]["sdd21"]["version"], "2.1.0")
            self.assertNotIn("sdd17", receipt["routes"])
            self.assertEqual(receipt["publicProducers"]["rendering"], "0.32.1")
            self.assertEqual(receipt["apiMirror"]["historicalRenderingVersion"], "0.31.0")
            self.assertFalse(receipt["publication"])


class HistoricalAuthoringObserverTests(unittest.TestCase):
    def subject(self):
        # Independent fixture: actual immutable identities declared by the public
        # qualification route, not a current-source metadata tuple relabelled old.
        return {
            "templateVersion": "0.13.0",
            "templateSource": "6acdfc5f5da41156db0aeaffcd54885b3b9e66be",
            "templateArchiveSha256": "ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c",
            "descriptorSha256": "e3f3aa1c77af9f9e559c376ffe1ad8131e205c0d68d81b4556f617b796636309",
            "renderingVersion": "0.31.0", "receiverRenderingVersion": "0.31.0",
            "renderingReferenceSha256": "98ba3cf0a2a1db103ca7ac1711017062bf2c3697d59a0880e376c3629c5953b6",
            "observerSha256": "3c2849f82203f136f73decfae230e2ab9aa06949c7d410307bf910e054298637",
        }

    def test_exact_receipt_selects_the_frozen_historical_contract_only(self):
        selected = provider.authoring_contract(self.subject())
        self.assertEqual(selected, "svg-authoring-observe-v013.mjs")
        raw = (HERE / selected).read_bytes()
        self.assertEqual(provider.sha(raw), self.subject()["observerSha256"])
        self.assertIn(b'fontReadyOrMountedAcceptance:false', raw)
        self.assertNotIn(b'verified Noto text was not mounted exactly once', raw)

    def test_current_mixed_missing_or_extra_identity_cannot_select_old_contract(self):
        values = {"templateVersion": "0.19.0", "templateSource": "8952e1c5753b0abc972154c7596ddc8da772b271",
                  "templateArchiveSha256": "80d537aacb99419c9a6b7b86a003b41fab75e0077331d0e242c1a5ec1cf4e3fd",
                  "descriptorSha256": "0" * 64, "renderingVersion": "0.32.1", "receiverRenderingVersion": "0.32.1",
                  "renderingReferenceSha256": "0" * 64,
                  "observerSha256": provider.sha((HERE / "svg-authoring-observe.mjs").read_bytes())}
        for key, value in values.items():
            subject = self.subject(); subject[key] = value
            with self.subTest(axis=key), self.assertRaises(ValueError):
                provider.authoring_contract(subject)
        for change in (lambda x: x.pop("templateSource"), lambda x: x.update(extra="unknown")):
            subject = self.subject(); change(subject)
            with self.assertRaises(ValueError): provider.authoring_contract(subject)

    def fixture(self, directory):
        receiver = directory / "receiver"; project = receiver / "SvgFoundation/Studio/Studio.fsproj"
        project.parent.mkdir(parents=True)
        project.write_text('<Project><PropertyGroup><FsGgSvgAuthoringVersion>0.31.0</FsGgSvgAuthoringVersion></PropertyGroup></Project>')
        archive, descriptor, reference = [directory / name for name in ("archive", "descriptor", "reference")]
        archive.write_bytes(b"inert archive"); descriptor.write_bytes(b"inert descriptor"); reference.write_bytes(b"inert reference")
        t = self.subject()
        args = (archive, t["templateVersion"], t["templateSource"], t["templateArchiveSha256"], t["descriptorSha256"],
                descriptor, t["renderingVersion"], reference, receiver, directory / "observer.mjs")
        return args, project

    def test_actual_wrong_archive_bytes_refuse_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            args, _ = self.fixture(Path(folder))
            with self.assertRaisesRegex(ValueError, "declared hashes"):
                provider.bind_authoring_observer(*args)
            self.assertFalse(args[-1].exists())

    def test_binding_copies_verified_bytes_and_refuses_wrong_receiver_or_existing_output(self):
        # Explicit inert hash port for three custody inputs. The frozen observer
        # itself still uses its real digest; no network or credentials are used.
        with tempfile.TemporaryDirectory() as folder:
            args, project = self.fixture(Path(folder)); t = self.subject(); real_sha = provider.sha
            identities = {b"inert archive": t["templateArchiveSha256"], b"inert descriptor": t["descriptorSha256"],
                          b"inert reference": t["renderingReferenceSha256"]}
            def custody_hash(raw): return identities[raw] if raw in identities else real_sha(raw)
            with patch.object(provider, "sha", custody_hash):
                project.write_text(project.read_text().replace("0.31.0", "0.32.1"))
                with self.assertRaises(ValueError): provider.bind_authoring_observer(*args)
                self.assertFalse(args[-1].exists())
                project.write_text(project.read_text().replace("0.32.1", "0.31.0"))
                provider.bind_authoring_observer(*args)
                self.assertEqual(args[-1].read_bytes(), (HERE / "svg-authoring-observe-v013.mjs").read_bytes())
                args[-1].write_bytes(b"authored bytes")
                with self.assertRaisesRegex(ValueError, "new exact"):
                    provider.bind_authoring_observer(*args)
                self.assertEqual(args[-1].read_bytes(), b"authored bytes")

    def test_real_source_copy_and_dispatch_still_selects_strict_observer(self):
        source = (HERE / "verify-svg-preview-c-source.sh").read_text()
        copy = next(line for line in source.splitlines() if line.startswith("cp ") and "/svg-authoring-observe.mjs" in line)
        invoke = next(line.strip() for line in source.splitlines() if "node svg-authoring-observe.mjs " in line)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder); target = out / "direct/Browser.Tests"; target.mkdir(parents=True)
            bin = out / "inert-bin"; bin.mkdir(); node = bin / "node"
            node.write_text('#!/usr/bin/python3\nimport hashlib,json,pathlib,sys\np=pathlib.Path(sys.argv[1]);raw=p.read_bytes()\nrequired=[b"verified Noto text was not mounted exactly once",b"document.fonts.load",b"fontProof.painted"]\nif not all(x in raw for x in required):raise SystemExit(4)\nprint(json.dumps({"dispatchOnly":"strict-current", "sha256":hashlib.sha256(raw).hexdigest()}))\n')
            node.chmod(0o755)
            env = {"PATH": str(bin) + ":/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            setup = 'set -euo pipefail\nroot="$1"\nout="$2"\nfamily=chromium\n'
            args = ["/bin/bash", "-c", setup + copy + "\n" + invoke, "inert-source-dispatch", str(ROOT), str(out)]
            result = subprocess.run(args, env=env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, "closed source dispatch failed")
            self.assertEqual((target / "svg-authoring-observe.mjs").read_bytes(), (HERE / "svg-authoring-observe.mjs").read_bytes())
            observed = json.loads((out / "chromium-authoring.json").read_text())
            self.assertEqual(observed["dispatchOnly"], "strict-current")
            (target / "svg-authoring-observe.mjs").write_bytes((HERE / "svg-authoring-observe-v013.mjs").read_bytes())
            negative = subprocess.run(["/bin/bash", "-c", setup + invoke, "inert-source-dispatch", str(ROOT), str(out)],
                                      env=env, capture_output=True, timeout=5)
            self.assertEqual(negative.returncode, 4, "historical observer reached current strict dispatch")


if __name__ == "__main__":
    unittest.main()
