#!/usr/bin/env python3
"""Assert that installed scaffold provenance records the selected descriptor's exact floor.

The live registry equality check remains separate. Reuse its descriptor parser so this
assertion neither invents a floor nor accepts an unreadable/ambiguous descriptor.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def check(descriptor: Path, provenance: Path, provider: str, repo: Path) -> str:
    spec = importlib.util.spec_from_file_location("provider_floors", repo / "scripts/check-provider-floors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.parse_descriptor(descriptor)
    selected = [floor for name, floor, _ in rows if name == provider]
    if len(selected) != 1 or selected[0] is None:
        raise ValueError(f"{provider}: expected exactly one declared minimumFsggSdd.version in {descriptor}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{provider}: duplicate provenance key {key}")
            result[key] = value
        return result

    observed = json.loads(provenance.read_text(encoding="utf-8"), object_pairs_hook=unique).get("requiredMinimumCliVersion")
    expected = selected[0]
    if observed != expected:
        raise ValueError(f"{provider}: provenance requiredMinimumCliVersion={observed!r}; "
                         f"descriptor minimumFsggSdd.version={expected!r} ({descriptor})")
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    try:
        check(args.descriptor, args.provenance, args.provider, args.repo)
    except Exception as error:
        print(f"lifecycle matrix: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
