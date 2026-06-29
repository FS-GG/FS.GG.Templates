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
| **verify pins/links** | parameter substitution lands; the descriptor is in the Governance-owned `.fsgg/governance.yml` slot (ADR-0005 — **not** the SDD-owned `project.yml`); the governance gate set is **populated** (not inert `checks: []`/`commands: []`); the `rendering` provider pin is coherent (version tag + `lifecycle=sdd` / `profile=app`) | no |
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

  | profile | handoff | expected | proves | needs |
  |---|---|---|---|---|
  | `strict` | failing | exit `2` | the overlay **consumes and enforces** the handoff | consumer-bearing CLI (≥ 1.1.0, #28) |
  | `strict` | satisfied | exit `0` | the verdict tracks the declared facts (consumption is real, not just populated) | consumer-bearing CLI (≥ 1.1.0, #28) |
  | `light` | failing | exit `0` | the profile shifts the blocking boundary (`light` relaxes the gate) | descriptor in the `governance.yml` slot (#28) **+** profile-aware CLI (≥ 1.2.0, #34) |

  Two capabilities are probed **independently**, because consumption and profile-awareness ship
  separately upstream — a coarse "consumption ⇒ whole matrix" assumption would false-fail against
  an older CLI:

  - **Consumption probe** — the stage runs `strict + failing` first. If it does **not** block
    (exit `0`), the installed CLI's build omits the SDD-handoff consumer
    (`FS.GG.Governance.Adapters.SddHandoff`, spec `081`) — so the whole matrix **skips with a
    reason**. It flips to asserting the consumption rows automatically once a consumer-bearing CLI
    (`FS.GG.Governance.Cli >= 1.1.0`) is on `PATH`.
  - **Profile-aware probe** — with consumption confirmed, the stage runs `light + failing`. This
    relaxes only if the overlay ships its descriptor in the Governance-owned `.fsgg/governance.yml`
    slot (so the CLI can read `defaultProfile` — else it falls back to the Strict fail-safe and
    over-blocks every profile) **and** the CLI is profile-aware (`>= 1.2.0`). The slot is correct
    in this repo; against an older profile-unaware CLI (`1.1.0`) the row **skips with a reason**
    (tracking: `FS-GG/FS.GG.Governance#34`) and flips to asserting `exit 0` once `>= 1.2.0` is on
    `PATH`.

  A usage/input/tool exit (`64`/`66`/`70`) is always a hard failure, never a skip.

```sh
tests/composition/run.sh                          # owned stages only; gated stages skip
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh   # require the scaffold+build stage
KEEP_WORKDIR=1 tests/composition/run.sh            # keep the temp workdir for inspection
```

Exit code is non-zero if any assertion fails. CI runs this on every push/PR
(`.github/workflows/composition.yml`).
