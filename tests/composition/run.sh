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
# spec-kit, Stage 5b) — the two agent-skill roots (.claude/.agents skills) must be
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
# child processes it spawns (Stage 5's inlined compose_full and the `fsgg-sdd scaffold` it drives) —
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
#   lib/skill-union.sh  the pinned FS-GG/.github ref + its staleness alarm (#315) +
#                       fetch_skill_assert + assert_skill_union.
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
. "$COMPOSITION_DIR/lib/skill-union.sh"       # SKILL_ASSERT_REF + the #315 staleness alarm + fetch_skill_assert + assert_skill_union (A3)

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
# `git` joined `dotnet` as a hard prerequisite when the #315 staleness alarm landed: resolving the
# pinned commit's date uses git in BOTH arms (a sibling clone, or a --depth 1 fetch of that one
# commit). Preflighted here so a git-less host says so once, instead of surfacing as an
# unresolvable-ref RED whose message sends the reader looking at network reachability.
command -v git >/dev/null || { echo "FATAL: git not on PATH (needed to resolve SKILL_ASSERT_REF's commit date — #315)"; exit 2; }

# ── SKILL_ASSERT_REF staleness alarm (#315) ──────────────────────────────────────────────────
# Runs HERE — once, unconditionally, before any stage — and deliberately not from
# assert_skill_union. It is a fact about the PIN, not about a scaffolded product, and
# assert_skill_union is reached only from two GATED stages (05 needs fsgg-sdd plus a successful
# scaffold and build; 05b needs the pinned template to install and instantiate). Hanging the alarm
# off those would mean that on any host where both lanes SKIP — the ordinary local dev run — the
# pin's freshness is never evaluated and the run still reports green. That is the very failure
# #315 exists to close, rebuilt one level up. Running it at the top also means the verdict is the
# FIRST thing in the log when the gate reds for this reason, and that the network probe happens
# once per run rather than once per lane.
step "pin — the shared skill-union assertion is not frozen (#315)"
assert_skill_assert_ref_alarm_can_fire "pin"
assert_skill_assert_ref_fresh "pin"

# ── THIS REPO's runtime skill-root set (FS-GG/.github#1676, ADR-0067 §8/§9 phase 4) ──────────
# Here for the same reason the alarm above is: it is a fact about THIS REPOSITORY, not about a
# scaffolded product, so hanging it off a gated stage would leave it unevaluated on exactly the
# ordinary local run where both lanes skip. Offline — it reads this repo's own receiver project
# and its own working tree, and costs no network.
#
# THIS USED TO BE `lib/skill-view-roots.sh`, 10,798 BYTES OF THIS REPO'S OWN (FS-GG/.github#1710).
# Seven receivers retired their second committed skill root, ADR-0067 §8 obliged each to replace the
# loud failure it removed, and seven of them hand-wrote the same alarm on the same day — 23,050 to
# 10,798 bytes, a 55% spread over one invariant. The delivery seam already existed:
# `scripts/skill-view` is a kit-delivered file (a `kit:` row in the hub's registry/repos.yml), so the
# assertion now lives THERE and this repo calls it. One implementation, one place to fix, and the
# can-fire demonstration ships with it.
#
# ADOPTING IT FIXED THIS REPO'S OWN DEFECT BY CONSTRUCTION rather than by repair
# (FS.GG.Templates#324). The old file graded the DECLARATION well and had **no view-resolution lane
# at all** — a dangling `.agents/skills`, a plain text file where the directory belongs, and a
# partial view were ALL unobserved by the required `composition` check, which is exactly the silent
# class ADR-0067 §8 exists to make loud. Repairing a file that was about to be deleted would have
# been waste; the kit's implementation covers all three, and grades a partial view PER SKILL rather
# than by the directory COUNT every hand-copy used.
#
# WHY AN ABSENT VIEW ROOT IS GREEN HERE, MEASURED ON THIS REPO RATHER THAN INHERITED. `composition`
# runs on a bare `actions/checkout` that never materializes and never generates, so an unpopulated
# `.agents/skills` is the NORMAL state of this job and reddening it would fire on every green build.
# What covers absence instead is the MATERIALIZE path, and on this repo that is NOT a required
# context — measured 2026-07-28:
#
#   * `gh api repos/FS-GG/FS.GG.Templates/branches/main/protection`
#       contexts: ["kit / coordination-kit", "composition"]     enforce_admins: true
#   * NEITHER runs `-t:FsggKitMaterialize`. `kit / coordination-kit` runs `coordination-sync --check
#     --against-pin`, which grades `<FsggKitSkillRoots>` bytes ONLY (.github#1584) and is green on a
#     tree with the view root gone. The only job that materializes is `kit-materialize.yml`, which is
#     renovate-gated and NOT required.
#   * So absence is caught on every kit bump PR and every local `dotnet build … -t:FsggKitMaterialize`,
#     where `FsggKitCheckSkillView` reds — but NOT on an ordinary PR.
#
# That is FS.GG.Audio's posture, not FS.GG.Game's, and the difference is why #324 said to measure it
# here rather than assume Game's answer transfers. It does not.
step "roots — this repo's runtime skill-root set and its generated view (.github#1710)"

# The demonstration that every lane CAN FIRE ships inside the tool, so this repo runs the same one
# the hub does rather than a copy of it. It is offline and takes about a second.
if bash "$REPO_ROOT/scripts/skill-view" selftest >"$WORKDIR/skill-view-selftest.log" 2>&1; then
  ok "roots: the skill-root alarm demonstrates every lane can fire ($(grep -oE '[0-9]+ passed' "$WORKDIR/skill-view-selftest.log" | head -1))"
else
  bad "roots: scripts/skill-view selftest FAILED — a lane of the alarm cannot fire, or fires with the wrong class. A gate that cannot fire is not a gate (.github#1611 category D). See $WORKDIR/skill-view-selftest.log"
  sed 's/^/      | /' "$WORKDIR/skill-view-selftest.log"
fi

if bash "$REPO_ROOT/scripts/skill-view" check \
     --tree "$REPO_ROOT" \
     --source "$REPO_ROOT/.claude/skills" \
     --receiver-proj "$REPO_ROOT/.config/kit/FS.GG.Kit.receiver.proj" \
     --absent-ok "the required 'composition' job runs on a bare checkout that never materializes, so an ungenerated view is its normal state; absence is caught on the materialize path instead — measured above, and NOT on any required context here" \
     >"$WORKDIR/skill-view-check.log" 2>&1; then
  ok "roots: the runtime skill-root declaration and the generated view both hold"
  sed -n 's/^  /      /p' "$WORKDIR/skill-view-check.log"
else
  bad "roots: scripts/skill-view check FAILED — this repo's runtime skill-root contract is broken. See the classes named below (ADR-0067 §8)."
  sed 's/^/      | /' "$WORKDIR/skill-view-check.log"
fi

# Stages run in order in THIS shell (sourced, not executed): each sees the globals the
# previous set (NUPKG, PIN_VER, FULL, FULL_OK, …) and an `exit` in a stage ends the run.
. "$COMPOSITION_DIR/stages/01-pack.sh"
. "$COMPOSITION_DIR/stages/02-install.sh"
. "$COMPOSITION_DIR/stages/03-instantiate.sh"
. "$COMPOSITION_DIR/stages/04-verify.sh"
. "$COMPOSITION_DIR/stages/05-build.sh"
. "$COMPOSITION_DIR/stages/05b-standalone.sh"
. "$COMPOSITION_DIR/stages/06-govern.sh"

# The neutral web workspace is a first-class packaged template. Its isolated lane performs the
# complete generated root lifecycle (including observed TRX/JUnit evidence), so a green required
# composition check cannot merely prove that the descriptor happens to pack.
step "web — clean generated workspace lifecycle"
if bash "$COMPOSITION_DIR/web/run.sh"; then
  ok "web template clean lifecycle passes"
else
  bad "web template clean lifecycle failed"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
printf '\n\033[1m== summary ==\033[0m  \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
