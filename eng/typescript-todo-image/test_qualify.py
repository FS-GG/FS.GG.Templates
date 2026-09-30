import hashlib
import importlib.util
import io
import json
import os
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
        self.assertIn("--userns=keep-id:uid=32768,gid=32768", args)
        self.assertIn("--user=32768:32768", args)
        self.assertIn(f"--volume={QUALIFY.ROOT}:/source:ro", args)
        self.assertIn("--volume=/private/output:/output:rw", args)
        self.assertNotIn("/bin/bash", args)

    def test_host_evidence_requires_private_calling_user_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            reports = output / "reports"
            reports.mkdir(parents=True, mode=0o700)
            output.chmod(0o700); reports.chmod(0o700)
            result = output / "result.json"; result.write_text("{}\n"); result.chmod(0o600)
            report = reports / "results.json"; report.write_text("{}\n"); report.chmod(0o600)
            QUALIFY.validate_host_evidence(output)
            report.chmod(0o640)
            with self.assertRaisesRegex(RuntimeError, "mode mismatch"):
                QUALIFY.validate_host_evidence(output)
            report.chmod(0o600)
            with self.assertRaisesRegex(RuntimeError, "ownership mismatch"):
                QUALIFY.validate_host_evidence(output, host_uid=0 if os.getuid() != 0 else 1)

    def test_oci_archive_identity_checks_manifest_and_config_closure(self):
        config = b'{"architecture":"amd64","os":"linux"}'
        config_digest = hashlib.sha256(config).hexdigest()
        layer = b"qualified layer bytes"
        layer_digest = hashlib.sha256(layer).hexdigest()
        manifest = json.dumps({
            "schemaVersion": 2,
            "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": f"sha256:{config_digest}", "size": len(config)},
            "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": f"sha256:{layer_digest}", "size": len(layer)}],
        }, separators=(",", ":")).encode()
        manifest_digest = hashlib.sha256(manifest).hexdigest()
        index = json.dumps({"schemaVersion": 2, "manifests": [{
            "mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": f"sha256:{manifest_digest}", "size": len(manifest),
            "platform": {"architecture": "amd64", "os": "linux"},
        }]}).encode()
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "candidate.tar"
            with tarfile.open(archive_path, "w") as archive:
                for name, value in (("oci-layout", b'{"imageLayoutVersion":"1.0.0"}'), ("index.json", index), (f"blobs/sha256/{manifest_digest}", manifest), (f"blobs/sha256/{config_digest}", config), (f"blobs/sha256/{layer_digest}", layer)):
                    info = tarfile.TarInfo(name); info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            self.assertEqual(QUALIFY.oci_archive_identity(archive_path), {
                "manifestDigest": f"sha256:{manifest_digest}",
                "configDigest": f"sha256:{config_digest}",
                "layerDigests": [f"sha256:{layer_digest}"],
            })

    def test_oci_archive_identity_refuses_a_missing_referenced_layer(self):
        config = b'{"architecture":"amd64","os":"linux"}'
        config_digest = hashlib.sha256(config).hexdigest()
        missing_layer = hashlib.sha256(b"missing").hexdigest()
        manifest = json.dumps({"schemaVersion": 2, "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": f"sha256:{config_digest}", "size": len(config)}, "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": f"sha256:{missing_layer}", "size": 7}]}).encode()
        manifest_digest = hashlib.sha256(manifest).hexdigest()
        index = json.dumps({"schemaVersion": 2, "manifests": [{"mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": f"sha256:{manifest_digest}", "size": len(manifest), "platform": {"architecture": "amd64", "os": "linux"}}]}).encode()
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "candidate.tar"
            with tarfile.open(archive_path, "w") as archive:
                for name, value in (("oci-layout", b'{"imageLayoutVersion":"1.0.0"}'), ("index.json", index), (f"blobs/sha256/{manifest_digest}", manifest), (f"blobs/sha256/{config_digest}", config)):
                    info = tarfile.TarInfo(name); info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            with self.assertRaisesRegex(RuntimeError, "lacks layer 0 blob"):
                QUALIFY.oci_archive_identity(archive_path)

    def test_oci_descriptor_refuses_declared_size_and_content_digest_mismatch(self):
        value = b"blob bytes"
        digest = hashlib.sha256(value).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "blobs.tar"
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo(f"blobs/sha256/{digest}"); info.size = len(value)
                archive.addfile(info, io.BytesIO(value))
            with tarfile.open(archive_path, "r") as archive:
                with self.assertRaisesRegex(RuntimeError, "size does not match"):
                    QUALIFY.oci_descriptor_blob(archive, QUALIFY.oci_archive_members(archive), {"mediaType": "test/blob", "digest": f"sha256:{digest}", "size": len(value) + 1}, "test")
            wrong_digest = hashlib.sha256(b"different").hexdigest()
            wrong_path = Path(temporary) / "wrong.tar"
            with tarfile.open(wrong_path, "w") as archive:
                info = tarfile.TarInfo(f"blobs/sha256/{wrong_digest}"); info.size = len(value)
                archive.addfile(info, io.BytesIO(value))
            with tarfile.open(wrong_path, "r") as archive:
                with self.assertRaisesRegex(RuntimeError, "content does not match"):
                    QUALIFY.oci_descriptor_blob(archive, QUALIFY.oci_archive_members(archive), {"mediaType": "test/blob", "digest": f"sha256:{wrong_digest}", "size": len(value)}, "test")

    def test_changed_manifest_with_same_config_cannot_bind_to_local_image(self):
        oci = {"manifestDigest": "sha256:" + "a" * 64, "configDigest": "sha256:" + "b" * 64}
        QUALIFY.require_archive_image_binding(oci, {"Digest": oci["manifestDigest"], "Id": oci["configDigest"]})
        with self.assertRaisesRegex(RuntimeError, "manifest digest"):
            QUALIFY.require_archive_image_binding(oci, {"Digest": "sha256:" + "c" * 64, "Id": oci["configDigest"]})
        with self.assertRaisesRegex(RuntimeError, "config digest"):
            QUALIFY.require_archive_image_binding(oci, {"Digest": oci["manifestDigest"], "Id": "sha256:" + "c" * 64})

    def test_oci_archive_refuses_ambiguous_duplicate_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "ambiguous.tar"
            with tarfile.open(archive_path, "w") as archive:
                for value in (b"first", b"second"):
                    info = tarfile.TarInfo("index.json"); info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            with tarfile.open(archive_path, "r") as archive:
                with self.assertRaisesRegex(RuntimeError, "ambiguous duplicate member"):
                    QUALIFY.oci_archive_members(archive)


if __name__ == "__main__":
    unittest.main()
