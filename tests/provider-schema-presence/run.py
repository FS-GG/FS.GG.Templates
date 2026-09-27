#!/usr/bin/env python3
"""Copied-descriptor controls for required, leading provider schema declaration."""

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

for name, transform, accepted, diagnostic in [
    ("selected leading schema", lambda t: t.replace("schemaVersion: 1", "# lead\n\nschemaVersion: 1 # selected", 1),
     True, ""),
    ("missing schema", lambda t: t.replace("schemaVersion: 1\n", "", 1),
     False, "providers appear before schemaVersion: 1"),
    ("schema after providers", lambda t: t.replace("schemaVersion: 1\n", "", 1).rstrip("\n") + "\nschemaVersion: 1\n",
     False, "providers appear before schemaVersion: 1"),
]:
    with tempfile.TemporaryDirectory(prefix="fsc05-schema-presence-") as folder:
        providers = Path(folder) / "providers"
        shutil.copytree(ROOT / "providers", providers)
        web = providers / "web.providers.yml"
        before = web.read_text(encoding="utf-8")
        assert before.count("schemaVersion: 1\n") == 1
        after = transform(before)
        assert after != before
        web.write_text(after, encoding="utf-8")
        for owner, command in [
            ("F#", ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
                    "--", "grade", "--providers", str(providers), "--registry", str(REGISTRY)]),
            ("Python", ["python3", str(CHECKER), "--providers", str(providers),
                        "--registry", str(REGISTRY)]),
        ]:
            result = subprocess.run(command, capture_output=True, text=True)
            output = result.stdout + result.stderr
            if accepted and result.returncode != 0:
                raise AssertionError(f"{name}: {owner} refused selected descriptor: {output[-1200:]!r}")
            if not accepted and (result.returncode == 0 or diagnostic not in output):
                raise AssertionError(f"{name}: {owner} admitted unsupported descriptor or gave wrong diagnostic: "
                                     f"exit={result.returncode}, output={output[-1200:]!r}")
        print(f"PASS {name}: F# and Python agree")
