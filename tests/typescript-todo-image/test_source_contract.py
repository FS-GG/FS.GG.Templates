import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "eng" / "typescript-todo-image"
FIXTURE = ROOT / "examples" / "language-routes" / "typescript-todo"


class SourceContractTests(unittest.TestCase):
    def test_readonly_adapter_routes_all_mutable_state_to_output(self):
        adapter = (IMAGE / "qualify-readonly.sh").read_text()
        for variable in ("HOME", "XDG_CACHE_HOME", "TMPDIR", "TYPESCRIPT_TODO_DIST_DIR", "TYPESCRIPT_TODO_REPORT_DIR"):
            self.assertIn(f"export {variable}=", adapter)
        self.assertIn("test ! -w \"$source_root\"", adapter)
        self.assertIn("--test", adapter)
        self.assertIn("browser.spec.mjs", adapter)
        self.assertIn("umask 077", adapter)

    def test_rootless_operation_maps_fixed_container_user_to_calling_host_user(self):
        qualifier = (IMAGE / "qualify.py").read_text()
        self.assertIn('"--userns=keep-id:uid=32768,gid=32768"', qualifier)
        self.assertIn('"--user=32768:32768"', qualifier)
        self.assertNotIn('["unshare", "chown"', qualifier)
        self.assertIn("validate_host_evidence(output)", qualifier)

    def test_fixture_and_image_describe_the_same_exact_toolchain(self):
        fixture = json.loads((FIXTURE / "toolchain-lock.json").read_text())
        image = json.loads((IMAGE / "inputs.json").read_text())
        self.assertEqual((fixture["node"], fixture["typescript"], fixture["playwright"]), (image["node"]["version"], image["typescript"], image["playwright"]))
        self.assertEqual(fixture["qualificationImage"]["base"], image["base"]["reference"])
        self.assertEqual(fixture["qualificationImage"]["status"], "source-preparation")

    def test_browser_assets_have_sources_hashes_and_retained_license_identity(self):
        image = json.loads((IMAGE / "inputs.json").read_text())
        for asset in image["browserAssets"]:
            self.assertTrue(asset["url"].startswith("https://"))
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
        shell = next(asset for asset in image["browserAssets"] if asset["name"] == "chromium-headless-shell")
        self.assertRegex(shell["licenseSha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
