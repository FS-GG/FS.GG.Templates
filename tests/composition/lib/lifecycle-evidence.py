#!/usr/bin/env python3
"""Run the installed-package lifecycle acceptance matrix and emit JUnit evidence."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET


def run_case(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> tuple[str, float, str, str]:
    started = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    elapsed = time.monotonic() - started
    output = (completed.stdout + completed.stderr)[-16000:]
    failure = "" if completed.returncode == 0 else f"exit {completed.returncode}"
    return name, elapsed, output, failure


def matrix_script(root: Path, archive: Path, provider: str, parameters: list[str], dotnet_root: Path, controls: bool = False) -> str:
    quoted_parameters = " ".join(parameters)
    controls_command = 'assert_typed_lifecycle_controls "$work/typed-sdd" "$tmp/controls"' if controls else ":"
    return f"""
set -euo pipefail
export DOTNET_ROOT={dotnet_root}
export PATH={dotnet_root}:$PATH
LANE_REPO_ROOT={root}
. {root}/tests/composition/lib/lane-package.sh
. {root}/tests/composition/lib/lifecycle-matrix.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export DOTNET_CLI_HOME="$tmp/dotnet-home"
mkdir -p "$DOTNET_CLI_HOME"
dotnet new install {archive} >/dev/null
work="$tmp/{provider}"
assert_provider_lifecycle_matrix {provider} {archive} "$work" {quoted_parameters}
{controls_command}
"""


def tree_equivalence_script(root: Path) -> str:
    return f"""
set -euo pipefail
. {root}/tests/composition/lib/lifecycle-matrix.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
assert_lifecycle_tree_equivalence_can_fire "$tmp"
"""


def rendering_script(root: Path, parameters: list[str], label: str) -> str:
    quoted_parameters = " ".join(parameters)
    return f"""
set -euo pipefail
LANE_REPO_ROOT={root}
. {root}/tests/composition/lib/lane-package.sh
. {root}/tests/composition/lib/lifecycle-matrix.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export DOTNET_CLI_HOME="$tmp/dotnet-home"
mkdir -p "$DOTNET_CLI_HOME"
assert_provider_lifecycle_matrix rendering published "$tmp/{label}" {quoted_parameters}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sdd", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    archive = args.archive.resolve()
    default_dotnet = Path(shutil.which("dotnet") or "/usr/share/dotnet/dotnet").resolve().parent
    env = os.environ.copy()
    system_dotnet = Path("/usr/share/dotnet")
    dotnet_path = f"{system_dotnet}:" if (system_dotnet / "dotnet").exists() else ""
    env["PATH"] = f"{args.sdd.resolve().parent}:{dotnet_path}{env['PATH']}"
    if dotnet_path:
        env["DOTNET_ROOT"] = str(system_dotnet)
    dotnet_400 = system_dotnet if (system_dotnet / "sdk/10.0.400").is_dir() else default_dotnet
    dotnet_302 = default_dotnet if (default_dotnet / "sdk/10.0.302").is_dir() else dotnet_400

    cases: list[tuple[str, list[str]]] = [
        ("static lifecycle contract and mutation controls", ["python3", str(root / "tests/composition/lib/lifecycle-contract.py"), "--self-test"]),
        ("omitted lifecycle tree equivalence mutation control", ["bash", "-c", tree_equivalence_script(root)]),
        ("provider floors and mutation controls", ["python3", str(root / "scripts/check-provider-floors.py"), "--registry", str(args.registry.resolve())]),
        ("release candidate archive and dual-feed mechanism preflight", ["python3", str(root / "tests/composition/lib/release-preflight.py"), "--self-test", "--archive", str(archive), "--workflow", str(root / ".github/workflows/release.yml")]),
        ("console installed-package lifecycle matrix", ["bash", "-c", matrix_script(root, archive, "console", ["productName=MatrixConsole", "rootNamespace=MatrixConsole"], dotnet_400, True)]),
        ("web installed-package lifecycle matrix", ["bash", "-c", matrix_script(root, archive, "web", ["productName=MatrixWeb", "rootNamespace=MatrixWeb"], dotnet_400)]),
        ("fable-game installed-package lifecycle matrix", ["bash", "-c", matrix_script(root, archive, "fable-game", ["productName=MatrixGame", "rootNamespace=MatrixGame"], dotnet_400)]),
        ("fable-bindings installed-package lifecycle matrix", ["bash", "-c", matrix_script(root, archive, "fable-bindings", ["productName=MatrixBindings", "rootNamespace=MatrixBindings"], dotnet_302)]),
        ("rendering game published-package lifecycle matrix", ["bash", "-c", rendering_script(root, ["productName=MatrixRenderGame", "rootNamespace=MatrixRenderGame", "profile=game", "designSystem=wcag"], "rendering-game")]),
        ("rendering app published-package lifecycle matrix", ["bash", "-c", rendering_script(root, ["productName=MatrixRenderApp", "rootNamespace=MatrixRenderApp", "profile=app", "designSystem=wcag"], "rendering-app")]),
    ]

    results = [run_case(name, command, root, env) for name, command in cases]
    failures = sum(1 for _, _, _, failure in results if failure)
    suite = ET.Element("testsuite", name="typed-sdd-p4-templates", tests=str(len(results)), failures=str(failures), errors="0", skipped="0", time=f"{sum(item[1] for item in results):.3f}")
    for name, elapsed, output, failure in results:
        case = ET.SubElement(suite, "testcase", classname="FS.GG.Templates.TypedSddP4", name=name, time=f"{elapsed:.3f}")
        if failure:
            ET.SubElement(case, "failure", message=failure).text = output
        ET.SubElement(case, "system-out").text = output

    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(args.output, encoding="utf-8", xml_declaration=True)
    print(f"lifecycle evidence: {len(results) - failures}/{len(results)} passed; report={args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
