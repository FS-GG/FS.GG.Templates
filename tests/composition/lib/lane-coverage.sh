# shellcheck shell=bash
# ── Composition lane discovery + required-path coverage (FS.GG.Templates#379) ──────────────────
#
# THE DEFECT THIS CLOSES. tests/composition/run.sh enumerated its per-identity lanes BY HAND — one
# literal `if bash "$COMPOSITION_DIR/<name>/run.sh"` block per lane, appended by whichever item
# added that template. Nothing observed a lane directory that no block referenced, so "add a lane
# file" and "put the lane on the required path" were two separate acts and the second was silently
# optional. Two of four lanes were added without it — console by #356, fable-game by #348, two
# different items on two different days — and both templates' full lifecycle contracts were
# therefore green by omission: each could regress to a hard failure with every required check on
# `main` still green. Same class as #313 (a gate authored and never referenced), rebuilt one level
# down, where the caller is this orchestrator rather than a workflow.
#
# THE MECHANISM IS TWO HALVES, AND THE SECOND IS THE ONE WITH TEETH.
#
#   1. DISCOVERY IS THE AUTHORITY ON WHICH LANES EXIST. A directory under tests/composition/ that
#      carries a run.sh IS a lane, full stop. run.sh's default lane set is that discovered set, so
#      adding a lane directory puts it on the required check BY CONSTRUCTION — there is no second
#      act left to forget. That alone makes the exact defect above unbuildable.
#
#   2. …BUT A CALLER CAN STILL NARROW IT, so the narrowing is what gets gated. COMPOSITION_LANES
#      (#349) exists so a caller can select a subset, and a developer running one lane locally is a
#      legitimate use of it — reds on that would just train people to stop running the suite. What
#      is NOT legitimate is the REQUIRED CHECK's configuration reaching fewer lanes than exist. So
#      the gate below does not grade THIS INVOCATION's selection. It grades the WORKFLOW FILES,
#      statically, on every run — including that one-lane dev run, which is the point: the fact
#      being asserted is a property of the repository, not of the invocation, so it must not be
#      reachable only from the invocations that happen to be complete.
#
# WHY IT GRADES FILES AND NOT THE LIVE BRANCH POLICY. The protected context list
# (`gh api repos/FS-GG/FS.GG.Templates/branches/main/protection` → ["kit / coordination-kit",
# "composition"]) is not readable from inside this run: the composition job holds `contents: read`
# and no admin scope, and a local dev run has no token at all. A gate that needs a credential its
# callers may not have does not fail closed, it fails ALWAYS (the .github#463 shape). The mapping
# from that context to a file is therefore declared here ONCE — and then ASSERTED rather than
# assumed: the file must exist, must declare `name: composition` so that renaming the workflow reds
# instead of silently detaching the gate from its subject, and must actually invoke
# tests/composition/run.sh so that deleting the step reds too.
#
# WHAT THAT LEAVES OUT, NAMED RATHER THAN ROUNDED OFF: the branch-protection list itself. If
# someone removes `composition` from the protected contexts, every assertion here still passes and
# the lanes still run — they just stop blocking anything. That is a real limit on what a green here
# means. It is not closable from inside a job with `contents: read`, and it is a different subject
# (which contexts are required) from this item's (which lanes those contexts reach).

# The workflow whose job produces the protected status context, relative to REPO_ROOT, and the
# context name it must declare. Asserted below — not decorative.
COMPOSITION_REQUIRED_WORKFLOW='.github/workflows/composition.yml'
COMPOSITION_REQUIRED_CONTEXT='composition'

# ── The deferral registry ─────────────────────────────────────────────────────────────────────
# The ONLY sanctioned way for a discovered lane to sit off the required check, and it is
# deliberately the #316 shape: an explicit, reasoned, checked-in decision, not an omission. Each
# entry is `<lane>|<reason>`, and the reason must name an issue so the decision has somewhere to be
# argued with.
#
# A DEFERRAL IS NOT A DELETION. A deferred lane must still be reached by SOME caller — today that
# would be the release gate — or the registry becomes a quiet way to retire coverage, which is this
# item's own defect with paperwork on top. That is asserted, not trusted.
#
# IT IS EMPTY, AND THE MEASUREMENT THAT KEEPS IT EMPTY IS QUOTED next to `timeout-minutes: 30` in
# .github/workflows/composition.yml. Do not add an entry without re-measuring and quoting the run
# the way that block does; "it felt slow" is how the required check lost two lanes the first time.
COMPOSITION_LANE_DEFERRALS=()

# lane_universe <composition-dir>
# Every lane that EXISTS, one per line, sorted. Discovery, not a list — this is half 1.
lane_universe() {
  local d
  for d in "$1"/*/; do
    [[ -f "$d/run.sh" ]] && basename "$d"
  done | sort
}

# lane_suite_callers <repo-root>
# Every workflow file that invokes the composition suite, sorted. `-l` over the literal path is
# enough and is deliberately not a YAML parse: the thing being detected is "this file runs the
# suite", which is exactly a textual reference to it.
lane_suite_callers() {
  grep -rlF 'tests/composition/run.sh' "$1/.github/workflows" 2>/dev/null | sort
}

# lane_workflow_selection <workflow-file> <universe>
# The lane set this workflow will ACTUALLY run: the literal list it assigns to COMPOSITION_LANES,
# or — when it assigns none — the discovered universe, because that is run.sh's default. Comment
# lines cannot match: the anchor requires the key at the start of the line after whitespace only,
# and a YAML comment starts with `#`. This matters, because both workflows discuss the variable in
# prose at length.
#
# BOUND, stated rather than left implicit: it returns the FIRST assignment in the file. Each caller
# invokes the suite exactly once today. If one ever invokes it twice with different sets, widen this
# in the same change — a second assignment silently ignored is this item's defect rebuilt here.
lane_workflow_selection() {
  local wf="$1" universe="$2" line
  line="$(grep -m1 -E '^[[:space:]]*COMPOSITION_LANES:' "$wf" 2>/dev/null)"
  if [[ -z "$line" ]]; then
    printf '%s\n' "$universe"
    return 0
  fi
  line="${line#*:}"
  line="${line%%#*}"
  line="${line//\"/}"
  line="${line//\'/}"
  # Word-splitting is the parse here: COMPOSITION_LANES is a space-separated list by contract.
  # shellcheck disable=SC2086
  printf '%s\n' $line | sort -u
}

# lane_in_set <lane> <newline-separated-set>
lane_in_set() {
  local needle="$1" item
  while IFS= read -r item; do
    [[ "$item" == "$needle" ]] && return 0
  done <<<"$2"
  return 1
}

# lane_deferral_reason <lane> — echoes the registered reason, or returns 1.
lane_deferral_reason() {
  local lane="$1" entry
  for entry in ${COMPOSITION_LANE_DEFERRALS[@]+"${COMPOSITION_LANE_DEFERRALS[@]}"}; do
    if [[ "${entry%%|*}" == "$lane" ]]; then
      printf '%s\n' "${entry#*|}"
      return 0
    fi
  done
  return 1
}

# lane_coverage_findings <composition-dir> <repo-root>
# THE PREDICATE. Prints one finding per line and returns 1 when there is at least one, 0 when the
# repository's lane coverage is whole. Split from the assertion so the self-demonstration below can
# drive both, and so the assertion's ok/bad mapping is itself testable.
lane_coverage_findings() {
  local composition_dir="$1" repo_root="$2"
  local universe required_wf required_sel callers wf sel lane reason entry found other_reach
  local findings=0

  universe="$(lane_universe "$composition_dir")"
  if [[ -z "$universe" ]]; then
    echo "no lane directories were discovered under $composition_dir — discovery itself is broken, and a lane set that is empty for the wrong reason reports every lane as covered"
    return 1
  fi

  required_wf="$repo_root/$COMPOSITION_REQUIRED_WORKFLOW"
  if [[ ! -f "$required_wf" ]]; then
    echo "$COMPOSITION_REQUIRED_WORKFLOW does not exist, so the workflow that produces the required '$COMPOSITION_REQUIRED_CONTEXT' context cannot be graded — every lane below is unreached until it is back"
    return 1
  fi
  if ! grep -qE "^name:[[:space:]]*$COMPOSITION_REQUIRED_CONTEXT[[:space:]]*$" "$required_wf"; then
    echo "$COMPOSITION_REQUIRED_WORKFLOW no longer declares 'name: $COMPOSITION_REQUIRED_CONTEXT' — the protected status context and the file this gate grades have come apart, so a green here would be about the wrong file"
    findings=$((findings + 1))
  fi
  if ! grep -qF 'tests/composition/run.sh' "$required_wf"; then
    echo "$COMPOSITION_REQUIRED_WORKFLOW does not invoke tests/composition/run.sh at all — the required check no longer runs the composition suite, so every lane is unreached"
    return 1
  fi

  required_sel="$(lane_workflow_selection "$required_wf" "$universe")"
  callers="$(lane_suite_callers "$repo_root")"

  # (a) EVERY suite-calling workflow reaches every discovered lane — not just the required one.
  #     The required check is the lane set that matters most, but it is not the only hand-written
  #     enumeration in the repository: .github/workflows/release.yml pins its own four-name list,
  #     and its stated acceptance is "all four identities install and instantiate through the packed
  #     artifact". A fifth lane added tomorrow would land on the required check by construction
  #     (discovery) and be missed by that list in silence — this item's defect rebuilt one level
  #     over, in the job whose whole premise is completeness. So a workflow that PINS a list must
  #     cover the universe, and the only exemption is a registered deferral.
  while IFS= read -r wf; do
    [[ -n "$wf" ]] || continue
    sel="$(lane_workflow_selection "$wf" "$universe")"
    while IFS= read -r lane; do
      [[ -n "$lane" ]] || continue
      lane_in_set "$lane" "$sel" && continue
      if reason="$(lane_deferral_reason "$lane")"; then continue; fi
      if [[ "$wf" == "$required_wf" ]]; then
        echo "lane '$lane' exists at $composition_dir/$lane/run.sh but the required '$COMPOSITION_REQUIRED_CONTEXT' check does not run it, and no deferral is registered — this is exactly #379: a full template-lifecycle proof that is green by omission. Either let it run (delete the narrowing COMPOSITION_LANES in $COMPOSITION_REQUIRED_WORKFLOW) or register a measured deferral in COMPOSITION_LANE_DEFERRALS"
      else
        echo "lane '$lane' exists at $composition_dir/$lane/run.sh but ${wf#"$repo_root"/} pins a COMPOSITION_LANES list that omits it, and no deferral is registered — that workflow runs one fewer lane than its own acceptance claims. Delete its narrowing list (the default is now every discovered lane) or register a measured deferral"
      fi
      findings=$((findings + 1))
    done <<<"$universe"
  done <<<"$callers"

  # (b) A DEFERRAL IS NOT A DELETION: whatever is exempted above must still be reached somewhere.
  for entry in ${COMPOSITION_LANE_DEFERRALS[@]+"${COMPOSITION_LANE_DEFERRALS[@]}"}; do
    lane="${entry%%|*}"
    reason="${entry#*|}"
    if ! lane_in_set "$lane" "$universe"; then
      echo "COMPOSITION_LANE_DEFERRALS defers lane '$lane', which no longer exists under $composition_dir — a stale deferral is a standing exemption for a name anybody can reuse"
      findings=$((findings + 1))
      continue
    fi
    if [[ ! "$reason" =~ \#[0-9]+ ]]; then
      echo "the deferral registered for lane '$lane' names no issue ('$reason') — a deferral is a decision, and a decision with nowhere to be argued with is an omission with a sentence attached"
      findings=$((findings + 1))
    fi
    other_reach=0
    found=0
    while IFS= read -r wf; do
      [[ -n "$wf" ]] || continue
      sel="$(lane_workflow_selection "$wf" "$universe")"
      if lane_in_set "$lane" "$sel"; then other_reach=1; else found=1; fi
    done <<<"$callers"
    if (( other_reach == 0 )); then
      echo "lane '$lane' is registered as deferred ('$reason') but NO workflow runs it at all — a deferral is not a deletion, and this one retires the lane's coverage entirely"
      findings=$((findings + 1))
    elif (( found == 0 )); then
      echo "COMPOSITION_LANE_DEFERRALS defers lane '$lane', but every workflow that calls the suite runs it anyway — the registry and the workflows disagree, and the registry is the document people read"
      findings=$((findings + 1))
    fi
  done

  # (c) Every lane a caller NAMES exists. #349 already fails a named-but-absent lane at RUN time;
  #     this catches the same typo statically, in every caller, including the ones this invocation
  #     is not being run by. A release gate that names 'fable-games' would otherwise run three lanes
  #     and report four until the next release.
  while IFS= read -r wf; do
    [[ -n "$wf" ]] || continue
    grep -qE '^[[:space:]]*COMPOSITION_LANES:' "$wf" || continue
    sel="$(lane_workflow_selection "$wf" "$universe")"
    while IFS= read -r lane; do
      [[ -n "$lane" ]] || continue
      if ! lane_in_set "$lane" "$universe"; then
        echo "${wf#"$repo_root"/} names lane '$lane' in COMPOSITION_LANES, but no such lane exists under $composition_dir — that caller runs one fewer lane than it reports"
        findings=$((findings + 1))
      fi
    done <<<"$sel"
  done <<<"$callers"

  (( findings == 0 )) && return 0
  return 1
}

# assert_lane_coverage <composition-dir> <repo-root>
# THE GATE. Unconditional, offline, and independent of which lanes THIS invocation selected.
assert_lane_coverage() {
  local out lane_count
  lane_count="$(lane_universe "$1" | grep -c .)"
  if out="$(lane_coverage_findings "$1" "$2")"; then
    ok "lanes: all $lane_count discovered lane(s) are reached by the required '$COMPOSITION_REQUIRED_CONTEXT' check ($(lane_universe "$1" | tr '\n' ' ' | sed 's/ $//')), every caller's COMPOSITION_LANES names only lanes that exist, and the deferral registry holds $(printf '%s' "${#COMPOSITION_LANE_DEFERRALS[@]}") entries (#379)"
  else
    bad "lanes: a lane directory exists that the required '$COMPOSITION_REQUIRED_CONTEXT' check does not reach, or a caller's lane list has rotted — the findings are below. This is #379's gate; do NOT silence it by narrowing the discovered set."
    printf '%s\n' "$out" | sed 's/^/      | /'
  fi
}

# assert_lane_coverage_can_fire <lane-label> <scratch-dir>
# #379 AC1, "a gate that is DEMONSTRATED to fire": drive the coverage gate through every outcome it
# can reach, on every real run, against fixture trees under a scratch dir. Entirely offline and
# filesystem-local — no network, no clock, no token — so it can neither flake nor cost anything, and
# a refactor that quietly turned the gate into a no-op reds the run instead of passing.
#
# IT DRIVES THE ASSERTION, NOT ONLY THE PREDICATE. The last two cases call assert_lane_coverage
# itself and require that the FAIL counter actually moved, because without that a mutation of the
# `else bad` arm to `else ok` — the precise fail-open #379 exists to prevent — survives every
# predicate case above it. `ok`/`bad` are counter bumps, so this is a snapshot-and-restore.
#
# Residual gap, named rather than buried: every case here grades FILES, so it demonstrates that the
# gate reds when a workflow stops reaching a lane. It cannot demonstrate that the protected context
# list still names `composition` — see the limit recorded at the top of this file.
assert_lane_coverage_can_fire() {
  local label="$1" scratch="$2" fails=0 n=0
  local saved_deferrals=()
  [[ "${#COMPOSITION_LANE_DEFERRALS[@]}" -gt 0 ]] && saved_deferrals=("${COMPOSITION_LANE_DEFERRALS[@]}")

  # fixture <name> <lanes...> — a repo root with the named lane dirs and no workflows yet.
  _lc_fixture() {
    local root="$scratch/$1" lane
    shift
    rm -rf "$root"
    mkdir -p "$root/.github/workflows" "$root/tests/composition"
    for lane in "$@"; do
      mkdir -p "$root/tests/composition/$lane"
      printf '#!/usr/bin/env bash\nexit 0\n' >"$root/tests/composition/$lane/run.sh"
    done
    printf '%s\n' "$root"
  }
  # _lc_workflow <root> <file> <name> <lanes-or-empty>
  _lc_workflow() {
    local root="$1" file="$2" wfname="$3" lanes="${4:-}"
    {
      printf 'name: %s\n' "$wfname"
      printf 'jobs:\n  %s:\n    steps:\n' "$wfname"
      printf '      # prose mentioning COMPOSITION_LANES: must never be parsed as an assignment\n'
      [[ -n "$lanes" ]] && printf '      env:\n        COMPOSITION_LANES: %s\n' "$lanes"
      printf '      run: tests/composition/run.sh\n'
    } >"$root/.github/workflows/$file"
  }
  # _lc_expect <expected-rc> <root>
  _lc_expect() {
    local want="$1" root="$2"
    n=$((n + 1))
    lane_coverage_findings "$root/tests/composition" "$root" >/dev/null 2>&1
    [[ "$?" == "$want" ]] || fails=$((fails + 1))
  }

  local root
  COMPOSITION_LANE_DEFERRALS=()

  # 1. Whole: three lanes, a required workflow that narrows nothing. The default IS the universe.
  root="$(_lc_fixture whole a b c)"
  _lc_workflow "$root" composition.yml composition ''
  _lc_expect 0 "$root"

  # 2. THE #379 DEFECT ITSELF: a lane on disk the required check's list does not name.
  root="$(_lc_fixture narrowed a b c)"
  _lc_workflow "$root" composition.yml composition 'a b'
  _lc_expect 1 "$root"

  # 3. …and it is the LANE that is missed, not merely "a list exists": naming all three passes.
  root="$(_lc_fixture listed a b c)"
  _lc_workflow "$root" composition.yml composition 'a b c'
  _lc_expect 0 "$root"

  # 3b. THE SAME DEFECT ONE LEVEL OVER: the required check reaches every lane (it pins no list at
  #     all), and a SECOND caller — the release gate, whose acceptance is "all identities" — pins a
  #     hand-written list that has fallen behind. Discovery cannot save that one, so it is graded.
  root="$(_lc_fixture sibling_narrowed a b c)"
  _lc_workflow "$root" composition.yml composition ''
  _lc_workflow "$root" release.yml release 'a b'
  _lc_expect 1 "$root"

  # 4. A registered deferral clears it — but ONLY with another caller actually running the lane.
  root="$(_lc_fixture deferred a b c)"
  _lc_workflow "$root" composition.yml composition 'a b'
  _lc_workflow "$root" release.yml release 'a b c'
  COMPOSITION_LANE_DEFERRALS=("c|measured at 41m against a 30m budget, see #379")
  _lc_expect 0 "$root"

  # 5. A DEFERRAL IS NOT A DELETION: same registry, no other caller reaching the lane.
  root="$(_lc_fixture deferred_orphan a b c)"
  _lc_workflow "$root" composition.yml composition 'a b'
  _lc_expect 1 "$root"

  # 6. A deferral whose reason names no issue is not a decision.
  root="$(_lc_fixture deferred_unreasoned a b c)"
  _lc_workflow "$root" composition.yml composition 'a b'
  _lc_workflow "$root" release.yml release 'a b c'
  COMPOSITION_LANE_DEFERRALS=("c|it is slow")
  _lc_expect 1 "$root"

  # 7. A stale deferral for a lane that no longer exists is a standing exemption for a free name.
  root="$(_lc_fixture deferred_stale a b)"
  _lc_workflow "$root" composition.yml composition ''
  COMPOSITION_LANE_DEFERRALS=("c|retired, see #379")
  _lc_expect 1 "$root"

  # 8. A deferral for a lane every caller runs anyway — registry and workflows disagreeing.
  root="$(_lc_fixture deferred_contradicted a b)"
  _lc_workflow "$root" composition.yml composition 'a b'
  COMPOSITION_LANE_DEFERRALS=("b|deferred on paper only, see #379")
  _lc_expect 1 "$root"

  COMPOSITION_LANE_DEFERRALS=()

  # 9. A caller naming a lane that does not exist — the typo #349 catches at run time, caught
  #    statically here and in EVERY caller, not only the one this invocation runs.
  root="$(_lc_fixture typo a b)"
  _lc_workflow "$root" composition.yml composition 'a b'
  _lc_workflow "$root" release.yml release 'a b fable-games'
  _lc_expect 1 "$root"

  # 10. The required workflow renamed out from under the protected context.
  root="$(_lc_fixture renamed a b)"
  _lc_workflow "$root" composition.yml composition-suite ''
  _lc_expect 1 "$root"

  # 11. The required workflow still exists but no longer invokes the suite.
  root="$(_lc_fixture detached a b)"
  printf 'name: composition\njobs:\n  composition:\n    steps:\n      run: echo hi\n' \
    >"$root/.github/workflows/composition.yml"
  _lc_expect 1 "$root"

  # 12. The required workflow is gone entirely.
  root="$(_lc_fixture absent a b)"
  _lc_expect 1 "$root"

  # 13. Discovery returning nothing is a BROKEN gate, never a covered repo — the fail-open that
  #     would make every case above pass vacuously.
  root="$(_lc_fixture empty)"
  _lc_workflow "$root" composition.yml composition ''
  _lc_expect 1 "$root"

  # 14–15. THE ASSERTION'S OWN ok/bad MAPPING. Without these, `else bad` → `else ok` passes 1–13.
  local p0="$PASS" f0="$FAIL"
  root="$(_lc_fixture map_bad a b c)"
  _lc_workflow "$root" composition.yml composition 'a b'
  assert_lane_coverage "$root/tests/composition" "$root" >/dev/null 2>&1
  n=$((n + 1)); [[ "$FAIL" == "$((f0 + 1))" ]] || fails=$((fails + 1))
  root="$(_lc_fixture map_ok a b c)"
  _lc_workflow "$root" composition.yml composition ''
  assert_lane_coverage "$root/tests/composition" "$root" >/dev/null 2>&1
  n=$((n + 1)); [[ "$PASS" == "$((p0 + 1))" && "$FAIL" == "$((f0 + 1))" ]] || fails=$((fails + 1))
  PASS="$p0"; FAIL="$f0"

  COMPOSITION_LANE_DEFERRALS=()
  [[ "${#saved_deferrals[@]}" -gt 0 ]] && COMPOSITION_LANE_DEFERRALS=("${saved_deferrals[@]}")
  unset -f _lc_fixture _lc_workflow _lc_expect

  if (( fails == 0 )); then
    ok "$label: the unreached-lane gate can FIRE — driven offline through all $n outcomes: a whole repo, the #379 defect itself (a lane on disk the required check does not name), the same defect in a SIBLING caller whose pinned list fell behind, a deferral that clears it only while some caller still runs the lane, a deferral that is a deletion, one with no issue, a stale one, one every workflow contradicts, a caller naming a lane that does not exist, the required workflow renamed / detached from the suite / absent, an empty discovery, and the assertion's own ok+bad counter mapping"
  else
    bad "$label: the unreached-lane gate is BROKEN — $fails of its $n outcomes did not reproduce, so the coverage verdict below is not evidence of anything. Fix lane_coverage_findings / lane_workflow_selection / assert_lane_coverage; do NOT delete this self-demonstration (#379)"
  fi
}
