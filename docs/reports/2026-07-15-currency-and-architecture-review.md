---
title: "FS.GG.Templates — currency & architecture review"
date: 2026-07-15
status: Complete — currency gap found and closed
author: FS-GG (analysis)
affects: FS.GG.Templates (providers/, README, tests/composition/, .github/, csproj)
baseline: main @ 41d94d5, then main @ 13a65caf6 (post PR #140 merge)
follows: docs/reports/2026-07-02-code-quality-and-architecture-review.md
---

# FS.GG.Templates — currency & architecture review (2026-07-15)

> **One-line verdict:** The architecture is sound and every finding from the 2026-07-02
> review is closed. The one live problem was **currency** — the provider pinned
> `FS.GG.UI.Template::0.8.0` while the platform (org feed + `FS-GG/.github` registry) had
> moved to the breaking framework major `0.10.0`. The bump PR existed but was stuck on a
> by-design human gate plus a transient release-timing CI failure. Both are now resolved:
> **PR #140 is merged, `main` pins `0.10.0`, and all coherence surfaces agree.**

## 1. Currency finding (the headline)

At review start this repo was the **lagging consumer** in a live cross-repo incoherence:

| Surface | Was pinned | Platform truth (2026-07-15) |
|---|---|---|
| `FS.GG.UI.Template` (provider `source:` / README / pin-tag) | **0.8.0** | **0.10.0** — published on the org feed + nuget.org; registry `fs-gg-ui-template` version/package-version/package-tag all `0.10.0` (framework **major**, merged 2026-07-14) |
| `minimumFsggSdd` | 0.6.0 | registry `minimum-fsgg-sdd` = 0.6.0 — coherent |
| `scaffold-provider contractVersion` | 1.1.0 | registry `scaffold-provider` = 1.1.0 — coherent |
| `FS.GG.Templates` package `<Version>` | 0.4.0 | published 0.4.0 — coherent |

Only the rendering pin was stale — but it is the single most load-bearing value in the
repo. Between 0.8.0 and 0.10.0 the framework shipped: `0.9.0` (additive interactive-audio
seam), a **phantom `0.9.1`** (tags cut, **never published** — zero packages on any feed; do
not pin), `0.9.2` (delivered 0.9.1's aborted payload + fixes), and the breaking `0.10.0`
that **retires** the inert `Persistence.interpret` and `TextInput.interpretEffect` members
(FS.GG.Rendering#642, epic #537; ApiCompat green on the removals).

### Why it was stuck: PR #140 red for two distinct reasons

`chore/bump-fs-gg-ui-template` (PR #140, opened by the automated bump path) was red with
3 failed / 32 passed:

1. **`provider PIN HISTORY has no unwritten entry`** — *by design*.
   `bump-rendering-pin.sh` inserts a `PIN HISTORY ENTRY REQUIRED` stub because a bumper
   cannot know a release's story; `stages/04-verify.sh` fails until a human writes it. This
   is the human-in-the-loop gate working correctly.
2. **`dotnet build of the composed product failed` (MSB1003) + `cannot install
   FS.GG.UI.Template::0.10.0 for the standalone lane`** — *not* by design. Both traced to a
   single root cause: the CI run fired **14 minutes** after 0.10.0 published (15:44Z →
   15:58Z) and could not yet resolve the template from the feed. Feed-indexing lag, not a
   real 0.10.0 break.

### Resolution

- Wrote the real **0.10.0 PIN HISTORY entry** (framework major; the two surface removals;
  Game 0.4.0 / Audio 0.2.0 axes **holding** — verified no newer coherent set exists on the
  feed; the 0.8.0→0.10.0 jump skipping additive 0.9.0, phantom 0.9.1, and 0.9.2). This
  cleared gate #1.
- Re-ran the composition check a full day after publish → **green**, confirming #2 was
  release-timing lag. The composed `game`-profile product builds clean against the breaking
  major.
- **PR #140 merged** (squash `13a65caf6`). `main` now pins `0.10.0`; provider ⇔ README ⇔
  registry ⇔ org feed all coherent.

### Propagation is already complete

`NewSddWorkspace` (the no-checkout scaffold tool) defaults to `gitRef = "main"` and fetches
`providers/rendering.providers.yml` over the network from `main`. Default (newest-set)
scaffolds therefore resolve `0.10.0` **as of the merge** — no NuGet release required. The
`FS.GG.Templates` NuGet package packs only `templates/**` (the governance overlay), which is
**byte-identical to v0.4.0**; a release would republish identical content. The only value a
new `fs-gg-templates/v0.5.0` tag would add is a `--pinned --ref`-able reproducible-scaffold
ref carrying 0.10.0 — a minor nicety, deliberately left to the team's release convention.

## 2. Prior review (2026-07-02) — all findings closed

| Prior finding | Status |
|---|---|
| **A1** package has no publish pipeline | ✅ `release.yml` exists — tag-driven (`fs-gg-templates/v*`), fail-closed tag⇔`<Version>` assert; 0.2.0/0.3.0/0.4.0 published |
| **A2** pin parsing duplicated 3× | ✅ extracted to `scripts/lib/read-pin.sh`, sourced by all call sites |
| **A3** 470-line `run.sh` | ✅ split into `tests/composition/stages/NN-*.sh` + `lib/` |
| **A4** governed commands never runnable | ✅ `tooling.yml` governs `<App>.slnx` (what fs-gg-ui emits), asserted in Stage 5 |
| **F1** `new-fullstack.sh` dead argument | ✅ script removed; network-fetch `NewSddWorkspace`/`NewSddFullstack` tools replace it |
| **F4** unpinned `@main` skill-assert | ✅ pinned to `SKILL_ASSERT_REF` SHA |
| **F7** injection / unvalidated version | ✅ `upstream-bump.yml` uses `env:`; `create-pull-request` SHA-pinned; `bump-rendering-pin.sh` has a version-format regex guard |

The core design (ADR-0002: compose at scaffold time, pin one version, vendor nothing)
remains correctly enforced by a composition suite that *asserts* the coherence surfaces
rather than trusting the bump tooling.

## 3. Minor observations (non-blocking)

- **`SKILL_ASSERT_REF` comment reads "as of 2026-07-02"** (`lib/skill-union.sh`) — the
  pinned SHA is a security control that Renovate is meant to move; worth confirming Renovate
  is actually bumping it (see Dependency Dashboard, issue #19).
- **The recurring root cause is process, not code.** The org registry itself records the
  `publish-before-flip` step-2 miss (a downstream repo must be manually re-pinned after an
  *upstream* release) as having recurred six times platform-wide. The 0.8.0→0.10.0 lag here
  is the same class. The automation opened the PR correctly; the residual gap is purely the
  human pin-history entry + a CI re-run whose timing raced feed propagation. Consider making
  the composition re-run trigger on feed availability rather than on push timing.
- **`docs/TestSpecs/Games/` (15 specs, ~80% of repo bytes)** remains unreferenced by the
  README Contents table or any test — same placement note as the prior review.

## 4. Net status

Templates are current with the platform. Nothing blocks work. The coherence machinery, the
publish pipeline, and the recent hardening are all in the state the 2026-07-02 review asked
for, and the one currency gap that had opened is closed.
