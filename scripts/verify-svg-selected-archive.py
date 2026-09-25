#!/usr/bin/env python3
"""Read-only exact archive gate for the selected SVG complete-workspace candidate.

This binds a local NuGet archive to the one selected source candidate in the
adoption baseline. It establishes byte identity and internal package identity;
the archive's producer and public-feed custody still require separate evidence.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = "fsgg.svg-complete-adoption-manifest/v1"
PACKAGE_ID = "FS.GG.Workspace.Template"
VERSION = "0.14.0"
PREFIX = "content/templates/fs-gg-fable-game/"
MAX_ARCHIVE_BYTES = 30_000_000
MAX_MEMBER_BYTES = 4_000_000
MAX_EXPANDED_BYTES = 64_000_000


class Refusal(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal(f"duplicate baseline key: {key}")
        result[key] = value
    return result


def safe_name(name: str) -> bool:
    return (bool(name) and not name.startswith("/")
            and not any(char in name for char in ("\\", ":", "\x00"))
            and all(part not in ("", ".", "..") for part in name.split("/")))


def selected_candidate(manifest_path: Path):
    try:
        manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=unique_object,
                              parse_constant=lambda token: (_ for _ in ()).throw(Refusal(f"invalid JSON constant: {token}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Refusal(f"baseline unreadable: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise Refusal("unsupported baseline schema")
    candidates = manifest.get("sourceCandidates")
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
        raise Refusal("selected candidate must be unique")
    candidate = candidates[0]
    if (candidate.get("version") != VERSION
            or not isinstance(candidate.get("sourceHead"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", candidate["sourceHead"])
            or not isinstance(candidate.get("nativeArchiveSha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", candidate["nativeArchiveSha256"])):
        raise Refusal("selected candidate identity invalid")
    managed = manifest.get("managedPaths")
    if (not isinstance(managed, list) or not managed
            or any(not isinstance(name, str) or not safe_name(name) for name in managed)
            or managed != sorted(set(managed))):
        raise Refusal("managed paths invalid")
    return candidate, managed


def read_archive(path: Path) -> bytes:
    if not hasattr(os, "O_NOFOLLOW"):
        raise Refusal("no-follow archive open unsupported")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError as error:
        raise Refusal(f"archive open refused: {error.strerror}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_ARCHIVE_BYTES:
            raise Refusal("archive is nonregular or too large")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(MAX_ARCHIVE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise Refusal("archive too large")
        return data
    except OSError as error:
        raise Refusal(f"archive read refused: {error.strerror}") from error
    finally:
        os.close(descriptor)


def one_child(parent: ET.Element, name: str) -> ET.Element:
    matches = parent.findall(f"{{*}}{name}")
    if len(matches) != 1:
        raise Refusal(f"nuspec {name} must occur once")
    return matches[0]


def verify(archive_path: Path, manifest_path: Path) -> tuple[str, str, int, int]:
    candidate, managed = selected_candidate(manifest_path)
    archive_bytes = read_archive(archive_path)
    actual = hashlib.sha256(archive_bytes).hexdigest()
    if actual != candidate["nativeArchiveSha256"]:
        raise Refusal(f"selected archive SHA-256 mismatch: expected {candidate['nativeArchiveSha256']}, got {actual}")
    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if any(not safe_name(name) for name in names):
                raise Refusal("unsafe archive member name")
            if len(names) != len(set(name.casefold() for name in names)):
                raise Refusal("duplicate or aliased archive member")
            for entry in entries:
                mode = (entry.external_attr >> 16) & 0xffff
                if not (entry.filename == ".signature.p7s" and mode == 0) and stat.S_IFMT(mode) != stat.S_IFREG:
                    raise Refusal(f"nonregular archive member: {entry.filename}")
            expanded = 0
            for entry in entries:
                if entry.file_size > MAX_MEMBER_BYTES:
                    raise Refusal(f"archive member too large: {entry.filename}")
                member_size = 0
                with archive.open(entry) as member:
                    while chunk := member.read(8192):
                        member_size += len(chunk)
                        expanded += len(chunk)
                        if member_size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES:
                            raise Refusal("archive expanded limit exceeded")
            nuspec_name = PACKAGE_ID + ".nuspec"
            if names.count(nuspec_name) != 1:
                raise Refusal("package nuspec missing")
            nuspec = archive.read(nuspec_name)
            if b"<!DOCTYPE" in nuspec.upper() or b"<!ENTITY" in nuspec.upper():
                raise Refusal("nuspec DTD or entity unsupported")
            metadata = one_child(ET.fromstring(nuspec), "metadata")
            if (one_child(metadata, "id").text != PACKAGE_ID
                    or one_child(metadata, "version").text != VERSION
                    or one_child(metadata, "repository").get("commit") != candidate["sourceHead"]):
                raise Refusal("package id, version or source commit mismatch")
            mapped = {
                PREFIX + (".agents/skills/" + name[len(".claude/skills/"):]
                          if name.startswith(".claude/skills/") else name)
                for name in managed
            }
            missing = mapped - set(names)
            if missing:
                raise Refusal(f"managed archive member missing: {sorted(missing)[0]}")
            return actual, candidate["sourceHead"], len(entries), len(mapped)
    except (zipfile.BadZipFile, ET.ParseError, OSError) as error:
        raise Refusal(f"archive unreadable: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).resolve().with_name("svg-complete-workspace-baselines.json"))
    args = parser.parse_args()
    try:
        digest, source, members, managed = verify(args.archive, args.manifest)
    except Refusal as error:
        print(f"selected archive refused: {error}", file=sys.stderr)
        return 1
    print(f"selected archive verified: sha256={digest} sourceHead={source} members={members} managedMembers={managed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
