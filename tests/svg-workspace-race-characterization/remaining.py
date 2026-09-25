#!/usr/bin/env python3
"""Disposable late-swap negatives at the Linux descriptor-relative write boundary."""

from pathlib import Path
import tempfile

import run as controls


def late_parent_swap(root, rollback):
    facts = controls.fixture(root)
    _, workspace, outside, _, _, backup = facts
    if rollback:
        controls.adopter.apply(controls.apply_args(facts))
    parked = workspace / "parked-managed"
    original = controls.adopter.uuid.uuid4
    fired = False

    def swapped_uuid():
        nonlocal fired
        if not fired:
            (workspace / "Managed").rename(parked)
            (workspace / "Managed").symlink_to(outside, target_is_directory=True)
            fired = True
        return original()

    controls.adopter.uuid.uuid4 = swapped_uuid
    try:
        if rollback:
            controls.refused(lambda: controls.adopter.restore(workspace, backup))
        else:
            controls.refused(lambda: controls.adopter.apply(controls.apply_args(facts)))
    finally:
        controls.adopter.uuid.uuid4 = original
    assert fired
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"
    expected = b"HELLO Receiver\n" if rollback else b"BASE Receiver\n"
    assert (parked / "Asset.txt").read_bytes() == expected


def late_owner_edit(root):
    facts = controls.fixture(root)
    _, workspace, outside, _, _, _ = facts
    original = controls.adopter.pinned_destination_matches
    fired = False

    def edited_check(*args, **kwargs):
        nonlocal fired
        if not fired:
            (workspace / controls.LOGICAL).write_bytes(b"new authored bytes\n")
            fired = True
        return original(*args, **kwargs)

    controls.adopter.pinned_destination_matches = edited_check
    try:
        controls.refused(lambda: controls.adopter.apply(controls.apply_args(facts)))
    finally:
        controls.adopter.pinned_destination_matches = original
    assert fired
    assert (workspace / controls.LOGICAL).read_bytes() == b"new authored bytes\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


def late_leaf_link(root):
    facts = controls.fixture(root)
    _, workspace, outside, _, _, _ = facts
    original = controls.adopter.pinned_destination_matches
    fired = False

    def linked_check(*args, **kwargs):
        nonlocal fired
        if not fired:
            (workspace / controls.LOGICAL).unlink()
            (workspace / controls.LOGICAL).symlink_to(outside / "Asset.txt")
            fired = True
        return original(*args, **kwargs)

    controls.adopter.pinned_destination_matches = linked_check
    try:
        controls.refused(lambda: controls.adopter.apply(controls.apply_args(facts)))
    finally:
        controls.adopter.pinned_destination_matches = original
    assert fired
    assert (workspace / controls.LOGICAL).is_symlink()
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


def unsupported_writer(root):
    facts = controls.fixture(root)
    _, workspace, outside, _, _, backup = facts
    original = controls.adopter.sys.platform
    controls.adopter.sys.platform = "win32"
    try:
        controls.refused(lambda: controls.adopter.apply(controls.apply_args(facts)))
    finally:
        controls.adopter.sys.platform = original
    assert not backup.exists()
    assert (workspace / controls.LOGICAL).read_bytes() == b"BASE Receiver\n"
    assert (outside / "Asset.txt").read_bytes() == b"authored outside\n"


for name, check in [
    ("apply late parent swap", lambda root: late_parent_swap(root, False)),
    ("rollback late parent swap", lambda root: late_parent_swap(root, True)),
    ("apply late ownership edit", late_owner_edit),
    ("apply late leaf symlink", late_leaf_link),
    ("unsupported platform", unsupported_writer),
]:
    with tempfile.TemporaryDirectory() as folder:
        check(Path(folder))
    print(f"{name}: refused without overwriting outside or authored content")
