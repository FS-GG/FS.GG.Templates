# FS.GG.Templates

Composes the FS.GG components into a ready-to-run workspace: the
[FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) spec-driven lifecycle, a runnable
[FS.GG.Rendering](https://github.com/FS-GG/FS.GG.Rendering) app, and
[FS.GG.Governance](https://github.com/FS-GG/FS.GG.Governance) config.

## NuGet package quickstart

Acquire or update the template package through the standard `dotnet new` flow:

```sh
dotnet new install FS.GG.Workspace.Template
dotnet new update
```

Use the packaged `fs-gg-governance` overlay with an existing SDD-managed workspace:

```sh
dotnet new fs-gg-governance -o ./MyApp --appName MyApp --defaultProfile light
```

`FS.GG.Workspace.Template` is the thin governance/composition package; it does not vendor the
Rendering runtime or the SDD CLI. Full-stack workspaces are created through `fsgg-sdd
scaffold` as shown below. The rendering provider pins a compatible
`FS.GG.UI.Template` release, while `dotnet new update` keeps this independently
versioned package current.

> **Platform vs. workspace.** FS-GG is a **platform** of independently-owned
> components; Templates is the **composition component** of it. What you scaffold
> *with* the platform is a **workspace**: a generated repo with a runnable **app**,
> the `.fsgg/` lifecycle, skills, and optional governance. For the platform
> vocabulary and the live component inventory see the
> [vocabulary (ADR-0020)](https://github.com/FS-GG/.github/blob/main/docs/adr/0020-platform-workspace-component-vocabulary.md)
> and [`docs/architecture.md`](https://github.com/FS-GG/.github/blob/main/docs/architecture.md).

Per [ADR-0002](https://github.com/FS-GG/.github/blob/main/docs/adr/0002-composition-by-scaffold-lifecycle-parameter-governance-populated.md),
composition happens **at scaffold time** — `fsgg-sdd scaffold` installs and drives the
live, version-pinned upstream template; FS.GG.Templates is the thin **composition +
registry** layer (a provider descriptor, a populated governance overlay, and these
composition tests), **not** a fork host. This repo ships no vendored framework copy.

## Create a full-stack workspace (composition, primary path)

Drive the [FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) CLI (`fsgg-sdd`, a `dotnet tool`)
with the `rendering` provider from this repo. Each component stays decoupled and
independently owned; the scaffold just glues them:

```sh
# 1. Register the rendering provider in your project (copy or merge the descriptor).
mkdir -p ./MyApp/.fsgg
cp providers/rendering.providers.yml ./MyApp/.fsgg/providers.yml

# 2. SDD skeleton + the live FS.GG.Rendering app (lifecycle=sdd → app-only workspace).
fsgg-sdd scaffold --root ./MyApp --provider rendering --param productName=MyApp

# 3. Activate Governance: drop the populated reference gate set into the project.
dotnet new install ./templates/fs-gg-governance
dotnet new fs-gg-governance -o ./MyApp --appName MyApp --defaultProfile light

cd ./MyApp && dotnet build && dotnet run     # the runnable Skia/Elmish app
```

For the common case, the [`new-sdd-workspace <target> <product>`](https://github.com/FS-GG/.github/tree/main/scripts/NewSddWorkspace)
dotnet tool (in FS-GG/.github: `dotnet tool install --global FS.GG.NewSddWorkspace`) wraps these three
steps with **no FS.GG.Templates checkout** — it fetches the provider-pinned descriptor over the network.
Run the three steps above by hand only when working from a Templates checkout (e.g. testing an unpublished
Rendering build via the local feed / `dev-repack-ui-feed.sh`).

It produces:

- **Rendering** — the FS.GG.Rendering `fs-gg-ui` app (Skia/OpenGL, Elmish/MVU, Scene,
  SkiaViewer, Controls), installed live from the published `FS.GG.UI.Template` package
  pinned by the provider (currently `FS.GG.UI.Template@0.25.1`, behind the
  immutable tag `fs-gg-ui-template/v0.25.1`). The provider passes
  `lifecycle=sdd` so the workspace carries **only the runnable app** — the `.fsgg/`
  lifecycle comes from the SDD skeleton, not a second copy.
- **SDD** — the lifecycle skeleton: `.fsgg/project.yml`, `.fsgg/sdd.yml`,
  `.fsgg/agents.yml`, `work/`, `readiness/` (drive it with `fsgg-sdd charter …`).
- **Governance** — the populated reference gate set from the immutable
  `FS.GG.Governance.ReferenceGateSet` authority pinned in
  `templates/fs-gg-governance/.template.config/reference-gate-set.json`:
  `.fsgg/policy.yml`, `.fsgg/capabilities.yml` (build/test/evidence plus the command-free
  `gameplay:fr-covered` and `gameplay:production-journey` organization floors),
  `.fsgg/tooling.yml`, and the controlled-import verifier/manifest. The package's
  `schema-manifest.json` is emitted beside `.fsgg/`. `--defaultProfile` sets the default
  profile; `light` is the non-blocking inner-loop posture, while `strict`/`release`
  enforce block-on-ship gates.

### Why composition, not a single template

`dotnet new` cannot include or depend on another template, so a one-invocation
"full-stack" template could only exist by **vendoring** a copy of the rendering payload —
a fork that goes stale when Rendering changes (this is exactly the `FsGgUiVersion`
staleness class that broke the old monolith). Composing at scaffold time installs the
pinned upstream package directly, so there is no fork to drift. See `docs/design.md` and
the [architecture report](docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md).

### Keeping the rendering pin fresh

With the monolith gone, the only thing that can go stale is the **single
`FS.GG.UI.Template` version pin** in `providers/rendering.providers.yml` (mirrored in this
README; the composition test asserts the two agree). The retired `sync-from-rendering.sh`
re-vendored a payload by hand; its successors only move that pin:

- **[Renovate](.github/renovate.json)** — a custom manager tracks the pin against the
  `nuget` datasource and opens a grouped `FS.GG.UI.*` (`rangeStrategy: bump`) PR when
  Rendering publishes a newer `FS.GG.UI.Template`. The always-on path.
- **[`upstream-bump` workflow](.github/workflows/upstream-bump.yml)** — `repository_dispatch`
  (`fs-gg-ui-template-released`) lets Rendering push a bump on a release tag;
  `workflow_dispatch` re-pins by hand. Both open a PR.
- **`scripts/bump-rendering-pin.sh <version>`** — the shared, human-runnable primitive
  both lean on; updates every coherence surface in one shot.

## Just add Governance to an existing workspace

The `fs-gg-governance` overlay drops the populated FS.GG reference gate set into any
existing SDD-managed workspace:

```sh
dotnet new install ./templates/fs-gg-governance
dotnet new fs-gg-governance -o ./MyApp --appName MyApp --defaultProfile light
```

## Composition tests

`tests/composition/run.sh` runs the standard packaging-repo checks
(**pack → install → instantiate → build → verify pins/links**):

```sh
tests/composition/run.sh                  # owned stages run fully; full scaffold/build is gated
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh   # require the fsgg-sdd scaffold+build stage
```

It packs `FS.GG.Workspace.Template`, installs it, instantiates the `fs-gg-governance` overlay, and
asserts the pins/links: parameter substitution lands, the governance gate set is
**populated** (not the inert `checks: []`/`commands: []` it used to ship), both gameplay
floors remain command-free, controlled-import/schema payloads execute and materialize, the
committed overlay matches its exact published authority with only declared template transforms, and the
`rendering` provider pin is internally coherent (version tag + `lifecycle=sdd` /
`profile=game`). The full scaffold + `dotnet build` of the live rendering app needs the
`fsgg-sdd` CLI and a reachable template feed; that stage runs when they are available and
otherwise **skips with a reason** (it never green-passes by omission).

In both composition lanes — orchestrated (`fsgg-sdd scaffold`) and standalone (direct
`dotnet new fs-gg-ui`, spec-kit) — the gate asserts the **skill-union invariant** (ADR-0014,
issue #49): the two agent-skill roots (`.claude`/`.agents` `skills/`) are the
byte-identical union of process + product skills (via the reusable FS-GG/.github
`skill-union-assert.sh`), every materialized manifest-declared skill matches its
canonical-body sha256, and nothing undeclared ships (dangling fails).

That shared script is fetched at a **pinned FS-GG/.github commit SHA** (`SKILL_ASSERT_REF`
in `tests/composition/lib/skill-union.sh`), never `@main` (issue #56): a full-SHA raw fetch is content-addressed, so the
gate is both deterministic (its semantics can't change under this repo without a reviewable
pin bump) and integrity-checked (GitHub can't serve different bytes for a SHA — no separate
content hash needed). Renovate moves the pin against the `main` head like the `FS.GG.UI.*`
pin. The gate also **alarms on a frozen pin** (#315): before any stage runs it resolves that
commit's date and reds if it is older than the threshold in `lib/skill-union.sh`, so a pin that
stops moving can no longer ride along under a green tick.

**CI runbook note:** this couples the gate to **two distinct network dependencies**, and they
fail independently — an egress allowlist routinely permits one and blocks the other, and
GitHub tracks them separately on its status page:

1. **`raw.githubusercontent.com`** at the pinned SHA — fetching the shared
   `skill-union-assert.sh` itself.
2. **`github.com` git-over-HTTPS** — `git fetch --depth 1` of that one commit, to read its
   committer date for the staleness alarm. (Deliberately not `api.github.com`, whose
   unauthenticated 60/hour/IP budget is shared: a required check that reds because someone else
   spent it would be a worse outage than the staleness it watches for.)

Either being unreachable — or an offline host with no sibling `../.github` clone at the ref —
**fails the lane by design**; it never green-passes unverified. The same escape hatch covers
both: `git clone https://github.com/FS-GG/.github ../.github` makes the whole thing offline.
Both `dotnet` and `git` are hard prerequisites the runner preflights, exiting 2 without them.

On a provisioned container the full path needs no extra setup. `~/.nuget/NuGet/NuGet.Config`
binds `FS.GG.*` to the published FS.GG org feed (`packageSourceMapping`), and the container
entrypoint floats `fsgg-sdd` / `fsgg-governance` to the latest published version on every
start. The scaffold then resolves `FS.GG.UI.Template::<pin>` and the coherent `FS.GG.UI.*`
set straight from the org feed:

```sh
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh # full scaffold/build + skill-union (both lanes) + enforcement
```

(The run prints its own pass total on its `== summary ==` line; no count is transcribed here.
This one had already rotted twice — #75 corrected `45/45` to `47/47`, and #321 found `47/47`
against an actual 76. See [`tests/composition/README.md`](tests/composition/README.md).)

The org feed is private, so the full composition lane needs a GitHub token with
`read:packages` (baked into the
container's NuGet config — `%GH_TOKEN%`, read at restore time, never stored in an image
layer). Absent it the gated stages skip with a reason rather than green-passing. Because
`FS.GG.*` is pinned to the org feed, a stale local snapshot can never shadow the published
CLIs — that was the old drift class, and the source mapping closes it structurally.
The governance-overlay drift gate independently downloads its exact public nuget.org pin
and verifies the recorded archive digest, so it never follows a mutable latest version.

To test an **unpublished** local FS.GG.Rendering build before it reaches the org feed, use
`scripts/dev-repack-ui-feed.sh` (repacks the pinned `FS.GG.UI.*` set from a Rendering checkout
into the local cache; you then map `FS.GG.UI.*` to that cache in NuGet.Config so the test
consults it). It is a dev convenience, not part of provisioning, and per ADR-0002 it is **not**
a republish — the `FS.GG.UI.*` family already ships as one locked set behind
`fs-gg-ui-template/v<ver>`.

### Owner-sourced product skills for the Fable workspaces

The generic Fable product skills — `fable-project`, `fable-interop`, `fable-remoting`,
`fable-signalr`, `fable-testing`, `fable-bindings` — are **authored once**, under
`template/product-skills/`, and **projected** into each provider template's packed
`.agents/skills/` payload by package items in `FS.GG.Templates.csproj`. Nothing is copied into
`templates/` in the working tree: there is one authored file per skill and no second file that can
drift. Which templates a skill lands in is declared by its `materializes-when` row in the producer
manifest `template/skill-manifest/skill-manifest.json`, which ships into every such product as
`.agents/skills/skill-manifest.json` and carries each skill's canonical-body sha256.

`scripts/generate-skill-manifest.fsx` owns all of it and has three arms:

| arm | what it grades |
| --- | --- |
| *(no flag)* | regenerates the manifest from the catalog |
| `--check` | the catalog, the checked-in manifest, and the csproj package items still agree |
| `--assert-product <dir> --template <id>` | a product instantiated from the **packed archive** received exactly the declared set — reds on an absent selected skill, a skill the manifest does not select for that template, an undeclared (dangling) skill directory, a drifted digest, or a missing/non-canonical producer manifest |

The product-side arm is the load-bearing one, and the reason it exists is worth keeping: the
catalog originally shipped in a tree no package item referenced. Every source-side check was green,
CI was green, and **no generated product could receive a single declared skill** — a source-side
check grades a repository file, and only instantiating the archive grades delivery. Both arms run
on the required `composition` job; `fs-gg-fable-bindings` is additionally asserted inside its own
lane, on the same product that then goes through npm/Fable/Node/Chromium/SDD/Governance.

## Install (the template package)

The templates ship as a versioned NuGet **template package**, so the standard `dotnet new`
update path applies:

```sh
dotnet new install FS.GG.Workspace.Template          # from the org feed
# or from a local pack:  dotnet new install ./artifacts/FS.GG.Workspace.Template.<version>.nupkg
dotnet new update                           # upgrade to the latest published version
dotnet new update --check-only              # see what would update
```

### Release (publishing a new version)

The package is published by `.github/workflows/release.yml`, tag-driven and symmetric with
Rendering's `fs-gg-ui-template/v<ver>` flow — Templates publishes behind
`fs-gg-templates/v<ver>`. To cut a release, bump `<Version>` in `FS.GG.Templates.csproj`,
then push a matching tag:

```sh
git tag "fs-gg-templates/v<version>" && git push origin "fs-gg-templates/v<version>"
```

The workflow's `gate` job re-runs the composition suite and asserts the tag version equals
`<Version>` (fail-closed — a red gate or a version mismatch skips the publish). The `publish`
job then packs, pushes to `nuget.pkg.github.com/FS-GG`, and cuts a GitHub Release. This is
the producer side of the org **publish-before-flip** dance: the package is LIVE on the feed
before any downstream registry/pin flip advertises it.

## Contents

| Path | What |
|---|---|
| `providers/rendering.providers.yml` | the SDD scaffold-provider descriptor, pinned to `FS.GG.UI.Template` and passing `lifecycle=sdd` (the **primary** composition path). |
| `templates/fs-gg-governance/` | the populated Governance-config overlay (`fs-gg-governance`). |
| `tests/composition/run.sh` | end-to-end composition test (pack→install→instantiate→build→verify pins/links). |
| `scripts/dev-repack-ui-feed.sh` | DEV-ONLY: repacks the pinned `FS.GG.UI.*` set from a local FS.GG.Rendering checkout into the local cache, for testing an unpublished UI build before it reaches the org feed. The CLIs and the published UI set come from the org feed (container provisioning), not this script. |
| `scripts/bump-rendering-pin.sh` | re-pins `FS.GG.UI.Template` coherently across provider + README (successor to the retired `sync-from-rendering.sh`). |
| `.github/renovate.json` | Renovate config that bumps the `FS.GG.UI.*` pin and the pinned FS-GG/.github `skill-union-assert.sh` ref (issue #56) automatically. |
| `.github/workflows/upstream-bump.yml` | `repository_dispatch`/`workflow_dispatch` auto-PR that re-pins on an upstream release. |
| `.github/workflows/release.yml` | tag-driven (`fs-gg-templates/v*`) publish: gate (composition + version⇔tag assert) → pack → push to the org feed → GitHub Release. |
| `FS.GG.Templates.csproj` | packs the templates into the updatable NuGet package. |
| `docs/design.md` | the composition-vs-monolith rationale (why the vendored monolith was retired). |

## License

MIT.
