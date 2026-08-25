#!/usr/bin/env python3
"""Validate the lifecycle contract across every provider and owned template.

This is intentionally descriptor-driven: adding a provider makes it part of the gate. Rendering's
template is upstream, so its published 0.28.0 contract is represented by the descriptor and proved
again by the installed-product composition stage. The four templates owned here are checked directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

LANES = ("none", "sdd", "typed-sdd")
PROVIDER = re.compile(r"^  - name:\s*(\S+)", re.MULTILINE)
TEMPLATE = re.compile(r"^    templateId:\s*(\S+)", re.MULTILINE)
LIFECYCLE = re.compile(
    r"^      - key:\s*lifecycle\s*$\n"
    r"^        required:\s*false\s*$\n"
    r"^        default:\s*sdd\s*$",
    re.MULTILINE,
)
FLOOR = re.compile(r'^      version:\s*"1\.4\.0-preview\.1"', re.MULTILINE)


def inspect(root: Path) -> list[str]:
    failures: list[str] = []
    descriptors = sorted((root / "providers").glob("*.providers.yml"))
    if not descriptors:
        return ["lifecycle.contractNoProviders"]

    for descriptor in descriptors:
        text = descriptor.read_text(encoding="utf-8")
        provider = PROVIDER.search(text)
        template = TEMPLATE.search(text)
        label = provider.group(1) if provider else descriptor.name
        if not provider or not template:
            failures.append(f"lifecycle.descriptorUnreadable:{label}")
            continue
        if not LIFECYCLE.search(text):
            failures.append(f"lifecycle.parameterMissingOrWrongDefault:{label}")
        if not FLOOR.search(text):
            failures.append(f"lifecycle.minimumCompilerWrong:{label}")

        template_id = template.group(1)
        owned = root / "templates" / template_id / ".template.config" / "template.json"
        if not owned.exists():
            if label != "rendering":
                failures.append(f"lifecycle.templateMissing:{label}:{template_id}")
            continue
        try:
            symbols = json.loads(owned.read_text(encoding="utf-8"))["symbols"]
            lifecycle = symbols["lifecycle"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            failures.append(f"lifecycle.templateSymbolUnreadable:{label}")
            continue
        choices = tuple(item.get("choice") for item in lifecycle.get("choices", []))
        if lifecycle.get("type") != "parameter" or lifecycle.get("datatype") != "choice":
            failures.append(f"lifecycle.templateSymbolWrongKind:{label}")
        if lifecycle.get("defaultValue") != "sdd":
            failures.append(f"lifecycle.templateDefaultWrong:{label}")
        if choices != LANES:
            failures.append(f"lifecycle.templateChoicesWrong:{label}")
    return failures


def self_test(root: Path) -> list[str]:
    cases = (
        ("dropped-provider-parameter", "lifecycle.parameterMissingOrWrongDefault", lambda p: p.write_text(p.read_text().replace("      - key: lifecycle", "      - key: dropped"))),
        ("wrong-provider-default", "lifecycle.parameterMissingOrWrongDefault", lambda p: p.write_text(p.read_text().replace("        default: sdd", "        default: none"))),
        ("missing-template-choice", "lifecycle.templateChoicesWrong", lambda p: p.write_text(p.read_text().replace('{ "choice": "typed-sdd", "description": "Standard SDD plus the Typed Protocol Kernel." }', '{ "choice": "sdd", "description": "aliased" }'))),
        ("wrong-template-default", "lifecycle.templateDefaultWrong", lambda p: p.write_text(p.read_text().replace('"defaultValue": "sdd"', '"defaultValue": "none"'))),
    )
    failures: list[str] = []
    for name, expected, mutate in cases:
        with tempfile.TemporaryDirectory(prefix="fsgg-lifecycle-contract-") as temporary:
            fixture = Path(temporary)
            shutil.copytree(root / "providers", fixture / "providers")
            shutil.copytree(root / "templates", fixture / "templates")
            target = fixture / ("providers/console.providers.yml" if "provider" in name else "templates/fs-gg-console/.template.config/template.json")
            mutate(target)
            diagnostics = inspect(fixture)
            if not any(item.startswith(expected) for item in diagnostics):
                failures.append(f"lifecycle.selfTestDidNotFire:{name}:{expected}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    failures = inspect(args.root)
    if args.self_test:
        failures.extend(self_test(args.root))
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print(f"PASS lifecycle contract: {len(list((args.root / 'providers').glob('*.providers.yml')))} providers; lanes={','.join(LANES)}; omitted=sdd")
    if args.self_test:
        print("PASS lifecycle contract self-test: every mutation class fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
