#!/usr/bin/env python3
"""Disposable provider routing-metadata refusals for the F# source candidate."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
SOURCE = ROOT / "providers/web.providers.yml"
REGISTRY = ROOT.parent / ".github/registry/dependencies.yml"

subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
               check=True, capture_output=True, text=True)


def check(name: str, original: str, replacement: str, diagnostic: str) -> None:
    with tempfile.TemporaryDirectory(prefix="fsc05-routing-") as folder:
        descriptor = Path(folder) / "web.providers.yml"
        source = SOURCE.read_text()
        assert source.count(original) == 1, f"fixture source shape changed: {name}"
        descriptor.write_text(source.replace(original, replacement, 1))
        result = subprocess.run(
            ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
             "--", "workspace-check", "--providers", str(ROOT / "providers"),
             "--workspace", str(descriptor), "--registry", str(REGISTRY)],
            capture_output=True, text=True,
        )
        if result.returncode == 0 or diagnostic not in result.stderr:
            raise AssertionError(f"{name}: expected refusal containing {diagnostic!r}; "
                                 f"exit={result.returncode}, stderr={result.stderr!r}")
        print(f"PASS {name}")


check("name route drift", "nameParameter: productName", "nameParameter: otherName",
      "provider 'web' differs from source descriptor")
check("identifier route drift", "identifierParameter: rootNamespace",
      "identifierParameter: otherNamespace", "provider 'web' differs from source descriptor")
check("duplicate route key", "nameParameter: productName",
      "nameParameter: productName\n    nameParameter: otherName", "repeats nameParameter")
check("empty route value", "identifierParameter: rootNamespace",
      "identifierParameter: # missing", "expected a scalar value")
