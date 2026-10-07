"""Cheap real-descriptor inventory and controls; this is not installed qualification."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receiver import ROOT, call, inventory


class InventoryTests(unittest.TestCase):
    def test_owned_successor_pins_preserve_external_identity_and_defaults(self):
        rows = {r["provider"]: r for r in inventory()}
        for name in ("console", "web", "fable-bindings", "python", "fable-game"):
            self.assertEqual(rows[name]["source"], "FS.GG.Workspace.Template::0.18.1")
            descriptor = (ROOT / rows[name]["descriptor"]).read_text()
            self.assertIn('minimumFsggSdd:\n      version: "2.1.0"', descriptor)
        for row in rows.values():
            self.assertIn('contractVersion: "2.0.0"', (ROOT / row["descriptor"]).read_text())
        self.assertEqual(rows["rendering"]["source"], "FS.GG.UI.Template::0.32.1")
        self.assertEqual([r["provider"] for r in rows.values() if r["external"]], ["rendering"])

    def mutate(self, relative, transform):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ("providers", "templates", "pack"):
                shutil.copytree(ROOT / folder, root / folder)
            path = root / relative
            path.write_text(transform(path.read_text()))
            with self.assertRaises(ValueError):
                inventory(root)

    def test_changed_effective_default_refuses(self):
        self.mutate("providers/fable-game.providers.yml", lambda x: x.replace("default: typed-sdd", "default: sdd"))

    def test_removed_typed_choice_refuses(self):
        def change(text):
            value = json.loads(text)
            value["symbols"]["lifecycle"]["choices"] = [x for x in value["symbols"]["lifecycle"]["choices"] if x["choice"] != "typed-sdd"]
            return json.dumps(value)
        self.mutate("templates/fs-gg-console/.template.config/template.json", change)

    def test_missing_owned_template_refuses(self):
        self.mutate("providers/python.providers.yml", lambda x: x.replace("templateId: fs-gg-python", "templateId: missing"))

    def test_raw_legacy_default_is_separate(self):
        self.mutate("pack/fs-gg-fable-game-legacy/.template.config/template.json", lambda x: x.replace('"defaultValue": "sdd"', '"defaultValue": "typed-sdd"'))

    def test_new_uninventoried_family_refuses(self):
        self.mutate("providers/web.providers.yml", lambda x: x.replace("name: web", "name: other"))

    def test_old_cli_cannot_pass_as_capability(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            stub = Path(temp) / "old.py"
            stub.write_text('import sys\nprint("2.0.2" if "--version" in sys.argv else "unknown command")\nsys.exit(0 if "--version" in sys.argv else 1)\n')
            command = [sys.executable, str(stub)]
            self.assertEqual(subprocess.run(command + ["--version"], capture_output=True, text=True).stdout.strip(), "2.0.2")
            call(command, "knowledge", "search", expect_success=False)
            with self.assertRaises(AssertionError):
                call(command, "knowledge", "search")

    def test_insufficient_cli_refusal_is_explicit(self):
        result = call([sys.executable, "-c", "import sys; sys.exit(1)"], "knowledge", "search", expect_success=False)
        self.assertEqual(result.returncode, 1)
        with self.assertRaises(AssertionError):
            call([sys.executable, "-c", "import sys; sys.exit(1)"], "knowledge", "search")

    def test_fixture_covers_concise_findings_and_excluded_inputs(self):
        fixture = json.loads((Path(__file__).parent / "findings.json").read_text())
        self.assertEqual({x["kind"] for x in fixture["findings"]}, {"decision", "diagnostic", "experiment", "bug-fix"})
        for finding in fixture["findings"]:
            self.assertTrue((ROOT / finding["evidence"]["path"]).is_file())
            self.assertLess(len(finding["finding"].encode()), 1024)
            self.assertEqual(finding["state"], "accepted" if finding["kind"] == "decision" else "observed")
        self.assertEqual({x["kind"] for x in fixture["excludedInputs"]}, {"source-code", "raw-log", "document-dump"})

    def test_broader_ignore_rule_can_hide_canonical_initial_files(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".fsgg/knowledge").mkdir(parents=True)
            (root / ".fsgg/knowledge/finding.json").write_text("{}")
            (root / ".gitignore").write_text(".fsgg/\n")
            check = subprocess.run(["git", "-C", str(root), "check-ignore", ".fsgg/knowledge/finding.json"], capture_output=True)
            self.assertEqual(check.returncode, 0)


if __name__ == "__main__":
    unittest.main()
