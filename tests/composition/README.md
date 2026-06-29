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
| **govern** | the overlay does not just *exist* — it **enforces**: a produced `governance-handoff.json` actually drives a Governance verdict (strict **blocks**, `light` does not) | **yes** |

The **build** stage needs the `fsgg-sdd` CLI and a reachable `FS.GG.UI.Template` feed. It
runs when the CLI is on `PATH` (or `FSGG_COMPOSITION_FULL=1` forces it) and otherwise
**skips with a reason** — it never passes by omission.

The **govern** stage closes the gap between *populated* and *enforcing*. It has two parts,
each independently gated and never green-by-omission:

- **producer** — a real `fsgg-sdd ship` over the composed product emits
  `readiness/<id>/governance-handoff.json` (needs `fsgg-sdd` + a successful **build** stage).
- **consumer/enforcement** — needs only `fsgg-governance` (and the overlay this repo ships,
  instantiated fresh — the rendering app does not affect a governance verdict). It runs
  `fsgg-governance route --mode gate` (the CI/merge-boundary mode; a blocking verdict exits
  `2`) over a contract-v1 handoff fixture and holds the product fixed while varying only
  *(handoff, profile)*:

  | profile | handoff | expected | proves | gated on |
  |---|---|---|---|---|
  | `strict` | failing | exit `2` | the overlay **consumes and enforces** the handoff | consumer (#28) |
  | `strict` | satisfied | exit `0` | the verdict tracks the declared facts (consumption is real, not just populated) | consumer (#28) |
  | `light` | failing | exit `0` | the profile shifts the blocking boundary (`light` relaxes the gate) | profile-aware enforcement (#34) |

  Two capabilities are gated **independently**, because consumption and profile-awareness ship
  separately upstream — a coarse "consumption ⇒ whole matrix" assumption would false-fail
  against the strict-only baseline:

  - **Consumption probe** — the stage runs `strict + failing` first. If it does **not** block
    (exit `0`), the installed CLI's build omits the SDD-handoff consumer
    (`FS.GG.Governance.Adapters.SddHandoff`, spec `081`) — so the whole matrix **skips with a
    reason** (tracking: `FS-GG/FS.GG.Governance#28`). It flips to asserting the consumption rows
    automatically once a consumer-bearing CLI (`FS.GG.Governance.Cli >= 1.1.0`) is on `PATH`.
  - **Profile-aware probe** — with consumption confirmed, the stage runs `light + failing`. The
    strict-only baseline (`1.1.0`) consumes the handoff but blocks regardless of profile, so this
    row **skips with a reason** (tracking: `FS-GG/FS.GG.Governance#34`) while `light` still blocks,
    and flips to asserting `exit 0` once profile-aware enforcement ships.

  A usage/input/tool exit (`64`/`66`/`70`) is always a hard failure, never a skip.

```sh
tests/composition/run.sh                          # owned stages only; gated stages skip
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh   # require the scaffold+build stage
KEEP_WORKDIR=1 tests/composition/run.sh            # keep the temp workdir for inspection
```

Exit code is non-zero if any assertion fails. CI runs this on every push/PR
(`.github/workflows/composition.yml`).
