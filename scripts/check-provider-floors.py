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

    scripts/check-provider-floors.py                      # grade providers/ against the live registry,
                                                          # THEN self-demonstrate; exit 1 if either fails
    scripts/check-provider-floors.py --registry ../.github/registry/dependencies.yml
    scripts/check-provider-floors.py --self-test          # ONLY the offline demonstration

A NORMAL RUN GRADES FIRST AND DEMONSTRATES SECOND, and that order is a repair, not a preference. See
the ORDER IS LOAD-BEARING block in `main`: running the demonstration first (as this file did in its
first revision) let a drifted descriptor abort the run inside the demonstration, so CI emitted no
diagnostic about the descriptor that was actually wrong.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
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


def read_descriptor(path: Path, shown: str | None = None) -> str:
    """Read a descriptor as UTF-8, turning an unreadable file into a FloorError, never a traceback.

    THE ONE PLACE A DESCRIPTOR IS TURNED INTO TEXT, and it is one place on purpose
    (FS.GG.Templates#398). `Path.read_text(encoding="utf-8")` raises `UnicodeDecodeError` — a
    `ValueError`, but NOT a `FloorError` — so every caller that had written `except FloorError` around
    its read was catching the condition it named and missing this one. Measured at `1166da62` with a
    non-UTF-8 byte in a descriptor: `main`'s `except FloorError` did not catch it, so the LIVE grading
    died at `parse_descriptor` and the run printed **no** report, **no** `::error` and **no** step
    summary at all — the opposite of what #398's body predicted for this input, and the same
    unread-subject shape #383 exists to remove. Raising the condition this file already knows how to
    report fixes both legs at their single cause instead of adding a second `except` at each site.

    `OSError` is here for the same reason and not a wider one: an unreadable or vanished descriptor is
    a condition that makes grading impossible, which is exactly what `FloorError` means.

    `shown` names the file the READER must fix when that is not the file being read — the fixture
    builder reads a temporary COPY, whose path is a `/tmp/tmpXXXXXXXX/...` that changes every run and
    no longer exists by the time anyone reads the line.
    """
    where = shown or display(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise FloorError(
            f"{where}: is not valid UTF-8 ({error.reason} at byte {error.start}), so the "
            "providers it declares cannot be read. Every descriptor under providers/ is UTF-8 YAML; "
            "re-save this one as UTF-8. An undecodable descriptor FAILS this gate rather than being "
            "skipped, because a descriptor nothing can read is the unread subject FS.GG.Templates#383 "
            "removes."
        ) from error
    except OSError as error:
        raise FloorError(f"{where}: could not be read ({error})") from error


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

    for number, line in enumerate(read_descriptor(path).splitlines(), 1):
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
# real files' real SHAPE — their comments, their 200-line PIN HISTORY prose, their quoting and
# indentation — without touching them.
#
# IT EXERCISES THEIR SHAPE AND NOT THEIR VALUES, AND THAT DISTINCTION IS THE WHOLE REPAIR
# (independent review of this PR, round 1, critic `avocet-7ba2`). The first version of this file
# hard-coded `0.6.0` in the synthetic registry while grading copies of the real descriptors, and
# derived the mutation values from that same literal. So the demonstration silently asserted "the org
# pin is 0.6.0" — the hand-named singleton this whole change exists to delete, reintroduced one
# function lower down. Two measured consequences, both on scenarios this file is FOR:
#
#   * A COMPLETED, CORRECT RE-MIRROR WEDGED THE REPOSITORY. Advance the registry 0.6.0 -> 0.7.0 and
#     re-mirror all five descriptors — the exact thing #383 exists to make possible — and the live
#     grading correctly said `every declared floor mirrors … = 0.7.0`, exit 0, while the self-test
#     went red (`pristine-set-is-green` graded 0.7.0 descriptors against a 0.6.0 fixture, and the
#     `0.7.0` above-mutant became a no-op). `composition` is required under `enforce_admins`, so that
#     is every PR in the repository unmergeable, by anyone, over a CORRECT tree — until somebody
#     hand-edited four constants in the file whose stated design is "no edit here and nobody to
#     remember". The pin has already moved three times, so that was scheduled, not hypothetical.
#   * IT ACCUSED THE WRONG COMPONENT. `--self-test` ran FIRST under `set -euo pipefail`, so a drifted
#     real descriptor aborted the step inside the demonstration and the live grading never ran: no
#     `FAIL providers/…` line, no annotation, no step summary, no remedy — and the developer was told
#     "the verdict this gate publishes is not evidence of anything. Fix the checker", when the
#     checker was fine and their mirror was wrong.
#
# THE FIX IS TWO PROPERTIES, AND BOTH ARE ASSERTED RATHER THAN ASSUMED:
#
#   1. THE FIXTURE IS NORMALIZED. `_fixture` copies the real descriptors and then rewrites every
#      provider's floor to SYNTHETIC_PIN — an obviously synthetic value that is not, and must never
#      be, any org pin — inserting the block where a descriptor has none. The synthetic registry and
#      every mutant are derived from that one constant. The demonstration therefore holds for a tree
#      at ANY coherent value X, and for a tree that is currently drifting, because it no longer reads
#      the real values at all. `_normalize_floors` refuses to leave a provider ungraded, so
#      `pristine-set-is-green` is green by construction whenever the descriptors PARSE.
#   2. THE LIVE GRADING RUNS FIRST AND IS NEVER SUPPRESSED. See `main`: the real subject is graded and
#      its diagnostics, annotations and step summary are emitted BEFORE the demonstration runs, and
#      the two verdicts are combined into the exit code. A broken demonstration can no longer hide a
#      real red, and `SELF-TEST BROKEN` is now emitted only for a fixture this file fully controls —
#      which is what makes that sentence true when it appears.

# NOT AN ORG PIN, AND DELIBERATELY UNMISTAKABLE AS ONE. If this value ever looks like something the
# registry could plausibly say, the coupling that #383's round-1 review found has grown back.
SYNTHETIC_PIN = "4.5.6"


def _shift_patch(version: str, delta: int) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + delta}"


SYNTHETIC_BELOW = _shift_patch(SYNTHETIC_PIN, -1)
SYNTHETIC_ABOVE = _shift_patch(SYNTHETIC_PIN, +1)

SYNTHETIC_REGISTRY = f"""\
schemaVersion: 2
contracts:
  - id: some-other-contract
    minimum-fsgg-sdd:
      version: "9.9.9"     # a decoy: the wrong contract's floor must never be read
  - id: fs-gg-ui-template
    package-version: "0.26.0"
    # minimum-fsgg-sdd: {SYNTHETIC_BELOW} is quoted in this comment, and must not be read as the declaration
    minimum-fsgg-sdd:
      version: "{SYNTHETIC_PIN}"
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

SIXTH_DESCRIPTOR = f"""\
schemaVersion: 1
providers:
  - name: sixth
    contractVersion: "1.1.0"
    templateId: fs-gg-sixth
    source: FS.GG.Workspace.Template::0.8.0
    minimumFsggSdd:
      version: "{SYNTHETIC_BELOW}"
      requires: "synthetic"
"""


# FS.GG.Templates#398's two subject states, as bytes, so one definition serves both the live-grading
# arms (written into a built fixture) and the builder arms (written into the directory the builder
# copies FROM). `providers: []` is the shape `providers/web.providers.yml` could plausibly be edited
# into; the non-UTF-8 one is a byte a UTF-8 decoder cannot start a sequence with.
PROVIDER_LESS_DESCRIPTOR = b"schemaVersion: 1\nproviders: []\n"
NON_UTF8_DESCRIPTOR = (
    b'schemaVersion: 1\nproviders:\n  - name: undecodable\n    minimumFsggSdd:\n'
    b'      version: "0.0.0"  # \xff not valid UTF-8\n'
)


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


def _normalize_floors(path: Path, pin: str, shown: str | None = None) -> None:
    """Rewrite EVERY provider's floor in a fixture copy to `pin`, inserting the block where absent.

    This is what decouples the demonstration from whatever the org pin happens to be today, and from
    whatever state the working tree is in. Per provider, not per file, and it never leaves a provider
    ungraded — a descriptor whose block was deleted in the real tree gets one here, so a genuine
    mirror drift can no longer make `pristine-set-is-green` red and accuse the checker of being
    broken (round-1 review, M1b).
    """
    lines = read_descriptor(path, shown).splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if PROVIDER.match(line.rstrip("\n"))]
    if not starts:
        raise FloorError(f"{shown or path.name}: declares no providers, so the fixture cannot be normalized")

    spans = [(start, starts[n + 1] if n + 1 < len(starts) else len(lines)) for n, start in enumerate(starts)]
    for start, end in reversed(spans):  # from the end, so an insertion cannot shift an earlier span
        block_index: int | None = None
        version_index: int | None = None
        in_block = False
        for index in range(start + 1, end):
            raw = lines[index].rstrip("\n")
            if is_skippable(raw):
                continue
            if FLOOR_BLOCK.match(raw):
                block_index, in_block = index, True
                continue
            if in_block:
                if VERSION.match(raw):
                    version_index = index
                    break
                if len(raw) - len(raw.lstrip(" ")) <= 4:
                    in_block = False
        if version_index is not None:
            lines[version_index] = f'      version: "{pin}"\n'
        elif block_index is not None:
            lines.insert(block_index + 1, f'      version: "{pin}"\n')
        else:
            lines[start + 1 : start + 1] = ["    minimumFsggSdd:\n", f'      version: "{pin}"\n']
    path.write_text("".join(lines), encoding="utf-8")


REAL_PROVIDERS = Path(__file__).resolve().parents[1] / "providers"

# Everything that can make the fixture BUILDER give up. `FloorError` is a `ValueError` and so is
# `UnicodeDecodeError`, so this tuple is wider than it looks — it is spelled out rather than collapsed
# because the names are what a reader checks against `read_descriptor`'s raises.
FIXTURE_FAILURES = (FloorError, OSError, ValueError)


def _fixture(root: Path, source: Path | None = None) -> tuple[Path, str]:
    """Copies of the REAL descriptors, floors normalized to SYNTHETIC_PIN, plus a matching registry.

    The copies keep the real files' shape — comments that quote this key, the 200-line PIN HISTORY
    prose, the quoting and indentation — which is the point of copying them. Their VALUES are
    replaced, which is the point of normalizing them.

    `source` defaults to the real `providers/` and exists so the demonstration can point the BUILDER
    at a directory whose state makes it give up (FS.GG.Templates#398). Without it, the only way to
    exercise the builder's own failure paths would be to put a broken descriptor in the real tree,
    which is not a thing a self-test may do.
    """
    providers = root / "providers"
    providers.mkdir(parents=True, exist_ok=True)
    real = REAL_PROVIDERS if source is None else source
    for descriptor in sorted(real.glob(DESCRIPTOR_GLOB)):
        target = providers / descriptor.name
        shutil.copy2(descriptor, target)
        _normalize_floors(target, SYNTHETIC_PIN, shown=display(descriptor))
    registry = root / "dependencies.yml"
    registry.write_text(SYNTHETIC_REGISTRY, encoding="utf-8")
    return providers, str(registry)


def _brief(error: Exception) -> str:
    """The first sentence of a diagnostic, for a line that is repeated once per skipped case.

    An unbuildable baseline skips every case, so whatever this returns is printed a dozen times. The
    FULL text is not lost — it is the same condition the LIVE grading reports once, above, in the
    place a reader is already looking. Repeating a paragraph twelve times is the output hygiene
    FS.GG.Templates#398 is about, so this repair does not get to reintroduce it in a new shape.
    """
    text = " ".join(str(error).split())
    head, sep, _ = text.partition(". ")
    return f"{head}." if sep else text


def _build_fixture(name: str, root: Path, results: list[str], source: Path | None = None):
    """THE ONLY WAY THIS DEMONSTRATION BUILDS A FIXTURE. `None` means the baseline is unavailable.

    Three call sites used to call `_fixture` directly and exactly one of them had a `try` around it,
    so a builder failure escaped from the other two as a raw traceback (FS.GG.Templates#398). The
    remedy is not two more `try` blocks that can drift apart from the first — it is one guard that
    every site goes through, so a fourth site cannot be added unguarded without deleting this call.

    The outcome is deliberately NOT `FAIL`. A case that never ran has not disagreed with anything, and
    `SELF-TEST BROKEN` means "the checker's behaviour changed" — see `self_test`'s summary.
    """
    try:
        return _fixture(root, source)
    except FIXTURE_FAILURES as error:
        results.append(f"SKIP  self-test/{name}: baseline unavailable — {_brief(error)}")
        return None


def _run_case(name: str, mutate, expect_fail: bool, expect: str, results: list[str], source: Path | None = None) -> str:
    """Returns one of `pass`, `fail`, `unavailable` — three outcomes, because there are three."""
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        built = _build_fixture(name, root, results, source)
        if built is None:
            return "unavailable"
        providers, registry = built
        try:
            mutate(providers)
        except FloorError as error:
            results.append(f"FAIL  self-test/{name}: {error}")
            return "fail"
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
            return "fail"
        if expect and expect not in text:
            results.append(f"FAIL  self-test/{name}: output did not contain {expect!r}\n{text}")
            return "fail"
        results.append(f"PASS  self-test/{name}")
        return "pass"


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


# Set in the CHILD of the two end-to-end arms below, which re-invoke this script as a subprocess.
# Without it those arms would spawn a child that runs them again, forever.
CHILD_GUARD = "FSGG_FLOORS_CHILD"


def _verdict(total: int, passed: int, unavailable: int, graded_ok: bool | None = None) -> str:
    """`green`, `broken`, `builder-broken`, or `unavailable` — four, because there are four remedies.

    THIS IS WHY IT IS A FUNCTION AND NOT AN `if`. `SELF-TEST BROKEN` accuses THIS FILE of having
    changed behaviour and tells the reader to fix the checker. A baseline that could not be BUILT is
    normally the opposite claim: the checker is not in question, a descriptor under providers/ is,
    and the live grading above has already named it. Collapsing the two sends the reader to the wrong
    file (FS.GG.Templates#398 acceptance 2).

    `graded_ok` IS THE DISAMBIGUATING SIGNAL, AND IT WAS ALREADY BEING COMPUTED (round-1 review, M3).
    "The fixture could not be built" is evidence about a DESCRIPTOR only if a descriptor is actually
    bad. `main` grades the real tree FIRST, so by the time this runs we already know whether the
    tree is coherent. When the grading passed and the builder still could not copy and normalize
    that same tree, the descriptors are fine and the BUILDER is broken — and blaming the descriptor
    then names a file the run has just certified as correct, in the same output. That was the exact
    misattribution this outcome was introduced to prevent, pointing the wrong way.

    `None` means nobody graded (the `--self-test` route, which is offline and reads no registry), so
    the signal is unavailable and the descriptor remains the more likely explanation.

    `broken` wins over both: a checker that has genuinely disagreed on a case it DID run is the more
    urgent claim, and it must not be downgraded by an unrelated bad descriptor.
    """
    broken = total - passed - unavailable
    if broken:
        return "broken"
    if unavailable:
        return "builder-broken" if graded_ok else "unavailable"
    return "green"


def _summarize(outcomes: list[str], graded_ok: bool | None = None) -> str:
    """Tally the outcomes and classify them. THE ONLY PLACE OUTCOMES ARE COUNTED.

    Round-1 review, M1: the count used to be two hand-maintained `+= 1` counters spread over five
    sites, and severing just the `unavailable` one left the suite 13/13 GREEN while production
    misreported a broken descriptor as `SELF-TEST BROKEN`. Nothing asserted that an outcome ever
    REACHED the tally, because the arms that check the classification did so on a tally they made up
    themselves. There is now one list and one derivation from it, so "reaching the tally" is not a
    separate step that can be severed — and the end-to-end arms drive the whole path anyway.
    """
    return _verdict(len(outcomes), outcomes.count("pass"), outcomes.count("unavailable"), graded_ok)


# The exact source line the M3 arm replaces in its CHILD copy to simulate a pure fixture-builder
# regression. Asserted present before use: if a refactor moves it, the arm says so instead of
# silently testing nothing.
BUILDER_ANCHOR = "        _normalize_floors(target, SYNTHETIC_PIN, shown=display(descriptor))"
BUILDER_REGRESSION = (
    '        raise FloorError(f"{display(descriptor)}: INJECTED fixture-builder regression")'
)


def _end_to_end(name: str, results: list[str]) -> str:
    """Run THIS script as CI runs it, over a synthetic checkout, and read the verdict off stderr.

    WHY A SUBPROCESS AND NOT A CALL. `main` grades, then demonstrates, then decides whom to blame
    from both. Round-1 review found two mutations no in-process arm here could see: severing the step
    that puts an `unavailable` outcome into the tally (the suite stayed green while production
    misreported), and never consulting the grading before blaming a descriptor. Both live in the
    WIRING between the pieces, so the assertion has to drive the whole thing.

    The synthetic checkout is `<tmp>/child/scripts/check-provider-floors.py` beside
    `<tmp>/child/providers/`, so the child's `REAL_PROVIDERS` — derived from `__file__` — resolves
    into the temporary tree, not into this repository. **Both arms pass `--providers` equal to that
    same tree**, which is the production relationship: the tree that gets graded is the tree the
    builder copies. The arms differ only in WHY the builder fails:

      * a descriptor that cannot be normalized  -> grading red   -> blame the DESCRIPTOR
      * a coherent tree + a regression injected
        into the builder itself                 -> grading green -> blame the CHECKER

    The second is round-1 review's M3 verbatim: a pure checker regression that used to report
    `BASELINE UNAVAILABLE` and name a descriptor the same run had just graded correct.
    """
    blames_checker = name.endswith("blames-the-checker")
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        built = _build_fixture(name, root, results)
        if built is None:
            return "unavailable"
        coherent, registry = built

        child = root / "child"
        (child / "scripts").mkdir(parents=True)
        providers = child / "providers"
        providers.mkdir(parents=True)

        source = Path(__file__).resolve().read_text(encoding="utf-8")
        if blames_checker:
            # A COHERENT tree — copies of the real descriptors, already normalized to the synthetic
            # pin — so the grading passes and the only thing wrong is the checker.
            for descriptor in sorted(coherent.glob(DESCRIPTOR_GLOB)):
                shutil.copy2(descriptor, providers / descriptor.name)
            # Matched with its line boundaries: the unanchored text also occurs inside the
            # BUILDER_ANCHOR constant a few lines above, which is not the line to break.
            anchored = f"\n{BUILDER_ANCHOR}\n"
            if source.count(anchored) != 1:
                results.append(
                    f"FAIL  self-test/{name}: could not find the fixture-builder line this arm has to "
                    f"break ({BUILDER_ANCHOR.strip()!r}). The arm is stale, not the checker."
                )
                return "fail"
            source = source.replace(anchored, f"\n{BUILDER_REGRESSION}\n", 1)
        else:
            (providers / "unbuildable.providers.yml").write_bytes(PROVIDER_LESS_DESCRIPTOR)

        script = child / "scripts" / "check-provider-floors.py"
        script.write_text(source, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--providers", str(providers), "--registry", registry],
                capture_output=True, text=True, timeout=300,
                env={**os.environ, CHILD_GUARD: "1", "GITHUB_ACTIONS": ""},
            )
        except (OSError, subprocess.SubprocessError) as error:
            results.append(f"SKIP  self-test/{name}: baseline unavailable — could not run the child ({error})")
            return "unavailable"

        output = f"{proc.stdout}\n{proc.stderr}"
        wanted = "SELF-TEST CHECKER BROKEN" if blames_checker else "SELF-TEST BASELINE UNAVAILABLE"
        unwanted = "SELF-TEST BASELINE UNAVAILABLE" if blames_checker else "SELF-TEST CHECKER BROKEN"

        if "Traceback (most recent call last)" in output:
            results.append(f"FAIL  self-test/{name}: the child emitted a traceback\n{_tail(output)}")
            return "fail"
        if proc.returncode == 0:
            results.append(
                f"FAIL  self-test/{name}: the child exited 0 on a tree it could not demonstrate on"
                f"\n{_tail(output)}"
            )
            return "fail"
        if wanted not in output:
            results.append(
                f"FAIL  self-test/{name}: expected the child to report {wanted!r}, and it did not. "
                "That is the WIRING, not the classifier: an outcome that never reaches the tally, or "
                f"a verdict that never consults the grading, both look exactly like this.\n{_tail(output)}"
            )
            return "fail"
        if unwanted in output:
            results.append(
                f"FAIL  self-test/{name}: the child ALSO reported {unwanted!r}, so the two verdicts are "
                f"not exclusive and the reader is told to fix two different things\n{_tail(output)}"
            )
            return "fail"
        if blames_checker and "every declared floor mirrors" not in output:
            results.append(
                f"FAIL  self-test/{name}: this arm only means anything if the child's LIVE grading was "
                f"GREEN — otherwise it is not the misattribution case at all\n{_tail(output)}"
            )
            return "fail"

    subject = "the CHECKER, on a tree its own grading just passed" if blames_checker else "the DESCRIPTOR it named"
    results.append(f"PASS  self-test/{name} (child exited {proc.returncode}, blaming {subject})")
    return "pass"


def _tail(output: str, lines: int = 12) -> str:
    return "\n".join(f"      | {line}" for line in output.strip().splitlines()[-lines:])


def self_test(graded_ok: bool | None = None) -> int:
    results: list[str] = []
    cases = [
        # The unmutated set is green. Without this, every red below could be red for a reason that
        # has nothing to do with the mutation.
        (
            "pristine-set-is-green",
            lambda providers: None,
            False,
            f"floor {SYNTHETIC_PIN} == registry pin {SYNTHETIC_PIN}",
        ),
        # #383's acceptance, verbatim: a deleted block, and one pinned below the registry, both red.
        (
            "deleted-block-reds",
            _edit("web.providers.yml", _delete_floor_block),
            True,
            "web: no readable minimumFsggSdd.version",
        ),
        (
            "floor-below-registry-reds",
            _edit("console.providers.yml", _set_floor(f'"{SYNTHETIC_BELOW}"')),
            True,
            f"console: floor {SYNTHETIC_BELOW} != registry pin {SYNTHETIC_PIN}",
        ),
        (
            "floor-ahead-of-registry-reds",
            _edit("fable-game.providers.yml", _set_floor(f'"{SYNTHETIC_ABOVE}"')),
            True,
            f"fable-game: floor {SYNTHETIC_ABOVE} != registry pin {SYNTHETIC_PIN}",
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
            f"sixth: floor {SYNTHETIC_BELOW} != registry pin {SYNTHETIC_PIN}",
        ),
        # FS.GG.Templates#398, THE LIVE-GRADING LEG. Both descriptor states that used to escape the
        # grading as a raw traceback must now be a NAMED refusal. These run through the ordinary
        # machinery because that is exactly the route `main` takes: `grade` raises `FloorError`,
        # `main` catches it, and the diagnostic reaches the log, the `::error` and the step summary.
        # The non-UTF-8 arm is the one that was not merely ugly: at `1166da62` the decode error was
        # not a `FloorError`, so `main` caught nothing and the run emitted NO report at all.
        (
            "provider-less-descriptor-fails-closed",
            lambda providers: (providers / "empty.providers.yml").write_bytes(PROVIDER_LESS_DESCRIPTOR),
            True,
            "declares no providers",
        ),
        (
            "non-utf8-descriptor-fails-closed",
            lambda providers: (providers / "undecodable.providers.yml").write_bytes(NON_UTF8_DESCRIPTOR),
            True,
            "is not valid UTF-8",
        ),
        # An unreadable authority fails closed rather than grading against nothing.
        # NAMED HONESTLY (round-1 review, non-material observation): this arm exercises the LOCAL
        # missing-file branch only. The live-URL failure branch — DNS failure, 404, or a 200 that is
        # not the registry — is `load_registry`'s `except` and `read_registry_pin`'s raise, and is not
        # reachable offline, so it is not claimed here.
        (
            "unreadable-local-registry-fails-closed",
            lambda providers: None,
            True,
            "",
        ),
        # THE ANTI-REGRESSION CASE, and the one that would have caught round 1. It asserts the
        # PROPERTY the repair establishes: the fixture's values come from SYNTHETIC_PIN and from
        # nowhere else, so no org pin — present or future — can change a single outcome above.
        (
            "fixture-is-independent-of-the-live-pin",
            lambda providers: None,
            True,
            "",
        ),
        # FS.GG.Templates#398, THE FIXTURE-BUILDER LEG. The same two states, but in the directory the
        # BUILDER copies from — where they are not a gradable descriptor at all, but a reason the
        # baseline could not be built. Each asserts BOTH halves of #398's acceptance: the builder
        # gives up as a named refusal rather than a traceback, AND the harness classifies the outcome
        # as `unavailable`, so `SELF-TEST BROKEN` never claims the checker's behaviour changed.
        (
            "builder-refuses-a-provider-less-descriptor",
            lambda providers: None,
            True,
            "",
        ),
        (
            "builder-refuses-a-non-utf8-descriptor",
            lambda providers: None,
            True,
            "",
        ),
        # END TO END, THROUGH `main`, IN A SUBPROCESS (round-1 review, M1 and M3). Everything above
        # asserts a PIECE. These two run this script the way CI runs it — grade, then demonstrate,
        # then combine — against a synthetic checkout whose real `providers/` cannot be built from,
        # and read the verdict off stderr. That is the only way to assert the WIRING rather than the
        # parts: that an unavailable outcome reaches the tally at all, and that the verdict consults
        # the grading before it decides whom to blame. A mutation that severs either is invisible to
        # a unit-shaped arm and fatal to these.
        (
            "end-to-end-an-unbuildable-descriptor-blames-the-descriptor",
            lambda providers: None,
            True,
            "",
        ),
        (
            "end-to-end-a-green-grade-with-an-unbuildable-fixture-blames-the-checker",
            lambda providers: None,
            True,
            "",
        ),
    ]

    # In the child these two are dropped, or it would spawn a child of its own without end. The
    # child's own suite is smaller and internally consistent; what the parent reads is its VERDICT.
    if os.environ.get(CHILD_GUARD) == "1":
        cases = [case for case in cases if not case[0].startswith("end-to-end-")]

    builder_cases = {
        "builder-refuses-a-provider-less-descriptor": PROVIDER_LESS_DESCRIPTOR,
        "builder-refuses-a-non-utf8-descriptor": NON_UTF8_DESCRIPTOR,
    }

    outcomes: list[str] = []
    for index, (name, mutate, expect_fail, expect) in enumerate(cases):
        if name.startswith("end-to-end-"):
            outcomes.append(_end_to_end(name, results))
            continue
        if name in builder_cases:
            with tempfile.TemporaryDirectory() as raw:
                source = Path(raw) / "providers"
                source.mkdir(parents=True)
                descriptor = source / "unbuildable.providers.yml"
                descriptor.write_bytes(builder_cases[name])
                observed: list[str] = []
                outcome = _run_case(name, lambda providers: None, True, "", observed, source)
            note = observed[0] if observed else "(the case recorded nothing)"
            if outcome != "unavailable":
                results.append(
                    f"FAIL  self-test/{name}: the builder was handed a descriptor it cannot normalize "
                    f"and the case came back {outcome!r}, not \'unavailable\' — a fixture that could "
                    f"not be built is not a disagreement about the checker (FS.GG.Templates#398). {note}"
                )
                outcomes.append("fail")
                continue
            # THE PREDICATE IS THE FULL SOURCE PATH, NOT ITS BASENAME (round-1 review, M2). The
            # fixture is a COPY that shares the basename, so a basename check passed just as happily
            # when the line named `/tmp/tmpXXXXXXXX/providers/unbuildable.providers.yml` — a path
            # already deleted by the time anyone reads it. The message claims the reader can act on
            # what is named; only the source path makes that true, so that is what is asserted.
            if str(descriptor) not in note:
                results.append(
                    f"FAIL  self-test/{name}: the refusal must name {descriptor}, the descriptor a "
                    f"reader can open — naming the temporary fixture copy, which shares its basename "
                    f"and no longer exists, is not actionable. Got: {note}"
                )
                outcomes.append("fail")
                continue
            results.append(f"PASS  self-test/{name} (baseline unavailable, reported as such, not as BROKEN)")
            outcomes.append("pass")
            continue
        if name == "fixture-is-independent-of-the-live-pin":
            # `floor` is None for a provider with no declaration, so these are rendered as strings
            # before they are sorted. A drifted or block-less real descriptor is EXACTLY the state
            # this case has to survive — it must not become a traceback, which is what this line
            # was on its first run against a tree whose web.providers.yml had lost its block.
            def floors_of(directory: Path) -> set[str]:
                return {
                    floor if floor is not None else "<none>"
                    for descriptor in sorted(directory.glob(DESCRIPTOR_GLOB))
                    for _, floor, _ in parse_descriptor(descriptor)
                }

            with tempfile.TemporaryDirectory() as raw:
                built = _build_fixture(name, Path(raw), results)
                if built is None:
                    outcomes.append("unavailable")
                    continue
                try:
                    fixture_floors = floors_of(built[0])
                    real_floors = floors_of(REAL_PROVIDERS)
                except FIXTURE_FAILURES as error:
                    # Reading the REAL tree is part of building this case's baseline, so a real
                    # descriptor that cannot be parsed makes the case unavailable, not broken.
                    results.append(f"SKIP  self-test/{name}: baseline unavailable — {_brief(error)}")
                    outcomes.append("unavailable")
                    continue
            if fixture_floors != {SYNTHETIC_PIN}:
                results.append(
                    f"FAIL  self-test/fixture-is-independent-of-the-live-pin: the fixture carries "
                    f"{sorted(fixture_floors)}, not just {SYNTHETIC_PIN} — normalization did not take, so "
                    "every case below is silently graded against the real pin again (round-1 review, M1)"
                )
            elif SYNTHETIC_PIN in real_floors:
                results.append(
                    f"FAIL  self-test/fixture-is-independent-of-the-live-pin: a REAL descriptor declares "
                    f"{SYNTHETIC_PIN}, so this case cannot distinguish a normalized fixture from an "
                    "un-normalized one. Change SYNTHETIC_PIN to a value no registry would ever say"
                )
            else:
                results.append(
                    f"PASS  self-test/fixture-is-independent-of-the-live-pin (fixture {SYNTHETIC_PIN}; "
                    f"real tree declares {sorted(real_floors)} and no outcome above depends on it)"
                )
                outcomes.append("pass")
                continue
            outcomes.append("fail")
            continue
        if name == "unreadable-local-registry-fails-closed":
            out: list[str] = []
            with tempfile.TemporaryDirectory() as raw:
                built = _build_fixture(name, Path(raw), results)
                if built is None:
                    outcomes.append("unavailable")
                    continue
                providers, _ = built
                try:
                    grade(providers, str(Path(raw) / "absent.yml"), out)
                    results.append("FAIL  self-test/unreadable-local-registry-fails-closed: it passed")
                    outcomes.append("fail")
                except FloorError as error:
                    if "no such file" in str(error):
                        results.append("PASS  self-test/unreadable-local-registry-fails-closed")
                        outcomes.append("pass")
                    else:
                        results.append(f"FAIL  self-test/unreadable-local-registry-fails-closed: {error}")
                        outcomes.append("fail")
            continue
        outcomes.append(_run_case(name, mutate, expect_fail, expect, results))

    print("\n".join(results))
    total = len(cases)
    verdict = _summarize(outcomes, graded_ok)
    unavailable = outcomes.count("unavailable")
    passed = outcomes.count("pass")
    if len(outcomes) != total:
        # The tally must cover every case. A case that fell through without recording an outcome
        # would silently shrink the denominator and could turn a red suite green.
        print(
            f"check-provider-floors: SELF-TEST BROKEN — {total} cases ran but {len(outcomes)} "
            "outcomes were recorded, so the tally does not cover the suite. Fix the checker.",
            file=sys.stderr,
        )
        return 1
    if verdict == "broken":
        # THE PREDICATE AND THE ACCUSATION MATCH. Every case above runs on a fixture this file builds
        # and normalizes itself: the real descriptors' VALUES, the org pin, and the state of the
        # working tree cannot reach any of these outcomes. So a failure here really does mean the
        # checker (or this demonstration) is broken. A mirror that has genuinely drifted is reported
        # by the LIVE grading, which `main` runs first and never suppresses — read that report above
        # this line before touching anything here.
        print(
            f"check-provider-floors: SELF-TEST BROKEN — {total - passed - unavailable} of {total} "
            "outcomes did not reproduce on a fixture this demonstration builds and normalizes itself, "
            "so the checker's own behaviour has changed. This is NOT a statement about providers/ — a "
            "real floor that disagrees with the registry is named in the live grading printed above. "
            "Fix the checker; do NOT delete the self-demonstration (FS.GG.Templates#383).",
            file=sys.stderr,
        )
        return 1
    if verdict == "builder-broken":
        # THE GRADING PASSED AND THE BUILDER STILL COULD NOT COPY THAT SAME TREE (round-1 review, M3).
        # So the descriptors are fine — the run just certified them, above — and blaming one would
        # name a file this very output declares correct. The fault is in the fixture builder.
        print(
            f"check-provider-floors: SELF-TEST CHECKER BROKEN — the live grading above passed every "
            f"descriptor, yet {unavailable} of {total} outcomes could not run because the fixture "
            "builder failed to copy and normalize that same coherent tree. Do NOT go looking at "
            "providers/: the descriptors were just graded correct. The fault is in this checker's "
            "fixture builder — see the SKIP lines above. (FS.GG.Templates#398)",
            file=sys.stderr,
        )
        return 1
    if verdict == "unavailable":
        # A DIFFERENT VERDICT BECAUSE IT HAS A DIFFERENT REMEDY. The demonstration builds its fixture
        # by COPYING the real descriptors, so a descriptor that cannot be read or normalized stops the
        # baseline from existing. Nothing here is evidence about the checker; the descriptor is named
        # in the SKIP lines above and in the live report above those.
        print(
            f"check-provider-floors: SELF-TEST BASELINE UNAVAILABLE — {unavailable} of {total} "
            "outcomes could not run, because the fixture is built from the real descriptors and one "
            "of them could not be copied and normalized. The checker's behaviour is NOT in question "
            "here: fix the descriptor named above, then this demonstration runs again. "
            "(FS.GG.Templates#398)",
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
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run ONLY the offline self-demonstration and exit (a normal run includes it, after grading)",
    )
    parser.add_argument("--github-output", type=Path, help="write `floor=<agreed floor>` here")
    parser.add_argument("--step-summary", type=Path, help="append a summary table here")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    # ── ORDER IS LOAD-BEARING: GRADE THE REAL SUBJECT FIRST, ALWAYS ────────────────────────────
    #
    # The workflow used to run `--self-test` as a separate command BEFORE this one, under
    # `set -euo pipefail`. A drifted descriptor then aborted the step inside the demonstration and
    # the real diagnostic — the `FAIL providers/…:N` line, the `::error`, the step summary, the
    # remedy — was never emitted, so #383's own verification line ("reds it, naming both values")
    # held through this CLI and NOT through CI, which is the only place anybody reads it. That is
    # FS.GG.Templates#349's shape and it was found by independent review of this very PR.
    #
    # So: grade, print, annotate, summarize — unconditionally. THEN demonstrate. Then combine the
    # two verdicts into one exit code, so neither can hide the other. The demonstration is offline
    # and costs well under a second, so there is no reason to make it conditional on the grading's
    # outcome, and a good reason not to: a checker that has broken should say so even on a tree that
    # happens to be coherent.
    out: list[str] = []
    graded = 1
    pin = None
    try:
        failures, pin = grade(args.providers, args.registry, out)
        graded = 1 if failures else 0
    except FloorError as error:
        annotate("provider floors could not be graded", str(error))
        out.append(f"check-provider-floors: {error}")
        failures = 1

    print("\n".join(out))
    flush_annotations()
    if args.step_summary:
        with args.step_summary.open("a", encoding="utf-8") as handle:
            handle.write("### composition — provider `minimumFsggSdd` floors\n\n")
            target = f"`{REGISTRY_SOURCE}` = **{pin}** (read live)" if pin else f"`{REGISTRY_SOURCE}` (UNREADABLE)"
            handle.write(f"Graded against {target}.\n\n")
            for line in out:
                handle.write(f"    {line}\n")
            handle.write("\n")
    if graded and pin:
        print(
            f"check-provider-floors: {failures} provider floor(s) do not mirror the org-wide pin {pin}",
            file=sys.stderr,
        )
    elif graded:
        print("check-provider-floors: the declared floors could not be graded (see above)", file=sys.stderr)
    else:
        print(f"check-provider-floors: every declared floor mirrors {REGISTRY_SOURCE} = {pin}")

    print()
    # THE SIGNAL IS ONLY EVIDENCE IF BOTH HALVES LOOKED AT THE SAME TREE. `grade` reads
    # `--providers`; the fixture builder always copies the repository's own `providers/`. They are
    # the same directory on every real run and the flag exists for offline experiments, so when they
    # differ a green grading says nothing about the tree the builder failed on, and this falls back
    # to blaming the descriptor the SKIP lines name.
    same_tree = args.providers.resolve() == REAL_PROVIDERS.resolve()
    demonstrated = self_test(graded_ok=(graded == 0 and same_tree))

    if graded or demonstrated:
        return 1
    # Only a run that both graded the real tree green AND demonstrated it could have gone red hands
    # the agreed floor onward.
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"floor={pin}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
