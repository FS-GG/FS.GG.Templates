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

## Chosen approach: a single monolithic template

`fs-gg-fullstack` is one `dotnet new` template that emits all three layers in a
single invocation — no `fsgg-sdd` CLI required to scaffold:

- **Rendering** — the FS.GG.Rendering `fs-gg-ui` template payload is **vendored** into
  `templates/fs-gg-fullstack/` (its `template/`, `.specify/`, `.agents/`,
  `.template.config/generated/`), keeping `fs-gg-ui`'s own `template.json` substitution
  rules (sourceName `Product`, `projectSlug`, the `copyOnly` governance-token guards).
- **SDD + Governance** — layered as one extra source, `template/fsgg/` → `./`, emitting
  `.fsgg/{project,sdd,agents}.yml` + `work/` + `readiness/` (SDD) and
  `.fsgg/{policy,capabilities,tooling}.yml` (Governance). The SDD `project.id` reuses
  the `projectSlug` substitution; `--governanceProfile` replaces the policy default.

The monolith's `template.json` is the `fs-gg-ui` manifest with the identity/shortName
changed (`FS.GG.Templates.FullStack` / `fs-gg-fullstack`), the `governanceProfile`
symbol and the `template/fsgg/` source added, and **post-actions removed** (the
upstream git-init/chmod scripts prompt interactively, which would hang non-interactive
use such as `fsgg-sdd scaffold`).

### Tradeoff (accepted)

`dotnet new` cannot include or depend on another template, so a single self-contained
template must **vendor** the rendering payload — a fork that goes stale when Rendering
changes. We accept that for the one-invocation UX, and mitigate it with an explicit
**update function** (below) rather than a hand copy.

## Update function

- **Consumers** — the templates ship as a versioned NuGet **template package**
  (`FS.GG.Templates.csproj`, `PackageType=Template`). `dotnet new update` checks the
  feed and upgrades to the latest published version. Validated: the package installs as
  `FS.GG.Templates@<version>` and is recognized by `dotnet new update`.
- **Maintainers** — `scripts/sync-from-rendering.sh <rendering-checkout>` re-vendors the
  upstream `fs-gg-ui` payload (leaving the SDD/Governance overlay and the monolith
  manifest intact); then bump `<Version>` and `dotnet pack`.

## Alternative: compose via `fsgg-sdd scaffold`

For users who already drive the SDD CLI, `scripts/new-fullstack.sh` +
`providers/rendering.providers.yml` + the `fs-gg-governance` overlay achieve the same
result by composition — `fsgg-sdd scaffold --provider rendering` (SDD skeleton + the
live, un-vendored Rendering app) then the Governance overlay. No fork, but it needs the
`fsgg-sdd` CLI and a reachable `fs-gg-ui` source. Kept as a secondary path.
