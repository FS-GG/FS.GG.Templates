#!/usr/bin/env python3
"""Disposable feed identity controls, including the release gate's mode-only blind spot."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/characterize-svg-feed-custody.py"
spec = importlib.util.spec_from_file_location("svg_feed_custody", SCRIPT)
custody = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custody)
COMMIT = "a" * 40
ASSET = "content/templates/fs-gg-fable-game/build.sh"


def package(path, *, mode=0o644, signed=False, commit=COMMIT, duplicate=False):
    nuspec = (f'<package><metadata><id>FS.GG.Workspace.Template</id><version>0.14.0</version>'
              f'<repository commit="{commit}" /></metadata></package>').encode()
    rows = [("FS.GG.Workspace.Template.nuspec", nuspec, 0o644), (ASSET, b"#!/bin/sh\n", mode)]
    if duplicate:
        rows.append((ASSET, b"changed", mode))
    if signed:
        rows.append((".signature.p7s", b"signature fixture", 0o644))
    with zipfile.ZipFile(path, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for name, body, permissions in rows:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, body)
    return sha256(path.read_bytes()).hexdigest()


def refused(action, phrase):
    try:
        action()
    except custody.Refusal as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError(f"expected refusal containing {phrase!r}")


with tempfile.TemporaryDirectory(prefix="fsc05-feed-custody-") as folder:
    folder = Path(folder)
    release_path = folder / "release.nupkg"
    changed_mode_path = folder / "mode-drift.nupkg"
    signed_path = folder / "signed.nupkg"
    release_sha = package(release_path)
    changed_sha = package(changed_mode_path, mode=0o755)
    signed_sha = package(signed_path, signed=True)

    # This is the release.yml comparison's exact data shape: names to body hashes.
    def old_payload(path):
        with zipfile.ZipFile(path) as archive:
            return {name: sha256(archive.read(name)).hexdigest()
                    for name in archive.namelist() if name != ".signature.p7s"}

    assert old_payload(release_path) == old_payload(changed_mode_path)
    print("PASS red-before release comparison admits mode-only drift")

    release = custody.inspect(release_path, release_sha, COMMIT)
    changed = custody.inspect(changed_mode_path, changed_sha, COMMIT)
    assert custody.difference(release, changed)["modeDrift"] == 1
    refused(lambda: custody.require_same_payload(release, changed, "mode control"), "modeDrift")
    print("PASS offline comparison refuses mode-only drift")

    signed = custody.inspect(signed_path, signed_sha, COMMIT, signed=True)
    custody.require_same_payload(release, signed, "signed control")
    assert signed["members"] == release["members"] + 1
    print("PASS signed ZIP keeps exact unsigned member names, bodies and modes")

    refused(lambda: custody.inspect(release_path, "0" * 64, COMMIT), "archive SHA-256 mismatch")
    refused(lambda: custody.inspect(release_path, release_sha, "b" * 40), "source commit mismatch")
    print("PASS archive hash and source commit are independently bound")

    duplicate_path = folder / "duplicate.nupkg"
    duplicate_sha = package(duplicate_path, duplicate=True)
    refused(lambda: custody.inspect(duplicate_path, duplicate_sha, COMMIT), "duplicate or aliased ZIP member")
    print("PASS duplicate archive members refuse")

    current, complete = custody.github_observation(release, None, 403)
    assert current == {"kind": "NO_VERDICT", "httpStatus": 403} and not complete
    refused(lambda: custody.github_observation(release, None, 200), "HTTP 200 requires package bytes")
    print("PASS historical release bytes cannot fill a current GitHub HTTP 403")

    receipt = folder / "receipt.json"
    receipt.write_text(json.dumps({"feed": "github-packages", "archiveSha256": release_sha,
                                   "payloadEntries": len(release["payload"]), "payloadExact": True}))
    value = custody.historical_receipt(receipt, sha256(receipt.read_bytes()).hexdigest(),
                                       "github-packages", release_sha, len(release["payload"]))
    assert value["kind"] == "HISTORICAL_RECEIPT"
    refused(lambda: custody.historical_receipt(receipt, "0" * 64, "github-packages",
                                                release_sha, len(release["payload"])), "historical receipt SHA-256 mismatch")
    print("PASS historical receipt is content-bound and remains historical")
