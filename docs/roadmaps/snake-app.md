# SNAKE-01 — Complete opt-in browser Snake

Status: proposed executable plan, 2026-09-29. Owner: FS-GG.Templates; one Sol-medium implementation owner, parent as shared-harness and delivery integrator. Canonical original: **SNAKE-01.1**. This is one whole-app original; implementation steps, test jobs and repairs never become additional cohort originals.

The app is an independent product track, prospectively selected at `2026-09-29T06:31:33Z` in the parent’s additional-app cohort amendment, before this plan or implementation outcome. It has no V0–V6 completion prerequisite. [Unified §9.8](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index) supplies the index; §9.9 governs the workspace boundary below.

## Product and inspected baseline

Deliver a complete local browser game: Start, steer with arrows or WASD, eat food, grow, see score, pause/resume, lose on wall or body collision, and restart. It runs from its real HTML entry point and builds no dependency on a backend, installed template, account or service.

Inspection used clean Templates main `408bc596ad435908ff730b464096bf700ed71b3e` and the protected Unified readback at `/tmp/r5-five-item-native-readback-20260929`. These sources establish the reusable baseline:

| Existing source | Finding and use |
|---|---|
| [Snake TestSpec](https://github.com/FS-GG/FS.GG.Templates/blob/408bc596ad435908ff730b464096bf700ed71b3e/docs/TestSpecs/Games/snake.md) | `status: spec`; prior research, not an app or completion. Reuse its 32×18 grid, length-three start, queued-turn guard, food/growth, +10 scoring, pause semantics, vacating-tail exception and full-board terminal case. |
| `templates/fs-gg-fable-game/Domain/ArcadeRules.fs`, `SvgFoundation/ArcadeExample.fs` | Implemented continuous collectible/hazard/goal game using Game.Core SessionRuntime and SVG rendering. They do not implement Snake; do not relabel or modify this delivered example. Reuse the separation of reducer, runtime and view as a design pattern. |
| `templates/fs-gg-fable-game/Domain.Tests/RoomTests.fs` and `Browser.Tests/` | Existing domain/browser testing patterns. Their presence does not independently demonstrate this new game. |
| `templates/fs-gg-web/Web/src/main.ts`, `Web.Tests/`, `Browser.Tests/` | Existing browser entry, Node-test and Playwright patterns. The web template has an API-backed greeting; neither server nor TypeScript is necessary for this standalone game. |
| `docs/roadmaps/svg-workspace-01.md`, bounded-authority section | Preserve canonical model and correspondence duties when changing modeled SVG engine modules. This isolated browser-native reducer adds no engine module and changes none of those existing authorities. |
| `FS.GG.Templates.csproj` | Package content is selected under `templates/**/*` and explicit skill/pack paths. The new `examples/` source is outside those selected template bytes. |

No `examples/` directory or delivered Snake app existed at the inspected head. Implementation, app acceptance and native delivery are missing. Existing source alone does not demonstrate installed behavior.

## Decisions and boundaries

Use browser-native ESM JavaScript, semantic HTML/CSS and an SVG grid. A pure domain module owns all state changes; an adapter translates keyboard/button events and elapsed browser time into reducer messages; rendering projects state. The parent has selected this shared runtime for the four independent apps. No framework, transpiler, server or package-owned engine change is needed.

Choose a 32-column × 18-row wall-bounded board. Start length is three, head `(16,9)`, heading right. A food pellet grows length by one and awards ten points. Adopt the existing specification’s speed curve: 180 ms initially, six ms faster per food, floor 60 ms. These are constant configuration values, not a new configuration UI. Food selection enumerates free cells deterministically and advances an explicit integer PRNG state; a fixed documented initial seed makes restart and input traces reproducible. Food never occupies a snake cell. Eating the last free cell produces a distinct won state with no food and no further movement.

Use states Ready, Running, Paused, Lost and Won. Only Running admits direction input and movement. Buffer at most two turns; reject reversal against the latest queued direction, and guard again when committing a turn. Consume at most one queued direction each simulation step. Reject repeated keyboard events so held keys cannot flood the queue. Freeze queued turns and fractional elapsed time while paused; reset the adapter’s elapsed-time baseline on resume to avoid catch-up. Cap catch-up at four steps after a stall, then discard excess backlog. Auto-pause on document hiding or window blur and require deliberate resume.

On a non-growing step, exclude the vacating tail from collision occupancy. On collision, keep the last valid bounded body and enter Lost. Ticks, directions and pause do not mutate terminal game state. Restart creates a fresh run with empty queue, zero score, initial timing and deterministic seed; repeated restarts must not create extra timers or listeners.

Provide visible score, state and brief control instructions, a focusable named play area, keyboard-operable Start/Pause/Resume/Restart buttons, and visibly distinct head/body/food. Keep keyboard handling scoped to the game and prevent browser scrolling only for handled controls. Use a responsive SVG viewBox so grid coordinates remain logical cells. Avoid per-tick live-region announcements; announce state and score changes. Audio, wrap mode, persistent high scores, mobile touch controls and arbitrary board settings are outside this requested whole-app outcome; the prior TestSpec is research rather than a promise to port its optional/native features.

## One ready delivery item

- [x] **SNAKE-01.1 — Play and deliver the complete browser Snake app — route: routine.**
  Depends on: none for local implementation. Parent’s shared runner is needed only for integrated browser/native qualification. Scope: `examples/enrollment-apps/snake/**`, including app entry, reducer, styles, unit tests, browser spec and concise README/owning acceptance record. The same item covers all steps below and all repairs.

The first executable window is the entire item’s local implementation and focused qualification. Complete these dependent steps on one isolated branch, without separate PRs or completion counts:

1. Implement the reducer and exact state contract, then meaningful Node tests. Verify movement, food/growth/score, speed floor, bounded turn queue, direct and queued reversal, pause/no accumulated pause time, terminal refusal, reset, self-collision versus legal vacating-tail movement, valid food placement and full-board win. Use small explicit valid states only in domain tests. Replaying the same seed and input/time trace must yield identical states. Test broad invariant traces: unique in-bounds body, length/score relationship, legal food and bounded queue.
2. Wire the actual browser entry, controls, timer and responsive display. A local user must be able to complete repeated playable runs with no test-only start state. Include a retained real-clock smoke journey to catch a disconnected timer or movement caused solely by test hooks.
3. Run browser journeys through actual keyboard/buttons from the normal initial page. Verify start and timed movement, food consumption with visible growth/score, two buffered turns and rejected reversal, pause/resume without fast-forward, wall loss and terminal input refusal, then restart and second run. Add a controls-driven self-collision journey using the deterministic food sequence; domain fixture injection does not satisfy this journey. Tests may use Playwright’s clock to advance time deterministically after loading the real entry; they must not call the reducer directly or overwrite browser game state. Assert rendered body/food coordinates as well as status text. A small viewport and keyboard-only controls smoke check establish the bounded accessibility/responsiveness claim.
4. Join the shared harness, qualify the exact candidate and deliver through the native routine route. Record the qualified commit/tree, commands, browser results and material limitations in the item’s concise evidence. Keep any incomplete delivery or failed acceptance open.

The worker uses `/home/developer/projects/.github/.agents/skills/work-roadmap/SKILL.md`, the located canonical fallback because Templates has no `.agents/skills/work-roadmap` installed. The parent supplies current routine policy/helper paths and authority. Local source and tests are authorized. Parent controls remote PR admission, native merge and cross-repository projections. No new issue, claim, ceremony ledger or metadata-Done write is necessary.

## Disjoint ownership and shared join

The Snake worker edits only `examples/enrollment-apps/snake/**`. Suggested files are `index.html`, `app.js`, `domain.js`, `style.css`, `domain.test.mjs`, `snake.spec.js` and `README.md`; naming can follow the integrator’s frozen harness convention. Use relative browser ESM imports and Node’s built-in test runner. The browser spec targets the parent’s `/snake/` route. Keep generated reports and screenshots out of source unless deliberately selected as evidence.

The root integrator alone owns `examples/enrollment-apps` shared package/lock, server, Playwright configuration, catalog, shared README and workflow changes, plus the durable plan placement at `docs/roadmaps/snake-01.md` and Unified/cohort projections. Before implementation, give the worker the frozen runner discovery convention; a rename of its local spec is a join adjustment, not a replan. Root must wire this app’s real domain and browser tests into candidate qualification: existing `composition` success alone does not prove Snake. Shared scripts/workflow changes receive their proportionate checks and existing required native gates. Queue admission remains at most one delivery PR for this dependency chain and two newly qualifying PRs in Templates; bundling the four app source trees in one coherent integration PR does not combine their original identities or weaken their individual acceptance.

Stop the local worker at a qualified local handoff unless the parent admits delivery. After all acceptance passes, parent reads back merged PR state, exact merge commit/tree and the owning checked outcome from protected main. Only then may **SNAKE-01.1** count as one completed original. A checked local candidate, browser test job, scaffold, shared integration shell or plan is insufficient. After native completion, land the asynchronous Unified §0/§9.8 and cohort update; keep usage and publication claims separate.

## Workspace impact and later scope

Under Unified §9.9, affected scaffold/provider/lifecycle families: **none**. Before this work the repository has a Snake specification; after SNAKE-01.1 it additionally offers an explicitly opened runnable source sample. SNAKE-01.1 first changes that sample’s runtime behavior. Template selection, package bytes and lifecycle defaults remain unchanged. There is no producer publication or installed receiver adoption in this item, and no release identity is claimed.

Clean acceptance is a fresh checkout/copy of the selected sample plus shared runner at the qualified revision, installed from the checked lockfile, then a real entry-point run and browser journeys. This proves fresh source use, not installed SDD/template creation. Existing workspaces are not modified and receive no automatic upgrade; retained source use can update explicitly through normal version control. No retained-template compatibility promise is introduced. Any future package inclusion or scaffold selection must separately name producer release, clean receiver creation and supported retained adoption before claiming installed behavior.

No additional milestone is needed for the requested game. Future optional touch controls, high-score persistence or template extraction remain outlines until separately selected; their absence does not inflate or split SNAKE-01.1.

## Observation and index update

Preserve `feature=SNAKE-01`, `item=originalItem=SNAKE-01.1` through planner, worker, tests, follow-ups and delivery. Parent reported telemetry begin exit 2 (`not configured`); native whole-item usage remains unknown. Preserve available native artifacts and real outcomes without inferred counters. The R5 target stays ten completed originals; this plan contributes zero. Missing usage cannot prove efficiency or the Unified §7.4 bureaucracy thresholds. Useful tests remain useful work under those definitions.

Proposed §9.8 row once the actual draft or durable plan exists:

| **Opt-in browser Snake** | Independent product track; SNAKE-01.1 is one prospectively selected whole-app original | `FS.GG.Templates`; complete keyboard play, food/growth/score, pause/restart and collision terminal behavior. Native source acceptance required; no scaffold/default or installed-adoption claim | [SNAKE-01 owning plan](https://github.com/FS-GG/FS.GG.Templates/blob/main/docs/roadmaps/snake-01.md) |

Do not publish that future main link before the file lands; use this actual draft path or its actual implementation-branch location in the interim. No unresolved product decision prevents the local window. A material request to use the Fable/SVG engine or ship a generated template would require a bounded scope amendment and the corresponding real model/receiver checks.

## Qualified source window — 2026-09-29

The complete local source window is qualified at clean code checkpoint `4181f1a6dacf92151fff7f6217d045137d4546cc`. The root-owned locked shared harness stages exact source bytes and passes all 18 domain checks and 14 serial Chromium journeys, including this app's real entry and controls. Each app remains one original. Native required qualification, source merge and protected owning-plan readback establish authoritative completion; this local checked outcome does not increment the cohort by itself. See [joined source evidence](evidence/r5-browser-apps-20260929.md). Publication and installed scaffold adoption remain separate and unselected.
