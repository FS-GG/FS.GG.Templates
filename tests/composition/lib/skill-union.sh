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
# the actual defect, not the age. Three things notice now, and the third had to be BUILT (#315):
#   1. assert_summary_reports_its_denominators (below) FAILS the lane if the assertion that ran
#      printed a pre-#1506 summary. The exact regression #309 is about — a pin serving an assertion
#      whose `byte-identical=` covers a population it never examined — is now a hard red here, in
#      this repo's own gate, offline, with no dependency on anyone noticing upstream landed something.
#      It is a SEMANTIC backstop, not a staleness alarm: it is silent on a pin that simply stops
#      moving, which is this file's actual observed failure mode three times over.
#   2. assert_skill_assert_ref_fresh (below, #315) FAILS the lane when the pinned commit is older
#      than SKILL_ASSERT_MAX_AGE_DAYS, and when its date cannot be resolved at all. This is the one
#      that closes the detection gap the other two leave open; its threshold rationale is next to
#      the pin, below.
#   3. Renovate still opens the bump PR (it does fire — the tests/ ignorePaths hole is fixed). This
#      is NOT a backstop and must not be counted as one: automerge is disabled org-wide, so nothing
#      merges the PR and nothing escalates when nobody does; the Dependency Dashboard (#19) lists it
#      and no schedule reads the dashboard. #310 measured that, and #315 is the answer to its third
#      acceptance criterion — "if automerge stays off, name the thing that notices." Before #315 the
#      honest answer was NOTHING, and all three freezes were found by a human weeks later.
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
# ── THE STALENESS THRESHOLD, AND WHY IT IS 14 DAYS (#315) ────────────────────────────────────
# This sits here, immediately under the pin, because a threshold recorded anywhere else is a fact
# in a place that cannot execute it — the drift class .github#1611 catalogued as category C. The
# same reason keeps it OFF the pin line itself: the banner above is right that Renovate rewrites
# exactly one token there and any prose beside it rots on the next bump. A `SKILL_ASSERT_MAX_AGE_DAYS`
# on its own line is not something the bumper touches, so it cannot rot that way.
#
# WHAT IT MEASURES: the age of the PINNED COMMIT, not the age of this line. The two differ by the
# lag between upstream committing and the bump landing here, and the pinned commit's date is the
# one that answers the question the lane actually publishes — "how old is the assertion that just
# ran?" It is also the only one of the two that survives a shallow CI checkout, where this repo's
# own history is one commit deep and `git log -S SKILL_ASSERT_REF` (which the banner above rightly
# recommends to a HUMAN, at a full clone) can see nothing at all.
#
# WHY 14: it is chosen to sit above the noise and below both observed freezes, and it is
# deliberately generous because the first job of an alarm is to be quiet enough that nobody learns
# to ignore it. Upstream FS-GG/.github moves many commits a day and the git-refs manager in
# .github/renovate.json tracks its main head, so a HEALTHY pin here is hours old — the margin
# between healthy and alarming is ~50x, not 2x, which is what makes a generous threshold cheap.
# Freeze 1 ran 14 days (ab6d9289, .github#843 — `**/tests/**` in ignorePaths, the manager never
# fired); freeze 2 ran 11 days (19500bc8→a476af7, #312 + .github#1533 — kit-materialize pushing
# onto the Renovate branch). At 14 days both would have been caught inside their own window with
# room to spare, and neither needed a human to trip over it.
#
# TIGHTEN IT ONCE IT HAS PROVEN QUIET — that is the intended direction, it is one token below, and
# the reason it may be tightened is written here so the next person does not have to re-derive it.
# It is a CONSTANT, not `${SKILL_ASSERT_MAX_AGE_DAYS:-14}`: a threshold that can be raised from the
# environment is a threshold a red run can be re-run around, and this alarm exists precisely because
# the last three failures were survivable-looking.
SKILL_ASSERT_MAX_AGE_DAYS=14
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

# ── THE STALENESS ALARM (#315) ───────────────────────────────────────────────────────────────
# Split into three pieces on purpose: a RESOLVER that talks to the world, a PURE PREDICATE that
# does not, and an ASSERTION that joins them. That split is not tidiness — it is what lets the
# assertion DEMONSTRATE its own three outcomes offline and deterministically on every run
# (assert_skill_assert_ref_alarm_can_fire, below) instead of asserting them in a comment. #315's
# third acceptance criterion asks for exactly that, and .github#1611's category D is the reason:
# a gate that never fires and a gate that always passes are indistinguishable from outside.

# skill_assert_ref_committed_at <ref> <allow-network>
# Echo the pinned commit's COMMITTER date as epoch seconds; echo nothing and return non-zero when
# it cannot be resolved. A commit's date is part of the commit OBJECT, so both sources below are
# equally authoritative and equally content-addressed at the SHA. That is why this is LOCAL-FIRST
# where fetch_skill_assert above is network-first: fetch_skill_assert reaches for the network to
# GET the integrity property, and here the SHA already carries it, so a source that is free and
# offline has no reason to be the fallback.
#   (1) a sibling FS-GG/.github clone at $REPO_ROOT/../.github, at the pinned ref — the same
#       offline-dev seam fetch_skill_assert already uses. Costs nothing, cannot be rate-limited,
#       and is the common path on a developer machine (#315 AC2).
#   (2) a --depth 1 fetch of THAT ONE COMMIT from github.com. This is deliberately NOT
#       api.github.com/repos/.../commits/<sha>, which is the obvious implementation and the wrong
#       one: unauthenticated it is 60 requests/hour per IP, `composition` is a REQUIRED check here
#       under enforce_admins, and a lane that reds because somebody else spent the shared API
#       budget is a worse outage than the staleness it watches for — this workflow's own `Scope`
#       step carries that warning in prose. The git transport has no such budget, it is the same
#       host and the same failure domain as the raw.githubusercontent fetch this gate already
#       depends on, and it fails FAST and loud on a ref that is not there ("upload-pack: not our
#       ref", exit 128) rather than hanging.
# Memoized by the caller (SKILL_ASSERT_REF_AT): two lanes ask per run and the answer cannot move
# within a run.
SKILL_ASSERT_REF_AT=""
# The network arm's transport, factored out only so the `timeout` guard is an if/else rather than
# an array splice: `git fetch` has no timeout of its own, and a hung transport on a REQUIRED check
# is the failure mode this alarm must not introduce. `timeout` is coreutils and effectively always
# present; when it is not, the fetch still runs — an alarm that refuses to look because a
# convenience binary is missing would be worse than one that can hang on a dead socket.
skill_assert_ref_fetch() {
  local scratch="$1" ref="$2" url="https://github.com/FS-GG/.github.git"
  if command -v timeout >/dev/null 2>&1; then
    timeout 30 git -C "$scratch" fetch -q --depth 1 "$url" "$ref" >/dev/null 2>&1
  else
    git -C "$scratch" fetch -q --depth 1 "$url" "$ref" >/dev/null 2>&1
  fi
}
skill_assert_ref_committed_at() {
  local ref="$1" allow_net="${2:-1}" at="" scratch
  # (1) sibling clone at the pinned ref. `^{commit}` so a ref that resolves to a non-commit is a
  #     resolution FAILURE rather than a date read off something that is not the pinned commit.
  at="$(git -C "$REPO_ROOT/../.github" show -s --format=%ct "$ref^{commit}" 2>/dev/null)" || at=""
  # (2) content-addressed shallow fetch of the single commit.
  if [[ ! "$at" =~ ^[0-9]+$ && "$allow_net" == "1" ]]; then
    scratch="$WORKDIR/skill-assert-ref"
    if [[ -d "$scratch" ]] || git init -q "$scratch" >/dev/null 2>&1; then
      if skill_assert_ref_fetch "$scratch" "$ref"; then
        at="$(git -C "$scratch" show -s --format=%ct 'FETCH_HEAD^{commit}' 2>/dev/null)" || at=""
      fi
    fi
  fi
  [[ "$at" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$at"
}

# skill_assert_ref_verdict <committed-epoch> <now-epoch> <max-age-days>
# PURE: no clock, no network, no git, no globals, no output but the age. Echoes the age in whole
# days whenever it can compute one. Returns 0 FRESH · 1 STALE · 2 UNRESOLVABLE.
#
# 2 is the FAIL-CLOSED code epic .github#266 requires, and it covers three inputs, not one: a date
# that is ABSENT (both sources failed), one that is NON-NUMERIC (a source answered with something
# that is not a date), and one in the FUTURE (clock skew, or a committer date that was written
# rather than observed — a commit's committer date is attacker-controlled metadata, and a pin
# dated next month must not be able to buy itself permanent freshness). "Could not look" is never
# "looked, and fine"; that exact trap is what made all three freezes invisible under a green tick.
#
# The comparison is STRICTLY GREATER: a pin exactly at the threshold is still fresh. The boundary
# is pinned in the self-demonstration below so it cannot drift by accident.
skill_assert_ref_verdict() {
  local at="$1" now="$2" max="$3" age
  [[ "$at" =~ ^[0-9]+$ && "$now" =~ ^[0-9]+$ && "$max" =~ ^[0-9]+$ ]] || return 2
  age=$(( (now - at) / 86400 ))
  (( age < 0 )) && return 2
  printf '%s\n' "$age"
  (( age > max )) && return 1
  return 0
}

# assert_skill_assert_ref_alarm_can_fire <lane>
# #315 AC3, "demonstrated, not asserted": drive the predicate through every outcome it can reach,
# including the unresolvable one, on every real run. Entirely offline and arithmetic — a fixed
# `now`, fixed inputs, no clock and no network — so it can neither flake nor cost anything, and a
# refactor that quietly turned the alarm into a no-op reds the lane instead of passing.
# The resolver's refusal arm is exercised too, with the network arm DISABLED and a SHA that cannot
# exist: same branch the real path reaches when both sources fail, at zero cost.
# Residual gap, named rather than buried: this proves the alarm fires on a resolution FAILURE, not
# that it fires on a source that answers with a plausible-but-wrong date. Nothing here can prove
# that, because at the pinned SHA there is no second opinion to disagree with.
assert_skill_assert_ref_alarm_can_fire() {
  local lane="$1" now=1785139673 fails=0 rc out
  # fresh, well inside the window
  out="$(skill_assert_ref_verdict "$((now - 86400))" "$now" 14)"; rc=$?
  [[ "$rc" == 0 && "$out" == 1 ]] || fails=$((fails+1))
  # the boundary, both sides: 14 days is fresh, 15 is stale (strictly-greater, pinned here)
  out="$(skill_assert_ref_verdict "$((now - 14 * 86400))" "$now" 14)"; rc=$?
  [[ "$rc" == 0 && "$out" == 14 ]] || fails=$((fails+1))
  out="$(skill_assert_ref_verdict "$((now - 15 * 86400))" "$now" 14)"; rc=$?
  [[ "$rc" == 1 && "$out" == 15 ]] || fails=$((fails+1))
  # both observed freezes would have been caught inside their own window
  out="$(skill_assert_ref_verdict "$((now - 14 * 86400))" "$now" 13)"; rc=$?   # freeze 1, 14d
  [[ "$rc" == 1 ]] || fails=$((fails+1))
  out="$(skill_assert_ref_verdict "$((now - 11 * 86400))" "$now" 10)"; rc=$?   # freeze 2, 11d
  [[ "$rc" == 1 ]] || fails=$((fails+1))
  # UNRESOLVABLE is an error, never a pass: absent, non-numeric, and future-dated.
  local u
  for u in "" "not-a-date" "$((now + 86400))"; do
    skill_assert_ref_verdict "$u" "$now" 14 >/dev/null; rc=$?
    [[ "$rc" == 2 ]] || fails=$((fails+1))
  done
  # …and the resolver itself refuses a ref that cannot exist (offline arm, so this cannot flake).
  if skill_assert_ref_committed_at "ffffffffffffffffffffffffffffffffffffffff" 0 >/dev/null 2>&1; then
    fails=$((fails+1))
  fi
  if (( fails == 0 )); then
    ok "$lane: the SKILL_ASSERT_REF staleness alarm can FIRE — its predicate was driven through fresh, the 14d boundary on both sides, both observed freezes, and all three unresolvable inputs (absent / non-numeric / future-dated), offline (#315)"
  else
    bad "$lane: the SKILL_ASSERT_REF staleness alarm's own predicate is BROKEN — $fails of its outcomes did not reproduce, so this lane's pin-freshness verdict below is not evidence of anything. Fix skill_assert_ref_verdict / skill_assert_ref_committed_at; do NOT delete this self-demonstration (#315)"
  fi
}

# assert_skill_assert_ref_fresh <lane>
# THE ALARM (#315). SKILL_ASSERT_REF has frozen three times from three unrelated causes, each fix
# addressed its own cause and left the DETECTION gap untouched, and every one was found by a human
# tripping over it weeks later. The through-line: the composition gate ran a weeks-old assertion
# under a green tick. Freezes are only survivable while they are loud, so this is the loudness.
assert_skill_assert_ref_fresh() {
  local lane="$1" now age rc short="${SKILL_ASSERT_REF:0:12}"
  now="$(date -u +%s)"
  if [[ -z "$SKILL_ASSERT_REF_AT" ]]; then
    SKILL_ASSERT_REF_AT="$(skill_assert_ref_committed_at "$SKILL_ASSERT_REF" 1)" || SKILL_ASSERT_REF_AT=""
  fi
  age="$(skill_assert_ref_verdict "$SKILL_ASSERT_REF_AT" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS")"; rc=$?
  case "$rc" in
    0) ok "$lane: SKILL_ASSERT_REF ($short) is ${age}d old, threshold ${SKILL_ASSERT_MAX_AGE_DAYS}d — the pinned assertion this lane's verdict rests on is current (#315)" ;;
    1) bad "$lane: SKILL_ASSERT_REF IS STALE — pinned at $SKILL_ASSERT_REF, committed ${age}d ago, threshold ${SKILL_ASSERT_MAX_AGE_DAYS}d. This lane is about to publish a coherence verdict computed by a ${age}-day-old assertion, which is how SKILL_ASSERT_REF froze three times without a gate noticing (#315). BUMP IT: merge the open Renovate PR for FS-GG/.github (it fires; automerge is off org-wide, so a human must merge it — see the Dependency Dashboard, #19), or set SKILL_ASSERT_REF in tests/composition/lib/skill-union.sh to the current FS-GG/.github@main head. Do NOT raise SKILL_ASSERT_MAX_AGE_DAYS to clear this; the threshold's rationale is next to the pin." ;;
    2) bad "$lane: SKILL_ASSERT_REF ($SKILL_ASSERT_REF) could not be RESOLVED to a commit date — neither a sibling FS-GG/.github clone at \$REPO_ROOT/../.github nor a --depth 1 fetch of that commit from github.com produced a usable date (absent, non-numeric, or in the future). This lane FAILS rather than passing: an unreadable age is 'could not look', and 'could not look' is never 'looked, and fine' (epic .github#266) — treating it as a pass is exactly what made all three freezes invisible. Check network reachability of github.com, and check that $SKILL_ASSERT_REF is a real FS-GG/.github commit (a bad bump can write a SHA that no longer exists after a force-push)." ;;
  esac
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
  # STALENESS ALARM (#315) — FIRST, and deliberately ahead of the fetch. It is a fact about the
  # PIN, not about the bundle, so it must not be masked by an early `return` on the fetch arm
  # below: a stale pin and an unreachable raw.githubusercontent are different findings with
  # different remedies, and the whole point of #315 is that this one stopped being reported.
  # Running it here rather than beside the #309 floor also means it fires for EVERY lane on EVERY
  # run — the floor sits after the (a) arm, which a failed fetch skips entirely.
  assert_skill_assert_ref_alarm_can_fire "$lane"
  assert_skill_assert_ref_fresh "$lane"
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
