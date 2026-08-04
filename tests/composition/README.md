# Composition tests

`run.sh` is the end-to-end composition check for FS.GG.Templates, following the standard
packaging-repo flow from the
[architecture report](../../docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md)
§5.2:

```
pack → install → instantiate → (restore/build) → verify pins/links
```

The table below enumerates **every** stage `run.sh` executes, in execution order. The `pin`
stage is this repo's own preflight rather than part of the report's flow, so it sits above the
`pack → … → verify` line quoted from §5.2; everything else maps onto it.

| Stage | What it checks | Gated? |
|---|---|---|
| **pin** | the shared skill-union assertion this run's verdict rests on is **not frozen**: `SKILL_ASSERT_REF` resolves to a real commit and is newer than `SKILL_ASSERT_MAX_AGE_DAYS` (#315). Runs **first and ungated**, straight from `run.sh` rather than from `assert_skill_union` — the lanes that call `assert_skill_union` are both gated, so hanging the alarm off them would leave the pin's freshness unevaluated on exactly the hosts where both lanes skip. It also self-demonstrates that it *can* fire before it reports a verdict. An unresolvable age **fails** (`.github#266` — "could not look" is never "looked, and fine") | no |
| **lanes** (coverage) | every lane directory that exists under `tests/composition/` is actually **reached by a required path**, and every lane **fails** rather than skipping when its prerequisites are absent (#379). Runs **second and ungated**, for the same reason `pin` runs first: it is a fact about the *repository* — which lanes exist, and which of them the workflow files reach — not about the lane set this invocation selected, so hanging it off the lane loop would let a narrowed run check coverage only for the lanes it already ran. Self-demonstrates that it *can* fire before it reports a verdict | no |
| **roots** | this repo's runtime skill-root declaration and its generated view both hold, via the kit-delivered `scripts/skill-view` (`.github#1710`). Ungated and offline; an absent view root is green here **by measurement**, because `composition` runs on a bare checkout that never materializes — see the decision block in `run.sh` | no |
| **pack** | `FS.GG.Templates` packs to a `.nupkg` | no |
| **install** | the package installs as a `dotnet new` source; `fs-gg-governance` registers | no |
| **instantiate** | the `fs-gg-governance` overlay generates with `--appName` / `--defaultProfile` | no |
| **verify pins/links** | parameter substitution lands; the descriptor is in the Governance-owned `.fsgg/governance.yml` slot (ADR-0005 — **not** the SDD-owned `project.yml`); the governance gate set is **populated** (not inert `checks: []`/`commands: []`); the `rendering` provider pin is coherent (version tag + `lifecycle=sdd` / `profile=game`) | no |
| **build** | full `fsgg-sdd scaffold` of the live rendering app with a non-default product name; executes the generated README's exact root `dotnet build` and product-named `dotnet fsi load-<Name>.fsx` commands; proves the tool manifest does not advertise fake-cli and neither output nor guidance claims unsupported shared `.fake` state; checks the composed workspace's family-agnostic default entrypoint (Viewer host or Controls interactive/audio host, with no `-- pong` gate — #36); and proves the governed `<App>.slnx` / `build.fsx` commands resolve to real root artifacts (#59) | **yes** |
| **standalone** | the spec-kit lane: the pinned `FS.GG.UI.Template` installs and instantiates directly, and its two agent-skill roots satisfy the same skill-union assertion under `speckit-*` co-tenants | **yes** |
| **govern** | the overlay does not just *exist* — it **enforces**: a produced `governance-handoff.json` actually drives a Governance verdict (strict **blocks**, `light` does not) | **yes** |
| **lanes** (per-identity) | one full generated-root lifecycle per packaged workspace identity — instantiate, restore, build, test, publish, and where the identity has one the browser and provider/SDD routes. The stages above prove the descriptors **pack**; only these prove an identity **works**. See [Per-identity lanes](#per-identity-lanes) | no |
| **product skills** | the owner-sourced product-skill catalog, its checked-in manifest and the `csproj` package items agree, **and** a product instantiated from the packed archive actually receives the declared set (#347) | no |

The **build** stage needs the `fsgg-sdd` CLI and a reachable `FS.GG.UI.Template` feed. It
runs when the CLI is on `PATH` (or `FSGG_COMPOSITION_FULL=1` forces it) and otherwise
**skips with a reason** — it never passes by omission.

The **govern** stage closes the gap between *populated* and *enforcing*. It has two parts,
each independently gated and never green-by-omission:

- **producer** — a real `fsgg-sdd ship` over the composed workspace emits
  `readiness/<id>/governance-handoff.json` (needs `fsgg-sdd` + a successful **build** stage).
- **consumer/enforcement** — needs only `fsgg-governance` (and the overlay this repo ships,
  instantiated fresh — the rendering app does not affect a governance verdict). It runs
  `fsgg-governance route --mode gate` (the CI/merge-boundary mode; a blocking verdict exits
  `2`) over a contract-v1 handoff fixture and holds the workspace fixed while varying only
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

  > **Status:** a profile-aware CLI (`>= 1.2.0`) is on `PATH` in CI, so every row of the matrix
  > above — including the `light`-relaxation row — **asserts** rather than skipping. The
  > generation-conditional framing above is retained on purpose: it keeps the gate honest if an
  > older CLI is ever the one on `PATH`.
  >
  > **No pass count is quoted here, deliberately.** This repo has now fixed a stale one twice
  > (#75: `45/45` → `47/47`; #321: `55/55` → 76), because a total that every new assertion
  > changes is a number no reviewer is prompted to re-derive. The run prints its own total on the
  > `== summary ==` line, and that is the only place it is authoritative. What is worth asserting
  > in prose is the property, not the arithmetic: **nothing here green-passes by omission** — a
  > skip always prints its reason, and an unresolvable answer fails rather than passes. Read the
  > summary for the count; read the `SKIP:` lines for what did not run.
  >
  > A `SKIP:` line is not automatically a defect. The **producer** half of `govern` skips on a
  > bare scaffold (`fsgg-sdd ship` emits no handoff when there is no ship-ready work item), which
  > is why the consumer/enforcement matrix runs against a contract fixture instead — that half is
  > what makes the enforcement claim, and it is the half tabulated above.

  A usage/input/tool exit (`64`/`66`/`70`) is always a hard failure, never a skip.

## Prerequisites

`run.sh` preflights exactly two binaries and **exits 2** without either:

- **`dotnet`** — the whole pack → install → instantiate → build pipeline.
- **`git`** — resolving `SKILL_ASSERT_REF`'s commit date for the `pin` stage. This became a
  *hard* prerequisite with #315. Previously `git` was only used by `fetch_skill_assert`'s
  offline fallback, so a git-less host still passed via the `curl` path; now it cannot.

Nothing else is preflighted, and the rest do **not** all behave the same way — worth knowing
before reading a red:

- **`curl`** — used unguarded by `fetch_skill_assert` for the raw-fetch arm. Absent (or blocked),
  a sibling `../.github` clone still covers it; with neither, the lane **fails**, it does not skip.
- **`jq`** — the manifest arm sits behind a `command -v jq` check and **skips with a reason**.
- **`timeout`** — optional. Without it the `git fetch` still runs, just unbounded;
  `GIT_TERMINAL_PROMPT=0` plus an emptied credential helper removes the one way it hangs forever.
- **`fsgg-sdd` / `fsgg-governance`** — gated, and skip with a reason (see the table above).

**Offline runs:** clone `FS-GG/.github` as a sibling of this repo —

```sh
git clone https://github.com/FS-GG/.github ../.github
```

— and the whole skill-union machinery, alarm included, works with no network at all: both the
assertion script (`fetch_skill_assert`) and the pin's commit date (`skill_assert_ref_committed_at`)
read the sibling clone at the pinned ref. This is the single most useful thing to know here,
because without it an offline run now **reds** the `pin` stage where both lanes previously just
skipped. Note that a `git worktree` checkout is *not* a sibling clone: `../.github` resolves
relative to the worktree, not to the main checkout.

## Running

```sh
tests/composition/run.sh                          # owned stages only; gated stages skip
FSGG_COMPOSITION_FULL=1 tests/composition/run.sh   # require the scaffold+build stage
KEEP_WORKDIR=1 tests/composition/run.sh            # keep the temp workdir for inspection
```

Exit code is non-zero if any assertion fails. CI runs this on every push/PR
(`.github/workflows/composition.yml`).

## Layout

`run.sh` is a thin orchestrator; the gate was split out of a single ~600-line file
(review A3) so each stage, helper, and fixture is independently readable and the next
ADR stage drops in as one new `stages/` file:

```
run.sh              orchestrator — sets the run-globals, preflights dotnet + git, runs the
                    `pin` stage inline, sources the libs + stages in order (they share one
                    shell, so PASS/FAIL and stage vars persist), summarizes
lib/helpers.sh      PASS/FAIL counters + ok/bad/skip/step/assert_*/installed_template_version
lib/skill-union.sh  the pinned FS-GG/.github ref (SKILL_ASSERT_REF, Renovate-bumped) + the
                    #315 staleness alarm (resolver / pure predicate / assertion + its own
                    self-demonstration) + fetch_skill_assert + assert_skill_union
lib/lane-coverage.sh  lane DISCOVERY (the authority on which lanes exist) + the #379 gates:
                    every discovered lane is reached by a required path, every lane fails
                    closed on an absent prerequisite, the deferral registry, and their own
                    self-demonstration
lib/lane-package.sh   lane_package_path / lane_pin_provider_to_archive — resolve the archive a
                    per-identity lane installs (the release gate's exact bytes when
                    FSGG_TEMPLATES_NUPKG is set, a local pack otherwise) (#349)
fixtures/*.json     the contract-v1 governance-handoff documents Stage 6b enforces
stages/NN-*.sh      one file per stage: 01 pack · 02 install · 03 instantiate · 04 verify ·
                    05 build · 05b standalone · 06 govern
<lane>/run.sh       one per packaged workspace identity — see below. EXECUTED, not sourced
```

## Per-identity lanes

Each packaged workspace identity owns an isolated lane at `tests/composition/<lane>/run.sh`
that performs its complete generated-root lifecycle. Today: `web`, `console`,
`fable-bindings`, `fable-game`.

**The lane set is discovered, not listed (#379).** A directory here that carries a `run.sh`
*is* a lane, and `run.sh`'s default lane set is exactly that discovered set — so adding a lane
directory puts it on the required `composition` check **by construction**. There is no second
act to remember, which is the whole point: `console` (#356) and `fable-game` (#348) were each
added as complete lifecycle proofs and then executed on no required path at all, because the
orchestrator enumerated its lanes by hand and nothing observed the gap.

`COMPOSITION_LANES` still **selects** — a developer running one lane locally must not have to
run four:

```bash
COMPOSITION_LANES=console tests/composition/run.sh
```

What is gated is a *caller* narrowing the set. The `lanes` stage reads the workflow **files**
on every run — including a narrowed one — and reds naming any discovered lane no caller
reaches. It grades `.github/workflows/release.yml` too, whose own pinned four-name list is the
same hand-written enumeration one level over. The only sanctioned exemption is an entry in
`COMPOSITION_LANE_DEFERRALS`, which must name an issue and must leave the lane reachable by
some other caller — a deferral is not a deletion. The default lane set is *discovery minus that
registry*, so an entry there is the one thing that can take a lane back off this check.

It currently holds **one** entry, `fable-game`, and it is **not** a budget decision: that lane
cannot pass on any host until #392 lands, and `composition` is required under
`enforce_admins`, so running it here would wedge every PR in the repository. The measured budget
— including the full `fable-game` lane running green end to end in 63s — is quoted next to
`timeout-minutes: 30` in `.github/workflows/composition.yml`. Delete the entry when those two
it lands (tracked by #393); no re-measurement is owed.

Lanes are **executed, not sourced**, and are graded purely by exit status — so a lane is
all-or-nothing and must abort rather than run past a failure. That is why every lane enables
`errexit` and why the `lanes` stage checks that it does: without it, an absent `fsgg-sdd`,
`jq`, `npm` or browser would let a lane run on to its final success line and exit 0, reporting
a pass on a host where it did nothing.

The stage files are **sourced, not executed** — they run in `run.sh`'s shell and share its
globals (`NUPKG`, `PIN_VER`, `FULL`, `FULL_OK`, …), so order matters and an `exit` in a stage
ends the whole run. Helpers and fixtures are the only two things a new stage needs from the
prelude.
