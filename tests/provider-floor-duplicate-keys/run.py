#!/usr/bin/env python3
"""Copied-descriptor parity for duplicate provider floor declarations."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/check-provider-floors.py"
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)


def duplicate_version(text: str) -> str:
    result, count = re.subn(r'(      version: "[^"]+"\n)', r'\1      version: "9.9.9"\n', text, count=1)
    assert count == 1
    return result


def duplicate_block(text: str) -> str:
    start = text.index("    minimumFsggSdd:\n")
    end = text.index("    parameters:\n", start)
    return text[:end] + text[start:end] + text[end:]


for name, mutate, diagnostic in [
    ("duplicate version", duplicate_version, "minimumFsggSdd.version"),
    ("duplicate floor block", duplicate_block, "minimumFsggSdd"),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-floor-duplicate-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        web = providers / "web.providers.yml"
        web.write_text(mutate(web.read_text()))
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
        print(f"PASS {name}: F# and Python both refuse")
