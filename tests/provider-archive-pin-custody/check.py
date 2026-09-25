#!/usr/bin/env python3
"""Offline package pin/roster observation. It never establishes installed parity."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from stat import S_IFLNK, S_IFMT
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

OWNER_FILES = {
    "console": "console.providers.yml",
    "fable-bindings": "fable-bindings.providers.yml",
    "fable-game": "fable-game.providers.yml",
    "web": "web.providers.yml",
}
NAME = re.compile(r"^  - name:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)
SOURCE = re.compile(r"^    source:\s*FS\.GG\.Workspace\.Template::([^\s#]+)\s*(?:#.*)?$", re.MULTILINE)
TEMPLATE_ID = re.compile(r"^    templateId:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)


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
            and S_IFMT(mode) != S_IFLNK)


def assess(archive: Path, baseline: dict, providers: Path) -> tuple[str, list[str]]:
    """Return a bounded source/archive observation, never an installed verdict."""
    candidates = baseline.get("sourceCandidates")
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
        return "NO_VERDICT", ["selected candidate is not unique"]
    selected = candidates[0]
    version, expected_sha = selected.get("version"), selected.get("nativeArchiveSha256")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return "NO_VERDICT", ["selected version is invalid"]
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        return "NO_VERDICT", ["selected archive SHA is invalid"]
    try:
        raw = archive.read_bytes()
    except OSError:
        return "NO_VERDICT", ["selected archive is inaccessible"]
    if sha256(raw).hexdigest() != expected_sha:
        return "NO_VERDICT", ["selected archive SHA mismatch"]

    reasons = []
    short_names: dict[str, list[str]] = {}
    try:
        with ZipFile(BytesIO(raw)) as package:
            members = package.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
                return "NO_VERDICT", ["archive member duplicate or case alias"]
            if any(not safe_member(member.filename, member.external_attr >> 16) for member in members):
                return "NO_VERDICT", ["archive member path or type is unsafe"]
            nuspec = [name for name in names if name == "FS.GG.Workspace.Template.nuspec"]
            if len(nuspec) != 1:
                return "NO_VERDICT", ["package identity member is missing or ambiguous"]
            xml = package.read(nuspec[0])
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                return "NO_VERDICT", ["package identity XML contains declarations"]
            root = ElementTree.fromstring(xml)
            ids = [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "id"]
            versions = [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "version"]
            if ids != ["FS.GG.Workspace.Template"] or versions != [version]:
                return "NO_VERDICT", ["package identity/version differs from selected candidate"]
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

    for owner, filename in OWNER_FILES.items():
        path = providers / filename
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            reasons.append(f"{owner} descriptor is inaccessible")
            continue
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
        selected_baseline = strict_json(args.baseline.read_bytes())
        if not isinstance(selected_baseline, dict):
            raise ValueError("selected baseline is not an object")
        result, observations = assess(args.archive, selected_baseline, args.providers)
    except (OSError, UnicodeError, ValueError) as error:
        result, observations = "NO_VERDICT", [f"baseline cannot be read exactly: {type(error).__name__}"]
    print(json.dumps({"status": result, "reasons": observations,
                      "scope": "source-only observation; no installed or release authorization"},
                     sort_keys=True))
