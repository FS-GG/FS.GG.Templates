#!/usr/bin/env python3
"""Independent controls for operational baseline pin and pathname swaps."""

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify-svg-selected-archive.py"
BASELINE = ROOT / "scripts/svg-complete-workspace-baselines.json"
spec = importlib.util.spec_from_file_location("selected_archive_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def refused(action, phrase):
    try:
        action()
    except gate.Refusal as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError(f"expected refusal containing {phrase!r}")


original = BASELINE.read_bytes()
assert sha256(original).hexdigest() == gate.SELECTED_BASELINE_SHA256
candidate, managed = gate.selected_candidate(gate.read_regular(BASELINE, gate.MAX_BASELINE_BYTES, "baseline"))
assert candidate["nativeArchiveSha256"] == "f301eb3e8264e2b3e9ab33f7b276f3480a7339b1cd5834a1e4876375be5758d4"
assert len(managed) == 126
print("PASS checked-in baseline matches separate operational pin")

with tempfile.TemporaryDirectory(prefix="fsc05-baseline-pin-") as folder:
    folder = Path(folder)
    current = folder / "baseline.json"
    replacement = folder / "forged.json"
    current.write_bytes(original)
    forged = json.loads(original)
    forged["sourceCandidates"][0]["nativeArchiveSha256"] = "0" * 64
    replacement.write_text(json.dumps(forged), encoding="utf-8")
    current.write_bytes(replacement.read_bytes())
    refused(lambda: gate.verify(folder / "unread.nupkg", current), "selected baseline SHA-256 mismatch")
    print("PASS forged baseline before open refuses before archive read")

    current.write_bytes(original)
    alias = folder / "alias.json"
    alias.symlink_to(current)
    refused(lambda: gate.verify(folder / "unread.nupkg", alias), "baseline open refused")
    print("PASS baseline path symlink refuses")

    real_open = os.open
    def swap_after_open(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        if Path(path) == current:
            os.replace(replacement, current)
        return descriptor

    with patch.object(gate.os, "open", side_effect=swap_after_open):
        captured = gate.read_regular(current, gate.MAX_BASELINE_BYTES, "baseline")
    assert captured == original
    assert current.read_bytes() != original
    assert gate.selected_candidate(captured)[0]["nativeArchiveSha256"] == candidate["nativeArchiveSha256"]
    print("PASS pathname swap after open cannot change parsed baseline bytes")

    package = folder / "served-like.nupkg"
    member_name = "content/templates/fs-gg-fable-game/Asset.txt"
    with zipfile.ZipFile(package, "w") as archive:
        for name, body in [
            ("FS.GG.Workspace.Template.nuspec", b'<package><metadata><id>FS.GG.Workspace.Template</id>'
             b'<version>0.14.0</version><repository commit="' + b"b" * 40 + b'" /></metadata></package>'),
            (member_name, b"served-like bytes"),
        ]:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, body)
    fixture = {"schema": gate.SCHEMA, "managedPaths": ["Asset.txt"],
               "sourceCandidates": [{"version": "0.14.0", "sourceHead": "b" * 40,
                                     "nativeArchiveSha256": sha256(package.read_bytes()).hexdigest()}]}
    fixture_path = folder / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    result = subprocess.run(["python3", str(SCRIPT), str(package), "--fixture-manifest", str(fixture_path)],
                            capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    assert "fixture archive verified (non-authorizing)" in result.stdout
    assert "selected archive verified" not in result.stdout
    print("PASS forged matching fixture cannot emit a selected verdict")

    old_option = subprocess.run(["python3", str(SCRIPT), str(package), "--manifest", str(fixture_path)],
                                capture_output=True, text=True)
    assert old_option.returncode != 0 and "unrecognized arguments" in old_option.stderr
    print("PASS old caller-controlled manifest option refuses")
