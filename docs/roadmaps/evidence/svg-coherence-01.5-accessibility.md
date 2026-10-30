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

Fixed rosters (the verifier refuses a shrunken roster): **33 gates** on Chromium, **15 causal
controls**, and **9 Orca steps** with **3 Orca controls**. Each control removes one accessible
property and must be refused on the assertion that depends on it:

- Chromium refusals (12): panel accessible name; panel focusability; roster button name; duplicate
  roster names; disabled command; live region switched off; roster hidden from the tree; pressed
  state removed; last roster alternative dropped; command removed from Tab order; roster button
  removed from Tab order; programmatic focus transfer suppressed. Roster mutations are re-applied
  on every product commit, because the product re-renders roster text and state.
- axe liveness (1): an unnamed button must produce `button-name`.
- Resolution controls (2): doing the missing thing flips the matching open finding to resolved.
- Orca refusals (3): unnamed roster button, no focus transfer, polite region switched off. Each must
  end `refused` at its own step, never `passed`, never at another step.
- A clean baseline run reports zero gate failures.
- `test-soldier-accessibility.py --self-test` refuses 19 deliberately weakened result sets.

Journey covered on the actual player: keyboard-only mount; every command and all roster buttons
reachable by Tab with AX focus equal to DOM focus at each of 139 stops; keyboard selection;
`aria-pressed` mirrored in the tree; keyboard move; removal moves focus to the first survivor and
Orca speaks it; offscreen removal in the 2,000-world/200-visible churn case; spawn; keyboard
download of the full world export (2,000 `use` elements); populations 1, 100, 250, 500 and 1,000
each expose that many uniquely named roster buttons; disposal leaves no panel nodes in the tree.

## Findings (open, not gates)

The player is unchanged by this work. Two gaps are recorded as `finding` assertions: they never
pass or refuse a run, and each has a resolution control proving the detector can see it fixed.

1. `roster-group-named`: the roster container has `aria-label="Soldier roster"` on a `div` with no
   role, so Chromium exposes it as generic and drops the name (axe: `aria-prohibited-attr`, one
   node, incomplete). Every roster button is individually named and reachable, so the alternatives
   are complete; only the group label is lost. A `role="group"` would resolve it.
2. `disposal-focus-returns-to-entry-control`: after "Dispose soldier reference" focus falls to
   `body`, not to the "Mount soldier reference" control. Focus is never left on a detached node.

A third observation concerns Orca, not the player: Orca receives `object:text-changed:insert` for
the `status` live region, which AT-SPI exposes with `container-live:polite`, but it did not speak the
removal message in the final runs (it spoke it in one earlier run), and spoke neither the removal nor
an `External authority required` update in two diagnostic runs. Orca 46.1 flushes live-region messages
on key presses, so this is a timing race. The Orca baseline therefore gates the AT-SPI exposure of
the polite region and the spoken focus target, and records `orcaSpokeLiveRegion` without gating it.
Whether a `div role="status"` behaves differently is unresolved (one probe spoke it in the removal
case only).

axe-core screening on the mounted panel: 0 violations, 2 incompletes (`aria-prohibited-attr` on one
node, `color-contrast` on 30 nodes), 16 passes.

## Local qualification record

fdev, 2026-10-30, Ubuntu 24.04 container with the CI package set (Orca 46.1), Chrome for Testing
153.0.8010.12, Playwright 1.63.0, bounded `systemd-run` (200% CPU, 4 GiB): Chromium observer passed
33/33 gates, 15/15 controls (557.6 s under load); Orca baseline and 3 controls passed
(`orca` 9 steps). Firefox `ariaSnapshot` passed. WebKit could not run in that container (missing system
libraries) and is covered only by the hosted job. Source: Rendering `c921eb13` staged fixture
unchanged (manifest `cb9636c5...`).

## Not claimed

No physical-input, physical-keyboard-latency or assistive-technology user evidence; Orca on Xvfb with
a null audio sink is not audible output. No screen-reader coverage beyond Orca/Chromium. No GPU,
performance, publication or installed-adoption claim. Local and external authority modes share one
panel; the external-authority path is exercised by the existing staged journey, not re-observed here.
