# GAME-PORTAL-01.P3 — Managed portal example in Fable Game workspaces

Status: T1 source preparation; candidate pack/generation/runtime, provider forwarding,
publication and preserving retained adoption/removal remain unqualified. Templates owns
this integration, Game owns canonical example sources, and Rendering owns the public
scene contract. The programme integrator owns coherent release/admission and roadmap joins.

This contributes the Box2D row of GAME-TEMPLATE-01 under
[Game Portal P3](https://github.com/FS-GG/FS.GG.Game/blob/main/docs/roadmaps/game-area-portals.md)
and [Box2D .4](https://github.com/FS-GG/FS.GG.Game/blob/main/docs/roadmaps/game-box2d-physics.md).
The [v3 programme](https://github.com/FS-GG/.github/blob/main/docs/roadmaps/2026-10-07-unified-development-roadmap-v3.md)
retains those owning plans and separates source, publication and installed outcomes.

## Supported consumer


Select an explicitly generated **managed .NET 10 PortalExample project inside the real `fs-gg-fable-game` workspace**. The template owns its inclusion, package references, committed lock, management commands and qualification. It is a separately invoked headless game/server example, not a new stock console product and not an ASP.NET server endpoint. The browser player, production server, protocol and default solution do not reference it. A user generates the real template with `--portalExample true`, then invokes `dotnet run --project PortalExample/Consumer.fsproj -- --presentation`. That project runs the canonical Game scene and traversal-safe managed presentation from public packages.

This contract is the smallest honest supported backend selection. Game's owning plan explicitly allows opt-in .NET game/server consumers. Neither the v3 Box2D template row nor P3 requires browser physics, a portal viewport, networking, or changes to the production arena. Managed presentation means interpolation plus immutable `Game.Render.Adapter.drawPoints` scene nodes; it does not mean browser/raster output. Do not call this server-integrated physics or browser support. A later request to drive Box2D from the ASP.NET authority or display portal snapshots in Fable invalidates this narrow integration contract and needs a separate wire/backend plan.

Completion requires both a fresh publicly installed template receiver and adoption into a genuinely retained `fs-gg-fable-game` workspace, preserving authored files and proving rollback/removal. Merely appending a project to an unrelated generated console is insufficient. A source candidate, local template pack, public producer dependency, published template and installed provider receiver are distinct facts.

## Producer inputs and boundaries

Canonical Game source is protected revision `49c7f5a74f2470f68e626b68293d5207c2068a93`,
tree `c2aa7259568ddb54f5397ff978ca3baa6d942255`. Templates integration starts from
protected `b005c26e43cd4a823577ff94e1ee6da2cfed58d4`. Game's real managed public
consumer established the seven-package closure and 0/0/2 entrypoints. Its original
performance observations remain bound to their exact older assembly; no timing promise
or performance rerun is required for template inclusion.

The ordinary template Game 0.16.0 / Rendering 0.32.1 / FSharp.Core 10.1.401 projects
remain independent. Provider v2 requires a separately qualified installed SDD >=2.1.0;
adding an optional descriptor parameter does not qualify forwarding, public activation
or Wizard availability.

## Package and generation contract


Use the existing `tests/release/Box2D.PackageConsumer/PresentationConsumer.fsproj` layout as the Portal project's basis, named `PortalExample/Consumer.fsproj` so the existing package-boundary verifier can be reused mechanically. Keep `DisableImplicitFSharpCoreReference=true`, `DisableImplicitLibraryPacksFolder=true`, no ProjectReference/assembly Reference/source Link/foreign Import, and three exact direct references: Physics.Box2D `[0.17.0]`, Render `[0.17.0]`, FSharp.Core `[10.1.302]`. Assert assets and nuspec closure contains exactly Core/Physics.Box2D/Render `0.17.0`, UI.Scene/KeyboardInput `0.31.0`, Box2D.NET `3.1.654`, FSharp.Core `10.1.302`. The root SDK remains `10.0.401`; receiver runtime initially remains the qualified .NET `10.0.12` Linux X64 profile.

The independent project may share the workspace's package cache, which supports side-by-side versions, but cannot share a process or project-reference graph with its Game `0.16.0`/Rendering `0.32.1` projects. Retain inherited private-cache/locked-mode controls and ship an authentic committed Portal lock. Qualification uses new empty caches. Do not globally bump existing browser/server pins or claim the seven-package closure applies to the whole generated workspace.

Add current-template boolean `portalExample`, default false, independent of `bundle` and lifecycle. False/omitted excludes `PortalExample/**`; explicit true includes it for current bundle selections. Keep the existing root solution/build entrypoints unchanged; the documentation names the explicit project command. Add optional provider parameter of the same name. The legacy `svgFoundation` descriptor must always exclude `PortalExample/**` and must not advertise the parameter; mixed legacy+portal selection must refuse rather than silently omit it. Template packing mirrors current content into the legacy member, so this exclusion is load-bearing.

Game algorithms stay canonical: populate `PortalScene.fs` from Game's exact `examples/Box2D.Portals/Scene.fs`, plus exact `Presentation.fs` and `Program.fs`. Record immutable repository/revision/path/SHA256 provenance; the Game package-consumer `PortalScene.fs` currently equals canonical Scene bytes (`24c91caaa54c1a09ba342355395b8c9796054aa31619aa2d4a68b425ff5aaf7e`). Copy the existing verifier as an immutable qualified tool, not a rewritten package predicate. These are deliberately vendored example content in the distributable template, updated only from canonical exact producer bytes and checked against an independently retained source archive at qualification. Do not locally edit copied algorithms or author a parallel physics model. No cross-repo ProjectReference, source fetch, or source fallback occurs in a generated receiver. A pack-time projection is unnecessary for this small fixed payload and would add another required source checkout to every release.

## T1 — Explicit real template source and candidate qualification

- [ ] Add `portalExample`, default false, to the current template and optional provider
  parameter; always exclude it from the legacy selector without advertising the option.
- [ ] Ship the independent Portal project, canonical producer files/tool, genuine lock,
  immutable source provenance and explicit invocation documentation.
- [ ] Run cheap source/descriptor/provenance controls before native effects. Then install
  one actual candidate archive through `FSGG_TEMPLATES_NUPKG`/`lane-package.sh`; never
  pack a substitute in the consumer lane.
- [ ] Generate omitted/false and explicit true player/complete cases; ordinary generated
  paths outside `PortalExample/**` remain byte-identical. Invalid boolean and mixed
  legacy/Portal selections refuse without receiver writes; legacy outputs omit Portal.
- [ ] Compare the candidate/generated canonical bytes against an independently retained
  exact Game source archive. Reject linked, missing, foreign or forged-provenance input.
- [ ] Qualify the actual opted-in generated project: copied verifier before/after
  public-only locked restore, byte-identical lock, Release warnings-as-errors build,
  default/presentation/invalid entrypoints 0/0/2. Retain traversal/pose/momentum,
  five snapshots, twelve frames, twenty-four nodes/points and canonical reset/midpoint
  correctness evidence. Source mocks are not positive runtime evidence.
- [ ] Separately qualify provider forwarding using the pinned installed provider-v2 SDD,
  distinct product/namespace names and actual emitted provenance. If unavailable, leave
  this portion pending rather than substituting direct template generation.

`tests/composition/fable-game/verify-portal-example.py` performs scoped source,
candidate archive and generated-payload checks. Its synthetic controls label generation
and runtime as unrun. `verify-portal-example.sh` requires a pinned actual candidate
archive and independent canonical Game archive before effects; it retains stage logs,
uses new private homes/caches and stops dependent stages on the first failure. Optional
provider execution requires a separately qualified executable and exact pin. These
commands are qualification recipes, not publication or effect admission.

T1 stops at qualified source delivery. Existing coherent template gates and exact-head
routine eligibility still apply. Broad unchanged Fable/Vite/browser composition may
reuse only validated exact semantic evidence under ADR-0084; static no-reference checks
alone cannot replace the coherent release obligations. T1 does not close P3.

## Retained adoption, publication and public receivers


- [ ] **P3-T2 — Retained adoption and removal source — route: routine.** Depends on T1's accepted payload. Extend the existing Templates `scripts/apply-svg-complete-workspace.py` with narrowly namespaced `portal-inventory/apply/remove/recover` entrypoints and a fixed Portal-only path allowlist/schema; reuse its path refusal, inventory/diff freshness, durable journal, before/post hashes and recovery implementation. Its current SVG manifest classifier is hard-coded to old SVG releases/skills and must not be passed a guessed Portal manifest. Keep SVG entrypoint semantics unchanged. Ship the same helper source as `PortalExample/manage.py` through explicit `FS.GG.Templates.csproj` package items, using a qualified candidate folder outside the target for management. Exact additional source surfaces: that existing helper, `FS.GG.Templates.csproj`, `tests/composition/fable-game/test-portal-adoption.py`, `tests/composition/fable-game/verify-portal-adoption.sh`, Portal README/provenance, and the Templates owning plan. This is a bounded extension of an existing transaction contract, not a second adoption service or broad refactor.

  Initial support is additive adoption into a genuine retained public Templates `0.18.1` Fable Game workspace with PortalExample absent. Record that supported baseline package's actual provenance; do not pretend `dotnet new update` upgrades existing files. Inventory previews the exact Portal paths; apply checks the same candidate and receiver before its first write and changes only those paths. The root solution, build scripts, lifecycle/skills, user source/data and all default locks remain byte-identical. A pre-existing unowned managed destination, changed owned file, symlink, stale inventory, corrupt backup or wrong receiver refuses before writes. Removal only removes manifest-owned unchanged files; foreign files inside the folder survive, so never recursively delete the directory. Fresh opted-in receivers use the shipped provenance to establish the same ownership. Recovery/rollback restores verified before states and reports uncertain cleanup explicitly. Exercise late conflict, interruption and corrupt-late-object controls plus the existing SVG transaction behavior on synthetic trees. Subsequent Portal-to-Portal upgrades accept only authentic supported prior manifest digests; no earlier Portal release exists today, so source fixture upgrade tests do not establish a public prior-version upgrade. T2 can promise only the adoption/removal actually qualified.

- [ ] **P3-T3 — Coherent public template successor — route: routine source; publication separately admitted.** Depends on accepted T1/T2 and existing Templates release gates. Reuse the repository's current pack-once, immutable artifact, dual-feed equality, feed occupancy and public readback paths. Release owner chooses the next genuinely unoccupied Templates version at dispatch (current source is 0.18.1; no successor number is reserved here), aligns the provider descriptor and exact source/archive identities, and verifies the installed artifact contains the opt-in payload/helper/lock. Game and Rendering need no new binary release unless the source owner discovers a producer API defect. A generated example source update does not turn Game 0.17.0 into a new binary release. Keep protected publication credentials, registry activation and Wizard release in their existing owners and custody. Do not repair or retry unrelated unknown publication effects.

- [ ] **P3-T4 — Fresh and preserving retained public receivers — route: separately admitted qualification.** After T3 public readback, create new outside-checkout receivers from the actual public template, public dependencies and fresh caches: direct explicit opt-in and default-off; then the qualified provider-v2 route using its exact public descriptor and installed SDD >=2.1.0. Repeat the real project entrypoint and exact graph/lock checks. Before release, the full unchanged Fable/Vite/browser composition remains a coherent artifact gate; retain its evidence separately from this headless Portal runtime. For retained adoption, freshly instantiate the actual public pre-Portal 0.18.1 template into a new owned retained receiver, add authored source/data/skills, record the full inventory, then inventory/apply from the real successor-generated candidate. Observe the Portal entrypoint and byte preservation; add a foreign in-folder sentinel, remove safely while preserving it, and observe ordinary workspace behavior; separately exercise recovery/rollback. Never operate on resume04/resume05 or old /tmp receivers. Report direct template, provider and Wizard boundaries independently. Full Wizard activation is not implied by the direct/provider proof; if it remains part of another v3 row, retain that open outcome there rather than relabel it complete.

Later only: a second public Portal successor permits genuine Portal-to-Portal version-upgrade acceptance. Browser simulation/viewport, server authority integration, portal queries, cross-area collision/joints, hidden-solver rollback and cross-platform determinism remain unselected. Do not expand them while implementing these four milestones.

## Ownership and closure

One Templates owner advances T1/T2 as one payload/adoption source chain. Workflow callers,
shared registry/projection files and Game owning-plan joins remain in their existing owners.
Do not edit unrelated hosted reference workflows or staged-adoption plans as a shortcut.

Fresh source/effect and resource/custody admission is required before pack, installation,
generation, restore, build, runtime or publication. Ordinary one-CPU/~2 GiB settings and
bounded owned-process cleanup are proportionate controls; heap/CPU limits do not prove
whole-tree RSS containment or detached-descendant cleanup. Historical interrupted operations
and receiver custody remain outside this integration; never adopt them as caches or targets.

After T4, Game may close P3/Box2D .4 only for this declared managed-template scope with
durable public fresh/retained evidence. Performance release obligations remain separate
until the owning plan accepts them. The programme integrator narrows the v3 row and records
the GAME-TEMPLATE-01 contribution; this subproject does not close template consolidation.
