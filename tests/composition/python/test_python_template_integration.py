import json
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECTOR = ROOT / "eng/portable-workspace/project-python-fixture.py"
MANIFEST = ROOT / "eng/portable-workspace/python-fixture-source.json"


class PythonTemplateIntegrationTests(unittest.TestCase):
    def run_projector(self, checkout, output):
        return subprocess.run(
            [str(PROJECTOR), "--coordination-root", str(checkout), "--manifest", str(MANIFEST), "--output", str(output)],
            text=True,
            capture_output=True,
        )

    def test_refuses_missing_and_unrelated_source_checkouts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = self.run_projector(root / "missing", root / "missing-output")
            self.assertEqual(missing.returncode, 2)

            unrelated = self.run_projector(ROOT, root / "unrelated-output")
            self.assertEqual(unrelated.returncode, 2)
            self.assertIn("fixture-source-git-refused", unrelated.stdout)

    def test_pack_and_workflows_bind_projection_before_costly_composition(self):
        project = (ROOT / "FS.GG.Templates.csproj").read_text()
        composition = (ROOT / ".github/workflows/composition.yml").read_text()
        release = (ROOT / ".github/workflows/release.yml").read_text()
        provider = (ROOT / "providers/python.providers.yml").read_text()
        template = json.loads(
            (ROOT / "templates/fs-gg-python/.template.config/template.json").read_text()
        )

        # These assertions inspect the current source, not the historical 0.16 fixture.
        versions = ET.fromstring(project).findall("./PropertyGroup/Version")
        self.assertEqual(len(versions), 1)
        package_version = versions[0].text
        self.assertRegex(package_version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertIn("obj/$(Configuration)/$(TargetFramework)/portable-python-fixture/", project)
        self.assertIn('BeforeTargets="GenerateNuspec"', project)
        self.assertIn("FSGG_PYTHON_COORDINATION_ROOT must name", project)
        self.assertIn(f"    source: FS.GG.Workspace.Template::{package_version}\n", provider)
        exclusions = set(template["sources"][0]["exclude"])
        self.assertTrue({
            "**/[Bb]in/**",
            "**/[Oo]bj/**",
            "**/.template.config/**",
            "**/*.filelist",
            "**/*.user",
            "**/node_modules/**",
            "**/.nuget/**",
        }.issubset(exclusions))
        self.assertNotIn("**/*.lock.json", exclusions)
        for target in ("python/app.py", "python/build.py", "python/test.py", "python-fixture-source.json"):
            self.assertIn(f"content/templates/fs-gg-python/{target}", project)

        checkout = "ref: b1849256e07d4d5d5e7f901745c4b40a8b8d28f8"
        self.assertEqual(composition.count(checkout), 1)
        self.assertEqual(release.count(checkout), 2)
        self.assertIn("repository: FS-GG/FS.GG.Coordination", composition)
        self.assertEqual(release.count("repository: FS-GG/FS.GG.Coordination"), 2)
        self.assertLess(composition.index("Verify canonical Python fixture source"), composition.index("actions/setup-dotnet@v6"))
        # Occupancy has its own earlier SDK step; projection protects pack and gate.
        for job in ("pack", "gate"):
            match = re.search(rf"(?ms)^  {job}:\n(.*?)(?=^  [a-zA-Z_-]+:|\Z)", release)
            self.assertIsNotNone(match, job)
            steps = match.group(1)
            self.assertLess(steps.index("Verify canonical Python fixture source"), steps.index("actions/setup-dotnet@v6"), job)
        self.assertIn("COMPOSITION_LANES: console web fable-bindings fable-game python", release)


if __name__ == "__main__":
    unittest.main()
