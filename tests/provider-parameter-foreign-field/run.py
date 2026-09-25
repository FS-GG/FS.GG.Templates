#!/usr/bin/env python3
"""Offline foreign parameter-field controls for both provider readers."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"
WEB = (ROOT / "providers/web.providers.yml").read_text(encoding="utf-8")
NEEDLE = "      - key: lifecycle\n        required: false\n"
assert WEB.count(NEEDLE) == 1, "live web parameter fixture shape changed"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("valid live parameter fields", WEB, None),
    ("valid quoted default", WEB.replace("        default: sdd\n", '        default: "sdd"\n', 1), None),
    ("foreign optional field", WEB.replace(NEEDLE, NEEDLE + "        optional: true\n"),
     "malformed parameter field"),
    ("foreign provider field", WEB.replace(NEEDLE, NEEDLE + "        provider: web\n"),
     "malformed parameter field"),
    ("default with trailing tokens", WEB.replace("        default: sdd\n", "        default: sdd extra\n", 1),
     "unsupported text after scalar"),
]
failures = []
for label, replacement, refusal in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-parameter-foreign-") as folder:
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
                failures.append(f"{label}: {owner} admitted foreign parameter field or wrong refusal: "
                                f"exit={result.returncode}, output={combined[-900:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: both readers agree")

if failures:
    raise AssertionError("\n".join(failures))
