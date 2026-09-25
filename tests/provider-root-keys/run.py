#!/usr/bin/env python3
"""Copied-descriptor parity for unsupported and repeated YAML roots."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

for name, extra, diagnostic in [
    ("foreign root", "foreignRoot: yes\n", "root key"),
    ("duplicate schema root", "schemaVersion: 1\n", "schemaVersion"),
    ("duplicate providers root", "providers: []\n", "providers"),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-provider-root-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        web = providers / "web.providers.yml"
        web.write_text(web.read_text() + extra)
        commands = [
            ("F#", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                     "--", "grade", "--providers", str(providers), "--registry", str(REGISTRY)]),
            ("Python", ["python3", str(CHECKER), "--providers", str(providers),
                        "--registry", str(REGISTRY)]),
        ]
        for owner, command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            combined = result.stdout + result.stderr
            if result.returncode == 0 or diagnostic not in combined:
                raise AssertionError(f"{name}: {owner} did not refuse with {diagnostic!r}; "
                                     f"exit={result.returncode}, output={combined[-1200:]!r}")
        print(f"PASS {name}: F# and Python refuse")
