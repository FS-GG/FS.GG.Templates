#!/usr/bin/env python3
"""Offline SVG 0.14.0 archive comparison; never a publication or receiver gate.

Paths are caller-supplied local readbacks. Historical receipts describe their
2026-09-15 release run, never the present GitHub Packages response.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import runpy
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile

gate = runpy.run_path(str(Path(__file__).with_name("verify-svg-selected-archive.py")))
Refusal = gate["Refusal"]

SELECTED_SHA = "f301eb3e8264e2b3e9ab33f7b276f3480a7339b1cd5834a1e4876375be5758d4"
SELECTED_HEAD = "5ef422de9f48b9763f12794882fe2b760607873d"
RELEASE_SHA = "bca6ed8ce679f34204245bfba5f44340e91e225155b054dfc3a2297bf351c829"
RELEASE_HEAD = "2d8802d527e01afe4755ae7015a5627be88e318f"
NUGET_SHA = "a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563"
HISTORICAL_GITHUB_RECEIPT_SHA = "c48b53526421151d1767b1ed69de38a24de5c86226710a06d41292d698e2b1db"
HISTORICAL_NUGET_RECEIPT_SHA = "ad06aef4b3d0e9d09166c9a5a2a3ac2818956afeadb89d5603cb6aaa4c9c79c3"
PACKAGE_ID = "FS.GG.Workspace.Template"
VERSION = "0.14.0"


def inspect(path: Path, expected_sha: str, expected_head: str, *, signed: bool = False) -> dict:
    content = gate["read_regular"](path, gate["MAX_ARCHIVE_BYTES"], "package")
    actual_sha = sha256(content).hexdigest()
    if actual_sha != expected_sha:
        raise Refusal(f"archive SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if any(not gate["safe_name"](name) for name in names):
                raise Refusal("unsafe ZIP member name")
            if len(names) != len(set(name.casefold() for name in names)):
                raise Refusal("duplicate or aliased ZIP member")
            if (".signature.p7s" in names) != signed:
                raise Refusal("signature member presence mismatch")
            payload = {}
            expanded = 0
            nuspec = None
            for entry in entries:
                mode = (entry.external_attr >> 16) & 0xffff
                if not (entry.filename == ".signature.p7s" and mode == 0) and stat.S_IFMT(mode) != stat.S_IFREG:
                    raise Refusal(f"nonregular ZIP member: {entry.filename}")
                if entry.file_size > gate["MAX_MEMBER_BYTES"]:
                    raise Refusal(f"ZIP member too large: {entry.filename}")
                digest = sha256()
                size = 0
                chunks = [] if entry.filename == PACKAGE_ID + ".nuspec" else None
                with archive.open(entry) as stream:
                    while chunk := stream.read(8192):
                        digest.update(chunk)
                        size += len(chunk)
                        expanded += len(chunk)
                        if size > gate["MAX_MEMBER_BYTES"] or expanded > gate["MAX_EXPANDED_BYTES"]:
                            raise Refusal("ZIP expansion limit exceeded")
                        if chunks is not None:
                            chunks.append(chunk)
                if chunks is not None:
                    nuspec = b"".join(chunks)
                if entry.filename != ".signature.p7s":
                    payload[entry.filename] = (digest.hexdigest(), mode)
            if nuspec is None:
                raise Refusal("package nuspec missing")
            if b"<!DOCTYPE" in nuspec.upper() or b"<!ENTITY" in nuspec.upper():
                raise Refusal("nuspec DTD or entity unsupported")
            metadata = gate["one_child"](ET.fromstring(nuspec), "metadata")
            if (gate["one_child"](metadata, "id").text != PACKAGE_ID
                    or gate["one_child"](metadata, "version").text != VERSION
                    or gate["one_child"](metadata, "repository").get("commit") != expected_head):
                raise Refusal("package id, version or source commit mismatch")
            return {"sha256": actual_sha, "sourceHead": expected_head, "members": len(entries),
                    "payload": payload, "signed": signed}
    except (zipfile.BadZipFile, ET.ParseError, OSError, RuntimeError) as error:
        raise Refusal(f"package unreadable: {error}") from error


def difference(left: dict, right: dict) -> dict:
    before, after = left["payload"], right["payload"]
    common = before.keys() & after.keys()
    return {"missing": len(before.keys() - after.keys()), "extra": len(after.keys() - before.keys()),
            "bodyDrift": sum(before[name][0] != after[name][0] for name in common),
            "modeDrift": sum(before[name][1] != after[name][1] for name in common)}


def require_same_payload(left: dict, right: dict, label: str) -> None:
    changes = difference(left, right)
    if any(changes.values()):
        raise Refusal(f"{label} payload mismatch: {changes}")


def historical_receipt(path: Path, digest: str, feed: str, archive_sha: str, entries: int) -> dict:
    content = gate["read_regular"](path, 10_000, "historical receipt")
    if sha256(content).hexdigest() != digest:
        raise Refusal(f"{feed} historical receipt SHA-256 mismatch")
    try:
        value = json.loads(content, object_pairs_hook=gate["unique_object"])
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Refusal(f"historical receipt unreadable: {error}") from error
    if (not isinstance(value, dict) or value.get("feed") != feed
            or value.get("archiveSha256") != archive_sha
            or value.get("payloadEntries") != entries or value.get("payloadExact") is not True):
        raise Refusal(f"{feed} historical receipt identity mismatch")
    return {"kind": "HISTORICAL_RECEIPT", "sha256": archive_sha, "payloadEntries": entries}


def github_observation(release: dict, archive: Path | None, http_status: int | None) -> tuple[dict, bool]:
    if archive is None:
        if http_status == 200:
            raise Refusal("HTTP 200 requires package bytes, not a status-only report")
        return {"kind": "NO_VERDICT", "httpStatus": http_status}, False
    observed = inspect(archive, RELEASE_SHA, RELEASE_HEAD)
    require_same_payload(release, observed, "current GitHub Packages local readback")
    return {"kind": "LOCAL_READBACK_MATCH", "sha256": observed["sha256"],
            "payloadEntries": len(observed["payload"])}, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--nuget", required=True, type=Path)
    parser.add_argument("--historical-github-receipt", required=True, type=Path)
    parser.add_argument("--historical-nuget-receipt", required=True, type=Path)
    github = parser.add_mutually_exclusive_group(required=True)
    github.add_argument("--github-archive", type=Path)
    github.add_argument("--github-http-status", type=int)
    args = parser.parse_args()
    try:
        selected_baseline = Path(__file__).with_name("svg-complete-workspace-baselines.json")
        gate["verify"](args.selected, selected_baseline)
        selected = inspect(args.selected, SELECTED_SHA, SELECTED_HEAD)
        release = inspect(args.release, RELEASE_SHA, RELEASE_HEAD)
        nuget = inspect(args.nuget, NUGET_SHA, RELEASE_HEAD, signed=True)
        require_same_payload(release, nuget, "release versus current NuGet")
        gh_history = historical_receipt(args.historical_github_receipt, HISTORICAL_GITHUB_RECEIPT_SHA,
                                        "github-packages", RELEASE_SHA, len(release["payload"]))
        nuget_history = historical_receipt(args.historical_nuget_receipt, HISTORICAL_NUGET_RECEIPT_SHA,
                                           "nuget.org", NUGET_SHA, len(release["payload"]))
        github_now, complete = github_observation(release, args.github_archive, args.github_http_status)
        report = {"schema": "fsgg.svg-feed-custody-characterization/v1", "authorizing": False,
                  "selectedNative": {"kind": "SELECTED_NATIVE", "sha256": selected["sha256"],
                                     "sourceHead": SELECTED_HEAD, "payloadEntries": len(selected["payload"])},
                  "retainedRelease": {"kind": "RETAINED_RELEASE_PACK", "sha256": release["sha256"],
                                      "sourceHead": RELEASE_HEAD, "payloadEntries": len(release["payload"])},
                  "selectedToRelease": difference(selected, release),
                  "historicalGitHubPackages": gh_history,
                  "currentGitHubPackages": github_now,
                  "historicalNuGet": nuget_history,
                  "currentNuGet": {"kind": "SIGNED_LOCAL_READBACK_MATCH", "sha256": nuget["sha256"],
                                   "payloadEntries": len(nuget["payload"])}}
        print(json.dumps(report, sort_keys=True))
        return 0 if complete else 2
    except Refusal as error:
        print(f"feed custody refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
