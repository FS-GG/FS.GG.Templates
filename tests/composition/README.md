# Composition tests

`run.sh` is the end-to-end composition check for FS.GG.Templates, following the standard
packaging-repo flow from the
[architecture report](../../docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md)
§5.2:

```
pack → install → instantiate → (restore/build) → verify pins/links
```

| Stage | What it checks | Gated? |
|---|---|---|
| **pack** | `FS.GG.Templates` packs to a `.nupkg` | no |
| **install** | the package installs as a `dotnet new` source; `fs-gg-governance` registers | no |
| **instantiate** | the `fs-gg-governance` overlay generates with `--appName` / `--defaultProfile` | no |
| **verify pins/links** | parameter substitution lands; the governance gate set is **populated** (not inert `checks: []`/`commands: []`); the `rendering` provider pin is coherent (version tag + `lifecycle=sdd` / `profile=app`) | no |
| **build** | full `fsgg-sdd scaffold` of the live rendering app + `dotnet build` | **yes** |

The **build** stage needs the `fsgg-sdd` CLI and a reachable `FS.GG.UI.Template` feed. It
runs when the CLI is on `PATH` (or `FSGG_COMPOSITION_FULL=1` forces it) and otherwise
**skips with a reason** — it never passes by omission.

```sh
tests/composition/run.sh                          # owned stages only; build stage skips
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh   # require the scaffold+build stage
KEEP_WORKDIR=1 tests/composition/run.sh            # keep the temp workdir for inspection
```

Exit code is non-zero if any assertion fails. CI runs this on every push/PR
(`.github/workflows/composition.yml`).
