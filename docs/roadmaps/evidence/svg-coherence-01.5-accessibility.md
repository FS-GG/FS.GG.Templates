# SVG-COHERENCE-01.5 accessible alternatives and focus: automated container qualification

Templates owner, 2026-10-30. Source for [FS-GG/.github#4645](https://github.com/FS-GG/.github/issues/4645).
Root's 2026-10-30 ruling on that issue corrects the earlier reading that `.5` accessible
alternatives need a human: the plan's `.5` acceptance is "Container-qualified ... focus"
([plan section 7](https://github.com/FS-GG/.github/blob/main/docs/roadmaps/svg-coherence-and-instancing-01.md)),
met by automated evidence. This file records what that evidence is and what it does not claim.

## What runs

`observe-soldier-accessibility.sh` reuses the staged candidate that
`verify-soldier-reference-candidate.sh ... staged` already builds (generated ASP.NET server plus
sealed webroot). It serves it once on a task-owned loopback port, runs three observers, verifies
their output with `test-soldier-accessibility.py`, and stops only the server it started. It adds no
endpoint, credential or checkout access and rebuilds nothing. CI runs it in the existing
`svg-preview-c` public-source job after the staged step.

| Route | Observer | What it establishes |
|---|---|---|
| Browser accessibility tree | `soldier-accessibility-observe.mjs`: CDP `Accessibility.getFullAXTree` / `getPartialAXTree`; Playwright `ariaSnapshot` on Chromium, Firefox and WebKit | The tree an assistive technology is offered: roles, names, states, focusability, live region |
| Trusted keyboard focus | Same observer, CDP keyboard input (Tab, Enter, Space), not DOM `click()` | Tab order, activation, focus transfer on removal and churn, keyboard export |
| Orca / AT-SPI | `observe-soldier-orca.sh`, `soldier-orca-browser.cjs`, `soldier-input-orca.py`; Xvfb, `xdotool` key events, Orca 46.1 speech log | Real X11 key events, AT-SPI focus agreeing with the DOM, Orca's spoken output, on the soldier player rather than the Studio |
| axe-core 4.11.0 (pinned, `accessibility/package-lock.json`) | Same Chromium observer | **Screening only.** Violations and incompletes are recorded; none is accepted or refused as a conformance claim |

## Gates and causal controls

Fixed rosters (the verifier refuses a shrunken roster): **34 gates** on Chromium, **32 causal
controls**, and **10 Orca steps** with **3 Orca controls**. Each control removes one accessible
property and must be refused on the assertion that depends on it.

**All 34 of 34 gates have a demonstrated refusal control.** The verifier computes this from the
recorded rows (the union of the assertions each refused control expected) and fails the run if any
gate is uncovered. An earlier revision of this note covered fewer: the churn, population, disposal,
AX-focus-parity, move, roster-label and live-region gates had no control that could fail them. They
now have one each, listed below.

Chromium refusals (31), each running only the journey phase its gate belongs to:

| Phase | Controls (expected failing gate) |
|---|---|
| structure | panel accessible name removed (`panel-region-name`); panel `tabindex` removed (`panel-focusable`); heading demoted to level 3 (`panel-heading-level-2`); note field name removed (`note-textbox-name`); live region switched off (`status-live-polite`); a command hidden from the tree (`command-buttons-present`); two commands sharing a name (`command-names-unique-nonempty`); a command disabled (`command-buttons-focusable-enabled`); roster hidden (`roster-alternatives-complete`); roster button name removed (`roster-names-nonempty-descriptive`); roster names duplicated (`roster-names-unique`); `aria-pressed` removed (`roster-pressed-state-exposed`); last roster alternative dropped (`roster-alternatives-complete`); a painted soldier removed from the SVG (`svg-canvas-has-roster-alternative`); roster group role removed and roster group name removed (`roster-group-named`, two controls) |
| keyboard | a command removed from Tab order (`tab-reaches-every-command`); a roster button removed from Tab order (`tab-reaches-every-roster-button`); a focusable command relabelled in the tree only (`ax-focus-matches-dom-focus`); pressed state removed after selection (`keyboard-select-roster`, `roster-pressed-matches-dom-after-selection`); Move click swallowed (`keyboard-command-moves-selected`); roster label drifting from state (`roster-name-follows-state`); programmatic focus transfer suppressed on Remove (`removal-focus-transfers-to-survivor`); live-region text cleared (`removal-written-to-live-region`) |
| churn | focus transfer suppressed (`offscreen-removal-focus-transfers`); focus stolen after Spawn (`spawn-keeps-focus-on-control`); a roster entry dropped from the 2,000-world (`roster-follows-churn-world`); Export click swallowed (`keyboard-export-full-world`) |
| populations | roster hidden at every population (`population-{1,100,250,500,1000}-roster-exposed-unique`) |
| disposal | Dispose click swallowed (`disposed-panel-absent-from-ax-tree`); programmatic focus suppressed during Dispose (`disposal-focus-returns-to-entry-control`) |

Also: one axe liveness control (an unnamed button must produce `button-name`), a clean baseline with zero gate failures, and a verifier self-test that refuses 26
deliberately weakened result sets (including a missing required browser family). Roster mutations are
re-applied on every product commit, because the product re-renders roster text and state. A timed-out
wait inside a gate is recorded as a failed assertion, never as an observer error, and an observer
error never counts as a refusal.

Orca controls (3): unnamed roster button, no focus transfer, polite region switched off. Each must end
`refused` at its own step (never `passed`, never at another step).

Two changes to the gate roster since the first revision: `removal-announced-in-live-region` is
renamed `removal-written-to-live-region` (it asserts the DOM text, not speech; speech is gated in the
Orca observer), and `disposed-focus-not-on-detached-node` is removed because it cannot fail (a browser
never leaves `activeElement` on a detached node). `svg-canvas-has-roster-alternative` is tightened:
the set of soldier ids painted in the SVG must equal the set of roster ids, one to one.

Journey covered on the actual player: keyboard-only mount; every command and all roster buttons
reachable by Tab with AX focus equal to DOM focus at each of 139 stops; keyboard selection;
`aria-pressed` mirrored in the tree; keyboard move; removal moves focus to the first survivor and
Orca speaks both the new focus target and the live-region message; offscreen removal in the
2,000-world/200-visible churn case; spawn; keyboard download of the full world export (2,000 `use`
elements); populations 1, 100, 250, 500 and 1,000 each expose that many uniquely named roster
buttons; disposal leaves no panel nodes in the tree and returns focus to `#mount-soldier-reference`.

## Findings (resolved; now gates)

Two gaps were first recorded as non-gating `finding` assertions, each with a resolution control.
Both are fixed in `SoldierReference.fs` and promoted to gates, each with its own refusal control, so a
regression is refused rather than reported:

1. `roster-group-named` ([Templates#827](https://github.com/FS-GG/FS.GG.Templates/issues/827)): the
   roster container now has `role="group"`, so Chromium keeps the `aria-label="Soldier roster"` name.
   Refusal controls remove the role and remove the name.
2. `disposal-focus-returns-to-entry-control`
   ([Templates#828](https://github.com/FS-GG/FS.GG.Templates/issues/828)): disposing the panel moves
   focus to `#mount-soldier-reference` when removal dropped it to `body`; focus already elsewhere is left
   alone. The refusal control suppresses programmatic focus during the Dispose click.

Before the fix, both gates failed against the unfixed source (`found: 0, roles: [generic]` and
`active: body`); after it, they pass. The finding mechanism stays for future gaps. The two files are
hash-tracked for retained upgrades, so the adoption manifest admits the successor digests of
`SvgFoundation/SoldierReference.fs` and `Browser.Tests/soldier-reference.spec.ts` beside the old ones.

## Orca and the live region (corrected)

The first revision recorded `orcaSpokeLiveRegion: false` and explained it as Orca flushing live-region
messages on key presses. That was wrong. The retained debug logs show Orca did speak
`Focused soldier removed; ...` about 51 to 58 ms after speaking the new focus target, in both the
hosted baseline and a local one. The `false` was a detector false negative: `/usr/bin/orca` opens its
`--debug-file` with default block buffering (`open(args.debug_file, 'w')`), so the final lines of the
log, which is all that is written after the last keypress, can sit unflushed while the observer polls.

`soldier-orca-launcher.py` now opens that one file line-buffered, `observe-soldier-orca.sh` uses it,
and the live-region speech is a gate (`removal-status-spoken-by-orca`), next to the AT-SPI exposure of the
polite region (`removal-status-exposed-as-polite-live-region`) and the spoken focus target. The live-region
message was spoken in 3 of 3 local baseline runs after the fix.

axe-core screening on the mounted panel: 0 violations, 1 incomplete (`color-contrast` on 4 nodes), 20
passes. The earlier `aria-prohibited-attr` incomplete on the roster container no longer appears.

## Local qualification record

fdev, 2026-10-30/31, Ubuntu 24.04 container with the CI package set (Orca 46.1), Chrome for Testing
153.0.8010.12, Playwright 1.63.0, bounded `systemd-run` (200% CPU, 4 GiB). Chromium: 32/32 gates, 31/31
controls (revision before the findings were promoted); Firefox and WebKit `ariaSnapshot` passed; Orca baseline 10/10 steps with the live-region message
spoken, and 3/3 controls refused. Source: Rendering `c921eb13` staged fixture unchanged.

## Not claimed

No physical-input, physical-keyboard-latency or assistive-technology user evidence; Orca on Xvfb with
a null audio sink is not audible output. No screen-reader coverage beyond Orca/Chromium. No GPU,
performance, publication or installed-adoption claim. Local and external authority modes share one
panel; the external-authority path is exercised by the existing staged journey, not re-observed here.

Findings promotion, fdev 2026-10-31 (same CI package set minus Orca, Chrome for Testing 153.0.8010.12,
SDK 10.0.403, bounded `systemd-run`): against the unfixed source Chromium reported 32/34 gates with
exactly `roster-group-named` and `disposal-focus-returns-to-entry-control` failing; against the fixed
source 34/34 gates and 32/32 controls passed (verifier: `gatesWithRefusalControl` 34). Firefox, WebKit
and Orca were not re-run locally; CI runs them.
