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
#      moving, which is this file's actual observed failure mode both times it has happened.
#   2. assert_skill_assert_ref_fresh (below, #315) FAILS the lane when the pinned commit is older
#      than SKILL_ASSERT_MAX_AGE_DAYS, and when its date cannot be resolved at all. This is the one
#      that closes the detection gap the other two leave open; its threshold rationale is next to
#      the pin, below.
#   3. Renovate still opens the bump PR (it does fire — the tests/ ignorePaths hole is fixed). This
#      is NOT a backstop and must not be counted as one: automerge is disabled org-wide, so nothing
#      merges the PR and nothing escalates when nobody does; the Dependency Dashboard (#19) lists it
#      and no schedule reads the dashboard. #310 measured that, and #315 is the answer to its third
#      acceptance criterion — "if automerge stays off, name the thing that notices." Before #315 the
#      honest answer was NOTHING, and both freezes were found by a human weeks later.
#      A COUNT, since two numbers are in circulation: TWO freezes have been OBSERVED, and they are
#      the two measured in the threshold block below. #315's title says three because its own table
#      lists a third row as "not yet observed" — an anticipated freeze, not a recorded one. Say two
#      and mean two; the case for this alarm does not need the third.
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
SKILL_ASSERT_REF="158be72cd757b895cf4f024a3fa6e5c6c8d5932b"
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
# WHY 14 — AND IT IS NOT THE NUMBER THE FREEZES WOULD SUGGEST. The obvious derivation is "put it
# under the observed freezes", and that derivation is WRONG here. An age-only alarm cannot tell a
# FROZEN pin from a QUIET UPSTREAM: both look like "the pin has not moved". When upstream is merely
# quiet there is no newer commit to bump to, so a red has NO REMEDY — and `composition` is a
# required check under enforce_admins, so that red blocks every PR in this repo until somebody
# deliberately edits this threshold. A false red here is a repo-wide outage; a slightly old
# assertion still runs and still catches things. The asymmetry sets the floor, not the freezes.
#
# So the binding constraint is upstream's longest QUIET period, and it was measured rather than
# guessed. Over FS-GG/.github@main's whole history to 2026-07-27 — 945 first-parent commits across
# 43 days — the mean gap between commits is 0.046d (~66 minutes) and the LONGEST quiet gap is
# 7.94 DAYS (ending 2026-06-27); the second longest is 3.10d. 14 days is therefore 1.76x the worst
# observed silence. Anything at or under ~8 days would already have fired spuriously once, with
# nothing anyone could have merged to clear it.
#
# WHAT THAT COSTS, SAID PLAINLY RATHER THAN GLOSSED. At 14 days NEITHER observed freeze would have
# fired. Measured from this repo's own history (every commit that rewrote the pin, against each
# pinned commit's own date):
#   freeze 1  ab6d9289  pinned 2026-07-02 11:55Z → replaced 2026-07-16 12:22Z  = 14.02d
#   freeze 2  19500bc8  pinned 2026-07-16 12:19Z → replaced 2026-07-27 02:16Z  = 10.58d
# The comparison below is strictly-greater over a TRUNCATED day count, so the alarm first fires at
# age >= 15.0d: freeze 1 ended 0.02d after reaching age 14, and freeze 2 never reached it. This
# alarm is calibrated to catch the NEXT freeze — the one #315 filed before it happened — not to
# have caught the previous two. What it buys is a BOUND: 15 days instead of the "found by a human
# weeks later" that all three actually ran to. That is the whole claim, and it is worth stating
# because an alarm that never fires and an alarm that always passes look identical from outside.
#
# TIGHTEN IT ONCE IT HAS PROVEN QUIET — that is the intended direction, it is one token below, and
# the arithmetic is already done so the next person does not have to redo it. Truncation plus
# strictly-greater means a freeze of D days fires only at a threshold <= floor(D) - 1:
#   catch freeze 1 (14.02d)  -> threshold <= 13
#   catch freeze 2 (10.58d)  -> threshold <= 9      <- the binding one
#   false red on the worst observed silence (7.94d) -> threshold <= 6
# So 9 IS THE VALUE THAT CATCHES BOTH FREEZES AND STILL CLEARS THE WORST OBSERVED SILENCE, and it
# is deliberately not taken yet: it leaves 2.06 days of margin over a SINGLE 7.94d outlier in 43
# days of history, and it would have fired on freeze 2 with only 0.6d of that freeze left to run.
# Re-measure upstream's quiet-gap distribution over a longer window; if 7.94d stays the outlier,
# 9 is the next stop. Do not tighten below the measured worst silence plus real margin — a red
# with nothing to bump to has no remedy at all.
#
# HEALTHY LOOKS NOTHING LIKE EITHER NUMBER: measured over the same five bumps, the pin's age AT
# THE MOMENT THE BUMP LANDED was 1h, 0h, 0h, 0h, 5h — Renovate tracks upstream's main head (the
# git-refs manager in .github/renovate.json) and lands within hours. So the margin between healthy
# and alarming is ~65x, which is what makes a generous threshold cheap rather than toothless.
#
# THE OTHER FALSE-RED AXIS, WHICH IS NOT STALENESS AND WILL FIRE FIRST ON A LAPTOP. Everything
# above weighs the AGE axis. The axis that actually bites locally is RESOLVABILITY: the alarm runs
# unconditionally from run.sh, so an offline run — or any checkout where $REPO_ROOT/../.github is
# not a sibling clone, which includes a git worktree — now reds the whole gate at verdict 2, where
# before both lanes would simply have SKIPPED. That is the intended fail-closed direction and arm
# (c) of the verdict-2 message names it, but it is a real change in what a local run costs, and it
# is the one thing here a developer will hit before CI does. The escape is a sibling clone, not a
# flag: `git clone https://github.com/FS-GG/.github ../.github` makes the whole alarm offline.
#
# It is a CONSTANT, not `${SKILL_ASSERT_MAX_AGE_DAYS:-14}`: a threshold that can be raised from the
# environment is a threshold a red run can be re-run around, and this alarm exists precisely because
# both previous failures were survivable-looking.
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
#       step carries that warning in prose. The git transport has no such budget, and it fails
#       FAST and loud on a ref that is not there ("upload-pack: not our ref", exit 128) rather
#       than hanging.
#       It IS a new failure domain, and pretending otherwise would be the kind of claim this file
#       exists to stop: github.com git-over-HTTPS and raw.githubusercontent.com are different
#       hosts on different serving paths, tracked separately on GitHub's status page, and an
#       egress allowlist that permits one routinely blocks the other. It fails CLOSED, which is
#       correct, so the cost of the new domain is bounded by one retry (below) and by arm (1)
#       covering the offline case.
# ONE RETRY, deliberately. A single dropped connection must not red a required check, and a loop
# that retries harder just converts a real outage into a slow one.
#
# Memoized by the caller (SKILL_ASSERT_REF_AT), and the memo caches FAILURE too — the "-" sentinel.
# Today that memo is DEFENSIVE rather than load-bearing: since the alarm moved to run.sh there is
# exactly ONE real resolution per run. It is kept because the cost of a second caller reappearing
# is a full repeat of the network arm — with the retry above, up to 2 x 30s — and because a
# resolution that already failed this run cannot succeed later in it.
SKILL_ASSERT_REF_AT=""
# The network arm's transport, factored out so the `timeout` guard is an if/else rather than an
# array splice: `git fetch` has no timeout of its own, and a hung transport on a REQUIRED check is
# the failure mode this alarm must not introduce. `timeout` is coreutils and effectively always
# present; when it is not (stock macOS ships it as `gtimeout`) the fetch still runs, because an
# alarm that refuses to LOOK because a convenience binary is missing is worse than one that can
# hang on a dead socket — and GIT_TERMINAL_PROMPT=0 plus an emptied credential helper removes the
# one way an unbounded `git fetch` actually blocks forever: a username prompt, which is what a
# public repo turning 404 (renamed, or made private) produces on a TTY.
skill_assert_ref_fetch() {
  local scratch="$1" ref="$2" url="https://github.com/FS-GG/.github.git" try
  for try in 1 2; do
    if command -v timeout >/dev/null 2>&1; then
      GIT_TERMINAL_PROMPT=0 timeout 30 git -c credential.helper= -C "$scratch" \
        fetch -q --depth 1 "$url" "$ref" >/dev/null 2>&1 && return 0
    else
      GIT_TERMINAL_PROMPT=0 git -c credential.helper= -C "$scratch" \
        fetch -q --depth 1 "$url" "$ref" >/dev/null 2>&1 && return 0
    fi
  done
  return 1
}
# skill_assert_ref_is_pinned_sha <ref>
# A PIN THAT IS NOT A 40-HEX SHA IS A FAIL-OPEN, AND IT IS ONE THE RESOLVER CAN BE TALKED INTO.
# Both of its arms will happily resolve a BRANCH name: `SKILL_ASSERT_REF="main"` reports 0d old
# forever, `fetch_skill_assert`'s raw URL still serves bytes, and every backstop in this file goes
# quiet at once. That is not hypothetical — the STALE message below tells a reader under time
# pressure to "set SKILL_ASSERT_REF to the current FS-GG/.github@main head", and one careless
# reading of that sentence produces exactly this state. renovate.json's manager already requires
# [0-9a-f]{40}; so does this. An abbreviated SHA is refused too: it is not what the integrity
# argument at the top of this file rests on.
#
# It is a PURE PREDICATE of its own rather than an inline test inside the resolver, and that is not
# style. Inlined, the self-demonstration below could only reach it through the resolver — where, on
# a host with no sibling clone (CI, and any git-worktree checkout), arm (1) fails for a branch name
# anyway and the demo passes whether or not the guard is there. Hoisted, the demo tests the guard
# DIRECTLY and the check means the same thing in every environment.
skill_assert_ref_is_pinned_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]]
}
skill_assert_ref_committed_at() {
  local ref="$1" allow_net="${2:-1}" at="" scratch
  skill_assert_ref_is_pinned_sha "$ref" || return 1
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
# "looked, and fine"; that exact trap is what made both freezes invisible under a green tick.
#
# The comparison is STRICTLY GREATER over a TRUNCATED day count, so the first age that is stale at
# a threshold of N is N+1 — i.e. 15.0 days at 14. The boundary is pinned in the self-demonstration
# below so it cannot drift by accident, and the threshold block above states what it costs.
#
# The future-date guard has a deliberate sub-24h dead zone: truncation makes anything up to 86399s
# ahead read as age 0 (fresh), and only a full day ahead trips verdict 2. That is the right way
# round — small NTP skew between a runner and a committer must not red a required check, while a
# pin dated a month ahead still cannot buy itself permanent freshness.
#
# The numeric guards are ^(0|[1-9][0-9]*)$, not ^[0-9]+$: a leading-zero string like "0008" passes
# a bare [0-9]+ and is then read as OCTAL by (( )), which writes "value too great for base" to
# stderr and breaks this function's no-output-but-the-age contract. `git show --format=%ct` never
# emits one, so this is unreachable today — it is guarded because the only thing keeping it
# unreachable is a property of a tool this function does not own.
skill_assert_ref_verdict() {
  local at="$1" now="$2" max="$3" age num='^(0|[1-9][0-9]*)$'
  [[ "$at" =~ $num && "$now" =~ $num && "$max" =~ $num ]] || return 2
  age=$(( (now - at) / 86400 ))
  (( age < 0 )) && return 2
  printf '%s\n' "$age"
  (( age > max )) && return 1
  return 0
}

# assert_skill_assert_ref_alarm_can_fire <lane>
# #315 AC3, "demonstrated, not asserted": drive the alarm through every outcome it can reach, on
# every real run. Entirely offline and arithmetic — a fixed `now`, fixed inputs, no clock and no
# network — so it can neither flake nor cost anything, and a refactor that quietly turned the
# alarm into a no-op reds the run instead of passing.
#
# IT DRIVES THE ASSERTION, NOT JUST THE PREDICATE, and that distinction is the whole value. An
# earlier draft exercised only skill_assert_ref_verdict; mutating the assertion's `2) bad` arm to
# `2) ok` — the precise fail-open #315 exists to prevent — SURVIVED it. So the last two cases call
# assert_skill_assert_ref_fresh itself against a forced memo and assert that the FAIL counter
# actually moved. `ok`/`bad` are counter bumps, so this is a snapshot-and-restore, not a fixture.
#
# Residual gaps, named rather than buried:
#   - it proves the alarm fires on a resolution FAILURE, not on a source that answers with a
#     plausible-but-WRONG date. Nothing here can prove that: at a pinned SHA there is no second
#     opinion to disagree with.
#   - every case runs with the network arm DISABLED, so the resolver's NETWORK path is not covered
#     here at all: a break in skill_assert_ref_fetch shows up as the live pin failing to resolve,
#     not as this demo reding. That is deliberate — a self-test that phones out on every run is a
#     flake source on a required check — and it is why the live verdict below is not redundant
#     with this one.
assert_skill_assert_ref_alarm_can_fire() {
  local lane="$1" now=1785139673 fails=0 rc out
  # fresh, well inside the window
  out="$(skill_assert_ref_verdict "$((now - 86400))" "$now" 14)"; rc=$?
  [[ "$rc" == 0 && "$out" == 1 ]] || fails=$((fails+1))
  # THE BOUNDARY, BOTH SIDES, at the real threshold: strictly-greater over a truncated day count,
  # so 14d is fresh and 15d is stale. This is the pair that pins what the threshold block claims.
  out="$(skill_assert_ref_verdict "$((now - SKILL_ASSERT_MAX_AGE_DAYS * 86400))" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS")"; rc=$?
  [[ "$rc" == 0 && "$out" == "$SKILL_ASSERT_MAX_AGE_DAYS" ]] || fails=$((fails+1))
  out="$(skill_assert_ref_verdict "$(( now - (SKILL_ASSERT_MAX_AGE_DAYS + 1) * 86400 ))" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS")"; rc=$?
  [[ "$rc" == 1 && "$out" == "$((SKILL_ASSERT_MAX_AGE_DAYS + 1))" ]] || fails=$((fails+1))
  # THE TWO OBSERVED FREEZES, AT THE LIVE THRESHOLD — asserted to be MISSED, because at 14 days
  # they are, and the threshold block says so. If someone tightens the threshold to cover them,
  # THIS IS THE LINE THAT FAILS, which is the intended way to find out that the prose above needs
  # rewriting with it. freeze 1 = 14.02d, freeze 2 = 10.58d, both measured from this repo's own
  # pin history against each pinned commit's date.
  skill_assert_ref_verdict "$(( now - 1402 * 864 ))" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS" >/dev/null; rc=$?
  [[ "$rc" == 0 ]] || fails=$((fails+1))
  skill_assert_ref_verdict "$(( now - 1058 * 864 ))" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS" >/dev/null; rc=$?
  [[ "$rc" == 0 ]] || fails=$((fails+1))
  # …and they ARE caught at the thresholds the block computes for them (<=13 and <=9), so the
  # alarm is calibrated rather than inert, and those two numbers cannot rot into prose-only claims.
  skill_assert_ref_verdict "$(( now - 1402 * 864 ))" "$now" 13 >/dev/null; rc=$?
  [[ "$rc" == 1 ]] || fails=$((fails+1))
  skill_assert_ref_verdict "$(( now - 1058 * 864 ))" "$now" 9 >/dev/null; rc=$?
  [[ "$rc" == 1 ]] || fails=$((fails+1))
  # The worst observed upstream SILENCE (7.94d) must NOT red at the live threshold — this is the
  # false-red floor, and it is the constraint that actually chose 14.
  skill_assert_ref_verdict "$(( now - 794 * 864 ))" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS" >/dev/null; rc=$?
  [[ "$rc" == 0 ]] || fails=$((fails+1))
  # UNRESOLVABLE is an error, never a pass: absent, non-numeric, leading-zero, and future-dated.
  # Each runs in a SUBSHELL because one of these inputs is specifically chosen to blow up a WEAKER
  # implementation: with a `^[0-9]+$` guard, "0008" reaches (( )) as an invalid octal, and bash
  # ABORTS THE ENCLOSING LOOP rather than returning — so `rc=$?` would never run, `fails` would
  # never increment, the future-dated case after it would never execute, and the demo would print a
  # tick. Containing it means an abort surfaces as a non-2 rc, i.e. as the failure it is.
  local u
  for u in "" "not-a-date" "0008" "$((now + 86400))"; do
    ( skill_assert_ref_verdict "$u" "$now" 14 ) >/dev/null 2>&1; rc=$?
    [[ "$rc" == 2 ]] || fails=$((fails+1))
  done
  # The pin-shape guard, tested DIRECTLY (not through the resolver — see its docblock for why that
  # distinction is the difference between a real check and one that only bites where a sibling
  # clone happens to exist). A BRANCH NAME is the fail-open that matters, because the stale-pin
  # remedy text names `@main` and reads like an invitation to write it here.
  for u in "main" "@main" "fe8261b96a0e" "FE8261B96A0E9AE0A4B739F4779563988ABFC134" ""; do
    if skill_assert_ref_is_pinned_sha "$u"; then fails=$((fails+1)); fi
  done
  skill_assert_ref_is_pinned_sha "fe8261b96a0e9ae0a4b739f4779563988abfc134" || fails=$((fails+1))
  # …AND THE RESOLVER HONOURS IT — the step that connects a correct predicate to an actual alarm,
  # and the one that is easy to test vacuously. Asking the resolver for a branch name where no
  # sibling clone exists proves nothing: arm (1) fails for want of a repo, not for want of a guard,
  # so deleting the guard's CALL SITE would still "pass". So point arm (1) at a git repository that
  # is certain to exist — this checkout — via a scratch REPO_ROOT whose ../.github reaches it, and
  # ask for "HEAD". HEAD resolves in any checkout, shallow or detached, so WITHOUT the guard the
  # resolver returns a real date; WITH it, it refuses before touching git. Offline, no network, and
  # it discriminates in every environment rather than only where a sibling clone happens to be.
  local probe="$WORKDIR/skill-assert-guard-probe" saved_root="$REPO_ROOT"
  if mkdir -p "$probe/anchor" 2>/dev/null && ln -sfn "$saved_root" "$probe/.github" 2>/dev/null; then
    REPO_ROOT="$probe/anchor"
    if skill_assert_ref_committed_at "HEAD" 0 >/dev/null 2>&1; then fails=$((fails+1)); fi
    # …and the same probe resolves a real 40-hex SHA, so the arm is live rather than inert — a
    # probe that can never resolve anything would pass the line above for the wrong reason.
    local self_sha; self_sha="$(git -C "$saved_root" rev-parse HEAD 2>/dev/null)"
    if [[ "$self_sha" =~ ^[0-9a-f]{40}$ ]]; then
      skill_assert_ref_committed_at "$self_sha" 0 >/dev/null 2>&1 || fails=$((fails+1))
    fi
    REPO_ROOT="$saved_root"
  fi
  # THE ASSERTION'S OWN rc → ok/bad MAPPING. Snapshot the counters, force the memo, and require
  # that a stale pin and an unresolvable one each move FAIL. Without this, `2) bad` → `2) ok`
  # passes every check above.
  local p0="$PASS" f0="$FAIL" memo0="$SKILL_ASSERT_REF_AT"
  SKILL_ASSERT_REF_AT="$(( now - 400 * 86400 ))"            # ~400d old: unambiguously stale
  assert_skill_assert_ref_fresh "$lane (self-check)" >/dev/null 2>&1
  [[ "$FAIL" == "$((f0 + 1))" ]] || fails=$((fails+1))
  SKILL_ASSERT_REF_AT="-"                                    # the negative-memo sentinel
  assert_skill_assert_ref_fresh "$lane (self-check)" >/dev/null 2>&1
  [[ "$FAIL" == "$((f0 + 2))" ]] || fails=$((fails+1))
  PASS="$p0"; FAIL="$f0"; SKILL_ASSERT_REF_AT="$memo0"
  if (( fails == 0 )); then
    ok "$lane: the SKILL_ASSERT_REF staleness alarm can FIRE — driven offline through fresh, both sides of the ${SKILL_ASSERT_MAX_AGE_DAYS}d boundary, both observed freezes (14.02d/10.58d: missed at ${SKILL_ASSERT_MAX_AGE_DAYS}d by design, caught at 13d/9d), the 7.94d worst-observed-silence false-red floor, all four unresolvable inputs, five refused pin shapes plus one accepted, and the assertion's own stale/unresolvable → FAIL mapping (#315)"
  else
    bad "$lane: the SKILL_ASSERT_REF staleness alarm is BROKEN — $fails of its outcomes did not reproduce, so the pin-freshness verdict below is not evidence of anything. If you just TIGHTENED SKILL_ASSERT_MAX_AGE_DAYS, the two 'observed freeze' cases are the expected failures and the threshold rationale next to the pin must be rewritten with them. Otherwise fix skill_assert_ref_verdict / skill_assert_ref_committed_at / assert_skill_assert_ref_fresh; do NOT delete this self-demonstration (#315)"
  fi
}

# assert_skill_assert_ref_fresh <lane>
# THE ALARM (#315). SKILL_ASSERT_REF has frozen twice from two unrelated causes, each fix
# addressed its own cause and left the DETECTION gap untouched, and every one was found by a human
# tripping over it weeks later. The through-line: the composition gate ran a weeks-old assertion
# under a green tick. Freezes are only survivable while they are loud, so this is the loudness.
#
# ONE CONSEQUENCE, NAMED HERE SO THE NEXT PERSON IS NOT SURPRISED BY IT. `composition` is a
# required check under enforce_admins and runs on push-to-main and pull_request only — there is no
# `schedule:` trigger. So detection latency is bounded by PR frequency rather than by days, and
# when this does fire it fires on somebody's UNRELATED PR and blocks it, and every other PR, until
# a pin bump lands. That is the intended loudness (#315: "freezes are only survivable while they
# are loud") and the remedy is a one-token commit that is always available. But note freeze 2's
# root cause was a PARKED, RED Renovate branch: if that recurs, the bump PR cannot merge itself out
# of the way and somebody must hand-edit the pin. There is deliberately no environment override to
# reach for. If that trade ever looks wrong, the fix is a scheduled run that fires the alarm off
# the critical path — not an escape hatch here.
assert_skill_assert_ref_fresh() {
  local lane="$1" now age rc short="${SKILL_ASSERT_REF:0:12}"
  now="$(date -u +%s)"
  # "-" is the NEGATIVE memo sentinel: a resolution that already failed this run cannot succeed
  # later in it, so a second caller must not pay the network arm again.
  if [[ -z "$SKILL_ASSERT_REF_AT" ]]; then
    SKILL_ASSERT_REF_AT="$(skill_assert_ref_committed_at "$SKILL_ASSERT_REF" 1)" || SKILL_ASSERT_REF_AT="-"
  fi
  age="$(skill_assert_ref_verdict "$SKILL_ASSERT_REF_AT" "$now" "$SKILL_ASSERT_MAX_AGE_DAYS")"; rc=$?
  case "$rc" in
    0) ok "$lane: SKILL_ASSERT_REF ($short) is ${age}d old, threshold ${SKILL_ASSERT_MAX_AGE_DAYS}d — the pinned assertion this run's verdict rests on is current (#315)" ;;
    1) bad "$lane: SKILL_ASSERT_REF IS STALE — pinned at $SKILL_ASSERT_REF, committed ${age}d ago, threshold ${SKILL_ASSERT_MAX_AGE_DAYS}d. This run is about to publish a coherence verdict computed by a ${age}-day-old assertion, which is how SKILL_ASSERT_REF froze twice without a gate noticing (#315). BUMP IT: merge the open Renovate PR for FS-GG/.github (it fires; automerge is off org-wide, so a human must merge it — see the Dependency Dashboard, #19), or hand-edit SKILL_ASSERT_REF in tests/composition/lib/skill-union.sh to the current FS-GG/.github@main HEAD COMMIT SHA — a full 40-hex SHA, never the branch name '@main', which this gate refuses precisely because it would report 0d old forever. Do not raise SKILL_ASSERT_MAX_AGE_DAYS just to clear a red. THE ONE EXCEPTION: if upstream genuinely has not moved and the pin ALREADY equals FS-GG/.github@main, there is nothing to bump to and raising the threshold is the correct fix — as a reviewed commit that also updates the rationale next to the pin, which records the longest upstream quiet period this number is derived from." ;;
    2) bad "$lane: SKILL_ASSERT_REF ($SKILL_ASSERT_REF) could not be RESOLVED to a commit date — neither a sibling FS-GG/.github clone at \$REPO_ROOT/../.github nor a --depth 1 fetch of that commit from github.com produced a usable date. This run FAILS rather than passing: an unreadable age is 'could not look', and 'could not look' is never 'looked, and fine' (epic .github#266) — treating it as a pass is exactly what made both freezes invisible. In likelihood order: (a) SKILL_ASSERT_REF is not a full 40-hex SHA — a branch name or an abbreviation is REFUSED here by design; (b) git is not on PATH, which this gate now requires and run.sh preflights; (c) github.com git-over-HTTPS is unreachable (note it is a DIFFERENT failure domain from the raw.githubusercontent.com fetch this gate also uses — an egress allowlist can permit one and block the other); (d) the SHA is not a real FS-GG/.github commit, which a bad bump or an upstream force-push can produce." ;;
    *) bad "$lane: skill_assert_ref_verdict returned an unenumerated code ($rc) for SKILL_ASSERT_REF ($short). This run FAILS rather than falling through: an outcome nobody enumerated is 'could not look', and a case statement with no default arm would have left this run GREEN with no output at all — the exact shape of both freezes (#315, epic .github#266)." ;;
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
# The staleness alarm (#315) is NOT called from here, and that is deliberate — see the call in
# run.sh. It is a fact about the PIN, not about a scaffolded product, and assert_skill_union is
# reached only from two GATED stages (05-build needs fsgg-sdd + a successful scaffold + build;
# 05b-standalone needs the pinned template to install and instantiate). Hanging the alarm off them
# would mean that on a host where both lanes SKIP — the ordinary local dev run — the pin's
# freshness is never evaluated and the run still reports green. That is #315's own failure mode
# rebuilt one level up, and in CI it would be load-bearing on a workflow comment staying true.
assert_skill_union() {
  local prod="$1" lane="$2" cotenant="$3"
  if ! fetch_skill_assert; then
    bad "$lane: cannot obtain the shared skill-union assertion (FS-GG/.github scripts/skill-union-assert.sh: raw.githubusercontent.com unreachable and no ../.github sibling clone) — the union cannot be verified, so this lane FAILS rather than passing unverified"
    return
  fi
  # (a) consumer arm — checks 1–2 (present-in-each-root ∧ byte-identical-across-roots).
  if "$SKILL_ASSERT" --product "$prod" >"$WORKDIR/skill-union.$lane.log" 2>&1; then
    ok "$lane: the two agent-skill roots are the byte-identical union (P3.G3.1: present-in-each-root ∧ byte-identical-across-roots)"
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
