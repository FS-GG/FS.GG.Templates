#!/usr/bin/env python3
"""Verify the immutable owner skill archives selected by SVG-WORKSPACE-01.1."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED = json.loads((Path(__file__).with_name("expected.json")).read_text())


def fail(message: str) -> None:
    raise SystemExit(f"owner-skills: {message}")


def download(url: str, destination: Path) -> None:
    for attempt in range(1, 13):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                destination.write_bytes(response.read())
            return
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 12:
                fail(f"cannot download {url}: {error}")
            time.sleep(5)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_digest(package: zipfile.ZipFile) -> tuple[int, str]:
    rows: list[bytes] = []
    for name in sorted(package.namelist()):
        lowered = name.lower()
        if (
            name.endswith("/")
            or name == ".signature.p7s"
            or lowered.startswith("package/services/metadata/core-properties/")
        ):
            continue
        rows.append(name.encode() + b"\0" + hashlib.sha256(package.read(name)).digest())
    return len(rows), sha256(b"".join(rows))


def repository_commit(package: zipfile.ZipFile) -> str:
    nuspecs = [name for name in package.namelist() if name.endswith(".nuspec")]
    if len(nuspecs) != 1:
        fail(f"archive has {len(nuspecs)} nuspec files")
    root = ET.fromstring(package.read(nuspecs[0]))
    repositories = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "repository"]
    if len(repositories) != 1:
        fail("archive does not carry one repository identity")
    return repositories[0].attrib.get("commit", "")


def matches(predicate: str, parameters: dict[str, str]) -> bool:
    def atom(value: str) -> bool:
        if value == "always":
            return True
        equality = re.fullmatch(r"([a-zA-Z][a-zA-Z0-9-]*) == ([a-zA-Z0-9-]+)", value)
        if equality:
            return parameters.get(equality.group(1)) == equality.group(2)
        membership = re.fullmatch(r"([a-zA-Z][a-zA-Z0-9-]*) in \[([^]]+)\]", value)
        if membership:
            choices = [choice.strip() for choice in membership.group(2).split(",")]
            return parameters.get(membership.group(1)) in choices
        fail(f"unsupported owner predicate atom: {value}")
        return False

    return any(all(atom(part) for part in clause.split(" and ")) for clause in predicate.split(" or "))


def verify_package(spec: dict[str, object], work: Path) -> list[dict[str, object]]:
    package_id = str(spec["id"])
    version = str(spec["version"])
    lowered = package_id.lower()
    archive = work / f"{lowered}.{version}.nupkg"
    download(f"https://api.nuget.org/v3-flatcontainer/{lowered}/{version}/{lowered}.{version}.nupkg", archive)
    archive_bytes = archive.read_bytes()
    if sha256(archive_bytes) != spec["publicArchiveSha256"]:
        fail(f"{package_id} {version} public archive digest changed")

    with zipfile.ZipFile(archive) as package:
        if repository_commit(package) != spec["sourceCommit"]:
            fail(f"{package_id} {version} does not bind its accepted source commit")
        entries, digest = payload_digest(package)
        if [entries, digest] != [spec["payloadEntries"], spec["payloadSha256"]]:
            fail(f"{package_id} {version} normalized payload identity changed")
        manifest = json.loads(package.read(f"{spec['contentRoot']}/skill-manifest.json"))
        if manifest.get("schemaVersion") != 2:
            fail(f"{package_id} {version} is not a closed schema-v2 manifest")
        skills = manifest.get("skills", [])
        for skill in skills:
            source = f"{spec['contentRoot']}/skills/{skill['id']}/"
            declared = {row["path"]: row["sha256"] for row in skill.get("files", [])}
            actual = {
                name.removeprefix(source): sha256(package.read(name))
                for name in package.namelist()
                if name.startswith(source) and not name.endswith("/")
            }
            if declared != actual or declared.get("SKILL.md") != skill.get("sha256"):
                fail(f"{package_id} {version} has an open or stale file set for {skill['id']}")
        by_id = {skill["id"]: skill for skill in skills}
        for skill_id, expected in dict(spec["focusedSkills"]).items():
            skill = by_id.get(skill_id)
            if not skill:
                fail(f"{package_id} {version} omits {skill_id}")
            if [skill.get("sha256"), skill.get("materializes-when")] != [expected["sha256"], expected["predicate"]]:
                fail(f"{package_id} {version} changed {skill_id}'s body or selection predicate")
        return skills


def main() -> None:
    work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "artifacts" / "owner-skills"
    work.mkdir(parents=True, exist_ok=True)
    all_skills: list[dict[str, object]] = []
    for package in EXPECTED["packages"]:
        all_skills.extend(verify_package(package, work))

    for bundle, expected in EXPECTED["fableGameSelections"].items():
        selected = [
            str(skill["id"])
            for skill in all_skills
            if matches(str(skill["materializes-when"]), {"template": "fable-game", "bundle": bundle})
        ]
        if len(selected) != len(set(selected)):
            fail(f"bundle {bundle} has an unresolved owner-id collision: {selected}")
        if sorted(selected) != sorted(expected):
            fail(f"bundle {bundle} selected {sorted(selected)}, expected {sorted(expected)}")

    player = set(EXPECTED["fableGameSelections"]["player"])
    forbidden = {"fs-gg-svg-assets", "fs-gg-layout", "fs-gg-styling", "fs-gg-ui-widgets", "fs-gg-rules"}
    if player & forbidden:
        fail(f"player contains Studio or rules guidance: {sorted(player & forbidden)}")
    if "fs-gg-collision" not in player:
        fail("fable-game does not select the Game-owned collision body")
    print("owner-skills: exact public archives, closed file sets, predicates, bundle negatives, and collision selection passed")


if __name__ == "__main__":
    main()
