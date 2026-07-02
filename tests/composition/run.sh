#!/usr/bin/env bash
# End-to-end composition test for FS.GG.Templates.
#
# Runs the standard packaging-repo checks prescribed by the architecture report
# (docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md §5.2):
#
#     pack → install → instantiate → (restore/build) → verify pins/links
#
# What this repo *owns* is verified end-to-end and unconditionally:
#   - the FS.GG.Templates package packs,
#   - it installs as a `dotnet new` template source,
#   - the populated `fs-gg-governance` overlay instantiates,
#   - parameter substitutions land and the governance gate set is populated
#     (not the inert `checks: []` / `commands: []` it used to ship), and
#   - the `rendering` provider pin is internally coherent (version + lifecycle/profile).
#
# The full rendering product (scaffold → restore/build of the live FS.GG.UI app) needs
# the `fsgg-sdd` CLI and a reachable FS.GG.UI.Template feed. That stage is GATED: it runs
# only when those are available (or FSGG_COMPOSITION_FULL=1 forces it) and otherwise SKIPS
# with an explicit reason — it never silently passes. When it does run, it also asserts the
# overlay's governed commands are RUNNABLE against the composed product (A4, issue #59): the
# governed `<App>.slnx` and `build.fsx` actually exist at the product root, so the overlay
# governs real commands, not phantoms whose first check-run in a scaffolded product would fail.
#
# Skill-union assertion (ADR-0014 P3.T3.2 — FS-GG/FS.GG.Templates#49): in BOTH lanes —
# orchestrated (fsgg-sdd scaffold, Stage 5) and standalone (direct `dotnet new fs-gg-ui`
# spec-kit, Stage 5b) — the three agent-skill roots (.claude/.codex/.agents skills) must be
# the BYTE-IDENTICAL UNION of process + product skills. This is asserted end-to-end by the ONE
# reusable P3.G3.1 script (FS-GG/.github scripts/skill-union-assert.sh): cross-root identity via
# `--product` (checks 1–2), and the producer manifest (.agents/skills/skill-manifest.json,
# canonical SKILL.md-body sha256) via `--manifest --co-tenants` (check 3, producer semantics) —
# every declared+present skill matches its digest, and every skill in the union is either
# manifest-declared or an expected lane co-tenant (fs-gg-sdd-* under sdd, speckit-* under
# spec-kit) — anything else is a dangling skill and FAILS. The manifest cross-check is the shared
# script's own `--manifest` arm (issue #52): the earlier inline bash reimplementation was retired
# once that arm adopted the shipped producer semantics (FS-GG/.github#120). This replaced the
# former "grep scaffold.providerWroteSddTree and SKIP" lockstep (#47): a provider writing outside
# .agents/skills/ is now a hard failure.
#
# A further GATED stage exercises the SDD→Governance enforcement loop end-to-end through
# the composed product — the seam Templates specifically owns (no single upstream repo
# covers the composition):
#     scaffold → fsgg-sdd ship (emit governance-handoff.json) → fsgg-governance route
#     (consume it → produce a verdict) → assert the populated overlay actually ENFORCES.
# It needs both the `fsgg-sdd` and `fsgg-governance` CLIs and the composed product the
# build stage scaffolds; absent either it SKIPS with a reason — never green-by-omission.
#
# Hermetic (issue #55, review F3): every `dotnet new` — this script's own AND those in the
# child processes it spawns (scripts/new-fullstack.sh and the `fsgg-sdd scaffold` it drives) —
# runs against a per-run ISOLATED template hive. We relocate the whole template-engine hive by
# exporting DOTNET_CLI_HOME under the temp workdir: it moves ~/.templateengine wholesale and is
# inherited by every child process, so the test never mutates the developer's global hive and
# parallel runs never collide. Disposing of WORKDIR disposes of every installed template — so no
# uninstall bookkeeping in cleanup(), and no stale versions can accumulate to arm the F2 fallback.
#
# Layout (review A3 — the gate was split out of a single ~600-line file):
#   run.sh              this orchestrator — sets the run-globals, sources the libs + stages in
#                       order (they share this shell, so PASS/FAIL and stage vars persist), summarizes.
#   lib/helpers.sh      PASS/FAIL counters + ok/bad/skip/step/assert_*/installed_template_version.
#   lib/skill-union.sh  the pinned FS-GG/.github ref + fetch_skill_assert + assert_skill_union.
#   fixtures/*.json     the contract-v1 governance-handoff documents Stage 6b enforces.
#   stages/NN-*.sh      one file per pipeline stage (sourced, not executed): 01 pack · 02 install ·
#                       03 instantiate · 04 verify · 05 build · 05b standalone · 06 govern.
#
# Usage:   tests/composition/run.sh
# Env:     FSGG_COMPOSITION_FULL=1   require (do not skip) the full scaffold+build stage
#          KEEP_WORKDIR=1            do not delete the temp workdir on exit
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSITION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="$COMPOSITION_DIR/fixtures"
# shellcheck source=scripts/lib/read-pin.sh
. "$REPO_ROOT/scripts/lib/read-pin.sh"        # read_pin <yml> — the one shared FS.GG.UI.Template pin parser (A2)
# shellcheck source=tests/composition/lib/helpers.sh
. "$COMPOSITION_DIR/lib/helpers.sh"           # PASS/FAIL + ok/bad/skip/step/assert_* (A3)
# shellcheck source=tests/composition/lib/skill-union.sh
. "$COMPOSITION_DIR/lib/skill-union.sh"       # SKILL_ASSERT_REF + fetch_skill_assert + assert_skill_union (A3)

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-composition.XXXXXX")"
ARTIFACTS="$WORKDIR/artifacts"
APP="$WORKDIR/app"
mkdir -p "$ARTIFACTS"

# Isolated, per-run template hive (F3) — see the header note. DOTNET_CLI_HOME relocates
# ~/.templateengine under WORKDIR and is inherited by child processes; the *_OPTOUT/NOLOGO/
# SKIP_FIRST_TIME vars keep a fresh home from spewing the .NET first-run banner into the logs.
export DOTNET_CLI_HOME="$WORKDIR/dotnet-home"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
mkdir -p "$DOTNET_CLI_HOME"

cleanup() {
  # No global-hive uninstall needed (F3): every `dotnet new` in this run — and in the child
  # processes it spawns — uses the isolated hive under DOTNET_CLI_HOME (=$WORKDIR/dotnet-home),
  # so removing WORKDIR removes every installed template. The developer's real ~/.templateengine
  # is never touched, and no per-run FS.GG.UI.Template::<pin> / fs-gg-governance copies leak.
  if [[ "${KEEP_WORKDIR:-}" == "1" ]]; then
    printf '\n(workdir kept at %s; isolated template hive at %s)\n' "$WORKDIR" "$DOTNET_CLI_HOME"
  else
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT

command -v dotnet >/dev/null || { echo "FATAL: dotnet not on PATH"; exit 2; }

# Stages run in order in THIS shell (sourced, not executed): each sees the globals the
# previous set (NUPKG, PIN_VER, FULL, FULL_OK, …) and an `exit` in a stage ends the run.
. "$COMPOSITION_DIR/stages/01-pack.sh"
. "$COMPOSITION_DIR/stages/02-install.sh"
. "$COMPOSITION_DIR/stages/03-instantiate.sh"
. "$COMPOSITION_DIR/stages/04-verify.sh"
. "$COMPOSITION_DIR/stages/05-build.sh"
. "$COMPOSITION_DIR/stages/05b-standalone.sh"
. "$COMPOSITION_DIR/stages/06-govern.sh"

# ── Summary ──────────────────────────────────────────────────────────────────
printf '\n\033[1m== summary ==\033[0m  \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
