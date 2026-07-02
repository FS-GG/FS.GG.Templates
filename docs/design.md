# Design: composing SDD + Governance + Rendering

## Why this repo exists

A "full-stack" FS.GG product wants three things at once:

- the **FS.GG.SDD** spec-driven lifecycle (skeleton + `fsgg-sdd` commands),
- a runnable **FS.GG.Rendering** app (Skia/OpenGL + Elmish/MVU), and
- **FS.GG.Governance** rule/evidence/gate config.

None of the three product repos can own that combination, because they are
deliberately decoupled:

- **FS.GG.Rendering never depends on Governance** (org-stated).
- **FS.GG.SDD stays provider-agnostic** — generic SDD contains no Rendering/Governance
  id, path, or docs URL (FR-002 / SC-005).
- **FS.GG.Governance is the optional downstream**, not an upstream that ships
  product templates.

`FS.GG.Templates` sits **downstream of all three** and composes them as a plain
consumer, with no reverse coupling back into any product.

## Chosen approach: compose at scaffold time

Per [ADR-0002](https://github.com/FS-GG/.github/blob/main/docs/adr/0002-composition-by-scaffold-lifecycle-parameter-governance-populated.md),
composition happens **at scaffold time** — `fsgg-sdd scaffold` installs and drives the
live, version-pinned upstream `fs-gg-ui` template; FS.GG.Templates ships **no vendored
framework copy**. `scripts/new-fullstack.sh` + `providers/rendering.providers.yml` + the
`fs-gg-governance` overlay produce a full-stack product by composition:

- **Rendering** — `fsgg-sdd scaffold --provider rendering` installs the **live,
  un-vendored** `FS.GG.Rendering` app from the published `FS.GG.UI.Template` package
  pinned by the provider descriptor, passing `lifecycle=sdd` so the product carries only
  the runnable app (the `.fsgg/` lifecycle comes from the SDD skeleton, not a second
  copy).
- **SDD** — the lifecycle skeleton (`.fsgg/{project,sdd,agents}.yml` + `work/` +
  `readiness/`), owned by `fsgg-sdd`.
- **Governance** — the populated `fs-gg-governance` overlay
  (`.fsgg/{policy,capabilities,tooling}.yml`), dropped in **after** scaffold so it is not
  flagged as a provider writing into the SDD-owned `.fsgg/` tree.

Because the rendering payload is installed live from its pinned upstream package, there
is no fork to drift — the `FsGgUiVersion` staleness class (below) is structurally gone.

## Update function

- **Consumers** — the `fs-gg-governance` overlay ships as a versioned NuGet **template
  package** (`FS.GG.Templates.csproj`, `PackageType=Template`). `dotnet new update`
  checks the feed and upgrades to the latest published version. The rendering payload
  updates independently, via the provider's package pin.

## Documentation convention: link the registry, don't restate it

Cross-repo state — package pins, minimum coherent versions, release dates, CLI capability
thresholds — is owned by `FS-GG/.github` `registry/dependencies.yml` (and its ADRs). When a
comment or doc needs to name that state, **link the registry entry (plus any tracking issue
or ADR) rather than restating the value**. A restated version or date is a dated claim that
silently rots when the upstream moves; a link stays correct by construction. Where a value
genuinely must be duplicated for a machine — e.g. the `FS.GG.UI.Template` pin the composition
test asserts, or the `minimumFsggSdd` mirror in `providers/rendering.providers.yml` — mark it
explicitly as a registry **mirror** and keep the coherence assertion that fails when the two
disagree (see "Keeping the rendering pin fresh" in the README). One authoritative source with
a checked mirror beats many prose copies. Prefer this when writing new comments; retrofit old
dated claims opportunistically as you touch them, not in a sweep.

## Rejected alternative: a single monolithic template (retired)

`fs-gg-fullstack` was one `dotnet new` template that emitted all three layers in a single
invocation — no `fsgg-sdd` CLI required. Because `dotnet new` cannot include or depend on
another template, a single self-contained template had to **vendor** the `fs-gg-ui`
rendering payload into `templates/fs-gg-fullstack/`, refreshed by a
`scripts/sync-from-rendering.sh` maintainer script. That vendored copy is a fork that
goes stale whenever Rendering changes (the `FsGgUiVersion` staleness class). The
one-invocation UX did not justify a perpetual drift liability, so the monolith and its
sync script were **removed** in favor of scaffold-time composition (P4 on the FS-GG
Coordination board).
