#!/usr/bin/env python3
"""Offline template payload comparison of pinned local 0.14.0 archives only."""

import argparse
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from stat import S_IFMT, S_IFREG
import subprocess
import unicodedata
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile
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
MAX_MEMBER_SEGMENT_BYTES = 255
PINNED_UNICODE_VERSION = "16.0.0"
CONFIG_SUFFIX = "/.template.config/template.json"
PREFIX = "content/templates/"
RESERVED_MEMBER_PUNCTUATION = '<>"|?*'
RESERVED_DEVICE_STEMS = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}
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
            and all(ord(character) >= 32 and character not in RESERVED_MEMBER_PUNCTUATION
                    for character in name)
            and all(part not in ("", ".", "..") and not part.endswith((".", " "))
                    for part in name.split("/")))


def reserved_device_part(part: str) -> bool:
    return part.split(".", 1)[0].upper() in RESERVED_DEVICE_STEMS


def snapshot(path: Path, expected_sha: str, expected_head: str, *, signed: bool = False) -> dict:
    if unicodedata.unidata_version != PINNED_UNICODE_VERSION:
        raise Refusal("Python Unicode data version differs from selected contract")
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
    if not raw.startswith(b"PK\x03\x04"):
        raise Refusal("archive start differs from selected contract")
    if len(raw) < 22 or raw[-22:-18] != b"PK\x05\x06" or raw[-2:] != b"\x00\x00":
        raise Refusal("archive end record differs from selected contract")
    try:
        with ZipFile(BytesIO(raw)) as package:
            entries = package.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > MAX_MEMBERS:
                raise Refusal("archive member count exceeds observation bound")
            end_record = len(raw) - 22
            if raw[end_record + 4:end_record + 8] != b"\x00" * 4:
                raise Refusal("ZIP multi-disk metadata differs from selected contract")
            disk_count = int.from_bytes(raw[end_record + 8:end_record + 10], "little")
            total_count = int.from_bytes(raw[end_record + 10:end_record + 12], "little")
            if disk_count != len(entries) or total_count != len(entries):
                raise Refusal("ZIP end-record entry count differs from parsed members")
            central_size = int.from_bytes(raw[end_record + 12:end_record + 16], "little")
            central_start = int.from_bytes(raw[end_record + 16:end_record + 20], "little")
            if (central_start + central_size != end_record
                    or raw[central_start:central_start + 4] != b"PK\x01\x02"):
                raise Refusal("ZIP central directory boundary differs from selected contract")
            aliases = {name.casefold() for name in names}
            if len(names) != len(set(names)) or len(names) != len(aliases):
                raise Refusal("archive member duplicate or case alias")
            if any(not safe_path(name) for name in names):
                raise Refusal("archive member path is unsafe")
            if any(not unicodedata.is_normalized("NFC", name)
                   or not unicodedata.is_normalized("NFKC", name) for name in names):
                raise Refusal("archive member path is noncanonical")
            if any(len(character.casefold()) > 1 for name in names for character in name):
                raise Refusal("archive member has a full case-fold expansion")
            if any(len(part.encode("utf-8")) > MAX_MEMBER_SEGMENT_BYTES
                   for name in names for part in name.split("/")):
                raise Refusal("archive member path segment exceeds byte bound")
            if any(reserved_device_part(part) for name in names for part in name.split("/")):
                raise Refusal("archive member has a reserved device name")
            for name in names:
                ancestor = name
                while "/" in ancestor:
                    ancestor = ancestor.rsplit("/", 1)[0]
                    if ancestor.casefold() in aliases:
                        raise Refusal("archive member has a file ancestor")
            local_ranges = []
            for entry in entries:
                if entry.volume != 0:
                    raise Refusal("ZIP multi-disk metadata differs from selected contract")
                if entry.comment:
                    raise Refusal("ZIP central member comment differs from selected contract")
                if (entry.create_version != 20 or entry.extract_version != 20
                        or entry.reserved != 0 or entry.internal_attr != 0):
                    raise Refusal("ZIP header metadata differs from selected contract")
                offset = entry.header_offset
                local_header = raw[offset:offset + 30] if offset >= 0 else b""
                if (len(local_header) != 30 or local_header[:4] != b"PK\x03\x04"
                        or int.from_bytes(local_header[6:8], "little") != entry.flag_bits
                        or int.from_bytes(local_header[8:10], "little") != entry.compress_type):
                    raise Refusal("ZIP local header differs from central directory")
                if local_header[4:6] != b"\x14\x00":
                    raise Refusal("ZIP header metadata differs from selected contract")
                year, month, day, hour, minute, second = entry.date_time
                try:
                    datetime(year, month, day, hour, minute, second)
                except ValueError as error:
                    raise Refusal("ZIP timestamp is invalid") from error
                central_time = (hour << 11) | (minute << 5) | (second // 2)
                central_date = ((year - 1980) << 9) | (month << 5) | day
                if (int.from_bytes(local_header[10:12], "little") != central_time
                        or int.from_bytes(local_header[12:14], "little") != central_date):
                    raise Refusal("ZIP local timestamp differs from central directory")
                if entry.extra or int.from_bytes(local_header[28:30], "little") != 0:
                    raise Refusal("ZIP extra fields differ from selected contract")
                local_name_bytes = int.from_bytes(local_header[26:28], "little")
                local_end = offset + 30 + local_name_bytes + entry.compress_size
                if local_end > central_start:
                    raise Refusal("ZIP local member crosses central directory")
                local_ranges.append((offset, local_end))
                if entry.flag_bits & 0x08:
                    raise Refusal("ZIP data descriptor differs from selected contract")
                if entry.flag_bits != 0:
                    raise Refusal("ZIP unsupported flag bits differ from selected contract")
                if (
                        int.from_bytes(local_header[14:18], "little") != entry.CRC
                        or int.from_bytes(local_header[18:22], "little") != entry.compress_size
                        or int.from_bytes(local_header[22:26], "little") != entry.file_size):
                    raise Refusal("ZIP local fixed fields differ from central directory")
                if entry.compress_type == ZIP_DEFLATED:
                    compressed_start = offset + 30 + local_name_bytes
                    decoder = zlib.decompressobj(-15)
                    expanded_member = decoder.decompress(
                        memoryview(raw)[compressed_start:local_end], MAX_MEMBER_BYTES + 1)
                    if len(expanded_member) > MAX_MEMBER_BYTES:
                        raise Refusal("ZIP deflate stream exceeds observation bound")
                    if not decoder.eof:
                        raise Refusal("ZIP deflate stream lacks an end marker")
                    if decoder.unused_data or decoder.unconsumed_tail:
                        raise Refusal("ZIP deflate stream has unused bytes")
                mode = entry.external_attr >> 16
                if entry.filename == ".signature.p7s" and entry.create_system == 0 and mode == 0:
                    continue  # The pinned local signed readback has this signature metadata.
                if entry.create_system != 3 or S_IFMT(mode) != S_IFREG:
                    raise Refusal("archive member is not a Unix regular file")
            next_offset = 0
            for start, end in sorted(local_ranges):
                if start != next_offset:
                    raise Refusal("ZIP bytes outside declared local members")
                next_offset = end
            if next_offset != central_start:
                raise Refusal("ZIP bytes outside declared local members")
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
                is_template = name.startswith(PREFIX)
                mode = entry.external_attr >> 16
                if is_template and (entry.create_system != 3 or mode != (S_IFREG | 0o644)):
                    raise Refusal("template member Unix mode differs from selected contract")
                if entry.file_size > MAX_MEMBER_BYTES:
                    raise Refusal("archive member exceeds observation bound")
                body_hash = sha256()
                size = 0
                with package.open(entry) as stream:
                    while chunk := stream.read(8192):
                        size += len(chunk)
                        expanded += len(chunk)
                        if size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES:
                            raise Refusal("archive expansion exceeds observation bound")
                        if is_template:
                            body_hash.update(chunk)
                if size != entry.file_size:
                    raise Refusal("archive member size differs from directory")
                if is_template:
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
