#!/usr/bin/env python3
"""Copied-descriptor parity for repeated provider names."""

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


def duplicate_in_file(providers: Path) -> None:
    descriptor = providers / "console.providers.yml"
    text = descriptor.read_text()
    entry = "  - name: console"
    assert text.count(entry) == 1
    descriptor.write_text(text.rstrip("\n") + "\n" + entry + text.split(entry, 1)[1])


def duplicate_across_files(providers: Path) -> None:
    shutil.copy2(providers / "web.providers.yml", providers / "copy.providers.yml")


for name, mutate in [
    ("same descriptor", duplicate_in_file),
    ("different descriptors", duplicate_across_files),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-provider-identity-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        mutate(providers)
        commands = [
            ("F#", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                     "--", "grade", "--providers", str(providers), "--registry", str(REGISTRY)]),
            ("Python", ["python3", str(CHECKER), "--providers", str(providers),
                        "--registry", str(REGISTRY)]),
        ]
        for owner, command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            combined = result.stdout + result.stderr
            if result.returncode == 0 or "provider names must be unique" not in combined:
                raise AssertionError(f"{name}: {owner} did not refuse repeated provider names; "
                                     f"exit={result.returncode}, output={combined[-1200:]!r}")
        print(f"PASS {name}: F# and Python refuse repeated provider names")
