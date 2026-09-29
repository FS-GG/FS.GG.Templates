# HELLO-01 — Hello-world browser app

Draft for `FS-GG/FS.GG.Templates`, to land with implementation at
`docs/roadmaps/hello-world-app.md`. Named part: **Hello-world browser app — HELLO-01**;
independent product example, prospectively enrolled in R5, with no V0–V6 dependency.
[Unified roadmap §9.8](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index)
is the planning index; the owning checkbox below is the completion authority.

## Outcome and inspected prior work

A user follows the example README, builds and serves the app, opens its URL, and
reads **Hello, world!** as a visible semantic heading rendered by its application
entry point. This is the complete requested app. It needs no form, backend,
account, persistence, network API, animation or invented interaction.

Inspected clean Templates main `408bc596ad435908ff730b464096bf700ed71b3e`:

- `templates/fs-gg-web/Web` implements an HTML document with a module entry
  point and a TypeScript/Vite production build. Its existing app fetches
  `/api/message`. Reuse the semantic-document/module-entry pattern; root selected
  native browser ESM for the four examples, so no compiler or server API is needed.
- `templates/fs-gg-web/Browser.Tests` supplies Playwright 1.63.0 and the existing
  `PLAYWRIGHT_EXECUTABLE_PATH` convention. Reuse the repository/browser tooling.
- `providers/web.providers.yml` selects `fs-gg-web`, package pin 0.13.0 and `sdd`
  lifecycle; `providers/fable-game.providers.yml` selects package 0.15.0 and
  `typed-sdd`. The Fable client includes game/protocol/SignalR dependencies that
  this single-heading example does not consume.
- `FS.GG.Templates.csproj` packs explicit `templates/**/*` and product-skill
  items. A sibling `examples/` tree is outside that payload.
- The existing console template and `ProgramTests.fs` already exercise
  `hello world`. That historical console outcome is excluded from HELLO-01.1.
  No new hello-world browser app or acceptance proof exists at this inspected base.

## One executable milestone

- [x] **HELLO-01.1 — Usable hello-world browser app delivered** — route: routine.
  Canonical original: `HELLO-01.1`. Depends on: none beyond the normal repository
  delivery boundary. Implement the whole app and its focused proof together;
  do not split scaffolding, build, browser observation or delivery into originals.

Use `examples/enrollment-apps/hello-world/` for the self-contained app:
`index.html`, browser-native ESM `app.js`, minimal `style.css` if needed, and a
short README. Root owns the shared static build/serve commands and Playwright
package/lock/config; do not add a framework or an app-local dependency manifest.
Use relative asset URLs so the directory can be served at its own URL path.
The shared build stages tracked static assets without a compiler, and the shared
server serves those assets on loopback. The document has `lang="en"`, a descriptive
title and viewport metadata. `app.js` creates the visible `h1` within `main`;
use system fonts and legible high-contrast text. The entry point must execute in
the served app; an inert HTML heading alone does not meet the enrolled boundary.

The implementation worker owns only that subtree and
`docs/roadmaps/hello-world-app.md` in an isolated routine worktree. Root is the
sole integrator for the common app harness, workflows, app index, shared ignores,
PR admission and `.github` projections. Keep any app-specific browser case within
the hello-world subtree, callable by the root-owned harness. Do not edit provider
descriptors, packaged templates, release pins, lifecycle defaults or other apps.
No package publication, new repository, hosted service or deployment is needed.

Acceptance is one real-browser smoke journey against clean served static output:

1. From a fresh copy/checkout containing only tracked inputs, install the shared
   locked browser harness, run its static build/staging command, and start the
   documented shared static server. The README names the exact app URL and
   root commands once their integration interface is fixed.
2. In actual Chromium, navigate to the HTTP URL and locate the visible heading
   by accessible role/name `heading`, `Hello, world!`. Confirm its main landmark,
   page title and English document language; observe no page errors or failed
   app module requests. Reload once and confirm the same usable result.
3. Retain a small sanitized result identifying exact source/tree, commands,
   served asset digest, browser and outcome; shut down owned browser/server
   processes. A DOM unit test, mocked renderer or source-text assertion is not
   a substitute. Do not add tests that mirror the trivial assignment.
4. Root integrates the coherent app changes, runs native required checks on the
   admitted exact head, merges through the native boundary, and independently
   reads the owning plan and source back from protected main. A checked box in
   the candidate becomes authoritative only with that merged-state readback.

First executable window is all of HELLO-01.1. Pass the accepted plan to one
`gpt-5.6-sol` medium worker using the canonical route skill at
`/home/developer/projects/.github/.agents/skills/work-roadmap/SKILL.md` (the
Templates generated skill view was absent during inspection). Root supplies the
shared harness interface before integration. No product decision is unresolved.
Stop at the assigned local handoff until root admits remote delivery. There is
no later feature horizon: delivery plus its own browser/native readback completes
this bounded app. Publication or scaffold integration would be separately selected.

## Generated-workspace boundary — Unified §9.9

No generated workspace family changes. Before HELLO-01.1 this source example is
absent; afterward a reader explicitly chooses and runs it from Templates source.
HELLO-01.1 first enables that source example, not a scaffold capability. The
current package content globs exclude its directory, so no producer release or
SDD/provider adoption is required or claimed. Existing lifecycle defaults stay
as inspected. The clean acceptance above proves a fresh **example checkout**;
it is not a claim of `dotnet new`/SDD clean-generated receiver adoption.

Existing generated workspaces have no automatic or promised upgrade here. An
owner may manually adopt the isolated example into a new, empty directory;
retained-file migration, installer overwrite behavior and generated-receiver
qualification are outside this outcome and must not be reported as passed.

## Enrollment, evidence and index update

Root enrolled HELLO-01.1 at `2026-09-29T06:31:33Z`, before outcome, in
`docs/reports/evidence/2026-09-07-routine-route-cohort.json` in the prospective
`.github` enrollment worktree `/tmp/r5-additional-app-enrollment-20260929`.
Count this one original only after its whole-app acceptance and authoritative
native Done/readback. Planning, pre-existing console behavior, checkpoints and
individual test runs contribute no completed originals; R5's target stays ten.
Planning dispatch reported telemetry `not-configured` (exit 2). Complete native
usage and bureaucracy remain unknown; do not infer counters or efficiency.

Root adds this §9.8 row asynchronously with the existing integration work:

| **Hello-world browser app — HELLO-01** | Independent opt-in source example; complete accessible browser app, one original HELLO-01.1 | Templates example owner; routine, independent of the other enrolled apps; source delivery and protected readback required | Draft `/tmp/r5-hello-world-app-plan-20260929.md`; replace with [owning plan](https://github.com/FS-GG/FS.GG.Templates/blob/main/docs/roadmaps/hello-world-app.md) only after delivery |

After authoritative closure, root updates Unified §0 and cohort evidence with
the actual source, native delivery and browser proof, preserving the usage gap
and the separate publication/generated-adoption boundary. Do not open a
planning-only PR or create a second completion ledger.

## Qualified source window — 2026-09-29

The complete local source window is qualified at clean code checkpoint `4181f1a6dacf92151fff7f6217d045137d4546cc`. The root-owned locked shared harness stages exact source bytes and passes all 18 domain checks and 14 serial Chromium journeys, including this app's real entry and controls. Each app remains one original. Native required qualification, source merge and protected owning-plan readback establish authoritative completion; this local checked outcome does not increment the cohort by itself. See [joined source evidence](evidence/r5-browser-apps-20260929.md). Publication and installed scaffold adoption remain separate and unselected.
