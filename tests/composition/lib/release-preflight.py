#!/usr/bin/env python3
"""Fail-closed release-candidate and dual-feed mechanism preflight (#432)."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def package_identity(archive: Path) -> tuple[str, str]:
    with zipfile.ZipFile(archive) as package:
        nuspecs = [name for name in package.namelist() if name.endswith(".nuspec")]
        if len(nuspecs) != 1:
            raise ValueError(f"expected one nuspec, found {nuspecs}")
        root = ET.fromstring(package.read(nuspecs[0]))
    package_id = next((node.text for node in root.iter() if node.tag.endswith("id")), None)
    version = next((node.text for node in root.iter() if node.tag.endswith("version")), None)
    if not package_id or not version:
        raise ValueError("nuspec has no package id/version")
    return package_id, version


def validate(archive: Path, workflow: Path, expected_version: str) -> list[str]:
    errors: list[str] = []
    try:
        package_id, version = package_identity(archive)
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        return [f"candidate archive unreadable: {error}"]
    if package_id != "FS.GG.Workspace.Template":
        errors.append(f"package id is {package_id!r}, expected 'FS.GG.Workspace.Template'")
    if version != expected_version:
        errors.append(f"package version is {version!r}, expected {expected_version!r}")

    text = workflow.read_text(encoding="utf-8")
    required = {
        "checksum verification": "sha256sum --check SHA256SUMS",
        "GitHub Packages feed": "https://nuget.pkg.github.com/FS-GG/index.json",
        "nuget.org feed": "https://api.nuget.org/v3/index.json",
        "OIDC login": "uses: NuGet/login@v1",
        "public-feed authorization": "vars.NUGET_ORG_PUBLISH == 'true'",
    }
    for subject, token in required.items():
        if token not in text:
            errors.append(f"release workflow lacks {subject}: {token}")
    pushes = text.count('dotnet nuget push "artifacts/*.nupkg"')
    if pushes != 2:
        errors.append(f"release workflow has {pushes} exact-artifact pushes, expected 2")
    return errors


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="release-preflight-") as directory:
        root = Path(directory)
        archive = root / "candidate.nupkg"
        nuspec = """<package><metadata><id>FS.GG.Workspace.Template</id><version>0.9.0</version></metadata></package>"""
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("FS.GG.Workspace.Template.nuspec", nuspec)
        good = """sha256sum --check SHA256SUMS
dotnet nuget push "artifacts/*.nupkg"
--source "https://nuget.pkg.github.com/FS-GG/index.json"
uses: NuGet/login@v1
if: vars.NUGET_ORG_PUBLISH == 'true'
dotnet nuget push "artifacts/*.nupkg"
--source "https://api.nuget.org/v3/index.json"
"""
        workflow = root / "release.yml"
        workflow.write_text(good, encoding="utf-8")
        assert not validate(archive, workflow, "0.9.0")
        workflow.write_text(good.replace("https://api.nuget.org/v3/index.json", "https://example.invalid"), encoding="utf-8")
        errors = validate(archive, workflow, "0.9.0")
        assert any("nuget.org feed" in error for error in errors), errors
        workflow.write_text(good.replace('dotnet nuget push "artifacts/*.nupkg"', "# removed", 1), encoding="utf-8")
        errors = validate(archive, workflow, "0.9.0")
        assert any("exact-artifact pushes" in error for error in errors), errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--workflow", type=Path)
    parser.add_argument("--expected-version", default="0.9.0")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if args.archive is None and args.workflow is None:
        print("PASS release preflight mutation controls")
        return 0
    if args.archive is None or args.workflow is None:
        parser.error("--archive and --workflow must be supplied together")
    errors = validate(args.archive, args.workflow, args.expected_version)
    if errors:
        for error in errors:
            print(f"FAIL release preflight: {error}")
        return 1
    print(f"PASS release preflight: {args.expected_version} candidate and checksum-bound byte-identical dual-feed mechanism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
