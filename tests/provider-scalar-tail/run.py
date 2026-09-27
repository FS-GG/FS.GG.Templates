#!/usr/bin/env python3
"""Compare copied live descriptor/registry scalar refusals in both provider readers."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
SELECTED = '      version: "1.4.0-preview.1"'
REGISTRY_TEXT = "contracts:\n  - id: fs-gg-ui-template\n    minimum-fsgg-sdd:\n" + SELECTED + "\n"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)


def run(providers: Path, registry: Path, accepted: bool, label: str) -> None:
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
            raise AssertionError(f"{label}: {owner} refused accepted scalar: {combined[-1200:]!r}")
        if not accepted and (result.returncode == 0 or "unsupported text after" not in combined):
            raise AssertionError(f"{label}: {owner} admitted foreign scalar text or wrong refusal: "
                                 f"exit={result.returncode}, output={combined[-1200:]!r}")
    print(f"PASS {label}: F# and Python agree")


for label, replacement, accepted in [
    ("selected quoted", SELECTED, True),
    ("quoted comment", SELECTED + " # selected", True),
    ("unquoted comment", "      version: 1.4.0-preview.1 # selected", True),
    ("quoted foreign suffix", SELECTED + " foreign", False),
    ("unquoted foreign suffix", "      version: 1.4.0-preview.1 foreign", False),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-scalar-tail-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        registry = Path(folder) / "registry.yml"
        registry.write_text(REGISTRY_TEXT, encoding="utf-8")
        web = providers / "web.providers.yml"
        text = web.read_text(encoding="utf-8")
        if text.count(SELECTED) != 1:
            raise AssertionError("selected web descriptor floor occurrence changed")
        web.write_text(text.replace(SELECTED, replacement, 1), encoding="utf-8")
        run(providers, registry, accepted, label)

with tempfile.TemporaryDirectory(prefix="fsc05-registry-scalar-") as folder:
    providers = Path(folder) / "providers"
    shutil.copytree(ROOT / "providers", providers)
    registry = Path(folder) / "registry.yml"
    registry.write_text(REGISTRY_TEXT.replace(SELECTED, SELECTED + " foreign"), encoding="utf-8")
    run(providers, registry, False, "registry quoted foreign suffix")
