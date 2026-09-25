#!/usr/bin/env python3
"""Offline repeated default-field controls for both provider readers."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"
WEB = (ROOT / "providers/web.providers.yml").read_text(encoding="utf-8")
NEEDLE = "        default: sdd\n"
assert WEB.count(NEEDLE) == 1, "live web parameter fixture shape changed"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("valid live default", WEB, True),
    ("valid quoted default", WEB.replace(NEEDLE, '        default: "sdd"\n'), True),
    ("repeated equal default", WEB.replace(NEEDLE, NEEDLE + "        default: sdd\n"), False),
    ("repeated conflicting default", WEB.replace(NEEDLE, NEEDLE + "        default: spec-kit\n"), False),
]
failures = []
for label, replacement, accepted in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-default-duplicate-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        (providers / "web.providers.yml").write_text(replacement, encoding="utf-8")
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
                failures.append(f"{label}: {owner} refused valid descriptor: {combined[-900:]!r}")
            if not accepted and (result.returncode == 0 or "repeated parameter field 'default'" not in combined):
                failures.append(f"{label}: {owner} admitted repeated default or wrong refusal: "
                                f"exit={result.returncode}, output={combined[-900:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: both readers agree")

if failures:
    raise AssertionError("\n".join(failures))
