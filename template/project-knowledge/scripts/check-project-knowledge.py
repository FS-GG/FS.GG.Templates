#!/usr/bin/env python3
"""Run the shared producer check for an explicitly typed generated product."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--command-json", help="Explicit source-candidate qualification argv; ordinary CI uses the pinned local tool")
    args = parser.parse_args()
    root = args.root.resolve()
    for relative in (".fsgg/knowledge-guide.md", ".fsgg/knowledge/schema.json"):
        if not (root / relative).is_file():
            raise ValueError(f"Missing {relative}; initialize knowledge through a capable SDD producer before the initial commit.")
    manifest = json.loads((root / ".config/dotnet-tools.json").read_text())
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tools"), dict):
        raise ValueError("The root local tool manifest must contain a tools object.")
    tool = manifest["tools"].get("fs.gg.sdd.cli", {})
    if not isinstance(tool, dict) or not isinstance(tool.get("commands"), list):
        raise ValueError("The root local tool manifest must pin FS.GG.SDD.Cli.")
    version = tool.get("version", "")
    if type(manifest.get("version")) is not int or manifest["version"] != 1 or manifest.get("isRoot") is not True or "fsgg-sdd" not in tool["commands"]:
        raise ValueError("The root local tool manifest must pin FS.GG.SDD.Cli with the fsgg-sdd command.")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise ValueError("FS.GG.SDD.Cli requires an exact local tool version; floating or absent pins refuse.")
    if args.preflight:
        print(json.dumps({"outcome": "preflight-passed", "pinnedVersion": version}))
        return
    command = json.loads(args.command_json) if args.command_json else ["dotnet", "tool", "run", "fsgg-sdd"]
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError("Source-candidate qualification requires a nonempty argv array.")
    result = subprocess.run(command + ["knowledge", "check", "--root", str(root)], cwd=root,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError("Producer knowledge check refused: " + (result.stderr or result.stdout).strip())
    size = json.loads(result.stdout)
    if size.get("Limit") != 10485760 or type(size.get("Bytes")) is not int or not 0 < size["Bytes"] <= size["Limit"]:
        raise ValueError("Producer returned an unsupported or invalid knowledge size report.")
    print(json.dumps({"outcome": "passed", "pinnedVersion": version, "bytes": size["Bytes"], "limit": size["Limit"],
                      "sourceCandidateOverride": args.command_json is not None}))


if __name__ == "__main__":
    try:
        run()
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print("project-knowledge: " + str(error), file=sys.stderr)
        raise SystemExit(1)
