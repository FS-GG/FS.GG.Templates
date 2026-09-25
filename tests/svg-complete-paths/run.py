#!/usr/bin/env python3
"""Negative manifest controls for the live complete-workspace adopter."""

import importlib.util
import json
from pathlib import Path
import stat
import tempfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/apply-svg-complete-workspace.py"
spec = importlib.util.spec_from_file_location("complete_workspace", SCRIPT)
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)

BASE = {
    "schema": "fsgg.svg-complete-adoption-manifest/v1",
    "managedPaths": ["a/b"],
    "retiredPaths": [],
    "baselineDigests": {},
    "baselineSkillManifestRowDigests": {"fable-example": ["a" * 64]},
    "sourceCandidates": [{"version": "0.14.0", "sourceHead": "a" * 40,
                          "nativeArchiveSha256": "b" * 64}],
}

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "manifest.json"
    path.write_text(json.dumps(BASE))
    _, managed, _, _ = adopter.manifest_data(path)
    assert managed == ["a/b"]
    for label, paths in [
        ("dot segment alias", ["a/./b", "a/b"]),
        ("repeated separator", ["a//b"]),
        ("Windows drive path", ["C:/outside"]),
        ("backslash path", [r"a\b"]),
        ("NUL path", ["a\x00b"]),
    ]:
        value = {**BASE, "managedPaths": paths}
        path.write_text(json.dumps(value))
        try:
            adopter.manifest_data(path)
        except SystemExit as error:
            assert error.code == 2, (label, error.code)
        else:
            raise AssertionError(f"{label}: noncanonical managed path passed")

    candidate = Path(folder) / "candidate"
    workspace = Path(folder) / "workspace"
    for root, product in ((candidate, "Candidate"), (workspace, "Receiver")):
        (root / "Domain").mkdir(parents=True)
        (root / f"{product}.slnx").write_text("solution\n")
        (root / "Domain/Room.fs").write_text(f"module {product}.Domain\n")
    (candidate / "Asset.txt").write_bytes(b"HELLO Candidate\n")
    (candidate / "Asset.txt").chmod(0o755)
    (workspace / "Asset.txt").write_bytes(b"BASE Receiver\n")
    (workspace / "authored.txt").write_bytes(b"owner bytes\n")
    transaction = {**BASE, "managedPaths": ["Asset.txt"],
                   "baselineDigests": {"v1": {"Asset.txt": adopter.digest(b"BASE FableGameWorkspace\n")}}}
    path.write_text(json.dumps(transaction))
    inventory = Path(folder) / "inventory.json"
    review = Path(folder) / "review.diff"
    backup = Path(folder) / "rollback"
    adopter.inventory(list(map(str, (candidate, workspace, path, inventory, review))))
    observation = json.loads(inventory.read_text())
    assert observation["ready"] and observation["changes"][0]["state"] == "replace"
    assert "authored.txt" in observation["preserved"]
    assert "HELLO Receiver" in review.read_text()
    adopter.apply(list(map(str, (candidate, workspace, path, inventory, backup))))
    assert (workspace / "Asset.txt").read_bytes() == b"HELLO Receiver\n"
    assert stat.S_IMODE((workspace / "Asset.txt").stat().st_mode) == 0o755
    assert (workspace / "authored.txt").read_bytes() == b"owner bytes\n"
    adopter.restore(workspace, backup)
    assert (workspace / "Asset.txt").read_bytes() == b"BASE Receiver\n"
    assert stat.S_IMODE((workspace / "Asset.txt").stat().st_mode) == 0o644
    (workspace / "Asset.txt").write_bytes(b"AUTHORED Receiver\n")
    try:
        adopter.inventory(list(map(str, (candidate, workspace, path, Path(folder) / "dirty.json",
                                      Path(folder) / "dirty.diff"))))
    except SystemExit as error:
        assert error.code == 3
    else:
        raise AssertionError("edited managed target was accepted for overwrite")
    assert (workspace / "Asset.txt").read_bytes() == b"AUTHORED Receiver\n"
print("svg complete workspace controls: 11 passed")
