#!/usr/bin/env python3
"""Copied-descriptor parity for the selected provider schema spelling."""

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

for name, spelling, accepted in [
    ("selected schema with comment", "schemaVersion: 1 # selected", True),
    ("unsupported schema", "schemaVersion: 2", False),
    ("quoted schema", 'schemaVersion: "1"', False),
    ("trailing schema tokens", "schemaVersion: 1 garbage", False),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-schema-version-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        web = providers / "web.providers.yml"
        text = web.read_text()
        assert text.count("schemaVersion: 1") == 1
        web.write_text(text.replace("schemaVersion: 1", spelling, 1))
        commands = [
            ("F#", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                     "--", "grade", "--providers", str(providers), "--registry", str(REGISTRY)]),
            ("Python", ["python3", str(CHECKER), "--providers", str(providers),
                        "--registry", str(REGISTRY)]),
        ]
        for owner, command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            combined = result.stdout + result.stderr
            if accepted and result.returncode != 0:
                raise AssertionError(f"{name}: {owner} refused selected spelling: {combined[-1200:]!r}")
            if not accepted and (result.returncode == 0 or "unsupported schemaVersion root" not in combined):
                raise AssertionError(f"{name}: {owner} admitted unsupported spelling; "
                                     f"exit={result.returncode}, output={combined[-1200:]!r}")
        print(f"PASS {name}: F# and Python agree")
