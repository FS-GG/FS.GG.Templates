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
# PIN-VS-FLOAT, RE-DECIDED AT #309 RATHER THAN INHERITED. The pin froze twice — .github#843
# (2026-07-02 → 07-16) and again 07-16 → 07-27 — and each freeze ran a KNOWN-WRONG assertion under a
# green tick. That is the strongest argument anyone will ever make for `@main`, and it is still not
# enough. Weigh the two failure modes by what they do to the CLAIM this gate publishes:
#   - FLOATING (@main) — fixes arrive free; in exchange every upstream commit can change this repo's
#     release gate with no commit here. A red then has no bisectable cause in this history, a green
#     yesterday and a red today are indistinguishable from a flake, and the fetch loses its integrity
#     check (a branch ref is not content-addressed). The org's receiver callers do float @main, but
#     they reach the assertion through actions/checkout inside a REUSABLE workflow the hub versions
#     and self-tests; this repo curls a raw file from a test harness. Same word, different contract.
#   - PINNING — staleness. Bounded, visible in `git log`, and repaired by a one-token commit.
# So: STILL PINNED. What makes the staleness acceptable is that it is no longer SILENT — which was
# the actual defect, not the age. Two things notice now:
#   1. assert_summary_reports_its_denominators (below) FAILS the lane if the assertion that ran
#      printed a pre-#1506 summary. The exact regression #309 is about — a pin serving an assertion
#      whose `byte-identical=` covers a population it never examined — is now a hard red here, in
#      this repo's own gate, offline, with no dependency on anyone noticing upstream landed something.
#   2. Renovate still opens the bump PR (it does fire — the tests/ ignorePaths hole is fixed). What it
#      cannot do is merge one, and #310 carries the measured reason its PRs pile up unmerged.
# A pin whose staleness is loud is a bounded cost. A float whose semantics move silently is not.
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
SKILL_ASSERT_REF="fe8261b96a0e9ae0a4b739f4779563988abfc134"
# FETCH THE BUNDLE, NOT A HAND-WRITTEN DEPENDENCY LIST (#309). This used to be
#   SKILL_ASSERT_FILES=("skill-union-assert.sh" "lib/args.sh" "lib/roots.sh")
# fetched out of upstream `scripts/` — a closed set that was correct at the pinned ref and correct
# only until the next `source`. It had already gone stale once: FS-GG/.github#358 hoisted need_val
# into scripts/lib/args.sh and #524 the root resolution into scripts/lib/roots.sh, and the
# 2026-07-02 → 07-16 bump died on a missing lib/args.sh. Upstream then BUILT THE FIX FOR THIS EXACT
# CONSUMER: .github#843 added scripts/generate-skill-union-bundle, which inlines the libs into
# dist/skill-union-assert.sh, and the `skill-union-bundle` CI job reds on any drift between them.
# Its banner names this repo as the one standalone consumer the bundle exists to serve. We were
# still hand-enumerating instead of using it.
#
# Enumerating another repo's file graph by name is a drift class, not a one-off bug, and the hub
# spent today proving it: .github#1510 killed every receiver caller AT LOAD for this shape, #1515
# repeated it, and #1522 landed a gate (check-sparse-checkout-closure.py) against it — a gate that
# reads only the hub repo and is structurally blind to this file. So the fix here cannot be a
# better list; it has to be NO LIST. One self-contained file, content-addressed at the pinned SHA:
# there is nothing left to enumerate, so nothing left to go stale. The next `source` upstream adds
# is inlined by the generator instead of breaking this gate two weeks later.
#
# (Verified at the ref below rather than assumed: dist/skill-union-assert.sh contains no `source`
# or `.` line, and running it against both composition lanes' products reproduces the scripts/
# arm's verdict and summary exactly.)
SKILL_ASSERT_PATH="dist/skill-union-assert.sh"
SKILL_ASSERT=""
fetch_skill_assert() {
  [[ -n "$SKILL_ASSERT" && -x "$SKILL_ASSERT" ]] && return 0
  local dir="$WORKDIR/skill-assert" dst
  mkdir -p "$dir" || return 1
  dst="$dir/skill-union-assert.sh"
  # (1) authoritative path — content-addressed fetch of the ONE self-contained bundle at the
  #     pinned commit SHA. No sibling files, so no set to keep closed.
  if curl -fsSL --max-time 30 \
       "https://raw.githubusercontent.com/FS-GG/.github/$SKILL_ASSERT_REF/$SKILL_ASSERT_PATH" \
       -o "$dst" 2>/dev/null && [[ -s "$dst" ]]; then
    SKILL_ASSERT="$dst"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  # (2) offline-dev fallback — a sibling FS-GG/.github clone. Prefer the blob AT THE PINNED REF
  #     (git object → same determinism as the curl); only if that commit isn't present locally
  #     fall back to the working copy (a dev's trusted checkout), which may be off-pin.
  local sib="$REPO_ROOT/../.github"
  if git -C "$sib" show "$SKILL_ASSERT_REF:$SKILL_ASSERT_PATH" >"$dst" 2>/dev/null && [[ -s "$dst" ]]; then
    SKILL_ASSERT="$dst"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  if [[ -f "$sib/$SKILL_ASSERT_PATH" ]] && cp "$sib/$SKILL_ASSERT_PATH" "$dst" && [[ -s "$dst" ]]; then
    SKILL_ASSERT="$dst"; chmod +x "$SKILL_ASSERT"; return 0
  fi
  rm -f "$dst"
  SKILL_ASSERT=""; return 1
}

# assert_summary_reports_its_denominators <lane> <summary-line>
# THE STALENESS FLOOR (#309). SKILL_ASSERT_REF is a pin, so this gate can go on running an old
# assertion indefinitely and stay green — that is the pin's accepted cost, and it is only
# acceptable while it is LOUD. This is what makes it loud, for the one property this lane's verdict
# actually rests on.
#
# Before .github#1506 the shared script evaluated "present in every root" as check 1 and byte
# identity as check 2, and check 1 SHORT-CIRCUITED: a [partitioned] skill was never byte-compared,
# and the summary's `byte-identical=<n>` was computed only over the ids that reached the
# comparison. On a real tree that printed `present=4 byte-identical=4` beside 46 partitioned ids,
# 30 of which actually differed. Three issue bodies were written on the premise that line invited.
# The line was never false; it just had no denominator, and readers supply the generous one.
#
# So do not check the pin's AGE — check the assertion's SHAPE. Every count in a #1506-or-later
# summary carries the population it was taken over, and a bare `byte-identical=<n>` is exactly the
# fingerprint of a script that may not have compared what this lane is about to claim it did.
# Offline, deterministic, no GitHub API, no jq, no dependency on a human noticing upstream landed
# something: if the pin ever regresses below the semantics this lane's `ok` message asserts, the
# lane goes RED here instead of publishing a coverage claim it never computed.
#
# It FAILS CLOSED on an unrecognised shape, and that is the intended direction even though it means
# a future upstream rename reds this gate before anyone has done anything wrong. The alternative —
# shrug and pass on a summary you cannot parse — is the precise behaviour #1506 exists to retire.
# The failure message says what to do about it; do that, do not relax the predicate.
assert_summary_reports_its_denominators() {
  local lane="$1" summary="$2"
  if [[ "$summary" =~ in-every-root=[0-9]+/[0-9]+ ]] \
     && [[ "$summary" =~ partitioned=[0-9]+ ]] \
     && [[ "$summary" =~ byte-comparable=[0-9]+ ]] \
     && [[ "$summary" =~ byte-compared=[0-9]+ ]] \
     && [[ "$summary" =~ byte-identical=[0-9]+/[0-9]+ ]] \
     && [[ "$summary" =~ byte-differing=[0-9]+ ]] \
     && [[ "$summary" =~ single-root=[0-9]+ ]]; then
    ok "$lane: every count in the assertion's summary carries its population (.github#1506 shape) — the byte-identity verdict above states the denominator it was taken over"
  elif [[ -z "$summary" ]]; then
    bad "$lane: the assertion at SKILL_ASSERT_REF printed NO 'skill-union-assert: <n> skill(s)' summary line — its verdict cannot be read, so this lane has no coverage evidence to report (#309)"
  else
    bad "$lane: the assertion at SKILL_ASSERT_REF printed a PRE-#1506 summary — '$summary' — whose 'byte-identical=' has no denominator and can therefore cover ids it never compared (a [partitioned] skill short-circuited out of the byte comparison). This lane's byte-coherence claim is unsupported at that ref. Move SKILL_ASSERT_REF to a FS-GG/.github@main commit at or after 22461b4 (.github#1506); do NOT relax this check (#309)"
  fi
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
  # STALENESS FLOOR (#309) — deliberately HERE, on arm (a), and not beside the summary the manifest
  # arm prints below. The manifest arm sits behind a `command -v jq` SKIP, so on a jq-less host the
  # lane would take the byte-identity `ok` it just emitted with NOTHING having checked that the
  # assertion which produced that verdict is even capable of computing it. Arm (a) always runs, so
  # this always runs, and it guards the exact claim on the line above it.
  assert_summary_reports_its_denominators "$lane" \
    "$(grep -E '^skill-union-assert: [0-9]+ skill' "$WORKDIR/skill-union.$lane.log" 2>/dev/null | head -1)"
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
    # Surface the script's own count line (the richest one — it carries the manifest fields too).
    # The grep pattern is UNCHANGED and still matches at the new pin: #1506 renamed the fields
    # AFTER the em dash, not the `skill-union-assert: <n> skill(s)` prefix this anchors on.
    grep -E '^skill-union-assert: [0-9]+ skill' "$WORKDIR/skill-union-manifest.$lane.log" 2>/dev/null | sed 's/^/  | /'
  else
    bad "$lane: manifest cross-check FAILED — a [drifted] digest mismatch or a [dangling] undeclared skill (ADR-0014 F3); see below"
    sed 's/^/  | /' "$WORKDIR/skill-union-manifest.$lane.log" 2>/dev/null
  fi
}
