#!/usr/bin/env python3
"""Offline package pin/roster observation. It never establishes installed parity."""

import argparse
from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
from stat import S_IFMT, S_IFREG, S_ISLNK, S_ISREG
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
import zlib

OWNER_FILES = {
    "console": "console.providers.yml",
    "fable-bindings": "fable-bindings.providers.yml",
    "fable-game": "fable-game.providers.yml",
    "web": "web.providers.yml",
}
DESCRIPTOR_FILES = set(OWNER_FILES.values()) | {"rendering.providers.yml"}
# Whole-file SHA-256 values for the five checked-in descriptors at this source
# head. The CLI requires these exact owner bytes; fixture callers may provide a
# disposable digest map. These hashes do not prove installed or served bytes.
REVIEWED_DESCRIPTOR_SHA256 = {
    "console.providers.yml": "b6ee8c9a3c79c60cbc9f99df970a9bf7beaf8ab6869ee492dee66697800a3cf8",
    "fable-bindings.providers.yml": "1853288af3a066d9aa1a152722e8c2be34b183e8fac60272dd5792bacbf3e8ca",
    "fable-game.providers.yml": "29b4c726ffacbd270e1e2f700243657ff10dcfb9ecaa4c2bd91421d9a0bb0ec7",
    "rendering.providers.yml": "ec460bd51426ffe697d97b159387e98dc04fd5cbb813e1789e2b4d74d9b2e761",
    "web.providers.yml": "30ce4273fbebfc449ee208dc713128b3cb6eb0cb9692f25d4ec31b6b9b549fef",
}
# SHA-256 of the checked-in scripts/svg-complete-workspace-baselines.json at
# this reviewed source head. It binds the CLI's selected candidate to reviewed
# source bytes; it does not authenticate the producer or a served package.
REVIEWED_BASELINE_SHA256 = "4bc5787d52cf867cdffca628a97e8822c6a23878e9870a949520c3c99f1b4335"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
NAME = re.compile(r"^  - name:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)
SOURCE = re.compile(r"^    source:\s*FS\.GG\.Workspace\.Template::([^\s#]+)\s*(?:#.*)?$", re.MULTILINE)
TEMPLATE_ID = re.compile(r"^    templateId:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)
ANY_SOURCE = re.compile(r"^    source:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)


def strict_json(data: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(data, object_pairs_hook=unique)


def safe_member(name: str, mode: int) -> bool:
    parts = name[:-1].split("/") if name.endswith("/") else name.split("/")
    return (bool(name) and not name.startswith("/") and "\\" not in name
            and ":" not in name and "\x00" not in name
            and all(part not in ("", ".", "..") for part in parts)
            and S_IFMT(mode) == S_IFREG)


def physically_closed(raw: bytes, members: list) -> bool:
    """Account for local members, the central directory, and the exact end record."""
    if (not members or not raw.startswith(b"PK\x03\x04") or len(raw) < 22
            or raw[-22:-18] != b"PK\x05\x06" or raw[-2:] != b"\x00\x00"):
        return False
    end = len(raw) - 22
    if (raw[end + 4:end + 8] != b"\x00" * 4
            or int.from_bytes(raw[end + 8:end + 10], "little") != len(members)
            or int.from_bytes(raw[end + 10:end + 12], "little") != len(members)):
        return False
    central_start = int.from_bytes(raw[end + 16:end + 20], "little")
    central_size = int.from_bytes(raw[end + 12:end + 16], "little")
    if central_start + central_size != end:
        return False
    central_cursor = central_start
    local_ranges = []
    for member in members:
        central = raw[central_cursor:central_cursor + 46]
        if len(central) != 46 or central[:4] != b"PK\x01\x02":
            return False
        central_name = int.from_bytes(central[28:30], "little")
        central_extra = int.from_bytes(central[30:32], "little")
        central_comment = int.from_bytes(central[32:34], "little")
        central_end = central_cursor + 46 + central_name + central_extra + central_comment
        if (central_end > end or int.from_bytes(central[34:36], "little") != 0
                or int.from_bytes(central[42:46], "little") != member.header_offset):
            return False
        central_name_bytes = raw[central_cursor + 46:central_cursor + 46 + central_name]
        central_cursor = central_end

        offset = member.header_offset
        local = raw[offset:offset + 30] if offset >= 0 else b""
        if (len(local) != 30 or local[:4] != b"PK\x03\x04"
                or int.from_bytes(local[6:8], "little") != member.flag_bits
                or member.flag_bits & 0x08):
            return False  # Descriptor-form members need a separate byte-bound proof.
        name_length = int.from_bytes(local[26:28], "little")
        extra_length = int.from_bytes(local[28:30], "little")
        data_start = offset + 30 + name_length + extra_length
        local_end = data_start + member.compress_size
        if (local_end > central_start or name_length != central_name
                or raw[offset + 30:offset + 30 + name_length] != central_name_bytes):
            return False
        local_ranges.append((offset, local_end))
    if central_cursor != end:
        return False
    next_offset = 0
    for start, stop in sorted(local_ranges):
        if start != next_offset:
            return False
        next_offset = stop
    return next_offset == central_start


def read_descriptors(providers: Path) -> tuple[dict[str, str], list[str]]:
    """Bind a bounded observation to one directory and an overlapping file set."""
    if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW")):
        return {}, ["descriptor no-follow traversal is unavailable"]
    try:
        directory = os.open(providers, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return {}, ["provider descriptor directory is inaccessible or linked"]
    try:
        entries = {name for name in os.listdir(directory) if name.endswith(".providers.yml")}
        if entries != DESCRIPTOR_FILES:
            return {}, ["provider descriptor inventory differs from observed owner set"]
        def stamp(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
            return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                    info.st_mtime_ns, info.st_ctime_ns)

        with ExitStack() as opened:
            readers = {}
            initial = {}
            for name in sorted(entries):
                if S_ISLNK(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode):
                    return {}, [f"{name} descriptor is a symlink"]
                handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                reader = opened.enter_context(os.fdopen(handle, "r", encoding="utf-8", newline=""))
                info = os.fstat(reader.fileno())
                if not S_ISREG(info.st_mode):
                    return {}, [f"{name} descriptor is not regular"]
                readers[name] = reader
                initial[name] = stamp(info)
            contents = {}
            for name, reader in readers.items():
                value = reader.read(1_048_577)
                if len(value) > 1_048_576:
                    return {}, [f"{name} descriptor exceeds observation bound"]
                contents[name] = value
            for name, reader in readers.items():
                if (stamp(os.fstat(reader.fileno())) != initial[name]
                        or stamp(os.stat(name, dir_fd=directory, follow_symlinks=False)) != initial[name]):
                    return {}, ["provider descriptor changed during observation"]
            if {name for name in os.listdir(directory) if name.endswith(".providers.yml")} != entries:
                return {}, ["provider descriptor inventory changed during observation"]
            return contents, []
    except (OSError, UnicodeError):
        return {}, ["provider descriptor inventory could not be read exactly"]
    finally:
        os.close(directory)


def assess(archive: Path, baseline: dict, providers: Path, *,
           expected_descriptors: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """Return a bounded source/archive observation, never an installed verdict."""
    candidates = baseline.get("sourceCandidates")
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
        return "NO_VERDICT", ["selected candidate is not unique"]
    selected = candidates[0]
    version, expected_sha = selected.get("version"), selected.get("nativeArchiveSha256")
    source_head = selected.get("sourceHead")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return "NO_VERDICT", ["selected version is invalid"]
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        return "NO_VERDICT", ["selected archive SHA is invalid"]
    if not isinstance(source_head, str) or not re.fullmatch(r"[0-9a-f]{40}", source_head):
        return "NO_VERDICT", ["selected source head is invalid"]
    try:
        with archive.open("rb") as source:
            raw = source.read(MAX_ARCHIVE_BYTES + 1)
    except OSError:
        return "NO_VERDICT", ["selected archive is inaccessible"]
    if len(raw) > MAX_ARCHIVE_BYTES:
        return "NO_VERDICT", ["selected archive exceeds observation bound"]
    if sha256(raw).hexdigest() != expected_sha:
        return "NO_VERDICT", ["selected archive SHA mismatch"]

    reasons = []
    short_names: dict[str, list[str]] = {}
    try:
        with ZipFile(BytesIO(raw)) as package:
            members = package.infolist()
            names = [member.filename for member in members]
            if len(members) > MAX_MEMBERS:
                return "NO_VERDICT", ["archive member count exceeds observation bound"]
            if any(member.orig_filename != member.filename for member in members):
                return "NO_VERDICT", ["archive member filename was shortened by parser"]
            if not physically_closed(raw, members):
                return "NO_VERDICT", ["archive bytes are not physically closed"]
            if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
                return "NO_VERDICT", ["archive member duplicate or case alias"]
            if any(not safe_member(member.filename, member.external_attr >> 16) for member in members):
                return "NO_VERDICT", ["archive member path or type is unsafe"]
            # The reviewed native candidate has Unix-created 0644 regular entries.
            # Other origins make those mode bits ambiguous to downstream hosts.
            if any(member.create_system != 3 or (member.external_attr >> 16) != (S_IFREG | 0o644)
                   for member in members):
                return "NO_VERDICT", ["archive member Unix mode differs from selected candidate"]
            expanded = 0
            try:
                for member in members:
                    if member.file_size > MAX_MEMBER_BYTES:
                        return "NO_VERDICT", ["archive member exceeds observation bound"]
                    size = 0
                    with package.open(member) as stream:
                        while chunk := stream.read(8192):
                            size += len(chunk)
                            expanded += len(chunk)
                            if size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES:
                                return "NO_VERDICT", ["archive expansion exceeds observation bound"]
                    if size != member.file_size:
                        return "NO_VERDICT", ["archive member size differs from directory"]
            except (BadZipFile, OSError, RuntimeError, EOFError, NotImplementedError, zlib.error) as error:
                return "NO_VERDICT", [f"archive member cannot be read exactly: {type(error).__name__}"]
            nuspec = [name for name in names if name == "FS.GG.Workspace.Template.nuspec"]
            if len(nuspec) != 1:
                return "NO_VERDICT", ["package identity member is missing or ambiguous"]
            xml = package.read(nuspec[0])
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                return "NO_VERDICT", ["package identity XML contains declarations"]
            root = ElementTree.fromstring(xml)
            def children(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
                return [element for element in parent if element.tag.rsplit("}", 1)[-1] == name]

            metadata = children(root, "metadata") if root.tag.rsplit("}", 1)[-1] == "package" else []
            if len(metadata) != 1:
                return "NO_VERDICT", ["package identity/version differs from selected candidate"]
            ids = [element.text for element in children(metadata[0], "id")]
            versions = [element.text for element in children(metadata[0], "version")]
            if ids != ["FS.GG.Workspace.Template"] or versions != [version]:
                return "NO_VERDICT", ["package identity/version differs from selected candidate"]
            repositories = children(metadata[0], "repository")
            if len(repositories) != 1:
                return "NO_VERDICT", ["package repository metadata is missing or ambiguous"]
            repository = repositories[0]
            if repository.get("type") != "git" or repository.get("url") != "https://github.com/FS-GG/FS.GG.Templates":
                return "NO_VERDICT", ["package repository source differs from selected candidate"]
            if repository.get("commit") != source_head:
                return "NO_VERDICT", ["package source commit differs from selected candidate"]
            for name in names:
                if not name.endswith("/.template.config/template.json"):
                    continue
                value = strict_json(package.read(name))
                if not isinstance(value, dict):
                    return "NO_VERDICT", [f"template config is not an object: {name}"]
                spellings = value.get("shortName")
                if isinstance(spellings, str):
                    spellings = [spellings]
                if not isinstance(spellings, list) or any(not isinstance(item, str) for item in spellings):
                    return "NO_VERDICT", [f"template shortName is invalid: {name}"]
                for spelling in spellings:
                    short_names.setdefault(spelling, []).append(name)
    except (BadZipFile, ValueError, ElementTree.ParseError, KeyError, RuntimeError) as error:
        return "NO_VERDICT", [f"archive cannot be read exactly: {type(error).__name__}"]

    contents, inventory_reasons = read_descriptors(providers)
    if inventory_reasons:
        return "NO_VERDICT", inventory_reasons
    if expected_descriptors is not None:
        if set(expected_descriptors) != DESCRIPTOR_FILES:
            return "NO_VERDICT", ["reviewed descriptor snapshot is incomplete"]
        for filename in sorted(DESCRIPTOR_FILES):
            if sha256(contents[filename].encode("utf-8")).hexdigest() != expected_descriptors[filename]:
                return "NO_VERDICT", [f"{filename} bytes differ from reviewed source snapshot"]
    other_sources = ANY_SOURCE.findall(contents["rendering.providers.yml"])
    if len(other_sources) != 1 or other_sources[0].startswith("FS.GG.Workspace.Template::"):
        reasons.append("non-owner provider source is ambiguous or selects the observed package")
    for owner, filename in OWNER_FILES.items():
        content = contents[filename]
        names = NAME.findall(content)
        sources = SOURCE.findall(content)
        template_ids = TEMPLATE_ID.findall(content)
        if names != [owner] or len(sources) != 1 or len(template_ids) != 1:
            reasons.append(f"{owner} provider identity/source is ambiguous")
            continue
        if sources[0] != version:
            reasons.append(f"{owner} source pin {sources[0]} differs from selected {version}")
        if len(short_names.get(template_ids[0], [])) != 1:
            reasons.append(f"{owner} template shortName {template_ids[0]} has {len(short_names.get(template_ids[0], []))} archive matches")
    return ("NO_VERDICT", reasons) if reasons else ("PIN_ROSTER_MATCH_ONLY", [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--providers", type=Path, required=True)
    args = parser.parse_args()
    try:
        baseline_bytes = args.baseline.read_bytes()
        if sha256(baseline_bytes).hexdigest() != REVIEWED_BASELINE_SHA256:
            raise ValueError("baseline bytes differ from reviewed source")
        selected_baseline = strict_json(baseline_bytes)
        if not isinstance(selected_baseline, dict):
            raise ValueError("selected baseline is not an object")
        result, observations = assess(args.archive, selected_baseline, args.providers,
                                      expected_descriptors=REVIEWED_DESCRIPTOR_SHA256)
    except ValueError as error:
        result, observations = "NO_VERDICT", [str(error)]
    except (OSError, UnicodeError) as error:
        result, observations = "NO_VERDICT", [f"baseline cannot be read exactly: {type(error).__name__}"]
    print(json.dumps({"status": result, "reasons": observations,
                      "scope": "source-only observation; no installed or release authorization"},
                     sort_keys=True))
