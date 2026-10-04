import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECTOR = ROOT / "eng/portable-workspace/project-python-fixture.py"
SOURCES = {
    "tests/portable-workspace/image/fixture/python/app.py": b'def greeting():\n    return "hello from portable python"\n\nif __name__ == "__main__":\n    print(greeting())\n',
    "tests/portable-workspace/image/fixture/python/build.py": b'print("build fixture")\n',
    "tests/portable-workspace/image/fixture/python/test.py": b'print("test fixture")\n',
}
TARGETS = {source: "python/" + Path(source).name for source in SOURCES}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PythonFixtureProjectionTests(unittest.TestCase):
    def test_default_manifest_is_frozen_to_the_canonical_fixture(self):
        manifest = json.loads((ROOT / "eng/portable-workspace/python-fixture-source.json").read_text())
        self.assertEqual(manifest["schema"], "fsgg.templates.python-fixture-source/1")
        self.assertEqual(manifest["repository"], "FS-GG/FS.GG.Coordination")
        self.assertRegex(manifest["revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(manifest["tree"], r"^[0-9a-f]{40}$")
        self.assertEqual(
            {item["source"]: item["target"] for item in manifest["files"]},
            {
                "tests/portable-workspace/image/fixture/python/app.py": "python/app.py",
                "tests/portable-workspace/image/fixture/python/build.py": "python/build.py",
                "tests/portable-workspace/image/fixture/python/test.py": "python/test.py",
            },
        )
        for item in manifest["files"]:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")

    def test_template_profile_and_provider_keep_the_route_opt_in(self):
        template_root = ROOT / "templates/fs-gg-python"
        template = json.loads((template_root / ".template.config/template.json").read_text())
        profile = json.loads((template_root / "portable-workspace-profile.template.json").read_text())
        provider = (ROOT / "providers/python.providers.yml").read_text()
        self.assertEqual(template["shortName"], "fs-gg-python")
        self.assertEqual(template["symbols"]["lifecycle"]["defaultValue"], "sdd")
        self.assertFalse(any(".fsgg" in path.parts for path in template_root.rglob("*")))
        self.assertEqual(profile["sourceRevision"], "RECEIVER_COMMIT")
        self.assertEqual(profile["qualifiedImage"], "QUALIFIED_IMAGE_REFERENCE")
        self.assertEqual(profile["components"], [{
            "id": "python",
            "language": "python",
            "workingDirectory": "python",
            "toolchain": {"id": "cpython", "version": "3.14.0"},
            "entryPoints": {"build": "python-build", "test": "python-test", "lint": None, "artifact": None},
        }])
        self.assertEqual(profile["productBuild"], "unsupported-product-build")
        self.assertEqual(profile["productTest"], "unsupported-product-test")
        self.assertEqual(profile["productJourney"], "unsupported-product-journey")
        self.assertIn('    contractVersion: "2.0.0"', provider)
        self.assertRegex(provider, r'(?m)^    minimumFsggSdd:\n      version: "2\.1\.0"$')
        self.assertIn("    templateId: fs-gg-python", provider)
        self.assertIn("    nameParameter: productName", provider)
        self.assertEqual(provider.count("      - key:"), 2)
        self.assertNotRegex(provider, r"(?m)^\s*adoption\s*:")

    def repository(self, root):
        for relative, data in SOURCES.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, env=environment, check=True)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
        return revision, tree

    def manifest(self, path, revision, tree, mutate=None):
        value = {
            "schema": "fsgg.templates.python-fixture-source/1",
            "repository": "FS-GG/FS.GG.Coordination",
            "revision": revision,
            "tree": tree,
            "files": [
                {"source": source, "target": TARGETS[source], "sha256": sha(data)}
                for source, data in SOURCES.items()
            ],
        }
        if mutate:
            mutate(value)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def run_projector(self, repository, manifest, output):
        return subprocess.run(
            [str(PROJECTOR), "--coordination-root", str(repository), "--manifest", str(manifest), "--output", str(output)],
            text=True,
            capture_output=True,
        )

    def test_projects_exact_commit_bytes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "coordination"
            repository.mkdir()
            revision, tree = self.repository(repository)
            manifest = root / "source.json"
            self.manifest(manifest, revision, tree)
            output = root / "projected"
            first = self.run_projector(repository, manifest, output)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = self.run_projector(repository, manifest, output)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            for source, data in SOURCES.items():
                self.assertEqual((output / TARGETS[source]).read_bytes(), data)
            receipt = json.loads((output / "python-fixture-source.json").read_text())
            self.assertEqual(receipt["revision"], revision)
            self.assertEqual(receipt["tree"], tree)
            self.assertEqual({item["target"] for item in receipt["files"]}, set(TARGETS.values()))
            self.assertEqual(receipt["projectorSha256"], sha(PROJECTOR.read_bytes()))

    def test_refuses_pending_hashes_changed_output_and_path_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "coordination"
            repository.mkdir()
            revision, tree = self.repository(repository)
            pending = root / "pending.json"
            self.manifest(pending, revision, tree, lambda value: value.__setitem__("revision", None))
            result = self.run_projector(repository, pending, root / "pending-output")
            self.assertEqual(result.returncode, 2)
            self.assertIn("fixture-source-revision-pending-or-invalid", result.stdout)

            manifest = root / "source.json"
            self.manifest(manifest, revision, tree)
            output = root / "projected"
            self.assertEqual(self.run_projector(repository, manifest, output).returncode, 0)
            (output / "python/app.py").write_text("changed\n")
            result = self.run_projector(repository, manifest, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("projection-output-bytes-refused", result.stdout)

            traversal = root / "traversal.json"
            self.manifest(traversal, revision, tree, lambda value: value["files"][0].__setitem__("target", "../app.py"))
            result = self.run_projector(repository, traversal, root / "traversal-output")
            self.assertEqual(result.returncode, 2)
            self.assertIn("fixture-source-path-refused", result.stdout)


if __name__ == "__main__":
    unittest.main()
