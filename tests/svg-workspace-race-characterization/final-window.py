#!/usr/bin/env python3
"""Disposable controls after the final pinned ownership comparison."""

from pathlib import Path
import tempfile

import run as controls


def fixture(root: Path):
    workspace = root / "workspace"
    source = root / "source"
    (workspace / "Managed").mkdir(parents=True)
    source.mkdir()
    staged = source / "Asset.txt"
    staged.write_bytes(b"adopted bytes\n")
    return workspace, source, staged


def after_final_check(action, operation):
    original = controls.adopter.pinned_destination_matches
    fired = False

    def hook(*args, **kwargs):
        nonlocal fired
        original(*args, **kwargs)
        if not fired:
            action()
            fired = True

    controls.adopter.pinned_destination_matches = hook
    try:
        operation()
    finally:
        controls.adopter.pinned_destination_matches = original
    assert fired, "final ownership boundary was not exercised"


def staged_state(staged):
    return controls.adopter.digest(staged.read_bytes()), controls.adopter.file_mode(staged)


def late_add(root):
    workspace, source, staged = fixture(root)
    target = workspace / "Managed/Asset.txt"
    after_final_check(lambda: target.write_bytes(b"authored add\n"),
                      lambda: controls.refused(lambda: controls.adopter.pinned_write(
                          workspace, "Managed/Asset.txt", source, "Asset.txt", None,
                          staged_state(staged), "fsgg-adoption")))
    assert target.read_bytes() == b"authored add\n"


def late_add_link(root):
    workspace, source, staged = fixture(root)
    target = workspace / "Managed/Asset.txt"
    outside = root / "outside.txt"
    outside.write_bytes(b"outside bytes\n")
    after_final_check(lambda: target.symlink_to(outside),
                      lambda: controls.refused(lambda: controls.adopter.pinned_write(
                          workspace, "Managed/Asset.txt", source, "Asset.txt", None,
                          staged_state(staged), "fsgg-adoption")))
    assert target.is_symlink()
    assert outside.read_bytes() == b"outside bytes\n"


def late_replace(root):
    workspace, source, staged = fixture(root)
    target = workspace / "Managed/Asset.txt"
    target.write_bytes(b"old bytes\n")
    before = controls.adopter.digest(target.read_bytes()), controls.adopter.file_mode(target)
    after_final_check(lambda: target.write_bytes(b"authored edit\n"),
                      lambda: controls.adopter.pinned_write(
                          workspace, "Managed/Asset.txt", source, "Asset.txt", before,
                          staged_state(staged), "fsgg-adoption"))
    assert target.read_bytes() == b"adopted bytes\n"


def late_delete(root):
    workspace, _, _ = fixture(root)
    target = workspace / "Managed/Asset.txt"
    target.write_bytes(b"old bytes\n")
    before = controls.adopter.digest(target.read_bytes()), controls.adopter.file_mode(target)
    after_final_check(lambda: target.write_bytes(b"authored edit\n"),
                      lambda: controls.adopter.pinned_delete(workspace, "Managed/Asset.txt", before))
    assert not target.exists()


def late_parent_move(root):
    workspace, source, staged = fixture(root)
    target = workspace / "Managed/Asset.txt"
    target.write_bytes(b"old bytes\n")
    before = controls.adopter.digest(target.read_bytes()), controls.adopter.file_mode(target)
    parked = workspace / "parked-managed"
    outside = root / "outside"
    outside.mkdir()
    (outside / "Asset.txt").write_bytes(b"outside bytes\n")

    def move():
        (workspace / "Managed").rename(parked)
        (workspace / "Managed").symlink_to(outside, target_is_directory=True)

    after_final_check(move, lambda: controls.adopter.pinned_write(
        workspace, "Managed/Asset.txt", source, "Asset.txt", before,
        staged_state(staged), "fsgg-adoption"))
    assert (outside / "Asset.txt").read_bytes() == b"outside bytes\n"
    assert (parked / "Asset.txt").read_bytes() == b"adopted bytes\n"


with tempfile.TemporaryDirectory() as folder:
    late_add(Path(folder))
print("PASS atomic no-overwrite add preserves a late authored file")
with tempfile.TemporaryDirectory() as folder:
    late_add_link(Path(folder))
print("PASS atomic no-overwrite add preserves a late symlink and its target")
for name, case in [
    ("replace can overwrite a late authored edit", late_replace),
    ("unlink can remove a late authored edit", late_delete),
    ("moved parent can receive a hidden write", late_parent_move),
]:
    with tempfile.TemporaryDirectory() as folder:
        case(Path(folder))
    print(f"KNOWN RESIDUAL: {name}")
