"""Inert copied source fixtures; never launch/import product or toolchain code."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
import warnings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("source_contract", HERE / "source_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

class SourceContract(unittest.TestCase):
    def setUp(self):
        self.owned = tempfile.TemporaryDirectory(prefix="polyglot-source-fixture-")
        self.addCleanup(self.owned.cleanup)
        self.root = Path(self.owned.name)
        for path in ["templates/fs-gg-typescript-cli", "templates/fs-gg-javascript-cli", "templates/fs-gg-rust-cli", "templates/fs-gg-go-cli", "template/product-skills", "template/skill-manifest", "template/polyglot-common"]:
            shutil.copytree(ROOT / path, self.root / path)
        shutil.copyfile(ROOT / "FS.GG.Templates.csproj", self.root / "FS.GG.Templates.csproj")
    def edit(self, relative, change):
        path = self.root / relative
        value = json.loads(path.read_text()); change(value); path.write_text(json.dumps(value))
    def test_actual_source_closure(self):
        self.assertEqual(len(contract.validate_source(ROOT)), 14)
    def test_required_go_module_refusal(self):
        self.edit("templates/fs-gg-go-cli/.template.config/template.json", lambda value: value["symbols"]["packageIdentity"].update(isRequired=False))
        with self.assertRaisesRegex(ValueError, "required identity"):
            contract.validate_source(self.root)
    def test_javascript_collapse_refusal(self):
        self.edit("templates/fs-gg-javascript-cli/tsconfig.json", lambda value: value["compilerOptions"].update(checkJs=False))
        with self.assertRaisesRegex(ValueError, "JavaScript"):
            contract.validate_source(self.root)
    def test_missing_compiler_integrity_refusal(self):
        self.edit("templates/fs-gg-typescript-cli/package-lock.json", lambda value: value["packages"]["node_modules/typescript"].update(integrity=""))
        with self.assertRaisesRegex(ValueError, "integrity"):
            contract.validate_source(self.root)
    def test_skill_digest_refusal(self):
        path = self.root / "template/product-skills/node-workspace/SKILL.md"
        path.write_text(path.read_text() + "drift")
        with self.assertRaisesRegex(ValueError, "digest"):
            contract.validate_source(self.root)
    def test_crlf_skill_mutation_refuses_lf_manifest_digest(self):
        path = self.root / "template/product-skills/node-workspace/SKILL.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "digest"):
            contract.validate_source(self.root)
    def test_utf8_bom_preserves_file_readalltext_digest(self):
        path = self.root / "template/product-skills/node-workspace/SKILL.md"
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        self.assertEqual(len(contract.validate_source(self.root)), 14)
    def test_skill_destination_refusal(self):
        path = self.root / "FS.GG.Templates.csproj"
        path.write_text(path.read_text().replace("content/templates/fs-gg-go-cli/.agents/skills/go-testing/", "content/templates/fs-gg-rust-cli/.agents/skills/go-testing/"))
        with self.assertRaisesRegex(ValueError, "destinations"):
            contract.validate_source(self.root)
    def test_reserved_tree_refusal(self):
        (self.root / "templates/fs-gg-go-cli/.fsgg").mkdir()
        with self.assertRaisesRegex(ValueError, "reserved"):
            contract.validate_source(self.root)
    def synthetic_archive(self):
        # An explicit byte-join fixture only: this is NOT an SDK-sealed catalog or package receipt.
        (self.root / "providers").mkdir(exist_ok=True)
        (self.root / "providers/polyglot.catalog.json").write_text('{"syntheticByteJoinOnly":true}')
        archive = self.root / "synthetic.nupkg"
        contract.validate_source(self.root)
        with zipfile.ZipFile(archive, "w") as package:
            for name, data in contract.expected_archive_members(self.root).items():
                package.writestr(name, data)
            package.write(self.root / "providers/polyglot.catalog.json", "content/providers/polyglot.catalog.json")
        return archive
    def test_synthetic_package_byte_join(self):
        observed = contract.validate_archive(self.root, self.synthetic_archive())
        self.assertEqual(observed["providerCount"], 4)
        self.assertIn("no product/catalog runtime", observed["state"])
    def test_projected_shared_helper_byte_drift_refusal(self):
        archive = self.synthetic_archive()
        path = self.root / "template/polyglot-common/security.sh"
        path.write_bytes(path.read_bytes() + b"\n# synthetic changed authored helper\n")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            contract.validate_archive(self.root, archive)
    def test_missing_projected_shared_helper_refusal(self):
        (self.root / "template/polyglot-common/node-build.sh").unlink()
        with self.assertRaisesRegex(ValueError, "projected product source"):
            contract.expected_archive_members(self.root)
    def test_cached_package_member_refusal(self):
        archive = self.synthetic_archive()
        with zipfile.ZipFile(archive, "a") as package:
            package.writestr("content/templates/fs-gg-go-cli/artifacts/credential-sentinel", "public synthetic sentinel")
        with self.assertRaisesRegex(ValueError, "inventory"):
            contract.validate_archive(self.root, archive)
    def test_changed_product_byte_refusal(self):
        archive = self.synthetic_archive()
        path = self.root / "templates/fs-gg-go-cli/main.go"
        path.write_text(path.read_text() + "// changed original input\n")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            contract.validate_archive(self.root, archive)
    def test_duplicate_archive_member_refusal(self):
        archive = self.synthetic_archive()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr("content/providers/polyglot.catalog.json", "synthetic duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            contract.validate_archive(self.root, archive)

    def test_nonregular_source_refusal(self):
        path = self.root / "templates/fs-gg-go-cli/source-fifo"
        os.mkfifo(path, 0o600)
        with self.assertRaisesRegex(ValueError, "non-regular"):
            contract.validate_source(self.root)
    def test_missing_cargo_lock_refusal(self):
        (self.root / "templates/fs-gg-rust-cli/Cargo.lock").unlink()
        with self.assertRaisesRegex(ValueError, "Cargo lock"):
            contract.validate_source(self.root)

if __name__ == "__main__":
    unittest.main()
