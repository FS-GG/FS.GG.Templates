# FS.GG.Templates

Composes the FS.GG products into a ready-to-run product: the
[FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) spec-driven lifecycle, a runnable
[FS.GG.Rendering](https://github.com/FS-GG/FS.GG.Rendering) app, and
[FS.GG.Governance](https://github.com/FS-GG/FS.GG.Governance) config.

Per [ADR-0002](https://github.com/FS-GG/.github/blob/main/docs/adr/0002-composition-by-scaffold-lifecycle-parameter-governance-populated.md),
composition happens **at scaffold time** — `fsgg-sdd scaffold` installs and drives the
live, version-pinned upstream template; FS.GG.Templates is the thin **composition +
registry** layer (a provider descriptor, a populated governance overlay, and these
composition tests), **not** a fork host. This repo ships no vendored framework copy.

## Create a full-stack product (composition, primary path)

Drive the [FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) CLI (`fsgg-sdd`, a `dotnet tool`)
with the `rendering` provider from this repo. Each product stays decoupled and
independently owned; the scaffold just glues them:

```sh
# 1. Register the rendering provider in your project (copy or merge the descriptor).
mkdir -p ./MyApp/.fsgg
cp providers/rendering.providers.yml ./MyApp/.fsgg/providers.yml

# 2. SDD skeleton + the live FS.GG.Rendering app (lifecycle=sdd → app-only product).
#    The product name rides the rendering template's standard `--name` option
#    (fsgg-sdd maps `--param name=…` → `--name …`).
fsgg-sdd scaffold --root ./MyApp --provider rendering --param name=MyApp

# 3. Activate Governance: drop the populated reference gate set into the project.
#    `--force` lets the overlay's .fsgg/project.yml land over the SDD skeleton's.
dotnet new install ./templates/fs-gg-governance
dotnet new fs-gg-governance -o ./MyApp --appName MyApp --defaultProfile light --force

cd ./MyApp && dotnet build && dotnet run     # the runnable Skia/Elmish product
```

`scripts/new-fullstack.sh <target> <product> <rendering-source>` wraps these three steps.

It produces:

- **Rendering** — the FS.GG.Rendering `fs-gg-ui` app (Skia/OpenGL, Elmish/MVU, Scene,
  SkiaViewer, Controls), installed live from the published `FS.GG.UI.Template` package
  pinned by the provider (currently `FS.GG.UI.Template@0.1.53-preview.1`, behind the
  immutable tag `fs-gg-ui-template/v0.1.53-preview.1`). The provider passes
  `lifecycle=sdd` so the product carries **only the runnable app** — the `.fsgg/`
  lifecycle comes from the SDD skeleton, not a second copy.
- **SDD** — the lifecycle skeleton: `.fsgg/project.yml`, `.fsgg/sdd.yml`,
  `.fsgg/agents.yml`, `work/`, `readiness/` (drive it with `fsgg-sdd charter …`).
- **Governance** — the populated reference gate set: `.fsgg/policy.yml`,
  `.fsgg/capabilities.yml` (build/test/evidence checks), `.fsgg/tooling.yml`
  (the matching commands). `--defaultProfile` sets the default profile; `light` is the
  non-blocking inner-loop posture, `strict`/`release` make the block-on-ship gates block.

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

## Just add Governance to an existing project

The `fs-gg-governance` overlay drops the populated FS.GG reference gate set into any
existing SDD-managed project:

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

It packs `FS.GG.Templates`, installs it, instantiates the `fs-gg-governance` overlay, and
asserts the pins/links: parameter substitution lands, the governance gate set is
**populated** (not the inert `checks: []`/`commands: []` it used to ship), and the
`rendering` provider pin is internally coherent (version tag + `lifecycle=sdd` /
`profile=app`). The full scaffold + `dotnet build` of the live rendering app needs the
`fsgg-sdd` CLI and a reachable template feed; that stage runs when they are available and
otherwise **skips with a reason** (it never green-passes by omission).

## Install (the template package)

The templates ship as a versioned NuGet **template package**, so the standard `dotnet new`
update path applies:

```sh
dotnet new install FS.GG.Templates          # from a feed, once published
# or from a local pack:  dotnet new install ./artifacts/FS.GG.Templates.<version>.nupkg
dotnet new update                           # upgrade to the latest published version
dotnet new update --check-only              # see what would update
```

## Contents

| Path | What |
|---|---|
| `providers/rendering.providers.yml` | the SDD scaffold-provider descriptor, pinned to `FS.GG.UI.Template` and passing `lifecycle=sdd` (the **primary** composition path). |
| `templates/fs-gg-governance/` | the populated Governance-config overlay (`fs-gg-governance`). |
| `tests/composition/run.sh` | end-to-end composition test (pack→install→instantiate→build→verify pins/links). |
| `scripts/new-fullstack.sh` | three-step wrapper for the `fsgg-sdd scaffold` composition path. |
| `scripts/bump-rendering-pin.sh` | re-pins `FS.GG.UI.Template` coherently across provider + README (successor to the retired `sync-from-rendering.sh`). |
| `.github/renovate.json` | Renovate config that bumps the `FS.GG.UI.*` pin automatically. |
| `.github/workflows/upstream-bump.yml` | `repository_dispatch`/`workflow_dispatch` auto-PR that re-pins on an upstream release. |
| `FS.GG.Templates.csproj` | packs the templates into the updatable NuGet package. |
| `docs/design.md` | the composition-vs-monolith rationale (why the vendored monolith was retired). |

## License

MIT.
