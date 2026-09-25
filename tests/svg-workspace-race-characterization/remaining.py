#!/usr/bin/env python3
"""Disposable proof of path races still open after the bounded rechecks."""

from pathlib import Path
import tempfile

import run as controls


def late_parent_swap(root, rollback):
    facts = controls.fixture(root)
    _, workspace, outside, _, _, backup = facts
    if rollback:
        controls.adopter.apply(controls.apply_args(facts))
    parked = workspace / "parked-managed"
    original = controls.adopter.tempfile.mkstemp
    fired = False

    def swapped_mkstemp(*args, **kwargs):
        nonlocal fired
        expected = ".fsgg-rollback-" if rollback else ".fsgg-adoption-"
        if kwargs.get("prefix", "").endswith(expected) and not fired:
            (workspace / "Managed").rename(parked)
            (workspace / "Managed").symlink_to(outside, target_is_directory=True)
            fired = True
        return original(*args, **kwargs)

    controls.adopter.tempfile.mkstemp = swapped_mkstemp
    try:
        if rollback:
            controls.adopter.restore(workspace, backup)
        else:
            controls.adopter.apply(controls.apply_args(facts))
    finally:
        controls.adopter.tempfile.mkstemp = original
    assert fired
    expected = b"BASE Receiver\n" if rollback else b"HELLO Receiver\n"
    assert (outside / "Asset.txt").read_bytes() == expected


def late_owner_edit(root):
    facts = controls.fixture(root)
    _, workspace, _, _, _, backup = facts
    original = controls.adopter.shutil.copy2
    fired = False

    def edited_copy(source, destination, *args, **kwargs):
        nonlocal fired
        if str(source).startswith(str(backup / "staged")) and not fired:
            (workspace / controls.LOGICAL).write_bytes(b"new authored bytes\n")
            fired = True
        return original(source, destination, *args, **kwargs)

    controls.adopter.shutil.copy2 = edited_copy
    try:
        controls.adopter.apply(controls.apply_args(facts))
    finally:
        controls.adopter.shutil.copy2 = original
    assert fired
    assert (workspace / controls.LOGICAL).read_bytes() == b"HELLO Receiver\n"


for name, check in [
    ("apply parent after per-row check", lambda root: late_parent_swap(root, False)),
    ("rollback parent after per-row check", lambda root: late_parent_swap(root, True)),
    ("apply owner after per-row check", late_owner_edit),
]:
    with tempfile.TemporaryDirectory() as folder:
        check(Path(folder))
    print(f"KNOWN RESIDUAL: {name} can still overwrite changed content in a disposable receiver")
