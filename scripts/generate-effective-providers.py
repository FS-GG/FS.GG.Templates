#!/usr/bin/env python3
"""Generate the concise effective-provider view in a provider descriptor.

The descriptor intentionally retains its long, hand-authored release history. This script owns only
the small generated block near the current pin. It parses the narrow provider-list shape without a
third-party YAML dependency, validates that provider names are unique and ordinally sorted, and then
renders the current selection deterministically.

DECIDED, AND THE ANSWER IS NO: `minimumFsggSdd` DOES NOT JOIN THE GENERATED SUMMARY
(FS.GG.Templates#383, which asked for this either way with the reason recorded). The argument for
adding it is that a floor drifting away from the org registry pin would then show up in a reviewable
diff. Three measured reasons it is the wrong control here:

  1. IT WOULD COVER TWO DESCRIPTORS OF FIVE — the same partial coverage #383 exists to remove. Only
     `rendering` and `fable-bindings` carry a `BEGIN GENERATED: effective-providers` block;
     `console`, `web` and `fable-game` deliberately carry none because they are not yet
     registry-active providers, and `fable-game.providers.yml` says so in its own header. Putting the
     floor in the generated block would make it visible for exactly the descriptors that already
     had the most attention, and invisible for the three that did not.
  2. THE STALENESS CHECK IS ALSO PARTIAL. `--check` is run from
     tests/composition/stages/04-verify.sh against the LANE's descriptor, not against the set, so
     "it would be in a checked file" does not mean "it would be checked" for every descriptor.
  3. A VISIBLE DIFF IS NOT A CONTROL, and this repository has already paid for treating it as one:
     the floor's single-descriptor scope was written down in composition.yml's own source, asking a
     future author to widen it "in the same change", and four descriptors were then added by three
     items without anyone widening it. What replaces that is scripts/check-provider-floors.py — a
     required check that reads every descriptor, grades it against the live registry pin, and is
     demonstrated to fail (`--self-test`). It renders the same values into the job's step summary on
     every run, so the visibility argument is satisfied without a second, weaker copy of the value.

If a descriptor's floor is ever wrong, the red comes from that checker and names the file, the
provider, the declared value and the registry value. Do not add a duplicate here.
"""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import re
import sys
import tempfile


BEGIN = "# BEGIN GENERATED: effective-providers"
END = "# END GENERATED: effective-providers"
PROVIDER = re.compile(r"^  - name:\s*(\S+)\s*(?:#.*)?$")
FIELD = re.compile(r"^    (contractVersion|templateId|source):\s*(.*?)\s*$")
REQUIRED = ("contractVersion", "templateId", "source")


class DescriptorError(ValueError):
    pass


def scalar(raw: str, line_number: int) -> str:
    """Read the simple scalar spellings used by the effective provider fields."""
    if not raw:
        raise DescriptorError(f"line {line_number}: provider field has no value")

    if raw[0] in "\"'":
        quote = raw[0]
        closing = raw.find(quote, 1)
        if closing < 0:
            raise DescriptorError(f"line {line_number}: unterminated quoted provider field")
        tail = raw[closing + 1 :].strip()
        if tail and not tail.startswith("#"):
            raise DescriptorError(f"line {line_number}: unsupported text after quoted provider field")
        return raw[1:closing]

    tokens = raw.split("#", 1)[0].strip().split()
    if not tokens:
        raise DescriptorError(f"line {line_number}: expected a scalar value")
    return tokens[0]


def parse_providers(lines: list[str]) -> list[dict[str, str]]:
    providers: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line_number, line in enumerate(lines, 1):
        match = PROVIDER.match(line)
        if match:
            current = {"name": match.group(1)}
            providers.append(current)
            continue

        match = FIELD.match(line)
        if match and current is not None:
            field, raw = match.groups()
            if field in current:
                raise DescriptorError(
                    f"line {line_number}: provider '{current['name']}' repeats field '{field}'"
                )
            current[field] = scalar(raw, line_number)

    if not providers:
        raise DescriptorError("descriptor has no providers")

    names = [provider["name"] for provider in providers]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise DescriptorError(f"provider names must be unique; duplicate(s): {', '.join(duplicates)}")

    ordered = sorted(names)
    if names != ordered:
        raise DescriptorError(
            "providers must be ordered by name; "
            f"found {', '.join(names)}, expected {', '.join(ordered)}"
        )

    for provider in providers:
        missing = [field for field in REQUIRED if field not in provider]
        if missing:
            raise DescriptorError(
                f"provider '{provider['name']}' is missing: {', '.join(missing)}"
            )

    return providers


def render(providers: list[dict[str, str]]) -> list[str]:
    result = [
        "# Effective providers — generated; ordered by unique provider name.",
        "# Review this block for the current selection; the release narrative remains in PIN HISTORY.",
    ]
    for index, provider in enumerate(providers, 1):
        result.append(
            f"# effective[{index}]: name={provider['name']} | "
            f"template={provider['templateId']} | source={provider['source']} | "
            f"contract={provider['contractVersion']}"
        )
    return result


def replace_region(lines: list[str], generated: list[str]) -> list[str]:
    begins = [index for index, line in enumerate(lines) if line == BEGIN]
    ends = [index for index, line in enumerate(lines) if line == END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise DescriptorError(
            f"descriptor must contain exactly one ordered '{BEGIN}' / '{END}' marker pair"
        )
    return lines[: begins[0] + 1] + generated + lines[ends[0] :]


def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "providers" / "rendering.providers.yml",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    try:
        original = args.provider.read_text(encoding="utf-8")
        lines = original.splitlines()
        expected_lines = replace_region(lines, render(parse_providers(lines)))
        expected = "\n".join(expected_lines) + ("\n" if original.endswith("\n") else "")
    except (OSError, DescriptorError) as error:
        print(f"effective-providers: {error}", file=sys.stderr)
        return 1

    if args.check:
        if original == expected:
            print(
                f"effective-providers: current — {len(parse_providers(lines))} ordered unique provider(s)"
            )
            return 0
        print(
            "effective-providers: generated summary is stale; "
            "run scripts/generate-effective-providers.py --write",
            file=sys.stderr,
        )
        sys.stderr.writelines(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=str(args.provider),
                tofile=f"{args.provider} (generated)",
            )
        )
        return 1

    write_atomic(args.provider, expected)
    print(
        f"effective-providers: wrote {len(parse_providers(expected_lines))} "
        f"ordered unique provider(s) to {args.provider}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
