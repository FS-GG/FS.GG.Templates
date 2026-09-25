#!/usr/bin/env python3
"""Refuse duplicate selected contract identities even when one has no floor."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
PIN = "1.4.0-preview.1"


def contract(identity: str, pin: str | None) -> str:
    lines = [f"  - id: {identity}\n"]
    if pin is not None:
        lines += ["    minimum-fsgg-sdd:\n", f'      version: "{pin}"\n']
    return "".join(lines)


subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)

cases = [
    ("one selected contract", [contract("fs-gg-ui-template", PIN)], True),
    ("foreign neighbors", [contract("unrelated", "9.9.9"),
                           contract("fs-gg-ui-template", PIN),
                           contract("another", None)], True),
    ("same id in coherence root", [contract("fs-gg-ui-template", PIN),
                                   "coherence:\n" + contract("fs-gg-ui-template", None)], True),
    ("duplicate selected second unpinned", [contract("fs-gg-ui-template", PIN),
                                            contract("fs-gg-ui-template", None)], False),
    ("duplicate selected first unpinned", [contract("fs-gg-ui-template", None),
                                           contract("fs-gg-ui-template", PIN)], False),
    ("duplicate selected both unpinned", [contract("fs-gg-ui-template", None),
                                          contract("fs-gg-ui-template", None)], False),
]

failures = []
for label, contracts, accepted in cases:
    with tempfile.TemporaryDirectory(prefix="fsc05-registry-identity-") as folder:
        folder = Path(folder)
        providers = folder / "providers"
        shutil.copytree(ROOT / "providers", providers)
        registry = folder / "registry.yml"
        registry.write_text("contracts:\n" + "".join(contracts), encoding="utf-8")
        commands = [
            ("F#", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                    "--", "grade", "--providers", str(providers), "--registry", str(registry)]),
            ("Python", ["python3", str(CHECKER), "--providers", str(providers),
                        "--registry", str(registry)]),
        ]
        for owner, command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            combined = result.stdout + result.stderr
            if accepted and result.returncode != 0:
                failures.append(f"{label}: {owner} refused selected registry: {combined[-1200:]!r}")
            if not accepted and (result.returncode == 0
                                 or "duplicate selected registry contract id" not in combined):
                failures.append(f"{label}: {owner} admitted duplicate selected identity or wrong "
                                f"refusal: exit={result.returncode}, output={combined[-1200:]!r}")
        if not any(item.startswith(label + ":") for item in failures):
            print(f"PASS {label}: F# and Python agree")

if failures:
    raise AssertionError("\n".join(failures))
