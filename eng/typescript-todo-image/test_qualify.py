import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import types
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("typescript_todo_qualify", HERE / "qualify.py")
assert SPEC and SPEC.loader
QUALIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFY)


class QualificationSourceTests(unittest.TestCase):
    def test_reviewed_inputs_recipe_and_fixed_entrypoint_are_bound(self):
        inputs = QUALIFY.load_inputs()
        self.assertEqual(inputs["node"]["version"], "24.8.0")
        self.assertEqual(inputs["typescript"], "5.9.2")
        self.assertEqual(inputs["playwright"], "1.63.0")
        self.assertEqual(inputs["browserAssets"][0]["revision"], "1243")
        self.assertEqual(inputs["base"]["reference"], QUALIFY.BASE_REFERENCE)

    def test_operation_is_closed_and_mounts_only_scoped_source_and_output(self):
        args = QUALIFY.operation_create_argv(["podman"], "image@sha256:" + "a" * 64, Path("/private/output"), "fixed-name")
        self.assertEqual(args[-2:], ["--entrypoint=/usr/local/bin/fsgg-typescript-todo-qualify", "image@sha256:" + "a" * 64])
        self.assertIn("--network=none", args)
        self.assertIn("--read-only", args)
        self.assertIn(f"--volume={QUALIFY.ROOT}:/source:ro", args)
        self.assertIn("--volume=/private/output:/output:rw", args)
        self.assertNotIn("/bin/bash", args)

    def test_oci_archive_identity_checks_manifest_and_config_closure(self):
        config = b'{"architecture":"amd64","os":"linux"}'
        config_digest = hashlib.sha256(config).hexdigest()
        manifest = json.dumps({"schemaVersion": 2, "config": {"digest": f"sha256:{config_digest}"}, "layers": []}, separators=(",", ":")).encode()
        manifest_digest = hashlib.sha256(manifest).hexdigest()
        index = json.dumps({"schemaVersion": 2, "manifests": [{"digest": f"sha256:{manifest_digest}"}]}).encode()
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "candidate.tar"
            with tarfile.open(archive_path, "w") as archive:
                for name, value in (("index.json", index), (f"blobs/sha256/{manifest_digest}", manifest), (f"blobs/sha256/{config_digest}", config)):
                    info = tarfile.TarInfo(name); info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            self.assertEqual(QUALIFY.oci_archive_identity(archive_path), {
                "manifestDigest": f"sha256:{manifest_digest}",
                "configDigest": f"sha256:{config_digest}",
            })


if __name__ == "__main__":
    unittest.main()
