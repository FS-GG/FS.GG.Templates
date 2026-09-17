#!/usr/bin/env python3
"""Static and public-package checks for the Templates GS2-08.8 receiver."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
VERSION = "0.90.0"
SOURCE = "3adada5a9738464291088830c47a30a3a8fc9561"
WORKFLOW = f"FS-GG/.github/.github/workflows/{{name}}.yml@{SOURCE}"
ARCHIVES = {
    "FS.GG.Coord.Cli": "69a7100358e01c846216cedb3f5ce17f72e99e8328a23be8e75b077dfd82d3e6",
    "FS.GG.Kit": "bea35100645f1acb459e385e303d0ef4ff7aa6576fa3f032ef8325cfef38b858",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"bridge-receivers: {message}")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nuspec(package: pathlib.Path) -> tuple[str, str, str]:
    with zipfile.ZipFile(package) as archive:
        names = [name for name in archive.namelist() if name.endswith(".nuspec") and "/" not in name]
        require(len(names) == 1, f"{package.name} does not contain one root nuspec")
        root = ET.fromstring(archive.read(names[0]))
    metadata = next(node for node in root if node.tag.rsplit("}", 1)[-1] == "metadata")
    values = {node.tag.rsplit("}", 1)[-1]: node for node in metadata}
    repository = values.get("repository")
    return (
        "" if values.get("id") is None else values["id"].text or "",
        "" if values.get("version") is None else values["version"].text or "",
        "" if repository is None else repository.attrib.get("commit", ""),
    )


def main() -> None:
    require(len(sys.argv) == 2, "usage: verify.py <public-package-directory>")
    package_dir = pathlib.Path(sys.argv[1]).resolve()

    manifest = json.loads((ROOT / ".config/dotnet-tools.json").read_text())
    tool = manifest["tools"].get("fs.gg.coord.cli", {})
    require(tool.get("version") == VERSION, "repository CLI pin is not exact 0.90.0")
    require(tool.get("commands") == ["fsgg-coord-engine"], "repository CLI command changed")

    receiver = (ROOT / ".config/kit/FS.GG.Kit.receiver.proj").read_text()
    require(f'PackageReference Include="FS.GG.Kit" Version="{VERSION}"' in receiver,
            "Kit receiver pin is not exact 0.90.0")
    for name in ("kit-materialize", "lockfile-sync"):
        workflow = (ROOT / f".github/workflows/{name}.yml").read_text()
        require(WORKFLOW.format(name=name) in workflow, f"{name} does not pin the immutable bridge source")
        require("@main" not in workflow, f"{name} retains a mutable hub ref")

    for package_id, digest in ARCHIVES.items():
        package = package_dir / f"{package_id.lower()}.{VERSION}.nupkg"
        require(package.is_file(), f"missing public archive {package.name}")
        require(sha256(package) == digest, f"public archive digest changed for {package_id}")
        actual_id, actual_version, commit = nuspec(package)
        require((actual_id, actual_version, commit) == (package_id, VERSION, SOURCE),
                f"wrong public identity for {package_id}: {(actual_id, actual_version, commit)}")

    report = json.loads((ROOT / "docs/reports/gs2-08-8-bridge-adoption.json").read_text())
    require(report.get("schema") == "fsgg.gs2-08.8-receiver-adoption/1", "report schema changed")
    require(report.get("receiver") == "FS-GG/FS.GG.Templates", "report names the wrong receiver")
    boundary = report.get("remainingBoundary", "")
    require("Default public wizard delivery is unclaimed" in boundary,
            "report must keep default wizard delivery pending")
    require("SDD release is public and adopted" in boundary,
            "report must keep SDD publication pending")
    allowed = {"bridge-adopted", "read-only-local-only", "gs2-08.9-sealing"}
    dispositions = [row.get("disposition") for row in report.get("routes", []) + report.get("callableRoutes", [])]
    require(dispositions and set(dispositions) <= allowed, "report uses an open or unknown route disposition")
    callables = {row.get("caller"): row.get("disposition") for row in report.get("callableRoutes", [])}
    for caller in (".github/workflows/kit-materialize.yml", ".github/workflows/lockfile-sync.yml"):
        require(callables.get(caller) == "gs2-08.9-sealing",
                f"{caller} must remain in GS2-08.9 sealing until it has common admission")
    print("bridge-receivers: pins, workflow refs, public packages, and dependency boundary PASS")


if __name__ == "__main__":
    main()
