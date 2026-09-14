#!/usr/bin/env python3
"""Verify public SDD 1.8 materialization against an exact Templates 0.14 candidate."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected.json").read_text())


def fail(message: str) -> None:
    raise SystemExit(f"sdd-svg-receiver: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owner_files(archives: list[Path]) -> tuple[dict[str, tuple[str, dict[str, bytes]]], set[str]]:
    skills: dict[str, tuple[str, dict[str, bytes]]] = {}
    all_ids: set[str] = set()
    game_precedence = {"fs-gg-collision", "fs-gg-grids", "fs-gg-line-drawing", "fs-gg-visibility"}
    for spec, archive in zip(EXPECTED["owners"], archives, strict=True):
        if sha(archive) != spec["archiveSha256"]:
            fail(f"public archive drifted: {spec['id']} {spec['version']}")
        with zipfile.ZipFile(archive) as package:
            manifest = json.loads(package.read(f"{spec['contentRoot']}/skill-manifest.json"))
            for skill in manifest["skills"]:
                skill_id = skill["id"]
                all_ids.add(skill_id)
                files = {
                    row["path"]: package.read(f"{spec['contentRoot']}/skills/{skill_id}/{row['path']}")
                    for row in skill["files"]
                }
                for row in skill["files"]:
                    if hashlib.sha256(files[row["path"]]).hexdigest() != row["sha256"]:
                        fail(f"owner manifest digest drifted: {spec['id']} {skill_id}/{row['path']}")
                if skill_id not in skills or (spec["id"] == "FS.GG.Game.Skills" and skill_id in game_precedence):
                    skills[skill_id] = (spec["id"], files)
    return skills, all_ids


def expected_ids(bundle: str) -> set[str]:
    result = set(EXPECTED["base"])
    if bundle in {"studio", "tactical", "arcade", "complete"}:
        result.update(EXPECTED["studio"])
    if bundle in {"tactical", "complete"}:
        result.update(EXPECTED["rules"])
    return result


def main() -> None:
    if len(sys.argv) != 8:
        fail("pass candidate, candidate SHA, source SHA, audit root, and three public owner archives")
    candidate, candidate_sha, source_sha, audit_root, *owner_archives = sys.argv[1:]
    candidate_path = Path(candidate)
    if sha(candidate_path) != candidate_sha:
        fail("Templates candidate archive digest changed")
    if len(source_sha) != 40 or any(c not in "0123456789abcdef" for c in source_sha):
        fail("Templates candidate source is not an exact commit")
    with zipfile.ZipFile(candidate_path) as package:
        nuspecs = [name for name in package.namelist() if name.endswith(".nuspec")]
        if len(nuspecs) != 1 or f'commit="{source_sha}"' not in package.read(nuspecs[0]).decode("utf-8-sig"):
            fail("Templates candidate nuspec does not bind its exact source commit")

    skills, all_owner_ids = owner_files([Path(path) for path in owner_archives])
    root = Path(audit_root)
    observed: dict[str, object] = {}
    for bundle in ["player", "studio", "tactical", "arcade", "complete"]:
        product = root / bundle
        report = json.loads((root / f"{bundle}.json").read_text())
        if report["outcome"] != "succeeded" or report["toolVersion"] != EXPECTED["sdd"]["version"]:
            fail(f"{bundle} did not scaffold with public SDD {EXPECTED['sdd']['version']}")
        provenance = json.loads((product / ".fsgg/scaffold-provenance.json").read_text())
        parameters = {row["key"]: row["value"] for row in provenance["effectiveParameters"]}
        if provenance["templateRef"] != "fs-gg-fable-game" or parameters.get("bundle") != bundle:
            fail(f"{bundle} lost durable template/bundle identity")
        selected = expected_ids(bundle)
        for root_name in [".agents", ".claude"]:
            for skill_id in selected:
                owner, files = skills[skill_id]
                for relative, content in files.items():
                    installed = product / root_name / "skills" / skill_id / relative
                    if not installed.is_file() or installed.read_bytes() != content:
                        fail(f"{bundle} {root_name} does not carry exact {owner} file {skill_id}/{relative}")
            unexpected = [
                skill_id for skill_id in all_owner_ids - selected
                if (product / root_name / "skills" / skill_id).exists()
            ]
            if unexpected:
                fail(f"{bundle} {root_name} contains unselected owner guidance: {sorted(unexpected)}")
        collision = product / ".agents/skills/fs-gg-collision/SKILL.md"
        if skills["fs-gg-collision"][0] != "FS.GG.Game.Skills" or collision.read_bytes() != skills["fs-gg-collision"][1]["SKILL.md"]:
            fail(f"{bundle} did not preserve Game-first collision selection")
        for path, digest in EXPECTED["routine"].items():
            installed = product / path
            if not installed.is_file() or sha(installed) != digest:
                fail(f"{bundle} routine workspace drifted at {path}")
        observed[bundle] = {"selectedOwnerSkills": sorted(selected), "effectiveParameters": parameters}

    for value in ["true", "false"]:
        report = json.loads((root / f"legacy-{value}.json").read_text())
        provenance = json.loads((root / f"legacy-{value}/.fsgg/scaffold-provenance.json").read_text())
        parameters = {row["key"]: row["value"] for row in provenance["effectiveParameters"]}
        if report["outcome"] != "succeeded" or parameters.get("svgFoundation") != value or "bundle" in parameters:
            fail(f"legacy svgFoundation={value} was not preserved without an injected bundle")
        legacy = root / f"legacy-{value}"
        retained_complete = [
            "SvgFoundation/SvgFoundation.fsproj",
            "SvgFoundation/Studio/Studio.fsproj",
            "SvgFoundation/Examples/Tactical/README.md",
            "SvgFoundation/Examples/Arcade/README.md",
        ]
        stable_base = ["Client/Client.fsproj", "Server/Server.fsproj", "Protocol/Http.fs", "build.sh"]
        if any(not (legacy / path).is_file() for path in stable_base):
            fail(f"legacy svgFoundation={value} lost the stable Fable game base")
        if value == "true" and any(not (legacy / path).is_file() for path in retained_complete):
            fail("legacy svgFoundation=true did not retain the complete SVG preview")
        if value == "false" and (legacy / "SvgFoundation").exists():
            fail("legacy svgFoundation=false unexpectedly emitted SVG content")

    upgrade = root / "upgrade"
    before = (root / "modified-helper.sha256").read_text().strip()
    if sha(upgrade / "tools/routine-delivery.py") != before:
        fail("upgrade clobbered the modified delivery helper")
    if not (upgrade / ".github/workflows/routine-eligibility.yml").is_file():
        fail("upgrade did not restore the missing routine workflow")
    upgrade_report = json.loads((root / "upgrade.json").read_text())
    if upgrade_report["outcome"] != "succeeded" or upgrade_report["upgrade"]["residualDrift"]:
        fail("installed no-clobber upgrade did not converge")

    receipt = {
        "schema": "fsgg.svg-workspace.sdd-receiver-readback/v1",
        "sdd": EXPECTED["sdd"],
        "templatesCandidate": {"version": "0.14.0", "source": source_sha, "sha256": candidate_sha},
        "bundles": observed,
        "legacySvgFoundationWithoutBundle": ["true", "false"],
        "modifiedHelperPreserved": True,
        "missingRoutineWorkflowReseeded": True,
    }
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    (root / "receiver-readback.json").write_text(encoded)
    if (HERE / "receipt.json").read_text() != encoded:
        fail("generated receiver readback differs from the committed receipt")
    print("sdd-svg-receiver: public SDD, five candidate bundles, exact owner bodies, negatives, and no-clobber upgrade passed")


if __name__ == "__main__":
    main()
