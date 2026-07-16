# shellcheck shell=bash
# Skill-union assertion (ADR-0014 P3.T3.2, issue #49) — split out of run.sh (review A3).
# Sourced by run.sh after lib/helpers.sh; uses the run-globals WORKDIR / REPO_ROOT and the
# ok/bad/skip helpers. The pinned FS-GG/.github ref that fetches the shared assertion lives
# here (see the Renovate custom manager in .github/renovate.json, repointed to this file).
#
# fetch_skill_assert — obtain the shared P3.G3.1 assertion (FS-GG/.github#111). One source of
# truth: fetched from FS-GG/.github at a PINNED COMMIT (SKILL_ASSERT_REF), falling back to a
# sibling clone at that same ref for offline dev. NOT vendored here — a pinned ref is not a
# vendored copy; vendoring is exactly the drift class ADR-0014 retires.
#
# Pinning (issue #56, review F4): the ref is a full 40-char commit SHA, never @main. This closes
# both holes the review named. (1) DETERMINISM — @main is a moving target, so the gate's own
# semantics could change under this repo with no commit here; a SHA freezes exactly which
# assertion runs, and moving it is a reviewable commit like any other pin. (2) INTEGRITY — a
# raw.githubusercontent fetch at a full commit SHA is content-addressed: GitHub cannot serve
# different bytes for that SHA, so the fetch carries its own cryptographic integrity check (that
# is the "sha256 alongside" the review floated, folded into the ref itself — a separate content
# hash would only go stale on every bump and defeat Renovate). Renovate moves the pin against the
# main head via the git-refs manager in .github/renovate.json; the fetch still FAILS-not-skips a
# lane when unreachable (see assert_skill_union). CI runbook: this couples the gate to
# raw.githubusercontent.com reachability at the pinned SHA — an outage FAILS the lane by design.
#
# MACHINE-MAINTAINED. Renovate rewrites exactly ONE token below — the 40-char SHA inside the
# quotes (the `currentDigest` capture of the git-refs manager in .github/renovate.json). It cannot
# rewrite anything else, so put NO prose on that line: a date or a "@main as of" note is a claim the
# bumper has no way to keep true, and it rots silently on the next bump. This line used to carry
# `# FS-GG/.github@main as of 2026-07-02`; the pin then sat still for two weeks because the manager
# never fired, which is the one circumstance that keeps such a comment accidentally honest. Same rule,
# and same reason, as the pin block in providers/rendering.providers.yml — read that banner for the
# incident that taught it. WHEN the pin moved is git's job, and ask it in a form that cannot rot either
# — `git log -S SKILL_ASSERT_REF -- tests/composition/lib/skill-union.sh` (a line number would go stale
# the moment this comment block changes length, as it did while being written).
# renovate: datasource=git-refs depName=FS-GG/.github packageName=https://github.com/FS-GG/.github
SKILL_ASSERT_REF="19500bc8e8ed9cae972b20563e15a056f9ad5809"
# The shared assertion is NOT A SINGLE FILE any more. FS-GG/.github#358 hoisted need_val into
# scripts/lib/args.sh, and #524 the root resolution into scripts/lib/roots.sh; skill-union-assert.sh
# sources both RELATIVE TO ITS OWN dirname. Fetching the script alone therefore dies on a missing
# lib/args.sh — which is exactly how the 2026-07-02 → 2026-07-16 pin bump first failed. So fetch the
# CLOSED SET into one directory reproducing the upstream `scripts/` layout (verified at the pinned
# ref: neither lib sources anything further, so the set terminates). If upstream adds a `source`,
# this list is what goes stale — the gate then FAILS loudly on the missing file, which is the
# intended direction: a gate that cannot obtain its assertion must never pass unverified.
SKILL_ASSERT_FILES=("skill-union-assert.sh" "lib/args.sh" "lib/roots.sh")
SKILL_ASSERT=""
fetch_skill_assert() {
  [[ -n "$SKILL_ASSERT" && -x "$SKILL_ASSERT" ]] && return 0
  local dir="$WORKDIR/skill-assert" f ok
  mkdir -p "$dir/lib" || return 1
  # (1) authoritative path — content-addressed fetch of every file at the pinned commit SHA.
  ok=1
  for f in "${SKILL_ASSERT_FILES[@]}"; do
    curl -fsSL --max-time 30 \
      "https://raw.githubusercontent.com/FS-GG/.github/$SKILL_ASSERT_REF/scripts/$f" \
      -o "$dir/$f" 2>/dev/null && [[ -s "$dir/$f" ]] || { ok=0; break; }
  done
  if [[ "$ok" -eq 1 ]]; then
    SKILL_ASSERT="$dir/skill-union-assert.sh"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  # (2) offline-dev fallback — a sibling FS-GG/.github clone. Prefer the files AT THE PINNED REF
  #     (git object → same determinism as the curl); only if that commit isn't present locally
  #     fall back to the working copy (a dev's trusted checkout), which may be off-pin.
  local sib="$REPO_ROOT/../.github"
  ok=1
  for f in "${SKILL_ASSERT_FILES[@]}"; do
    git -C "$sib" show "$SKILL_ASSERT_REF:scripts/$f" >"$dir/$f" 2>/dev/null && [[ -s "$dir/$f" ]] || { ok=0; break; }
  done
  if [[ "$ok" -eq 1 ]]; then
    SKILL_ASSERT="$dir/skill-union-assert.sh"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  ok=1
  for f in "${SKILL_ASSERT_FILES[@]}"; do
    [[ -f "$sib/scripts/$f" ]] && cp "$sib/scripts/$f" "$dir/$f" || { ok=0; break; }
  done
  if [[ "$ok" -eq 1 ]]; then
    SKILL_ASSERT="$dir/skill-union-assert.sh"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  SKILL_ASSERT=""; return 1
}

# assert_skill_union <product-dir> <lane> <co-tenant-glob>
# The T3.2 assertion, driven ENTIRELY by the one shared P3.G3.1 script — no inline
# reimplementation (issue #52; the former inline manifest arm is retired now that the shared
# script's --manifest adopted the shipped producer semantics per FS-GG/.github#120, PR #123):
#   (a) consumer arm  — `--product`: every union skill present in EVERY root ∧ byte-identical
#       across .claude/.codex/.agents (checks 1–2);
#   (b) manifest arm  — `--product --manifest <mf> --co-tenants <glob>` (check 3, producer
#       semantics = canonical SKILL.md-body sha256, superset-catalog set semantics): every
#       manifest-declared skill that is materialized matches its digest ([drifted] otherwise),
#       and every skill in the union is manifest-declared OR a --co-tenants co-tenant process
#       skill ([dangling] otherwise — the ADR-0014 F3 class). Declared-but-absent ids are
#       legitimate (the manifest is an upper-bound catalog) and the script reports their count.
# The manifest arm re-runs checks 1–2 (idempotent), so it is the single source of the verdict
# when a manifest is present; the standalone (a) call keeps the byte-identity signal explicit
# and still fires on hosts without jq (where the manifest arm SKIPs).
assert_skill_union() {
  local prod="$1" lane="$2" cotenant="$3"
  if ! fetch_skill_assert; then
    bad "$lane: cannot obtain the shared skill-union assertion (FS-GG/.github scripts/skill-union-assert.sh: raw.githubusercontent.com unreachable and no ../.github sibling clone) — the union cannot be verified, so this lane FAILS rather than passing unverified"
    return
  fi
  # (a) consumer arm — checks 1–2 (present-in-each-root ∧ byte-identical-across-roots).
  if "$SKILL_ASSERT" --product "$prod" >"$WORKDIR/skill-union.$lane.log" 2>&1; then
    ok "$lane: the three agent-skill roots are the byte-identical union (P3.G3.1: present-in-each-root ∧ byte-identical-across-roots)"
  else
    bad "$lane: agent-skill roots are NOT the byte-identical union (see below)"
    sed 's/^/  | /' "$WORKDIR/skill-union.$lane.log" 2>/dev/null
    return
  fi
  # (a-floor) minimum-cardinality floor (F6, issue #60): checks (a)/(b) verify that whatever the
  # union HOLDS is coherent, but an empty union is trivially byte-identical, so the shared script
  # only fails a TOTALLY empty union (its "no skills under any root" die) — not a lane that
  # materialized product skills yet NONE of its expected process co-tenants. Assert the lane's own
  # co-tenants exist: >= 1 dir matching the lane glob ($cotenant) under a (byte-identical) root —
  # exactly what minimumFsggSdd promises for the orchestrated lane (fs-gg-sdd-*), and symmetrically
  # for the standalone lane (speckit-*). Runs independent of jq so it fires even when (b) SKIPs.
  local cotenant_ct=0 r
  for r in .claude/skills .codex/skills .agents/skills; do
    if [[ -d "$prod/$r" ]]; then
      cotenant_ct=$(find "$prod/$r" -maxdepth 1 -type d -name "$cotenant" 2>/dev/null | wc -l | tr -d ' ')
      break
    fi
  done
  if [[ "$cotenant_ct" -ge 1 ]]; then
    ok "$lane: $cotenant_ct co-tenant skill(s) matching '$cotenant' present — the union is non-vacuous (minimum-cardinality floor)"
  else
    bad "$lane: NO co-tenant skill matching '$cotenant' under the skill roots — the union is byte-identical only because the lane materialized none of its own process skills (minimumFsggSdd floor, F6, issue #60)"
    return
  fi
  # (b) manifest arm — check 3 via the shared script's --manifest/--co-tenants (was inline; #52).
  local mf="$prod/.agents/skills/skill-manifest.json"
  if [[ ! -f "$mf" ]]; then
    bad "$lane: .agents/skills/skill-manifest.json missing — FS.GG.UI.Template >= 0.1.61-preview.1 ships the product skill-manifest in every lifecycle (ADR-0014 P2)"
    return
  fi
  ok "$lane: producer skill-manifest present (.agents/skills/skill-manifest.json)"
  if ! command -v jq >/dev/null 2>&1; then
    skip "$lane: jq not on PATH — manifest digest/dangling cross-check not exercised here (the shared --manifest arm requires jq; CI has it, and cross-root byte-identity above is still asserted)"
    return
  fi
  if "$SKILL_ASSERT" --product "$prod" --manifest "$mf" --co-tenants "$cotenant" \
       >"$WORKDIR/skill-union-manifest.$lane.log" 2>&1; then
    ok "$lane: manifest cross-check green — every materialized manifest-declared skill matches its canonical-body sha256, and the union is manifest-declared ∪ lane co-tenants ($cotenant)"
    # Surface the script's own count line (present/byte-identical/manifest-matched/co-tenant/declared-absent).
    grep -E '^skill-union-assert: [0-9]+ skill' "$WORKDIR/skill-union-manifest.$lane.log" 2>/dev/null | sed 's/^/  | /'
  else
    bad "$lane: manifest cross-check FAILED — a [drifted] digest mismatch or a [dangling] undeclared skill (ADR-0014 F3); see below"
    sed 's/^/  | /' "$WORKDIR/skill-union-manifest.$lane.log" 2>/dev/null
  fi
}
