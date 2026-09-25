#!/usr/bin/env python3
"""Disposable archive-backed controls for the live Python workspace adopter."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/apply-svg-complete-workspace.py"
spec = importlib.util.spec_from_file_location("adopter", SCRIPT)
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def refused(operation, code):
    try:
        operation()
    except SystemExit as error:
        assert error.code == code, error.code
    else:
        raise AssertionError("unsafe input was admitted")


def make_workspace(path):
    (path / "Domain").mkdir(parents=True)
    (path / "Receiver.slnx").write_bytes(b"solution\n")
    (path / "Domain/Room.fs").write_bytes(b"module Receiver.Domain\n")
    (path / "Asset.txt").write_bytes(b"\xef\xbb\xbfBASE Receiver\r\n")
    (path / "Asset.bin").write_bytes(b"\xffold\n")
    (path / "Retired.txt").write_bytes(b"RETIRE Receiver\r\n")
    (path / "authored.txt").write_bytes(b"keep authored bytes\n")
    (path / "Asset.txt").chmod(0o644)
    (path / "Asset.bin").chmod(0o600)
    (path / "Retired.txt").chmod(0o640)


def archive_candidate(path, destination):
    rows = {
        "Candidate.slnx": (b"solution\n", 0o644),
        "Domain/Room.fs": (b"module Candidate.Domain\n", 0o644),
        "Asset.txt": (b"\xef\xbb\xbfHELLO Candidate\r\n", 0o755),
        "Asset.bin": (b"\xffnew\n", 0o644),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, (data, file_mode) in rows.items():
            entry = zipfile.ZipInfo(name)
            entry.external_attr = (stat.S_IFREG | file_mode) << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
            target.chmod((entry.external_attr >> 16) & 0o777)


def run(output):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        candidate, workspace = root / "candidate", root / "workspace"
        candidate.mkdir()
        archive_candidate(root / "synthetic.nupkg", candidate)
        make_workspace(workspace)
        managed, retired = ["Asset.bin", "Asset.txt"], ["Retired.txt"]
        manifest = {
            "schema": "fsgg.svg-complete-adoption-manifest/v1",
            "managedPaths": managed,
            "retiredPaths": retired,
            "baselineDigests": {"baseline": {
                "Asset.bin": adopter.digest(b"\xffold\n"),
                "Asset.txt": adopter.digest(b"\xef\xbb\xbfBASE FableGameWorkspace\r\n"),
                "Retired.txt": adopter.digest(b"RETIRE FableGameWorkspace\r\n"),
            }},
            "baselineSkillManifestRowDigests": {"fable-example": ["a" * 64]},
            "sourceCandidates": [{"version": "0.14.0", "sourceHead": "a" * 40,
                                  "nativeArchiveSha256": "b" * 64}],
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        inventory, review, backup = root / "inventory.json", root / "review.diff", root / "backup"
        adopter.inventory(list(map(str, (candidate, workspace, manifest_path, inventory, review))))
        observation = json.loads(inventory.read_text())
        assert observation["ready"]
        assert [(row["path"], row["state"]) for row in observation["changes"]] == [
            ("Asset.bin", "replace"), ("Asset.txt", "replace"), ("Retired.txt", "delete")]
        assert "authored.txt" in observation["preserved"]

        # A symlinked candidate and a nonregular candidate must fail before writes.
        original = (candidate / "Asset.bin").read_bytes()
        (candidate / "Asset.bin").unlink()
        (candidate / "Asset.bin").symlink_to("Asset.txt")
        refused(lambda: adopter.classify(candidate, workspace, manifest_path), 2)
        (candidate / "Asset.bin").unlink()
        (candidate / "Asset.bin").mkdir()
        refused(lambda: adopter.classify(candidate, workspace, manifest_path), 2)
        (candidate / "Asset.bin").rmdir()
        (candidate / "Asset.bin").write_bytes(original)
        (candidate / "Asset.bin").chmod(0o644)

        # A symlinked target must also fail before an apply mutation.
        (workspace / "Asset.bin").unlink()
        (workspace / "Asset.bin").symlink_to("authored.txt")
        refused(lambda: adopter.classify(candidate, workspace, manifest_path), 2)
        (workspace / "Asset.bin").unlink()
        (workspace / "Asset.bin").write_bytes(b"\xffold\n")
        (workspace / "Asset.bin").chmod(0o600)
        assert (workspace / "authored.txt").read_bytes() == b"keep authored bytes\n"

        # An injected mid-apply refusal must restore every managed byte and mode.
        previous = os.environ.get("FSGG_SVG_COMPLETE_FAIL_AFTER")
        os.environ["FSGG_SVG_COMPLETE_FAIL_AFTER"] = "1"
        try:
            refused(lambda: adopter.apply(list(map(str, (candidate, workspace, manifest_path,
                                                         inventory, backup)))), 2)
        finally:
            if previous is None:
                os.environ.pop("FSGG_SVG_COMPLETE_FAIL_AFTER", None)
            else:
                os.environ["FSGG_SVG_COMPLETE_FAIL_AFTER"] = previous
        assert (workspace / "Asset.bin").read_bytes() == b"\xffold\n" and mode(workspace / "Asset.bin") == 0o600
        assert (workspace / "Asset.txt").read_bytes() == b"\xef\xbb\xbfBASE Receiver\r\n" and mode(workspace / "Asset.txt") == 0o644
        assert (workspace / "Retired.txt").read_bytes() == b"RETIRE Receiver\r\n" and mode(workspace / "Retired.txt") == 0o640
        assert (workspace / "authored.txt").read_bytes() == b"keep authored bytes\n"
        journal = json.loads((backup / "journal.json").read_text())
        assert journal["status"] == "rolled-back"
        assert [(row["logical"], row["postState"]) for row in journal["paths"]] == [
            ("Asset.bin", "present"), ("Asset.txt", "present"), ("Retired.txt", "absent")]

        # A fresh successful application verifies exact generated bytes and modes.
        adopter.apply(list(map(str, (candidate, workspace, manifest_path, inventory, root / "success-backup"))))
        assert (workspace / "Asset.bin").read_bytes() == b"\xffnew\n" and mode(workspace / "Asset.bin") == 0o644
        assert (workspace / "Asset.txt").read_bytes() == b"\xef\xbb\xbfHELLO Receiver\r\n" and mode(workspace / "Asset.txt") == 0o755
        assert not (workspace / "Retired.txt").exists()
        assert (workspace / "authored.txt").read_bytes() == b"keep authored bytes\n"
        adopter.restore(workspace, root / "success-backup")
        assert (workspace / "Asset.txt").read_bytes() == b"\xef\xbb\xbfBASE Receiver\r\n"

        output.write_text(json.dumps({"managed": managed, "retired": retired,
                                      "journalPaths": [row["logical"] for row in journal["paths"]],
                                      "journalStates": [row["postState"] for row in journal["paths"]]}))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
    print("archive-backed Python workspace characterization: passed")
