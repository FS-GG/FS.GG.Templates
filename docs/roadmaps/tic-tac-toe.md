# TTT-01 — Complete local tic-tac-toe browser game

Proposed owning document: `FS-GG/FS.GG.Templates/docs/roadmaps/tic-tac-toe.md`, landed with implementation. This draft exists only at `/tmp/r5-tic-tac-toe-plan-20260929.md`.

Named part: **TTT-01 — Local two-player tic-tac-toe**. Whole original/item: **TTT-01.1**. Stage: independent opt-in application source delivery, with no V0–V6 dependency. Owner: Templates implementation worker; parent `/root` integrates shared surfaces and admits the delivery PR. Route: routine. Implementation model: `gpt-5.6-sol`, medium. Canonical fallback skill (Templates has no installed copy): `/home/developer/projects/.github/.agents/skills/work-roadmap/SKILL.md`.

Backlink: [Unified §9.8](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index). User has authorized product decisions and the whole app; this plan adds no approval round. Planning, reducer completion, browser checks and merge are checkpoints of one original, not separately countable originals.

## Inspected baseline and choice

Inspected clean Templates main `408bc596ad435908ff730b464096bf700ed71b3e`; protected Unified guidance read from `/tmp/r5-five-item-native-readback-20260929`. Prospective R5 enrollment is `TTT-01.1`, selected `2026-09-29T06:31:33Z` in the parent's additional-app cohort draft, before outcomes.

Implemented source to reuse as patterns:

- `templates/fs-gg-web/Web/src/main.ts`, `Web.Tests/message.test.ts` and `Browser.Tests/home.spec.ts` demonstrate browser entry, Node assertions and Playwright. Its frontend toolchain pins TypeScript 5.9.3/Vite 7.3.6 and browser tests pin Playwright 1.63.0. The starter only fetches a server greeting.
- `templates/fs-gg-fable-game/Domain/{TacticalRules,ArcadeRules}.fs`, `SvgFoundation/PlayerInput.fs`, `Domain.Tests/RoomTests.fs` and `Browser.Tests/two-client.spec.ts` demonstrate pure transition logic, terminal refusal, restart and real controls. Delivered tactical and arcade examples are described in `docs/playground/selected-examples.md`; neither is tic-tac-toe.
- `models/svg-tactical/tactical-rules.qnt` models planning/commit/review; `models/svg-arena/arena-rules.qnt` models health/score/hazards. Neither defines this game's semantics. This independent sample does not select either provider/model contract. No new Quint tooling is necessary; exhaustive small-state behavioral checks cover the game. If scope changes to a modeled provider, preserve and satisfy its actual model authority before claiming that integration.

No tic-tac-toe implementation was found in Templates source/docs/tests. Existing source tests were inspected, not run during planning; no new installed or browser behavior is claimed.

Decision: deliver a standalone static browser sample in `examples/enrollment-apps/tic-tac-toe/`, served by the parent's shared sample harness. Use dependency-free browser ESM, a pure reducer and native HTML buttons. No server state, accounts, persistence, AI, network multiplayer or engine adapter is needed. Existing public game/runtime implementation remains a reference, not a new dependency. This is a useful complete game with its own real entry point, not another greeting scaffold.

## Product contract

The opening screen has a titled 3×3 board, X-to-play status, concise local two-player instructions and Restart. Cell indices are row-major 0–8. X starts; each valid move writes exactly one empty cell and alternates to O/X while play continues. The eight rows/columns/diagonals produce a win. Evaluate win before draw so a winning ninth move is still a win. A full board without a winner is a draw. Occupied, out-of-range/noninteger and post-terminal moves preserve state. Restart is available during play and after either result and returns the empty X-first game.

Expose a small `initialState()` and `reduce(state, action)` API in `game.mjs`, with explicit playing/won/draw state and immutable board updates. DOM code uses this reducer for every move and restart. No test-only win/draw setter or hidden midgame setup is a product API.

Use nine `button` elements with stable row/column accessible names plus the current mark/empty state, visible focus, readable marks, and a polite live status announcing turn/winner/draw. Keep occupied/terminal cells focusable with `aria-disabled` and reducer enforcement so the final board remains discoverable; native Enter/Space and pointer activation share the same command path. Avoid an ARIA grid unless its additional keyboard contract is implemented. Restart moves focus predictably to the first cell. Board and controls fit a 320px viewport without horizontal scrolling. Win presentation uses text/marks in addition to color.

## One whole delivery item and ready window

- [x] **TTT-01.1 — Play and restart a complete local tic-tac-toe game — routine.** Depends on no other product lane. Completion requires the product, focused verification, required native checks, source merge, protected readback and owning acceptance together.

The first executable window is the entire bounded source item, in three adjacent stages on one isolated branch. These stage labels do not create new item/original identities.

**A — Game and reducer.** Implement `game.mjs`, `main.mjs`, `index.html`, `styles.css` and concise launch documentation. Node tests cover all eight win lines, both winners, draw, occupied/invalid/terminal refusal, restart from each phase and input-state immutability. Enumerate reachable states from the empty game with an independent test oracle; verify mark-count/turn invariants, that terminal states cannot advance, and that each legal transition changes one cell. Use all reachable states rather than randomized coverage for this tiny domain. Do not duplicate the production winner helper in the oracle.

**B — Whole browser acceptance.** Add a game-local Playwright spec discovered by the parent harness, with no direct state injection. Launch the actual `index.html` through its real module entry. Play X win via indices `0,3,1,4,2`; restart and play O win via `0,3,1,4,8,5`; restart and play draw via `0,1,2,4,3,5,7,6,8`. Attempt an occupied move early and an empty-cell move after a win and assert board and result remain unchanged. Assert initial turn, alternating status, accessible marks and restart. Complete at least one full game with keyboard Tab/Enter/Space only, and another by pointer. Check visible focus and a narrow viewport; capture browser errors and fail unexpected page errors. Browser assertions examine rendered behavior, not private reducer state. Restart during an unfinished game is also covered.

**C — Native delivery and readback.** Parent joins the shared runner/workflow, then run Node tests and the real browser suite against the exact candidate, plus repository-native required checks and routine eligibility/operation fixtures applicable to that base. Apply ADR-0084's qualification dispositions through the existing routine helper. Parent controls PR admission through `.github/tools/pr-lane-admission.py` after reading the live queue; keep at most one delivery PR for this chain. Read back merged PR/commit, compare delivered content with the qualified head, and read the checked owning item from protected main. Only then record whole-item Done/completion. A local green test run or PR creation does not count.

## Disjoint work and joins

One Sol worker owns only `examples/enrollment-apps/tic-tac-toe/**`, including game-local unit/browser specs and README. Use an isolated worktree/branch from the current protected Templates head. Other app workers must not edit this subtree.

Parent `/root` owns `examples/enrollment-apps/package.json`, lockfile, static server, shared Playwright configuration, shared catalog/README, CI workflow and the owning roadmap path. Parent agrees the sample URL and test discovery/import convention before browser integration; a suitable URL is `/tic-tac-toe/`, with game-local `*.test.mjs` and `*.spec.mjs` and Playwright imported from `@playwright/test`. Root can collect the browser specs by directory. The game has no runtime npm dependency. Worker can implement and run reducer tests while that join is prepared. If the harness convention differs, adapt only this sample's paths/imports or send the shared request to the parent. Do not edit the web/fable-game templates, providers, package project or other games.

Parent owns the `.github` Unified §9.8 link and §0 closure projection plus R5 cohort update. Suggested new row:

`| **Local two-player tic-tac-toe — TTT-01** | Independent opt-in browser sample; whole TTT-01.1 requires full gameplay, controls-driven acceptance and native delivery | FS.GG.Templates; no product prerequisite; shared harness joins through parent | [Draft plan](/tmp/r5-tic-tac-toe-plan-20260929.md), replaced after delivery by [owning roadmap](https://github.com/FS-GG/FS.GG.Templates/blob/main/docs/roadmaps/tic-tac-toe.md) |`

Use the real draft location until the durable document exists; do not publish the future URL as an existing artifact. Apply link maintenance asynchronously with existing work, and §0 immediately after authoritative completion, without gating independent lanes.

## Unified §9.9 boundaries and observation

Affected generated-workspace families: **none**. The inspected package project explicitly packs `templates/**/*`; the new `examples/` sample is outside that payload. Before: no sample at this path. After: a checkout user explicitly launches a playable game. Stage A first changes this opt-in sample's runtime; none of these stages changes fresh `fs-gg-web`, `fs-gg-fable-game`, SDD or wizard creation. Publication and scaffold/receiver adoption are not selected and have no release identity. A later packaged-template integration would need its own producer publication, selected receiver adoption and clean/retained acceptance.

Clean-source proof here means a fresh checkout installs the pinned shared test tools and serves/runs the whole sample using documented commands. It must not be labeled an installed scaffold proof. Existing generated workspaces receive no automatic update; there is no retained-workspace upgrader or promise in this item. Preserve those distinct boundaries in delivery evidence.

Telemetry begin was reported by the parent as exit 2/not configured. Keep planning, implementation, repairs and delivery under `TTT-01.1`; preserve available real command/CI evidence. Native usage remains unknown until actual complete observations exist. Missing measurement does not block source delivery or establish efficiency. The R5 target remains ten completed canonical originals: this game contributes at most one after native acceptance/readback, never one per stage or win/draw case.

No consequential product decision remains unresolved. Stop on a newly discovered shared-surface collision or a failed technical/native gate, repair within the same original, and distinguish ready-window completion from whole delivery. AI, online multiplayer, persistence, packaging and publication are outside this selected outcome and need no outline milestone to finish it.

## Qualified source window — 2026-09-29

The complete local source window is qualified at clean code checkpoint `4181f1a6dacf92151fff7f6217d045137d4546cc`. The root-owned locked shared harness stages exact source bytes and passes all 18 domain checks and 14 serial Chromium journeys, including this app's real entry and controls. Each app remains one original. Native required qualification, source merge and protected owning-plan readback establish authoritative completion; this local checked outcome does not increment the cohort by itself. See [joined source evidence](evidence/r5-browser-apps-20260929.md). Publication and installed scaffold adoption remain separate and unselected.
