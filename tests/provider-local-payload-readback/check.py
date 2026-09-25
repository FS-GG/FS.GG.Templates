#!/usr/bin/env python3
"""Offline template payload comparison of pinned local 0.14.0 archives only."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from stat import S_IFMT, S_IFREG
import subprocess
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
import zlib

SELECTED_SHA = "f301eb3e8264e2b3e9ab33f7b276f3480a7339b1cd5834a1e4876375be5758d4"
SELECTED_HEAD = "5ef422de9f48b9763f12794882fe2b760607873d"
RELEASE_SHA = "bca6ed8ce679f34204245bfba5f44340e91e225155b054dfc3a2297bf351c829"
RELEASE_HEAD = "2d8802d527e01afe4755ae7015a5627be88e318f"
NUGET_SHA = "a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_NUSPEC_BYTES = 1024 * 1024
CONFIG_SUFFIX = "/.template.config/template.json"
PREFIX = "content/templates/"
PROJECT = Path(__file__).resolve().parents[1] / "ProviderPayloadComparison/ProviderPayloadComparison.fsproj"


class Refusal(ValueError):
    pass


def children(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [item for item in parent if item.tag.rsplit("}", 1)[-1] == name]


def one(parent: ElementTree.Element, name: str) -> ElementTree.Element:
    found = children(parent, name)
    if len(found) != 1:
        raise Refusal(f"package {name} is missing or ambiguous")
    return found[0]


def safe_path(name: str) -> bool:
    return (bool(name) and not name.startswith("/") and not name.endswith("/")
            and "\\" not in name and ":" not in name and "\x00" not in name
            and all(part not in ("", ".", "..") for part in name.split("/")))


def snapshot(path: Path, expected_sha: str, expected_head: str, *, signed: bool = False) -> dict:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_ARCHIVE_BYTES + 1)
    except OSError as error:
        raise Refusal(f"local archive is inaccessible: {type(error).__name__}") from error
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise Refusal("local archive exceeds observation bound")
    digest = sha256(raw).hexdigest()
    if digest != expected_sha:
        raise Refusal("local archive SHA differs from pinned identity")
    try:
        with ZipFile(BytesIO(raw)) as package:
            entries = package.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > MAX_MEMBERS:
                raise Refusal("archive member count exceeds observation bound")
            if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
                raise Refusal("archive member duplicate or case alias")
            if any(not safe_path(name) for name in names):
                raise Refusal("archive member path is unsafe")
            for entry in entries:
                mode = entry.external_attr >> 16
                if entry.filename == ".signature.p7s" and entry.create_system == 0 and mode == 0:
                    continue  # The pinned local signed readback has this signature metadata.
                if entry.create_system != 3 or S_IFMT(mode) != S_IFREG:
                    raise Refusal("archive member is not a Unix regular file")
            if (".signature.p7s" in names) != signed:
                raise Refusal("local archive signature presence differs from pinned role")
            identity_member = package.getinfo("FS.GG.Workspace.Template.nuspec")
            if identity_member.file_size > MAX_NUSPEC_BYTES:
                raise Refusal("package identity exceeds observation bound")
            with package.open(identity_member) as identity_stream:
                nuspec = identity_stream.read(MAX_NUSPEC_BYTES + 1)
            if len(nuspec) > MAX_NUSPEC_BYTES:
                raise Refusal("package identity exceeds observation bound")
            if b"<!DOCTYPE" in nuspec.upper() or b"<!ENTITY" in nuspec.upper():
                raise Refusal("package identity XML declarations are unsupported")
            root = ElementTree.fromstring(nuspec)
            if root.tag.rsplit("}", 1)[-1] != "package":
                raise Refusal("package root differs from pinned identity")
            metadata = one(root, "metadata")
            if (one(metadata, "id").text != "FS.GG.Workspace.Template"
                    or one(metadata, "version").text != "0.14.0"
                    or one(metadata, "repository").get("commit") != expected_head):
                raise Refusal("package id, version or source commit differs from pinned identity")
            templates = {}
            expanded = 0
            for entry in entries:
                name = entry.filename
                if not name.startswith(PREFIX):
                    continue
                mode = entry.external_attr >> 16
                if entry.create_system != 3 or mode != (S_IFREG | 0o644):
                    raise Refusal("template member Unix mode differs from selected contract")
                if entry.file_size > MAX_MEMBER_BYTES:
                    raise Refusal("template member exceeds observation bound")
                body_hash = sha256()
                size = 0
                with package.open(entry) as stream:
                    while chunk := stream.read(8192):
                        size += len(chunk)
                        expanded += len(chunk)
                        if size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES:
                            raise Refusal("template expansion exceeds observation bound")
                        body_hash.update(chunk)
                if size != entry.file_size:
                    raise Refusal("template member size differs from directory")
                templates[name] = (body_hash.hexdigest(), mode)
            if not templates:
                raise Refusal("archive has no template payload")
            return {"sha256": digest, "sourceHead": expected_head, "templates": templates,
                    "configs": {name: value for name, value in templates.items() if name.endswith(CONFIG_SUFFIX)},
                    "signed": signed}
    except (BadZipFile, ElementTree.ParseError, KeyError, OSError, RuntimeError,
            NotImplementedError, UnicodeError, zlib.error) as error:
        raise Refusal(f"local archive cannot be read exactly: {type(error).__name__}") from error


def compare(left: dict, right: dict) -> dict:
    def rows(snapshot: dict) -> list[dict]:
        return [{"name": name, "sha256": digest, "mode": mode}
                for name, (digest, mode) in sorted(snapshot["templates"].items())]

    request = json.dumps({"left": rows(left), "right": rows(right)}, sort_keys=True)
    try:
        result = subprocess.run(["dotnet", "run", "--project", str(PROJECT), "-c", "Release",
                                 "--no-launch-profile", "--"], input=request, capture_output=True,
                                text=True, check=True)
        value = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise Refusal(f"typed payload comparison is unavailable: {type(error).__name__}") from error
    if not isinstance(value, dict) or value.get("status") not in {"NO_VERDICT", "TEMPLATE_PAYLOAD_MATCH_ONLY"}:
        raise Refusal("typed payload comparison returned an invalid verdict")
    return value


def github_no_verdict(reported_http_status: int | None) -> dict:
    return {"status": "NO_VERDICT", "reportedHttpStatus": reported_http_status,
            "reason": "no authenticated current archive bytes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--nuget", type=Path, required=True)
    parser.add_argument("--github-http-status", type=int)
    args = parser.parse_args()
    try:
        selected = snapshot(args.selected, SELECTED_SHA, SELECTED_HEAD)
        release = snapshot(args.release, RELEASE_SHA, RELEASE_HEAD)
        nuget = snapshot(args.nuget, NUGET_SHA, RELEASE_HEAD, signed=True)
        report = {"status": "NO_VERDICT", "authorizing": False,
                  "selectedNative": {"sha256": selected["sha256"], "sourceHead": selected["sourceHead"]},
                  "retainedRelease": {"sha256": release["sha256"], "sourceHead": release["sourceHead"]},
                  "localNuGetFile": {"sha256": nuget["sha256"], "sourceHead": nuget["sourceHead"]},
                  "selectedToRelease": compare(selected, release),
                  "releaseToLocalNuGet": compare(release, nuget),
                  "currentGitHubPackages": github_no_verdict(args.github_http_status)}
    except Refusal as error:
        report = {"status": "NO_VERDICT", "authorizing": False, "reason": str(error)}
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
