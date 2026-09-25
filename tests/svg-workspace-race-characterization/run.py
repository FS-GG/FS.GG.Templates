#!/usr/bin/env python3
"""Deterministic disposable swaps at Python adoption transaction boundaries."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/apply-svg-complete-workspace.py"
spec = importlib.util.spec_from_file_location("adopter", SCRIPT)
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)
LOGICAL = "Managed/Asset.txt"


def fixture(root):
    candidate, workspace, outside = root / "candidate", root / "workspace", root / "outside"
    for directory, product in [(candidate, "Candidate"), (workspace, "Receiver")]:
        (directory / "Domain").mkdir(parents=True)
        (directory / f"{product}.slnx").write_text("solution\n")
        (directory / "Domain/Room.fs").write_text(f"module {product}.Domain\n")
        (directory / "Managed").mkdir()
    outside.mkdir()
    (candidate / LOGICAL).write_bytes(b"HELLO Candidate\n")
    (workspace / LOGICAL).write_bytes(b"BASE Receiver\n")
    (outside / "Asset.txt").write_bytes(b"authored outside\n")
    manifest = {
        "schema": "fsgg.svg-complete-adoption-manifest/v1",
        "managedPaths": [LOGICAL], "retiredPaths": [],
        "baselineDigests": {"v1": {LOGICAL: adopter.digest(b"BASE FableGameWorkspace\n")}},
        "baselineSkillManifestRowDigests": {"fable-example": ["a" * 64]},
        "sourceCandidates": [{"version": "0.14.0", "sourceHead": "a" * 40,
                              "nativeArchiveSha256": "b" * 64}],
    }
    manifest_path = root / "baseline.json"
    manifest_path.write_text(json.dumps(manifest))
    inventory, review, backup = root / "inventory.json", root / "review.diff", root / "backup"
    adopter.inventory([str(candidate), str(workspace), str(manifest_path), str(inventory), str(review)])
    return candidate, workspace, outside, manifest_path, inventory, backup


def refused(operation):
    try:
        operation()
    except SystemExit as error:
        assert error.code in {2, 3}, error.code
    else:
        raise AssertionError("changed receiver path or ownership was admitted")


def apply_args(facts):
    candidate, workspace, _, manifest, inventory, backup = facts
    return [str(candidate), str(workspace), str(manifest), str(inventory), str(backup)]


def with_write_hook(status, callback, operation):
    original = adopter.write_json_durable
    fired = False

    def hooked(path, value):
        nonlocal fired
        original(path, value)
        if value.get("status") == status and not fired:
            callback()
            fired = True

    adopter.write_json_durable = hooked
    try:
        operation()
    finally:
        adopter.write_json_durable = original
    assert fired, f"{status} boundary was not exercised"


def stale_owner(root):
    facts = fixture(root)
    _, workspace, outside, _, _, _ = facts
    original = adopter.classify
    fired = False

    def classify_then_edit(*args):
        nonlocal fired
        result = original(*args)
        if not fired:
            (workspace / LOGICAL).write_bytes(b"new authored bytes\n")
            fired = True
        return result

    adopter.classify = classify_then_edit
    try:
        refused(lambda: adopter.apply(apply_args(facts)))
    finally:
        adopter.classify = original
    assert fired
    assert (workspace / LOGICAL).read_bytes() == b"new authored bytes\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


def apply_parent_link(root):
    facts = fixture(root)
    _, workspace, outside, _, _, _ = facts
    parked = workspace / "parked-managed"

    def swap():
        (workspace / "Managed").rename(parked)
        (workspace / "Managed").symlink_to(outside, target_is_directory=True)

    with_write_hook("applying", swap, lambda: refused(lambda: adopter.apply(apply_args(facts))))
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"
    assert (parked / "Asset.txt").read_bytes() == b"BASE Receiver\n"


def restore_parent_link(root):
    facts = fixture(root)
    _, workspace, outside, _, _, backup = facts
    adopter.apply(apply_args(facts))
    parked = workspace / "parked-managed"

    def swap():
        (workspace / "Managed").rename(parked)
        (workspace / "Managed").symlink_to(outside, target_is_directory=True)

    with_write_hook("rolling-back", swap, lambda: refused(lambda: adopter.restore(workspace, backup)))
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"
    assert (parked / "Asset.txt").read_bytes() == b"HELLO Receiver\n"


def restore_owner_edit(root):
    facts = fixture(root)
    _, workspace, outside, _, _, backup = facts
    adopter.apply(apply_args(facts))

    def edit():
        (workspace / LOGICAL).write_bytes(b"new authored bytes\n")

    with_write_hook("rolling-back", edit, lambda: refused(lambda: adopter.restore(workspace, backup)))
    assert (workspace / LOGICAL).read_bytes() == b"new authored bytes\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


def apply_staged_edit(root):
    facts = fixture(root)
    _, workspace, outside, _, _, backup = facts

    def edit():
        (backup / "staged" / LOGICAL).write_bytes(b"forged staged bytes\n")

    with_write_hook("applying", edit, lambda: refused(lambda: adopter.apply(apply_args(facts))))
    assert (workspace / LOGICAL).read_bytes() == b"BASE Receiver\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


def restore_saved_edit(root):
    facts = fixture(root)
    _, workspace, outside, _, _, backup = facts
    adopter.apply(apply_args(facts))

    def edit():
        (backup / "files" / LOGICAL).write_bytes(b"forged backup bytes\n")

    with_write_hook("rolling-back", edit, lambda: refused(lambda: adopter.restore(workspace, backup)))
    assert (workspace / LOGICAL).read_bytes() == b"HELLO Receiver\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


CASES = {
    "stale-owner": stale_owner,
    "apply-parent-link": apply_parent_link,
    "restore-parent-link": restore_parent_link,
    "restore-owner-edit": restore_owner_edit,
    "apply-staged-edit": apply_staged_edit,
    "restore-saved-edit": restore_saved_edit,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or CASES:
        with tempfile.TemporaryDirectory() as folder:
            CASES[name](Path(folder))
        print(f"{name}: refused before outside or authored content was overwritten")
