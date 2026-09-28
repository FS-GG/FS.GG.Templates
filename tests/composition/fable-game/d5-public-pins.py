#!/usr/bin/env python3
"""Fail closed before public D.5 qualification can launch expensive work."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile


def validate(value):
    if value.get("schema") != "fsgg.svg-release-d5.public-pins/1":
        raise ValueError("expected public-pins/1 schema")
    if value.get("mode") not in ("templates", "full"):
        raise ValueError("mode must be templates or full")
    required = {"templates": "0.15.0", "sdd": "2.0.2"}
    if value["mode"] == "full":
        required["wizard"] = "0.12.0"
    elif "wizard" in value:
        raise ValueError("templates mode must omit wizard; use full to qualify it")
    for key, version in required.items():
        package = value.get(key, {})
        if package.get("version") != version:
            raise ValueError(f"{key}: selected D.5 version must be {version}")
        if not re.fullmatch(r"[0-9a-f]{64}", package.get("sha256", "")):
            raise ValueError(f"{key}: exact public archive sha256 required")
        if not re.fullmatch(r"[0-9a-f]{40}", package.get("sourceCommit", "")):
            raise ValueError(f"{key}: exact package sourceCommit required")
    if not re.fullmatch(r"[0-9a-f]{64}", value["templates"].get("providerSha256", "")):
        raise ValueError("templates: exact immutable providerSha256 required")
    return value


def archive_identity(path, package_id, pin):
    with ZipFile(path) as archive:
        specs = [p for p in archive.namelist() if p.endswith(".nuspec")]
        if len(specs) != 1:
            raise ValueError("package must contain exactly one nuspec")
        metadata = next(x for x in ET.fromstring(archive.read(specs[0]))
                        if x.tag.rsplit("}", 1)[-1] == "metadata")
        fields = {x.tag.rsplit("}", 1)[-1]: x for x in metadata}
        if fields["id"].text != package_id or fields["version"].text != pin["version"]:
            raise ValueError(f"{package_id}: nuspec identity mismatch")
        if fields["repository"].get("commit") != pin["sourceCommit"]:
            raise ValueError(f"{package_id}: nuspec source commit mismatch")
        if package_id == "FS.GG.Workspace.Template":
            templates = {p: json.loads(archive.read(p)) for p in archive.namelist()
                         if p.endswith("fs-gg-fable-game/.template.config/template.json")
                         or p.endswith("fs-gg-fable-game-legacy/.template.config/template.json")}
            if len(templates) != 2:
                raise ValueError("expected modern and legacy fable-game package members")
            for path, template in templates.items():
                lifecycle = template["symbols"]["lifecycle"]
                expected = "sdd" if "legacy" in path else "typed-sdd"
                if lifecycle["defaultValue"] != expected:
                    raise ValueError(f"{path}: incorrect raw-template lifecycle default")
                if [c["choice"] for c in lifecycle["choices"]] != ["none", "sdd", "typed-sdd", "spec-kit"]:
                    raise ValueError(f"{path}: incorrect explicit lifecycle choices")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pins", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--key", choices=["templates", "sdd", "wizard"])
    args = parser.parse_args()
    try:
        pins = validate(json.loads(args.pins.read_text()))
        if args.archive:
            ids = {"templates": "FS.GG.Workspace.Template", "sdd": "FS.GG.SDD.Cli",
                   "wizard": "FS.GG.NewSddWorkspace"}
            archive_identity(args.archive, ids[args.key], pins[args.key])
    except (ValueError, KeyError, StopIteration, OSError) as error:
        parser.exit(2, f"D.5 public preflight: {error}\n")
    print("PASS D.5 public identity preflight")


if __name__ == "__main__":
    main()
