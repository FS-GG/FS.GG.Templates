# FS.GG.Templates

Project templates and scaffold providers that **compose** the FS.GG products into a
ready-to-run product: the [FS.GG.SDD](https://github.com/FS-GG/FS.GG.SDD) spec-driven
lifecycle, a runnable [FS.GG.Rendering](https://github.com/FS-GG/FS.GG.Rendering) app,
and [FS.GG.Governance](https://github.com/FS-GG/FS.GG.Governance) config.

This repo sits **downstream** of all three and depends on them as a plain consumer —
none of the product repos depends back on it. See [docs/design.md](docs/design.md) for
why the combination lives here and not inside any single product.

## Full-stack: SDD + Rendering + Governance

```sh
# one command (SDD skeleton + full Rendering app + Governance config)
scripts/new-fullstack.sh ./MyApp MyApp <rendering-template-source>

cd ./MyApp && dotnet build && dotnet run   # the runnable product
fsgg-sdd charter                           # continue the SDD lifecycle
```

`<rendering-template-source>` is a local path or NuGet id for `dotnet new install` of
FS.GG.Rendering's `fs-gg-ui` template. Under the hood the script:

1. registers `fs-gg-ui` as an SDD scaffold provider (`providers/rendering.providers.yml`),
2. runs `fsgg-sdd scaffold --provider rendering` — SDD skeleton + full Rendering app,
   with produced files recorded in `.fsgg/scaffold-provenance.json`,
3. applies the `fs-gg-governance` overlay — drops `.fsgg/policy.yml`,
   `capabilities.yml`, and `tooling.yml` to activate Governance.

## Just add Governance to an existing project

```sh
dotnet new install <path-to>/FS.GG.Templates/templates/fs-gg-governance
dotnet new fs-gg-governance -o ./MyApp --defaultProfile standard   # light | standard | strict
```

## Contents

| Path | What |
|---|---|
| `templates/fs-gg-governance/` | `dotnet new` template that activates Governance (`.fsgg/policy.yml` / `capabilities.yml` / `tooling.yml`). |
| `providers/rendering.providers.yml` | drop-in SDD provider registry entry for the `fs-gg-ui` rendering template. |
| `scripts/new-fullstack.sh` | one-command composition of all three. |
| `docs/design.md` | the decoupling rationale and composition approach. |

## License

MIT.
