#!/usr/bin/env python3
"""Read-only grade and workspace-selection boundary for parameter names."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"
WEB = (ROOT / "providers/web.providers.yml").read_text(encoding="utf-8")
NEEDLE = "      - key: lifecycle\n"
assert WEB.count(NEEDLE) == 1, "live web parameter fixture shape changed"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("valid live name", WEB, None),
    ("valid quoted name", WEB.replace(NEEDLE, '      - key: "lifecycle"\n'), None),
    ("hyphenated name", WEB.replace(NEEDLE, "      - key: life-cycle\n"), "life-cycle"),
    ("digit-leading name", WEB.replace(NEEDLE, '      - key: "9lifecycle"\n'), "9lifecycle"),
]
failures = []
for label, replacement, invalid_key in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-parameter-name-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        workspace = providers / "web.providers.yml"
        workspace.write_text(replacement, encoding="utf-8")
        commands = [
            ("F# grade", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                           "--", "grade", "--providers", str(providers), "--registry", str(REGISTRY)]),
            ("F# workspace", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                               "--", "workspace-check", "--providers", str(providers),
                               "--workspace", str(workspace), "--registry", str(REGISTRY)]),
            ("Python grade", ["python3", str(CHECKER), "--providers", str(providers),
                              "--registry", str(REGISTRY)]),
        ]
        for owner, command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            combined = result.stdout + result.stderr
            if invalid_key is None and result.returncode != 0:
                failures.append(f"{label}: {owner} refused valid descriptor: {combined[-900:]!r}")
            if invalid_key is not None and (result.returncode == 0
                                            or f"invalid parameter '{invalid_key}'" not in combined):
                failures.append(f"{label}: {owner} admitted invalid name or wrong refusal: "
                                f"exit={result.returncode}, output={combined[-900:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: all three readers agree")

if failures:
    raise AssertionError("\n".join(failures))
