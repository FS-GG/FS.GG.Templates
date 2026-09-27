#!/usr/bin/env python3
"""Offline missing required-field controls for both provider readers."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"
WEB = (ROOT / "providers/web.providers.yml").read_text(encoding="utf-8")
FIRST = "      - key: productName\n        required: true\n"
LAST = "      - key: lifecycle\n        required: false\n"
assert WEB.count(FIRST) == WEB.count(LAST) == 1, "live web parameter fixture shape changed"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("valid live required fields", WEB, None),
    ("quoted valid required field", WEB.replace(LAST, LAST.replace("false", '"false"')), None),
    ("missing first required field", WEB.replace(FIRST, "      - key: productName\n"), "productName"),
    ("missing last required field", WEB.replace(LAST, "      - key: lifecycle\n"), "lifecycle"),
]
failures = []
for label, replacement, missing_key in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-required-presence-") as folder:
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
            if missing_key is None and result.returncode != 0:
                failures.append(f"{label}: {owner} refused valid descriptor: {combined[-900:]!r}")
            if missing_key is not None and (result.returncode == 0
                                            or f"parameter '{missing_key}' needs required: true|false" not in combined):
                failures.append(f"{label}: {owner} admitted missing required or wrong refusal: "
                                f"exit={result.returncode}, output={combined[-900:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: both readers agree")

if failures:
    raise AssertionError("\n".join(failures))
