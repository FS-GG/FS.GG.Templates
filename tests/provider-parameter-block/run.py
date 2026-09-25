#!/usr/bin/env python3
"""Offline duplicate parameter-block controls for both provider readers."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"
WEB = (ROOT / "providers/web.providers.yml").read_text(encoding="utf-8")

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("valid live descriptor", WEB, None),
    ("duplicate parameters after values", WEB + "    parameters:\n", "repeated parameters"),
    ("duplicate parameters before values", WEB.replace(
        "    parameters:\n", "    parameters:\n    parameters:\n", 1), "repeated parameters"),
    ("inline parameters collection", WEB.replace(
        "    parameters:\n", "    parameters: []\n", 1), "parameters must be a block sequence"),
]
failures = []
for label, replacement, refusal in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-parameter-block-") as folder:
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
            if refusal is None and result.returncode != 0:
                failures.append(f"{label}: {owner} refused valid descriptor: {combined[-900:]!r}")
            if refusal is not None and (result.returncode == 0 or refusal not in combined):
                failures.append(f"{label}: {owner} admitted duplicate or wrong refusal: "
                                f"exit={result.returncode}, output={combined[-900:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: both readers agree")

if failures:
    raise AssertionError("\n".join(failures))
