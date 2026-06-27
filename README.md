# FS.GG.Templates

`dotnet new` templates that compose the FS.GG products into a ready-to-run product:
the [FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) spec-driven lifecycle, a runnable
[FS.GG.Rendering](https://github.com/FS-GG/FS.GG.Rendering) app, and
[FS.GG.Governance](https://github.com/FS-GG/FS.GG.Governance) config.

## Install

```sh
dotnet new install FS.GG.Templates          # from a feed, once published
# or from a local pack:  dotnet new install ./artifacts/FS.GG.Templates.<version>.nupkg
```

## Create a full-stack product (single template)

`fs-gg-fullstack` is one monolithic template that, in a single `dotnet new`, emits all
three layers — no `fsgg-sdd` CLI required:

```sh
dotnet new fs-gg-fullstack -o ./MyApp --governanceProfile standard   # light | standard | strict

cd ./MyApp && dotnet build && dotnet run     # the runnable Skia/Elmish product
```

It produces:

- **Rendering** — the full FS.GG.Rendering `fs-gg-ui` app (Skia/OpenGL, Elmish/MVU,
  Scene, SkiaViewer, Controls); `--profile` (`app`/`headless-scene`/`governed`/
  `sample-pack`) and `--designSystem` (`wcag`/`ant`) are passed through.
- **SDD** — the lifecycle skeleton: `.fsgg/project.yml`, `.fsgg/sdd.yml`,
  `.fsgg/agents.yml`, `work/`, `readiness/` (drive it with `fsgg-sdd charter …`).
- **Governance** — `.fsgg/policy.yml`, `.fsgg/capabilities.yml`, `.fsgg/tooling.yml`
  (`--governanceProfile` sets the default profile).

## Update

The templates ship as a versioned NuGet **template package**, so the standard
`dotnet new` update path applies:

```sh
dotnet new update                # upgrade installed FS.GG.Templates to the latest published version
dotnet new update --check-only   # see what would update
```

To refresh the vendored rendering content from upstream and cut a new version
(maintainers): `scripts/sync-from-rendering.sh <FS.GG.Rendering-checkout>`, bump
`<Version>` in `FS.GG.Templates.csproj`, then `dotnet pack -c Release -o ./artifacts`.

## Just add Governance to an existing project

```sh
dotnet new fs-gg-governance -o ./MyApp --defaultProfile standard
```

## Contents

| Path | What |
|---|---|
| `templates/fs-gg-fullstack/` | the monolithic SDD + Rendering + Governance template (`fs-gg-fullstack`). |
| `templates/fs-gg-governance/` | Governance-config-only overlay (`fs-gg-governance`). |
| `providers/rendering.providers.yml` | drop-in SDD scaffold-provider entry (for the `fsgg-sdd scaffold` composition path). |
| `FS.GG.Templates.csproj` | packs the templates into the updatable NuGet package. |
| `scripts/sync-from-rendering.sh` | re-vendor the rendering payload from upstream. |
| `scripts/new-fullstack.sh` | alternative: compose via `fsgg-sdd scaffold` instead of the monolith. |
| `docs/design.md` | the monolith-vs-composition rationale. |

## License

MIT.
