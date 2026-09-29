# TODO-01 — Complete local todo app

Draft planning handoff, 2026-09-29. Owning repository: `FS-GG/FS.GG.Templates`.
One original item: **TODO-01.1**. This document plans implementation; it does not
record an implemented app, native delivery, or an R5 completion.

Backlink: [Unified Roadmap §9.8](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index).
Named part: user-selected independent todo app, prospectively enrolled as R5
ordinary work. Stage: bounded product source delivery and browser qualification
using Templates' already accepted ordinary-V2 receiver.

## Outcome and choices

Deliver an opt-in, runnable browser app in
`examples/enrollment-apps/todo/`. A user can add a task, edit its text, mark it
complete or active, switch All/Active/Completed filters, and delete it. Successful
changes survive reload in the same browser origin. The app has visible empty
states, remaining-task count, labeled controls, keyboard operation, visible
focus, and a usable narrow-screen layout. No backend or authentication is needed.

Use browser-native ESM JavaScript, semantic HTML and CSS, following the parent's
selected common runtime for these four small apps. Use a pure domain module
and Node tests where meaningful. The parent owns one shared static server and
Playwright harness; each app owns its source and focused tests. No app needs
a framework, bundler or separate tool installation. This is a Templates-owned sample, not a
new provider or a generated application advertised as already installed.
Use a namespaced, versioned localStorage record, e.g. `fs-gg.todo.v1`, containing
stable task IDs, text and completion state. Validate loaded data. Storage failure
must leave the app usable and visibly explain that changes cannot be retained;
malformed saved data must not crash the UI. Use text rendering for task text.
Trim added/edited text and reject empty or whitespace-only submissions. Editing
has explicit Save/Cancel controls, Enter saves and Escape cancels. Filtering
does not delete tasks or alter their completion state. Cross-tab synchronization,
accounts, sync, drag ordering, due dates and bulk operations are outside .1.

## Inspected source and reuse

Inspected clean Templates main `408bc596ad435908ff730b464096bf700ed71b3e` at
`/home/developer/projects/FS.GG.Templates`:

- `templates/fs-gg-web/README.md`, `Web/package.json`, `Web/tsconfig.json`,
  `Browser.Tests/package.json`, `playwright.config.ts`, and `home.spec.ts` supply
  the closest existing source route: neutral TypeScript/Vite plus browser tests.
  Current source pins are TypeScript **5.9.3**, Vite **7.3.6**, Playwright
  **1.63.0**. These identify the inspected reference, not app dependencies.
  Reuse Playwright **1.63.0** in the parent-owned shared locked harness.
  The existing web browser config serves a published ASP.NET app; the todo
  config should instead serve the common static app directory on an isolated port.
- `templates/fs-gg-fable-game/README.md` and client/browser manifests describe
  Fable/Elmish, SignalR and server-authoritative game composition. Those extra
  dependencies do not serve this todo outcome. The neutral web client is a
  useful DOM/browser-test reference; its TypeScript/Vite tooling is not a
  provider-contract requirement for an independent static sample.
- `providers/web.providers.yml` identifies contract **1.1.0**,
  `fs-gg-web`, package pin **FS.GG.Workspace.Template::0.13.0**, lifecycle default
  **sdd**, and product/namespace parameters. The actual fable-game descriptor is
  separately pinned to **0.15.0** and defaults to **typed-sdd**. Do not normalize
  these distinct current contracts while adding a sample.
- `tests/composition/web/run.sh` qualifies direct creation and the SDD provider
  route with separate raw and identifier names, lockfiles, production output and
  real browser JUnit results. `tests/ProviderComposition.Tests/Program.fs` refuses
  unknown/duplicate providers, identity/parameter drift and floor mismatches.
  Neither is a pre-existing todo acceptance test.
- `FS.GG.Templates.csproj` packs `templates/**` plus explicit owner-sourced skill
  items; a new `examples/enrollment-apps/todo/**` tree is outside those items.
  This placement requires no package version, provider or materializer change.

The client tools and browser lane are implemented prior work. A complete todo
app, its persistence semantics and its actual browser journeys remain missing.
No installed todo capability or generated receiver is demonstrated by inspection.

Templates' ordinary-V2 receiver is already accepted: Unified §9.1 records
[Templates #643](https://github.com/FS-GG/FS.GG.Templates/pull/643), protected
`938f9b11ee1f148ff495774d346b011c9f23d394`, immutable Coordination CLI **0.1.6**,
and [run 36463172201](https://github.com/FS-GG/FS.GG.Templates/actions/runs/36463172201).
It settled once; its normal rerun returned `SettlementAlreadyComplete` with
receipt `95e74b3d8652c83c1b856e3b1e58474c2688761e2aed6acb3d68a9457386a506`.
Independent Authority shard `b6` readback retained head
`71bf408a68ca0758746fc08f716a1caacc6b0d5f` and exactly one completed effect.
The owning `docs/roadmaps/v2-ordinary-adoption.md` still contains older disabled
wording; do not interpret it as reversing that later native acceptance. Existing
receiver acceptance is a delivery input, not evidence that TODO-01.1 has run.

## First executable window: one whole-app original

- [ ] **TODO-01.1 — Usable local todo app delivered and independently read back** — route: routine.
  Depends on: the existing Templates receiver and available browser/toolchain;
  no unfinished unrelated app, release or fleet migration.
  Scope: one isolated branch/worktree, one accountable Sol-medium owner, complete
  source app, focused browser qualification, concise usage/evidence, and one
  coherent native delivery. Retain this item/original identity through repairs.

Execute the following as dependent work within .1; these are not separately
counted milestones:

1. Create the standalone sample using the source choices above. Supply an HTML
   entry, ESM modules, CSS, README, tests, and a small app state/storage boundary.
   Use the parent's shared commands and dependency lockfile. README gives exact local run
   commands and states that data is per browser/origin. The default view is an
   empty All list; any explanatory sample text is not a prepopulated user task.
2. Qualify the actual served static app with Chromium through Playwright.
   Use accessible-role/label queries and real clicks/typing for the main journeys.
   Keep server ownership deterministic (`reuseExistingServer: false`, loopback
   binding, strict selected port), honor the existing
   `PLAYWRIGHT_EXECUTABLE_PATH` convention, and preserve JUnit plus failure traces
   outside committed build output. Use a real installed browser; unavailable
   Chromium is a qualification gap, not permission to substitute DOM mocks.
3. Deliver the coherent .1 branch through the parent's admitted native PR route,
   preserve focused and required exact-head checks, then read back merged state
   and protected content. Observe this delivery's applicable ordinary-V2 run and
   receiver result rather than borrowing #643's earlier settlement as .1 evidence.
   Only after native delivery/readback may the parent close .1 and count one
   original in the existing R5 cohort. The parent immediately follows with the
   Unified §0 closure projection and §9.8 link maintenance.

Focused acceptance must demonstrate:

- Add two differently named tasks through the labeled form; whitespace-only
  submission is refused. Edit one, cancel another edit, complete/reopen a task,
  verify all three filters and the count, and delete only the selected task.
- Reload after successful mutations and observe retained text, IDs through
  behavior, completion and deletion. Close/reopen a page in the same context and
  origin to exercise persistence beyond component memory. A fresh context starts
  empty. Do not seed storage as a substitute for the real mutation journey.
- Enter/Space/Tab and edit Escape work through actual controls; labels identify
  which task an action affects. Focus remains useful after saving/deleting.
  A narrow viewport retains visible operable controls without horizontal spill.
- Text resembling HTML displays literally. Invalid saved JSON or rejected storage
  produces a usable, explanatory state; a focused injected failure is acceptable
  for this negative case. Normal operation has no uncaught browser errors.

The parent supplies the shared `npm ci`, static serve and focused Playwright
commands, plus the shared browser installation. Run the app's meaningful pure
domain controls with Node's native test runner. Serve the checked-in static ESM
assets directly so qualification covers what a user runs. Add only focused state/storage tests
where they resolve behavior awkward to observe in the browser; do not duplicate
the full browser journey in a second test layer.

## Ownership, touch-sets and integration

Worker-exclusive touch-set: `examples/enrollment-apps/todo/**`, including its
app, tests, README and concise qualification note. No other app imports its
mutable state. Use the parent's assigned app path and shared-server port, with
separate browser contexts/storage per test, before concurrent qualification.

Parent/root integrator exclusively owns the shared examples catalog, package,
lockfile, static server, Playwright config and CI workflow,
`docs/roadmaps/todo-app.md` placement, Unified §0/§9.8,
and the existing cohort evidence. Request one focused invocation of the app's
Node/browser tests and artifact retention in the common four-app harness. Workers
must not independently edit workflow, root package, provider, template, release,
or sibling-app files. Escalate any required overlap to the parent.

No `work-roadmap` skill is installed under this Templates checkout's absent
`.agents`/`.codex` roots. The actual canonical fallback is
`/home/developer/projects/.github/.agents/skills/work-roadmap/SKILL.md`; the parent
must pass this exact path to the implementation worker. Respect Templates'
actual receiver requirements: `composition`, `kit / coordination-kit`, and
`materialize / receiver-validate`; its adoption contract explicitly does not add
`routine-eligibility`. Do not copy `.github`-specific check assumptions into it.
Use the parent-controlled admission helper and stable campaign/chain identity:
at most one open TODO chain PR and two newly qualifying PRs in Templates. Keep
prepared work local while capacity is full. No planner-created issue or PR.

## Generated-workspace boundary and later outline

Under Unified §9.9, .1 has **no generated-workspace effect**. Before delivery,
users have the existing neutral web and game providers; after delivery, an
explicit source checkout also contains a runnable todo sample. The first changed
runtime behavior is the user opting to run that sample at .1. Fresh installed
`fs-gg-web` and `fs-gg-fable-game` creation retains its current provider contents
and separate lifecycle defaults. No producer publication, scaffold pin adoption,
or retained-workspace update belongs to .1; no new release identity is claimed.

Prove clean sample use from a disposable clean checkout, shared `npm ci`, static
serve and browser journey. This is source-sample reproducibility, not public
installed generated-receiver acceptance. Prove browser-retained task state as
above; it is likewise not a retained SDD workspace upgrade. Existing generated
workspaces receive no rewrite and need no .1 migration.

Optional later work is an outline only: if explicitly selected, compose the app
through a provider/overlay, publish exact producer bytes, adopt the scaffold pin,
and qualify public clean creation plus a separately bounded retained adoption
with conflict/data-preservation cases. Evidence selecting that distribution
route, its owner and upgrade promise is required before detailing it. Accounts,
sync and deployment would also be new scope, not remaining conditions for .1.

## Observation, gates and index proposal

Prospective cohort enrollment was recorded at **2026-09-29T06:31:33Z**, before
outcomes, in the existing parent draft
`/tmp/r5-additional-app-enrollment-20260929/docs/reports/evidence/2026-09-07-routine-route-cohort.json`.
The target remains ten completed originals. Plans, scaffolds, commits, tests,
reruns and shared harness delivery do not independently count. Preserve
`feature=TODO-01`, `item=TODO-01.1`, `originalItem=TODO-01.1` across this lineage.
Parent telemetry begin returned exit 2, not configured. Usage and bureaucracy
remain unknown; record actual technical results and native outcomes without
inventing counters or certifying the 10% ceiling. This gap does not block valid
source delivery. The Unified accounting definition still applies when usable
whole-item measurements become available.

The implementation window is ready once the parent assigns an isolated worktree
and owner. Remaining technical gates are successful locked dependency install,
an actual browser, focused served-app journeys, the required common harness/CI
join, native exact-head checks/admission, merge readback and the selected ordinary
receiver observation. No product decision requires a new user response. A
material need for backend/Fable/provider changes invalidates this bounded plan
and returns to the parent before expanding the touch-set.

Proposed durable plan path: `FS.GG.Templates/docs/roadmaps/todo-app.md`, landed
with implementation by the integrator. Until then this file is the actual draft.
Proposed §9.8 row, retaining existing unrelated links:

| **Local todo app — TODO-01** | Independent opt-in source app; TODO-01.1 delivers add/edit/complete/filter/delete with retained browser state and actual browser qualification | Templates owner; accepted ordinary-V2 receiver, routine source delivery, one prospective whole-app original | Draft: `/tmp/r5-todo-app-plan-20260929.md`; replace with the durable Templates `docs/roadmaps/todo-app.md` link after delivery |
