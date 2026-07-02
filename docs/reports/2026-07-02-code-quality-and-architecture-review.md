---
title: "FS.GG.Templates — code quality & architecture review"
date: 2026-07-02
time: "14:02 CEST"
status: Findings for triage
author: FS-GG (analysis)
affects: FS.GG.Templates (scripts/, tests/composition/, .github/, providers/, templates/)
baseline: main @ 574e90c (feat(composition): assert byte-identical skill union in both lanes + re-pin 0.1.61-preview.1)
evidence: FSGG_COMPOSITION_FULL=1 tests/composition/run.sh — 45 passed, 0 failed (both CLIs on PATH; one honest producer-seam SKIP)
---

# FS.GG.Templates — code quality & architecture review (2026-07-02)

> **One-line verdict:** The repo does what ADR-0002 asks of it — a thin, well-tested,
> honestly-gated composition + registry layer with no vendored payload — and the full
> composition suite is green (45/45). The findings below are one confirmed regression
> (`new-fullstack.sh`'s dead third argument), a cluster of test-hermeticity and
> supply-chain hardening gaps in `tests/composition/run.sh`, and one structural gap:
> **the package this repo exists to ship has no publish pipeline.**

Scope: every non-generated source in the repo — `tests/composition/run.sh` (the 470-line
composition gate), the three `scripts/`, both workflows, `renovate.json`,
`FS.GG.Templates.csproj`, the provider descriptor, the `fs-gg-governance` template
(config + content), and the docs that double as coherence surfaces (README, design.md,
tests README). `docs/TestSpecs/Games/` (15 game design specs, ~400 KB) is content, not
code, and was skimmed only for placement. The review was grounded by running the full
suite locally with `fsgg-sdd` 0.4.x and a profile-aware `fsgg-governance` on PATH.

---

## 1. What is genuinely good (keep doing this)

- **The architecture is the right one, and it is enforced, not just documented.** The
  ADR-0002 shape — compose at scaffold time, pin one version, vendor nothing — removes
  the `FsGgUiVersion` staleness class structurally, and the composition test *asserts*
  the coherence surfaces (provider `source::` pin ⇔ provider comment tag ⇔ README) rather
  than trusting the bump tooling. Three bump paths (Renovate always-on,
  `repository_dispatch` push-from-upstream, human-runnable script) all converge on the
  single primitive `scripts/bump-rendering-pin.sh`. This is textbook.
- **"Never green-by-omission" is applied with unusual discipline.** Every gated stage in
  `run.sh` either runs or SKIPs with a printed reason, and the skill-union assertion goes
  further: if the shared assertion script cannot be obtained, the lane **fails** rather
  than passing unverified (`run.sh:100`). Exit-code assertions are exact-match so a usage
  error (64/66/70) can never masquerade as a verdict (`run.sh:64`).
- **The enforcement matrix tests behavior, not existence.** Stage 6b holds the product
  fixed and varies only *(handoff, profile)*, using the exit-code differential as the
  signal that the overlay actually *consumes and enforces* — a materially stronger claim
  than "the gate set is populated." Capability probes (consumption vs. profile-awareness)
  are gated independently so an older upstream CLI degrades to an honest SKIP, not a
  false failure.
- **The empty lockfile is a deliberate forward guardrail** (`FS.GG.Templates.csproj:32-43`),
  correctly gated on `GITHUB_ACTIONS` + lockfile existence so a fresh clone bootstraps,
  and correctly kept off a root `Directory.Build.props` so it cannot leak into template
  *content*. The inline comment explains all of this — the comment quality across the repo
  (csproj, provider yml, run.sh stage headers) is the best kind: constraints and
  rationale, with cross-repo tracking links.
- **Suite health: 45/45.** Both lanes of the ADR-0014 skill-union invariant assert
  (orchestrated: 8 manifest skills digest-checked; standalone: 9), the composed product
  builds, and the full enforcement matrix now asserts including the `light`-relaxation
  row (profile-aware CLI ≥ 1.2.0 is on PATH). Only the producer seam SKIPs, honestly
  (a bare scaffold has no ship-ready work item).

---

## 2. Confirmed defect

### F1 — `scripts/new-fullstack.sh`: the `<rendering-template-source>` argument is dead (regression)

`new-fullstack.sh:23-24` still does

```sh
sed "s|__RENDERING_TEMPLATE_SOURCE__|$RENDERING_SOURCE|" \
    "$REPO_ROOT/providers/rendering.providers.yml" > "$TARGET/.fsgg/providers.yml"
```

but commit `a790eb9` (2026-06-27, "repoint rendering provider at published
FS.GG.UI.Template@0.1.50-preview.1") replaced the `__RENDERING_TEMPLATE_SOURCE__`
placeholder in the provider yml with the concrete published pin. The token now exists
**only** in this script (verified by repo-wide grep), so the `sed` is a no-op: the
required third argument is accepted, validated (`${3:?…}`), documented in the usage
header ("a local path or NuGet id for `dotnet new install`") and in the README
(`scripts/new-fullstack.sh <target> <product> <rendering-source>`) — and then **silently
ignored**. The scaffold always installs the committed pin.

- **Why nothing caught it:** `run.sh:246` calls the script with `"$PIN_VER"` — the same
  value as the committed pin — so the composition test passes by coincidence.
- **Why it matters:** the documented use case for the argument is exactly the one that
  breaks — pointing the scaffold at a *local path or different version* (e.g. together
  with `dev-repack-ui-feed.sh` to test an unpublished Rendering build). A developer doing
  that gets the published pin instead, with no warning, and debugs a phantom.
- **Fix options (pick one, don't keep the limbo):**
  1. Make the argument work again: `sed` the *pin value* (`FS.GG.UI.Template::<pin>` →
     `$RENDERING_SOURCE`) instead of the retired placeholder; or
  2. Drop the argument (the pin is the single source of truth per ADR-0002) and update
     usage + README + the `run.sh:246` call site. Given the design direction, (2) is the
     more honest shape; keep an optional `--source` override if the dev-repack flow needs it.

Severity: **medium** (silent wrong behavior on a documented path; no data loss).

---

## 3. Test-gate robustness findings (`tests/composition/run.sh`)

### F2 — Stage 5b can run the standalone lane against a stale template version

`run.sh:305-306`:

```sh
if dotnet new install "FS.GG.UI.Template::$PIN_VER" >… 2>&1 \
   || dotnet new list 2>/dev/null | grep -q 'fs-gg-ui'; then
```

If the pinned install fails (feed hiccup, yanked version), the fallback accepts **any**
already-installed `fs-gg-ui` template — including an older version left in the hive by a
previous run (see F3). The lane then asserts the skill-union against a payload that is
*not* the pin, and can pass (or fail) for the wrong version. The fallback's legitimate
purpose ("already satisfied when Stage 5 ran — fsgg-sdd installs the same pin", per the
comment) can be preserved precisely: after the `||` branch, verify the *installed
version* matches `$PIN_VER` (`dotnet new details FS.GG.UI.Template` or parse
`dotnet new list` output), else `bad`. Related edge: if Stage 4 failed to parse the pin,
`$PIN_VER` is empty and `dotnet new install "FS.GG.UI.Template::"` fails into the same
stale-fallback path — guard the stage on a non-empty pin.

Severity: **medium** — it is a version-coherence hole in the exact invariant the repo
exists to guard, though it only opens on a failed install.

### F3 — The test mutates the user's global template hive and only half cleans up

`cleanup()` (`run.sh:148-156`) uninstalls `FS.GG.Templates` but **not** the
`FS.GG.UI.Template::<pin>` that Stage 5b installs (nor does `new-fullstack.sh` uninstall
the `fs-gg-governance` folder-install it does with `|| true`). Consequences: the hive
accumulates versions run-over-run; the developer's real environment is changed by running
a test; and the stale copies are what arms F2's fallback. Options: uninstall what the run
installed in `cleanup()`, or better, run every `dotnet new` in the script against an
isolated hive (`--debug:custom-hive "$WORKDIR/hive"`), which makes the whole test hermetic
and concurrency-safe in one move. If Stage 5's `fsgg-sdd scaffold` cannot be pointed at a
custom hive, do the uninstall-in-cleanup variant.

Severity: **medium** (hermeticity; user-visible side effects; feeds F2).

### F4 — The gate executes an unpinned remote script from `@main`

`fetch_skill_assert` (`run.sh:71-84`) curls
`raw.githubusercontent.com/FS-GG/.github/main/scripts/skill-union-assert.sh` and executes
it. Two distinct problems:

1. **Reproducibility / moving target:** the assertion's semantics can change under this
   repo with no commit here — a CI run today and tomorrow may enforce different things.
   The comment's anti-vendoring rationale is right, but *pinning is not vendoring*: fetch
   `…/.github/<sha-or-tag>/scripts/skill-union-assert.sh` and bump the ref like any other
   pin (Renovate can move it). That keeps one source of truth *and* deterministic gates.
2. **Supply-chain surface:** executing a curl'd script with no integrity check. Within
   one org this is a modest risk, but a SHA-pinned URL (or a pinned ref + recorded
   sha256) closes it for free.

Also note the availability coupling: a raw.githubusercontent outage **fails** the lane
(by design — honest, and the sibling-clone fallback softens it locally), which is the
right trade-off but worth stating in the CI runbook.

Severity: **medium** (determinism of the gate itself).

### F5 — Stage 6b never checks that the overlay instantiation succeeded

`run.sh:430`: `dotnet new fs-gg-governance -o "$GOV" … >…log 2>&1` has no `if`/assert. If
it fails, `set_profile`'s `sed` fails silently (its exit status is dropped by the callers)
and `govern_exit` runs against a half-empty product; the matrix then reports a confusing
"usage/input/tool error, not a verdict" failure instead of "instantiation failed". One
`|| { bad …; }` guard restores a first-cause diagnostic. (Stages 3 and 5 already model
the right pattern.)

Severity: **low** (fails loudly today, just with the wrong message).

### F6 — No minimum-cardinality floor under the skill-union assertion

`assert_skill_union` (`run.sh:97-146`) passes with "every materialized manifest-declared
skill matches its sha256 (**0 checked**)" if a lane materializes nothing: an empty union
is trivially byte-identical across roots, absence of manifest-declared skills is
informational by design (upper-bound catalog), and the loop then has nothing to check.
Today the lanes materialize 8–9 skills, so this is latent — but a producer regression
that stops materializing entirely would pass this gate. Cheap fix: assert `matched -ge 1`
(or assert the lane's co-tenants actually exist, e.g. at least one `fs-gg-sdd-*` dir in
the orchestrated lane — that is precisely what `minimumFsggSdd` promises).

Severity: **low** (latent; the invariant's floor is unstated).

---

## 4. Workflow & automation findings

### F7 — `upstream-bump.yml`: expression-interpolation into `run:` + unvalidated version

`upstream-bump.yml:51` interpolates `${{ steps.ver.outputs.version }}` directly into a
`run:` line. The value originates from `client_payload.version` — attacker-controlled
only by someone who can already fire `repository_dispatch` (write access), so the trust
boundary is org-internal, but it is the one injection-shaped pattern in a repo that
otherwise gets this right (the Resolve step correctly uses `env:`). Pass it via `env:`
here too. Compounding: nothing validates that the value *looks like* a version before it
reaches `bump-rendering-pin.sh`, whose `sed -i "s#${OLD_RE}#${NEW}#g"` uses `#` as the
delimiter and does not escape `NEW` — a value containing `#`, `&`, or `\` corrupts both
the provider yml and the README in the bump PR (caught by the composition gate on the PR,
so not silent, but noisy). A `[[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][A-Za-z0-9.]+)?$ ]]`
guard in the script serves all three callers.

Also: `peter-evans/create-pull-request@v6` is tag-pinned, not SHA-pinned — align with
whatever the org policy is for third-party actions (the FS-GG/.github preset presumably
has a stance).

Severity: **low** (auth-gated), but cheap to close.

### F8 — CI hygiene on `composition.yml`

All minor, all cheap:

- **No `timeout-minutes`** — a hung feed or scaffold holds a runner for the 6-hour default.
- **No `concurrency` group** — force-pushed PRs stack redundant full-composition runs
  (each packs, scaffolds, and builds the live rendering app).
- **No failure-artifact upload** — on a red run the only diagnostics are the inline
  `tail`s; `KEEP_WORKDIR=1` + `actions/upload-artifact` (with `if: failure()`) would ship
  `pack.log`/`scaffold.log`/`build.log`/`govern.log` wholesale.
- **Docs-only changes pay the full price** — `docs/TestSpecs/**` edits trigger the full
  scaffold+build. `README.md` is a genuine coherence surface (the test greps it) and must
  stay in scope, but a `paths-ignore` for `docs/**` (README is repo-root, unaffected)
  would cut the biggest waste. Judgement call: skipping *any* CI on push is a posture
  change; if "every push runs the gate" is deliberate, say so in the workflow comment.

### F9 — `tests/composition/README.md` is one capability behind reality

The matrix documentation (rows/probes) still frames the `light`-relaxation row as
"skips with a reason against an older profile-unaware CLI (1.1.0) … flips to asserting
once ≥ 1.2.0 is on PATH". That flip has happened — today's run asserts all three rows.
The doc is *designed* to stay true across CLI generations, so this is borderline, but the
"The slot is correct in this repo; against an older CLI the row skips" paragraph reads as
present-tense status. A one-line "as of 2026-07-02 the full matrix asserts in CI" note
keeps the honest-gating narrative current. Same class of rot risk exists in the many
inline comments carrying cross-repo temporal state ("FS.GG.SDD released v0.4.0
(2026-07-01)…", provider yml:33) — the registry mirror discipline mostly contains it, but
each dated claim is a small liability; prefer linking the registry over restating it.

---

## 5. Architecture-level observations

### A1 — The package this repo ships has no publish pipeline (the real structural gap)

Everything in the repo converges on "the templates ship as a versioned NuGet template
package, so `dotnet new update` is the consumer update function" (README §Install,
csproj header, design.md §Update function) — yet there is no release workflow: nothing
packs and pushes `FS.GG.Templates.nupkg` to the org feed, no tag-driven release, and
`<Version>0.2.0</Version>` is hand-maintained with no bump-on-release check. The README's
own install instructions hedge with "once published". Until this exists, the advertised
update function is theoretical, and the fs-gg-governance overlay is only consumable from
a checkout. This is the highest-leverage missing piece: a small `release.yml`
(tag `v*` → `dotnet pack` → push to `nuget.pkg.github.com/FS-GG` with a `packages:write`
token → GitHub Release) plus a version-vs-tag coherence assert closes it. It also
completes the symmetry the repo preaches: Rendering publishes behind
`fs-gg-ui-template/v<ver>`; Templates should publish behind `fs-gg-templates/v<ver>`.

### A2 — Pin parsing is duplicated 3× as unstructured grep/sed over YAML

`run.sh:220`, `bump-rendering-pin.sh:24`, and `dev-repack-ui-feed.sh:49` each carry the
identical `grep -oE 'FS\.GG\.UI\.Template::[^ ]+' | head -1 | sed 's/.*:://'` (two of
them with comments promising they match the third — the DRY-violation smell made
explicit). Any formatting change to the `source:` line (quoting, a second provider entry)
breaks three call sites, each discovered separately. Extract one `scripts/lib/read-pin.sh`
(or use `yq` if adding a dependency is acceptable — the grep is honest about not being a
YAML parser). Small, but this string *is* the repo's single most load-bearing value.

### A3 — `run.sh` is at the size where structure would start paying

470 lines, one file, hand-rolled assertion helpers, a mini-program
(`assert_skill_union`, ~80 lines), and JSON contract fixtures embedded as heredocs. It is
*good* bash — `set -uo pipefail` chosen deliberately so failures count rather than abort,
consistent quoting, every stage narrated — and at the current size this is a judgement
call, not a defect. But the growth pattern (each ADR adds a stage; #49 alone added ~120
lines) points one way. When the next stage lands, consider: fixtures out to
`tests/composition/fixtures/*.json`, stages as sourced `stages/NN-*.sh` files sharing the
helper prelude, and the helpers (`ok/bad/skip/assert_*`) as a lib. That also makes the
per-stage gating conditions individually testable.

### A4 — The governed commands are asserted present, never runnable

The overlay's `tooling.yml` governs `dotnet build <App>.sln`, `dotnet test <App>.sln`,
and `dotnet fsi build.fsx -- evidence`; `capabilities.yml` maps `build.fsx` → evidence.
The composition test asserts these **ids exist** (Stage 4) and that the overlay
**enforces a handoff fixture** (Stage 6b) — but never that the governed commands are
*executable against the composed product*: does the Stage-5 scaffold actually produce
`Acme.sln` and a `build.fsx`? If the fs-gg-ui template ships neither, the overlay governs
phantom commands and the first real `fsgg-governance` check-run in a scaffolded product
fails. Since Stage 5 already builds the composed product, one added assertion —
`[[ -f "$FULL/Acme.sln" ]]` (+ `build.fsx` if the evidence gate is meant to work
out-of-the-box) — closes the gap between "populated", "enforcing", and **"runnable"**.
This is the same seam-ownership argument the govern stage makes for itself.

### A5 — Placement notes (informational)

- `docs/TestSpecs/Games/` (15 specs, ~400 KB, 80% of the repo by bytes) is unreferenced
  by README's Contents table and by any test. If they are acceptance material for
  composed products (they read like SDD charter inputs), one line in the README saying so
  would prevent "why is this here" archaeology; if they belong to a product repo or a
  future FS.GG.TestSpecs, note the intended destination.
- The `.github/renovate.json` custom manager and hostRules are correct and well-reasoned
  (the "secrets don't substitute inside extends-presets" note is exactly the kind of
  non-obvious constraint worth writing down). One nit: the three `matchStrings` also
  match the `fs-gg-ui-template/v…` form inside *comment prose*, which is intended
  (coherence), but means any future prose mentioning an *old* version in a historical
  context will be "helpfully" rewritten by the next bump PR — same behavior as
  `bump-rendering-pin.sh`'s whole-file sed. Both tools assume README/provider mention the
  pin only in its current-value sense; keep honoring that writing convention.

---

## 6. Prioritized recommendations

| # | Action | Closes | Effort |
|---|---|---|---|
| 1 | Add a release/publish workflow for `FS.GG.Templates` (tag-driven pack→push→release, version⇔tag assert) | A1 | S |
| 2 | Fix or remove `new-fullstack.sh`'s dead `<rendering-source>` argument (+ README, + `run.sh:246` call site) | F1 | S |
| 3 | Stage 5b: verify installed `fs-gg-ui` version == `$PIN_VER` when falling back; guard on non-empty pin | F2 | S |
| 4 | Make `run.sh` hermetic: custom template hive (or uninstall everything installed, incl. `FS.GG.UI.Template`) | F3 | S–M |
| 5 | Pin `skill-union-assert.sh` fetch to a SHA/tag (Renovate-bumpable), keep the fail-not-skip posture | F4 | S |
| 6 | Version-format guard in `bump-rendering-pin.sh`; `env:` instead of `${{ }}`-in-`run:` in upstream-bump | F7 | S |
| 7 | CI: `timeout-minutes`, `concurrency` cancel-in-progress, failure-artifact upload of `$WORKDIR` logs | F8 | S |
| 8 | Assert composed-product runnability of governed commands (`Acme.sln`, `build.fsx`) in Stage 5 | A4 | S |
| 9 | Extract the shared pin-read helper; add `matched -ge 1` floor to `assert_skill_union`; guard Stage 6b instantiation | A2, F6, F5 | S |
| 10 | Refresh `tests/composition/README.md` matrix status; adopt "link the registry, don't restate it" for dated claims | F9 | S |
| 11 | When the next stage lands in `run.sh`, split fixtures/stages/helpers | A3 | M |

Nothing here blocks current work: the suite is green, the coherence machinery works, and
the recent ADR-0014 hardening (skill-union in both lanes, provider-defect SKIPs retired)
moved the gate in exactly the right direction. Items 1–2 are the only ones a consumer
could notice today.
