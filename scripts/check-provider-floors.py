#!/usr/bin/env python3
"""Grade EVERY provider descriptor's `minimumFsggSdd` floor against the org-wide registry pin.

WHY THIS EXISTS (FS.GG.Templates#383). `providers/` holds five descriptors and every one of them
declares a `minimumFsggSdd.version`. Until this script, exactly ONE of them was read by anything:
`.github/workflows/composition.yml` hard-coded `PROVIDER_DESCRIPTOR='providers/rendering.providers.yml'`,
so `console`, `web`, `fable-bindings` and `fable-game` could carry a floor that was wrong, stale, or
entirely absent while every required check stayed green. That is not hypothetical — it already
produced a defect: `providers/web.providers.yml` shipped with NO `minimumFsggSdd` block at all, from
the day it was authored until FS.GG.Templates#381's round-1 repair, so a product scaffolded through
the `web` provider received no `scaffold.cliBehindMinimum` warning on an under-floor CLI while its
three siblings did. Nothing detected that for the whole life of the descriptor.

THE GAP WAS PRE-REGISTERED IN THE GATE'S OWN SOURCE AND THEN NOT HONOURED. The workflow's floor
reader carried the note "If a second provider ever declares its own floor, this asserts the first
one's — widen it here in the same change." Four descriptors that declare their own floor were added
afterwards by three separate items (#348, #350/#356, ADR-0071/0072) and the widening never happened
in any of them. A note asking a future author to remember is not a control, which is why this file
is a check that is demonstrated to fire (`--self-test`) rather than another comment.

THE ROOT CAUSE IS THE HAND-NAMED SINGLETON, so the remedy is enumeration, not a longer list. This
script GLOBS `providers/*.providers.yml`. A sixth descriptor added tomorrow is graded by
construction, with no edit here and nobody to remember — the same lesson `composition.yml` already
records for lane discovery (#379: two lanes were added without the hand-written list being edited and
ran on nothing for days). This is a deliberate deviation from #383's literal verification line
"`grep -rn minimumFsggSdd .github/workflows/ scripts/` reaches all five descriptors", which assumes a
hand-enumeration: a glob names no descriptor, so that grep will not list five paths. The check still
NAMES every file it read, in the log, the annotations and the step summary — see `--self-test` case
`glob-covers-a-new-descriptor`, which adds an unknown sixth descriptor and proves it is graded.

THE AUTHORITY IS THE ORG REGISTRY, READ LIVE. The floor is an org-wide value —
`FS-GG/.github registry/dependencies.yml`, contract `fs-gg-ui-template`, key `minimum-fsgg-sdd.version`
(ADR-0008, coherence id `fsgg-sdd-orchestrator-axis`) — and this repository holds MIRRORS of it. The
registry pin has moved three times (null -> 0.3.0 -> 0.4.0 -> 0.6.0) and each move needed a
hand-tracked re-mirror here (#45, #47/#49, #99). Grading against the live value means the next move
REDS this repository on its next run instead of waiting for somebody to file a re-mirror request.

  * READ AT `main`, NOT CONTENT-ADDRESSED, and that is the opposite of what
    `tests/composition/lib/skill-union.sh` does with SKILL_ASSERT_REF — deliberately. There the
    subject is an ASSERTION IMPLEMENTATION, and a pinned SHA is what makes the verdict reproducible.
    Here the subject IS the current org value; pinning it would re-create the staleness this file
    exists to end.
  * AN OUTAGE FAILS THE GATE, by design and by local precedent (skill-union.sh: "an outage FAILS the
    lane by design"). Failing open would restore the exact green-over-an-unread-subject shape that
    epic FS-GG/.github#266 is about. `--registry` takes a local path for offline runs.

EQUALITY, NOT `>=`. A mirror that says something its authority does not say is not a mirror. A floor
BELOW the registry advertises a coherent set that is not coherent; a floor ABOVE it is a stricter
claim with no authority behind it — the same objection `composition.yml` records against
hand-freezing a ceiling ("a hand-frozen number with no authority behind it"). Both red, and the
diagnostic names both values and the direction so the remedy is never ambiguous. This DOES mean a
registry advance wedges every PR in this repository until the mirrors are re-cohered, because
`composition` is a required check under `enforce_admins`. That is the intended behaviour and #383's
stated acceptance ("a registry advance reds this repo instead of waiting for a hand-filed re-mirror
request"); the red carries a one-line remedy naming every file to edit and the value to write.

A MISSING BLOCK IS A HARD FAILURE, NOT AN EXEMPTION. #383 offered "a named failure or a named,
checked-in exemption" and its parenthetical answered its own question — "`rendering`'s existing
unreadable-descriptor hard failure is the right shape; widen it, do not weaken it." So there is no
exemption registry: a descriptor with no readable `minimumFsggSdd.version` fails and names itself. A
zero-entry exemption file would be a mechanism nobody exercises and a second place for a future
descriptor to hide.

Run it:

    scripts/check-provider-floors.py                      # grades providers/ against the live registry
    scripts/check-provider-floors.py --registry ../.github/registry/dependencies.yml
    scripts/check-provider-floors.py --self-test          # offline; proves the gate can fail
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request


REGISTRY_URL = "https://raw.githubusercontent.com/FS-GG/.github/main/registry/dependencies.yml"
REGISTRY_CONTRACT = "fs-gg-ui-template"
REGISTRY_KEY = "minimum-fsgg-sdd"
REGISTRY_SOURCE = f"FS-GG/.github registry/dependencies.yml -> {REGISTRY_CONTRACT}.{REGISTRY_KEY}"
DESCRIPTOR_GLOB = "*.providers.yml"

# Same narrow structural shapes scripts/generate-effective-providers.py already parses, and for the
# same reason: no third-party YAML dependency, and `version:` appears in several unrelated places in
# these files (the hand-authored PIN HISTORY block alone names this key repeatedly). Comment lines
# are dropped before any of this matches, so a prose mention can never be read as a declaration.
PROVIDER = re.compile(r"^  - name:\s*(\S+)\s*(?:#.*)?$")
FLOOR_BLOCK = re.compile(r"^    minimumFsggSdd:\s*(?:#.*)?$")
VERSION = re.compile(r"^      version:\s*(.*?)\s*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+].*)?$")

REGISTRY_CONTRACT_ID = re.compile(r"^  - id:\s*(\S+)\s*(?:#.*)?$")
REGISTRY_FLOOR_BLOCK = re.compile(rf"^    {re.escape(REGISTRY_KEY)}:\s*(?:#.*)?$")
REGISTRY_VERSION = re.compile(r"^      version:\s*(.*?)\s*$")


class FloorError(ValueError):
    """A condition that makes the grading impossible, as opposed to a descriptor that failed it."""


def scalar(raw: str, where: str) -> str:
    """Read the simple scalar spellings these descriptors use, dropping any trailing comment."""
    if not raw:
        raise FloorError(f"{where}: version has no value")
    if raw[0] in "\"'":
        quote = raw[0]
        closing = raw.find(quote, 1)
        if closing < 0:
            raise FloorError(f"{where}: unterminated quoted version")
        return raw[1:closing]
    token = raw.split("#", 1)[0].strip()
    if not token:
        raise FloorError(f"{where}: expected a scalar version")
    return token.split()[0]


def is_skippable(line: str) -> bool:
    return not line.strip() or line.lstrip().startswith("#")


def parse_descriptor(path: Path) -> list[tuple[str, str | None, int]]:
    """Return (provider name, declared floor or None, line number of the provider) for EVERY provider.

    Per provider, not per file. The workflow's previous awk reader returned the FIRST
    `minimumFsggSdd:` block in the file and asserted it as though it were the file's only one; a
    second provider in the same file would have inherited the first one's floor silently. That bound
    was written down and never widened, which is half of #383.
    """
    providers: list[tuple[str, str | None, int]] = []
    current: str | None = None
    current_line = 0
    floor: str | None = None
    in_block = False

    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if is_skippable(line):
            continue

        match = PROVIDER.match(line)
        if match:
            if current is not None:
                providers.append((current, floor, current_line))
            current, current_line, floor, in_block = match.group(1), number, None, False
            continue

        if current is None:
            continue

        if FLOOR_BLOCK.match(line):
            in_block = True
            continue

        if in_block:
            match = VERSION.match(line)
            if match and floor is None:
                floor = scalar(match.group(1), f"{path}:{number}")
                continue
            # Any line at or left of the block's own indent closes it. `minimumFsggSdd:` sits at four
            # spaces, so a sibling key ends the block and a nested key (six spaces) does not.
            if len(line) - len(line.lstrip(" ")) <= 4:
                in_block = False

    if current is not None:
        providers.append((current, floor, current_line))
    if not providers:
        raise FloorError(f"{path}: declares no providers")
    return providers


def read_registry_pin(text: str, source: str) -> str:
    """Read contracts[id=fs-gg-ui-template].minimum-fsgg-sdd.version out of the org registry."""
    contract: str | None = None
    in_block = False

    for number, line in enumerate(text.splitlines(), 1):
        if is_skippable(line):
            continue
        match = REGISTRY_CONTRACT_ID.match(line)
        if match:
            contract, in_block = match.group(1), False
            continue
        if contract != REGISTRY_CONTRACT:
            continue
        if REGISTRY_FLOOR_BLOCK.match(line):
            in_block = True
            continue
        if in_block:
            match = REGISTRY_VERSION.match(line)
            if match:
                return scalar(match.group(1), f"{source}:{number}")
            if len(line) - len(line.lstrip(" ")) <= 4:
                in_block = False

    raise FloorError(
        f"{source}: could not read contracts[id={REGISTRY_CONTRACT}].{REGISTRY_KEY}.version. "
        "The org-wide floor is the authority this repository's descriptors mirror, so an unreadable "
        "registry FAILS here rather than silently dropping the assertion (FS.GG.Templates#383)."
    )


def load_registry(source: str) -> tuple[str, str]:
    """Return (registry text, human-readable source). A local path when given, else a live fetch."""
    if not source.startswith(("http://", "https://")):
        path = Path(source)
        if not path.is_file():
            raise FloorError(f"--registry {source}: no such file")
        return path.read_text(encoding="utf-8"), str(path)
    try:
        with urllib.request.urlopen(source, timeout=30) as response:  # noqa: S310 - fixed https URL
            return response.read().decode("utf-8"), source
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise FloorError(
            f"{source}: could not be fetched ({error}). This gate grades the declared floors against "
            "the LIVE org registry, so an unreachable authority fails closed — a green computed "
            "without reading the authority would be exactly the unread-subject green #383 removes. "
            "For an offline run pass --registry <path to a checkout of FS-GG/.github>."
        ) from error


def display(path: Path) -> str:
    """Name a path the way this repository's issues and workflows name it — `providers/web...`.

    A diagnostic is only actionable if the reader can paste the path it names. An absolute runner
    path (`/home/runner/work/FS.GG.Templates/FS.GG.Templates/providers/...`) is not that.
    """
    try:
        relative = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return str(path)
    return str(relative)


def below(left: str, right: str) -> bool:
    """True when release core `left` sorts before release core `right`.

    Only ever used to WORD a diagnostic ("BELOW"/"AHEAD OF") — the verdict itself is equality, so a
    prerelease suffix cannot change any outcome and is dropped here rather than adjudicated. Plain
    string comparison would be wrong at the first double-digit minor ('0.10.0' < '0.6.0'), which is
    a defect that would sit dormant until exactly the release where it misdescribes a real red.
    """

    def key(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("-", 1)[0].split("+", 1)[0].split("."))

    return key(left) < key(right)


ANNOTATIONS: list[tuple[str, str]] = []


def annotate(title: str, message: str) -> None:
    """Queue a workflow annotation. Flushed AFTER the report so the log reads in order."""
    ANNOTATIONS.append((title, message))


def flush_annotations() -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for title, message in ANNOTATIONS:
            print(f"::error title={title}::{message}")
    ANNOTATIONS.clear()


def remedy(pin: str, source: str) -> str:
    return (
        f"Re-mirror it: set `minimumFsggSdd.version` to \"{pin}\" in the descriptor named above (and "
        f"in every sibling under providers/ that disagrees), matching {source}. If the descriptor is "
        "right and the registry is wrong, the fix belongs in FS-GG/.github — this repository mirrors "
        "that value and does not own it."
    )


def grade(providers_dir: Path, registry_source: str, out: list[str]) -> tuple[int, str]:
    """Grade every descriptor. Returns (failure count, agreed floor when the set is coherent)."""
    descriptors = sorted(providers_dir.glob(DESCRIPTOR_GLOB))
    if not descriptors:
        raise FloorError(
            f"{display(providers_dir)}/{DESCRIPTOR_GLOB} matched no descriptor. An empty subject is not a "
            "green: this gate exists because a descriptor that nothing reads stays green forever "
            "(FS.GG.Templates#383)."
        )

    registry_text, registry_name = load_registry(registry_source)
    pin = read_registry_pin(registry_text, registry_name)
    if not SEMVER.match(pin):
        raise FloorError(f"{registry_name}: {REGISTRY_CONTRACT}.{REGISTRY_KEY}.version is '{pin}', not a version")

    out.append(f"registry pin: {pin} (read from {registry_name}, {REGISTRY_SOURCE})")
    out.append(f"descriptors:  {len(descriptors)} matched {display(providers_dir)}/{DESCRIPTOR_GLOB}")

    failures = 0
    for descriptor in descriptors:
        shown = display(descriptor)
        for name, floor, line in parse_descriptor(descriptor):
            where = f"{shown}:{line}"
            if floor is None:
                failures += 1
                message = (
                    f"provider '{name}' in {shown} declares no readable "
                    f"minimumFsggSdd.version. Every provider under {display(providers_dir)}/ mirrors the "
                    f"org-wide floor ({REGISTRY_SOURCE} = {pin}); an absent floor silently disables "
                    f"the scaffold.cliBehindMinimum warning for that identity, which is the defect "
                    f"providers/web.providers.yml shipped with (FS.GG.Templates#383). "
                    + remedy(pin, registry_name)
                )
                out.append(f"FAIL  {where}  {name}: no readable minimumFsggSdd.version")
                annotate("minimumFsggSdd is missing or unreadable", message)
                out.append(f"      {message}")
                continue
            if not SEMVER.match(floor):
                failures += 1
                message = (
                    f"provider '{name}' in {shown} declares minimumFsggSdd.version '{floor}', "
                    f"which is not a version. " + remedy(pin, registry_name)
                )
                out.append(f"FAIL  {where}  {name}: floor '{floor}' is not a version")
                annotate("minimumFsggSdd is unreadable", message)
                out.append(f"      {message}")
                continue
            if floor != pin:
                failures += 1
                direction = "BELOW" if below(floor, pin) else "AHEAD OF"
                message = (
                    f"provider '{name}' in {shown} declares minimumFsggSdd.version {floor}, "
                    f"which is {direction} the org-wide pin {pin} ({REGISTRY_SOURCE}). This "
                    f"descriptor is a MIRROR of that value and must equal it: a floor below the pin "
                    f"advertises a coherent set that is not coherent, and a floor ahead of it is a "
                    f"stricter claim with no authority behind it. " + remedy(pin, registry_name)
                )
                out.append(f"FAIL  {where}  {name}: floor {floor} != registry pin {pin}")
                annotate(f"minimumFsggSdd {floor} disagrees with the registry pin {pin}", message)
                out.append(f"      {message}")
                continue
            out.append(f"ok    {where}  {name}: floor {floor} == registry pin {pin}")

    return failures, pin


# ── Self-demonstration ──────────────────────────────────────────────────────────────────────────
#
# A gate that has never been observed red is a claim, not a control — and this repository has paid
# for that twice (#315's frozen SKILL_ASSERT_REF, #379's lanes that ran on nothing). Every case below
# runs offline against a synthetic registry and a COPY of the real descriptors, so it exercises the
# real files' real shape without touching them. `--self-test` runs in CI immediately before the live
# grading, so a run that reports green has just demonstrated that it could have reported red.

SYNTHETIC_REGISTRY = """\
schemaVersion: 2
contracts:
  - id: some-other-contract
    minimum-fsgg-sdd:
      version: "9.9.9"     # a decoy: the wrong contract's floor must never be read
  - id: fs-gg-ui-template
    package-version: "0.26.0"
    # minimum-fsgg-sdd: 0.6.0 is quoted in this comment, and must not be read as the declaration
    minimum-fsgg-sdd:
      version: "0.6.0"
      requires: "synthetic"
    root-buildable:
      since: "synthetic"
"""

SECOND_PROVIDER = """\
  - name: zz-second
    contractVersion: "1.1.0"
    templateId: fs-gg-zz
    source: FS.GG.Workspace.Template::0.8.0
    parameters:
      - key: productName
        required: true
"""

SIXTH_DESCRIPTOR = """\
schemaVersion: 1
providers:
  - name: sixth
    contractVersion: "1.1.0"
    templateId: fs-gg-sixth
    source: FS.GG.Workspace.Template::0.8.0
    minimumFsggSdd:
      version: "0.5.0"
      requires: "synthetic"
"""


def _delete_floor_block(text: str) -> str:
    """Drop the `minimumFsggSdd:` block, exactly as providers/web.providers.yml shipped without one."""
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    dropping = False
    for line in lines:
        if FLOOR_BLOCK.match(line.rstrip("\n")):
            dropping = True
            continue
        if dropping:
            stripped = line.rstrip("\n")
            if not stripped.strip() or len(stripped) - len(stripped.lstrip(" ")) > 4:
                continue
            dropping = False
        kept.append(line)
    return "".join(kept)


def _fixture(root: Path) -> tuple[Path, str]:
    """A pristine copy of the REAL providers/ plus a synthetic registry pinned at 0.6.0."""
    providers = root / "providers"
    providers.mkdir(parents=True, exist_ok=True)
    real = Path(__file__).resolve().parents[1] / "providers"
    for descriptor in sorted(real.glob(DESCRIPTOR_GLOB)):
        shutil.copy2(descriptor, providers / descriptor.name)
    registry = root / "dependencies.yml"
    registry.write_text(SYNTHETIC_REGISTRY, encoding="utf-8")
    return providers, str(registry)


def _run_case(name: str, mutate, expect_fail: bool, expect: str, results: list[str]) -> bool:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        providers, registry = _fixture(root)
        try:
            mutate(providers)
        except FloorError as error:
            results.append(f"FAIL  self-test/{name}: {error}")
            return False
        out: list[str] = []
        ANNOTATIONS.clear()
        try:
            failures, _ = grade(providers, registry, out)
        except FloorError as error:
            failures, out = 1, out + [str(error)]
        ANNOTATIONS.clear()
        text = "\n".join(out)
        red = failures > 0
        if red != expect_fail:
            results.append(
                f"FAIL  self-test/{name}: expected {'red' if expect_fail else 'green'}, got "
                f"{'red' if red else 'green'}\n{text}"
            )
            return False
        if expect and expect not in text:
            results.append(f"FAIL  self-test/{name}: output did not contain {expect!r}\n{text}")
            return False
        results.append(f"PASS  self-test/{name}")
        return True


def _set_floor(value: str):
    """Rewrite the declaration line itself — `      version: "..."` at six spaces inside the block.

    Never a textual first-occurrence replace: see `_edit`.
    """

    def transform(text: str) -> str:
        lines = text.splitlines(keepends=True)
        in_block = False
        for index, line in enumerate(lines):
            stripped = line.rstrip("\n")
            if FLOOR_BLOCK.match(stripped):
                in_block = True
                continue
            if in_block and VERSION.match(stripped):
                lines[index] = f'      version: {value}\n'
                break
        return "".join(lines)

    return transform


def _edit(name: str, transform):
    """Apply `transform` to a descriptor copy, refusing a no-op.

    A mutation that silently matched nothing would make its case expect red and see green, and the
    reader would go looking in the checker rather than at the mutation. Measured hazard, not a
    hypothetical: the obvious first-occurrence replace of `version: "0.6.0"` in web.providers.yml
    hits a COMMENT on line 19, not the declaration on line 29.
    """

    def mutate(providers: Path) -> None:
        target = providers / name
        before = target.read_text(encoding="utf-8")
        after = transform(before)
        if after == before:
            raise FloorError(f"self-test mutation of {name} changed nothing — the mutation is broken, not the gate")
        target.write_text(after, encoding="utf-8")

    return mutate


def self_test() -> int:
    results: list[str] = []
    cases = [
        # The unmutated set is green. Without this, every red below could be red for a reason that
        # has nothing to do with the mutation.
        ("pristine-set-is-green", lambda providers: None, False, "floor 0.6.0 == registry pin 0.6.0"),
        # #383's acceptance, verbatim: a deleted block, and one pinned below the registry, both red.
        (
            "deleted-block-reds",
            _edit("web.providers.yml", _delete_floor_block),
            True,
            "web: no readable minimumFsggSdd.version",
        ),
        (
            "floor-below-registry-reds",
            _edit("console.providers.yml", _set_floor('"0.5.0"')),
            True,
            "console: floor 0.5.0 != registry pin 0.6.0",
        ),
        (
            "floor-ahead-of-registry-reds",
            _edit("fable-game.providers.yml", _set_floor('"0.7.0"')),
            True,
            "fable-game: floor 0.7.0 != registry pin 0.6.0",
        ),
        (
            "unparseable-floor-reds",
            _edit("fable-bindings.providers.yml", _set_floor("latest")),
            True,
            "fable-bindings: floor 'latest' is not a version",
        ),
        # THE ROOT-CAUSE CASE. The reader this replaces took the FIRST floor block in a file and
        # asserted it for the whole file. A second provider with no floor of its own must red.
        (
            "second-provider-in-one-file-is-graded-separately",
            _edit("console.providers.yml", lambda t: t.rstrip("\n") + "\n" + SECOND_PROVIDER),
            True,
            "zz-second: no readable minimumFsggSdd.version",
        ),
        # THE ENUMERATION CASE. A descriptor nobody edited this file to name is graded anyway.
        (
            "glob-covers-a-new-descriptor",
            lambda providers: (providers / "sixth.providers.yml").write_text(SIXTH_DESCRIPTOR, encoding="utf-8"),
            True,
            "sixth: floor 0.5.0 != registry pin 0.6.0",
        ),
        # An unreadable authority fails closed rather than grading against nothing.
        (
            "unreadable-registry-fails-closed",
            lambda providers: None,
            True,
            "",
        ),
    ]

    passed = 0
    for index, (name, mutate, expect_fail, expect) in enumerate(cases):
        if name == "unreadable-registry-fails-closed":
            out: list[str] = []
            with tempfile.TemporaryDirectory() as raw:
                providers, _ = _fixture(Path(raw))
                try:
                    grade(providers, str(Path(raw) / "absent.yml"), out)
                    results.append("FAIL  self-test/unreadable-registry-fails-closed: it passed")
                except FloorError as error:
                    if "no such file" in str(error):
                        results.append("PASS  self-test/unreadable-registry-fails-closed")
                        passed += 1
                    else:
                        results.append(f"FAIL  self-test/unreadable-registry-fails-closed: {error}")
            continue
        if _run_case(name, mutate, expect_fail, expect, results):
            passed += 1

    print("\n".join(results))
    total = len(cases)
    if passed != total:
        print(
            f"check-provider-floors: SELF-TEST BROKEN — {total - passed} of {total} outcomes did not "
            "reproduce, so the verdict this gate publishes is not evidence of anything. Fix the "
            "checker; do NOT delete the self-demonstration (FS.GG.Templates#383).",
            file=sys.stderr,
        )
        return 1
    print(f"check-provider-floors: self-test green — {total}/{total} outcomes reproduced, red arms included")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--providers", type=Path, default=root / "providers")
    parser.add_argument(
        "--registry",
        default=REGISTRY_URL,
        help="path to a checkout of FS-GG/.github registry/dependencies.yml, or a URL (default: live main)",
    )
    parser.add_argument("--self-test", action="store_true", help="prove the gate can fail; offline")
    parser.add_argument("--github-output", type=Path, help="write `floor=<agreed floor>` here")
    parser.add_argument("--step-summary", type=Path, help="append a summary table here")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    out: list[str] = []
    try:
        failures, pin = grade(args.providers, args.registry, out)
    except FloorError as error:
        print("\n".join(out))
        annotate("provider floors could not be graded", str(error))
        flush_annotations()
        print(f"check-provider-floors: {error}", file=sys.stderr)
        return 1

    print("\n".join(out))
    flush_annotations()
    if args.step_summary:
        with args.step_summary.open("a", encoding="utf-8") as handle:
            handle.write("### composition — provider `minimumFsggSdd` floors\n\n")
            handle.write(f"Graded against `{REGISTRY_SOURCE}` = **{pin}** (read live).\n\n")
            for line in out:
                handle.write(f"    {line}\n")
            handle.write("\n")
    if failures:
        print(
            f"check-provider-floors: {failures} provider floor(s) do not mirror the org-wide pin {pin}",
            file=sys.stderr,
        )
        return 1
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"floor={pin}\n")
    print(f"check-provider-floors: every declared floor mirrors {REGISTRY_SOURCE} = {pin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
