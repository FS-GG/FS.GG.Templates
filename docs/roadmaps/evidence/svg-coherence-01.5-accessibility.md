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

Fixed rosters (the verifier refuses a shrunken roster): **32 gates** on Chromium, **31 causal
controls**, and **10 Orca steps** with **3 Orca controls**. Each control removes one accessible
property and must be refused on the assertion that depends on it.

**All 32 of 32 gates have a demonstrated refusal control.** The verifier computes this from the
recorded rows (the union of the assertions each refused control expected) and fails the run if any
gate is uncovered. An earlier revision of this note covered fewer: the churn, population, disposal,
AX-focus-parity, move, roster-label and live-region gates had no control that could fail them. They
now have one each, listed below.

Chromium refusals (28), each running only the journey phase its gate belongs to:

| Phase | Controls (expected failing gate) |
|---|---|
| structure | panel accessible name removed (`panel-region-name`); panel `tabindex` removed (`panel-focusable`); heading demoted to level 3 (`panel-heading-level-2`); note field name removed (`note-textbox-name`); live region switched off (`status-live-polite`); a command hidden from the tree (`command-buttons-present`); two commands sharing a name (`command-names-unique-nonempty`); a command disabled (`command-buttons-focusable-enabled`); roster hidden (`roster-alternatives-complete`); roster button name removed (`roster-names-nonempty-descriptive`); roster names duplicated (`roster-names-unique`); `aria-pressed` removed (`roster-pressed-state-exposed`); last roster alternative dropped (`roster-alternatives-complete`); a painted soldier removed from the SVG (`svg-canvas-has-roster-alternative`) |
| keyboard | a command removed from Tab order (`tab-reaches-every-command`); a roster button removed from Tab order (`tab-reaches-every-roster-button`); a focusable command relabelled in the tree only (`ax-focus-matches-dom-focus`); pressed state removed after selection (`keyboard-select-roster`, `roster-pressed-matches-dom-after-selection`); Move click swallowed (`keyboard-command-moves-selected`); roster label drifting from state (`roster-name-follows-state`); programmatic focus transfer suppressed on Remove (`removal-focus-transfers-to-survivor`); live-region text cleared (`removal-written-to-live-region`) |
| churn | focus transfer suppressed (`offscreen-removal-focus-transfers`); focus stolen after Spawn (`spawn-keeps-focus-on-control`); a roster entry dropped from the 2,000-world (`roster-follows-churn-world`); Export click swallowed (`keyboard-export-full-world`) |
| populations | roster hidden at every population (`population-{1,100,250,500,1000}-roster-exposed-unique`) |
| disposal | Dispose click swallowed (`disposed-panel-absent-from-ax-tree`) |

Also: one axe liveness control (an unnamed button must produce `button-name`), two resolution
controls (below), a clean baseline with zero gate failures, and a verifier self-test that refuses 21
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
buttons; disposal leaves no panel nodes in the tree.

## Findings (open, not gates)

The player is unchanged by this work. Two gaps are recorded as `finding` assertions: they never
pass or refuse a run, each has a resolution control proving the detector can see it fixed, and each
is a tracked issue with an owner.

1. `roster-group-named` ([Templates#827](https://github.com/FS-GG/FS.GG.Templates/issues/827)): the
   roster container has `aria-label="Soldier roster"` on a `div` with no role, so Chromium exposes it
   as generic and drops the name (axe: `aria-prohibited-attr`, one node, incomplete). Every roster
   button is individually named and reachable, so the alternatives are complete; only the group label
   is lost. A `role="group"` would resolve it.
2. `disposal-focus-returns-to-entry-control`
   ([Templates#828](https://github.com/FS-GG/FS.GG.Templates/issues/828)): after "Dispose soldier
   reference" focus falls to `body`, not to the "Mount soldier reference" control.

Both files are hash-tracked for retained upgrades, so a fix needs the adoption manifest and upgrade
rehearsal updated in the same change.

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

axe-core screening on the mounted panel: 0 violations, 2 incompletes (`aria-prohibited-attr` on one
node, `color-contrast` on 30 nodes), 16 passes.

## Local qualification record

fdev, 2026-10-30/31, Ubuntu 24.04 container with the CI package set (Orca 46.1), Chrome for Testing
153.0.8010.12, Playwright 1.63.0, bounded `systemd-run` (200% CPU, 4 GiB). Chromium: 32/32 gates, 31/31
controls; Firefox and WebKit `ariaSnapshot` passed; Orca baseline 10/10 steps with the live-region message
spoken, and 3/3 controls refused. Source: Rendering `c921eb13` staged fixture unchanged.

## Not claimed

No physical-input, physical-keyboard-latency or assistive-technology user evidence; Orca on Xvfb with
a null audio sink is not audible output. No screen-reader coverage beyond Orca/Chromium. No GPU,
performance, publication or installed-adoption claim. Local and external authority modes share one
panel; the external-authority path is exercised by the existing staged journey, not re-observed here.
