#!/usr/bin/env python3
"""Disposable config-only false green and local template-payload comparison controls."""

from hashlib import sha256
from pathlib import Path
import stat
import tempfile
import warnings
from zipfile import ZipFile, ZipInfo

from check import Refusal, compare, github_no_verdict, snapshot

HEAD_A = "a" * 40
HEAD_B = "b" * 40
CONFIG = "content/templates/fs-gg-fable-game/.template.config/template.json"
ASSET = "content/templates/fs-gg-fable-game/build.sh"


def package(path: Path, *, head: str, asset: bytes, extra: bool = False,
            signed: bool = False, duplicate: bool = False, executable: bool = False,
            oversized_nuspec: bool = False) -> str:
    nuspec = ("<package><metadata><id>FS.GG.Workspace.Template</id><version>0.14.0</version>"
              f'<repository commit="{head}" /></metadata></package>').encode()
    if oversized_nuspec:
        nuspec += b"x" * (1024 * 1024)
    rows = [("FS.GG.Workspace.Template.nuspec", nuspec, 0o644),
            (CONFIG, b'{"shortName":"fs-gg-fable-game"}', 0o755 if executable else 0o644),
            (ASSET, asset, 0o644)]
    if extra:
        rows.append(("content/templates/fs-gg-fable-game/new-asset.txt", b"new", 0o644))
    if duplicate:
        rows.append((ASSET, b"duplicate", 0o644))
    if signed:
        rows.append((".signature.p7s", b"synthetic signature member", 0o644))
    with ZipFile(path, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for name, body, permissions in rows:
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, body)
    return sha256(path.read_bytes()).hexdigest()


def refused(action, phrase: str) -> None:
    try:
        action()
    except Refusal as error:
        if phrase not in str(error):
            raise AssertionError(f"wrong refusal: {error}") from error
    else:
        raise AssertionError(f"expected refusal containing {phrase!r}")


with tempfile.TemporaryDirectory(prefix="fsc05-provider-local-payload-") as folder:
    work = Path(folder)
    selected_path = work / "selected.nupkg"
    release_path = work / "release.nupkg"
    nuget_path = work / "nuget.nupkg"
    selected_sha = package(selected_path, head=HEAD_A, asset=b"old")
    release_sha = package(release_path, head=HEAD_B, asset=b"new", extra=True)
    nuget_sha = package(nuget_path, head=HEAD_B, asset=b"new", extra=True, signed=True)

    selected = snapshot(selected_path, selected_sha, HEAD_A)
    release = snapshot(release_path, release_sha, HEAD_B)
    nuget = snapshot(nuget_path, nuget_sha, HEAD_B, signed=True)
    if selected["configs"] != release["configs"]:
        raise AssertionError("config-only comparison did not reproduce the false parity signal")
    print("PASS red-before boundary: identical template configs hide asset drift")

    drift = compare(selected, release)
    if drift != {"status": "NO_VERDICT", "configOnlyMatch": True,
                 "missing": 0, "extra": 1, "bodyDrift": 1, "modeDrift": 0}:
        raise AssertionError(f"asset drift was not reported exactly: {drift}")
    print("PASS full template payload: changed and extra assets are NO_VERDICT")

    signed_match = compare(release, nuget)
    if signed_match["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY" or any(
            signed_match[key] for key in ("missing", "extra", "bodyDrift", "modeDrift")):
        raise AssertionError(f"signed local file template payload differed: {signed_match}")
    print("PASS signed local file: template payload match only")

    refused(lambda: snapshot(selected_path, "0" * 64, HEAD_A), "SHA differs")
    refused(lambda: snapshot(selected_path, selected_sha, HEAD_B), "source commit differs")
    print("PASS local archive SHA and source commit are both bound")

    duplicate_path = work / "duplicate.nupkg"
    duplicate_sha = package(duplicate_path, head=HEAD_A, asset=b"old", duplicate=True)
    refused(lambda: snapshot(duplicate_path, duplicate_sha, HEAD_A), "duplicate or case alias")
    print("PASS duplicate template member: refused")

    mode_path = work / "mode.nupkg"
    mode_sha = package(mode_path, head=HEAD_A, asset=b"old", executable=True)
    refused(lambda: snapshot(mode_path, mode_sha, HEAD_A), "Unix mode differs")
    print("PASS mode-only template change: refused")

    oversized_path = work / "oversized-nuspec.nupkg"
    oversized_sha = package(oversized_path, head=HEAD_A, asset=b"old", oversized_nuspec=True)
    refused(lambda: snapshot(oversized_path, oversized_sha, HEAD_A), "identity exceeds observation bound")
    print("PASS oversized package identity: refused before XML parse")

    for status in (403, 200, None):
        if github_no_verdict(status)["status"] != "NO_VERDICT":
            raise AssertionError("status-only GitHub report supplied archive evidence")
    print("PASS GitHub status-only reports: NO_VERDICT without bytes")
