# shellcheck shell=bash
# ── The Game Skills release reaching a game scaffold: asserted, and NAMED (FS.GG.Templates#349) ──
#
# THE ACCEPTANCE CRITERION THIS DISCHARGES. #349 requires that "the exact Game Skills release is
# pinned and proven through the production SDD materializer before publication". Before this file
# nothing in this repository mentioned `FS.GG.Game.Skills` at all — a repo-wide grep for
# `Game.Skills` / `game-skills` / `GameSkill` matched one incidental log FILENAME in run.sh and
# nothing else — so the criterion had no executable home and the release would have been cut on an
# unrecorded claim.
#
# ── WHICH ROUTE THIS IS, BECAUSE THE OBVIOUS GUESS IS WRONG AND COSTS AN HOUR ────────────────────
#
# It is NOT the fable-game identity. A product scaffolded through providers/fable-game.providers.yml
# receives ZERO Game Skills, BY DESIGN, and that is not a defect to file:
#
#   * every row in the `FS.GG.Game.Skills` producer manifest gates on
#     `materializes-when: profile in [game, sample-pack]`;
#   * `dotnet new fs-gg-fable-game` has NO `--profile` option, so the parameter can never hold —
#     supplying `--param profile=game` does not repair it, it makes the provider exit 127
#     (`Error: Invalid option(s): --profile`) and the scaffold reports `blocked`;
#   * closed FS.GG.Templates#264 records the decision that put it that way: "game skills reach a
#     game scaffold via owner-sourcing (FS.GG.SDD#622), so FS.GG.Templates gains NO
#     game.providers.yml".
#
#   Measured 2026-08-04: `fsgg-sdd scaffold --provider fable-game … --json` →
#   `scaffold.materializedGameSkillPaths: []`, exit 0, no diagnostic. The fable-game identity's
#   owner-sourced skills are this repo's own five `fable-*` rows, which its own lane already
#   asserts through both the direct and the provider route.
#
# The production materializer route is the RENDERING provider — providers/rendering.providers.yml,
# whose `profile` parameter defaults to `game` — which stage 05 already scaffolds as its composed
# product. Through it the materializer delivered 11 Game Skills into both skill roots, including
# `fs-gg-game-fable`, the FS.GG.Game#552 deliverable that is a declared blocker of #349. That is why
# this assertion hangs off the stage-5 composed product and not off a lane of its own: the scaffold
# it needs is already there, so the whole criterion costs one JSON report and a small download.
#
# ── WHY THIS NAMES A RELEASE INSTEAD OF PINNING A DIGEST ─────────────────────────────────────────
#
# The delivered bytes are NOT this repository's to pin. `fsgg-sdd` embeds the pinned
# `FS.GG.Game.Skills` package as assembly resources at ITS OWN build time (FS.GG.SDD
# src/FS.GG.SDD.Commands/CommandWorkflow/GameSkills.fs — "the materialize reads compiled-in bytes,
# never the NuGet cache, an owner-repo clone, or the network"), and this suite deliberately FLOATS
# `fsgg-sdd` to latest stable rather than pinning it (#317, whose decision block in
# .github/workflows/composition.yml argues the case at length). A frozen expected digest here would
# therefore be a hand-frozen number with no registry authority behind it — precisely what #317
# refused — and it would red the required check on the day FS.GG.SDD ships a build embedding a
# newer Game Skills release, punishing an upstream advance for being an advance.
#
# So this takes #317's own shape, one axis over: FLOAT, ASSERTED, AND NAMED.
#
#   ASSERTED (fails closed, needs no network): the materializer delivered a NON-EMPTY Game Skills
#   set, and `fs-gg-game-fable` is in it. That is the load-bearing half. The regression it exists to
#   catch is a silent one — an upstream predicate, parameter-name or manifest change that stops
#   delivering owner-sourced game guidance would leave every existing assertion in this suite green,
#   because they all grade the product against the manifest the materializer ITSELF wrote. A
#   materializer that delivers nothing writes a manifest declaring nothing, and a cross-check of
#   nothing against nothing passes.
#
#   NAMED: resolve WHICH published release those bytes are, by content, and print it. A drift then
#   arrives with the version already in the log instead of having to be reconstructed from publish
#   dates — the same reasoning #317 gives for printing the resolved CLI version.
#
# ── WHAT THE NAMING MEASURED WHEN IT WAS WRITTEN, AND WHY THE ANSWER IS NOT THE LATEST ───────────
#
# Resolved release: `FS.GG.Game.Skills` 0.7.0 — NOT the published-latest 0.8.0. The discriminator is
# `fs-gg-mapcraft`: 0.7.0 and 0.8.0 differ in exactly two files (`skill-manifest.json` and
# `skills/fs-gg-mapcraft/SKILL.md`), and of the 11 materialized bodies all 11 match 0.7.0 while only
# 10 match 0.8.0. The pin sits upstream at FS.GG.SDD `Directory.Packages.local.props:18`
# (`<PackageVersion Include="FS.GG.Game.Skills" Version="0.7.0" />`), embedded into `fsgg-sdd` 1.0.0
# at its build commit 5188f6289d897d8b67490283e57b3362edceea32 (its .nuspec `<repository commit=…>`).
#
# That lag is RECORDED, not gated. `fs-gg-game-fable` — the row #349 actually depends on — is
# byte-identical in 0.7.0 and 0.8.0, so nothing this item claims is affected, and a gate that reds
# because upstream has not yet rebuilt against a newer owner package would be asserting a coherence
# rule no registry declares (there is no coherent-set ceiling for this axis either; see #317 (1)(b)).
# If one is ever declared, assert against it HERE, the same way the `minimumFsggSdd` floor is
# asserted — do not hand-freeze a version in the meantime.
#
# ── WHAT A GREEN HERE DOES NOT MEAN ──────────────────────────────────────────────────────────────
#
# It does not say the delivered guidance is CORRECT, only that it is present, complete against a
# real published release, and identified. It says nothing about the fable-game identity, which by
# the decision above receives none of these rows. And it grades the composed product this run
# produced — if stage 5 skipped (no `fsgg-sdd` on PATH), there is no product and this reports a skip
# rather than a pass, because "could not look" is never "looked, and fine" (epic .github#266).

GAME_SKILLS_PACKAGE_ID="FS.GG.Game.Skills"
GAME_SKILLS_FLATCONTAINER="https://api.nuget.org/v3-flatcontainer/fs.gg.game.skills"
# A SAFETY CEILING ON A PATHOLOGICAL FEED — NOT A SEARCH WINDOW, and the distinction is the whole
# point of this constant (repair round 1, FS.GG.Templates#395).
#
# The first cut of this file searched the newest THREE releases. That was a defect, and a subtle one:
# the release it has to find (0.7.0) already sat at depth two, so ONE publish would have pushed it
# out of the window and reddened the required check with "matches NO published release" — blaming
# upstream packaging drift for what was purely an artifact of how far this file chose to look. The
# measured cadence is 8 releases in 14 days, including three same-day pairs, and only an FS.GG.SDD
# rebuild can pull the resolved release back toward the head — which this repository does not
# control. So the bound reintroduced, one level down, exactly the coupling that choosing to NAME a
# release instead of freezing a digest was meant to remove.
#
# The fix is not a bigger number, it is searching the whole published set: the resolution now walks
# EVERY published release, newest-first, and this ceiling exists only so a feed that has grown
# absurd cannot make the step unbounded. Measured 2026-08-04: the complete set is 8 releases,
# downloaded and unpacked in **1.99s** totalling 4.2 MB — against a job that already runs `npm ci`
# twice, several restores, a Vite build and Playwright. Depth is therefore free here, which is why
# the trade the first cut made was not worth making.
#
# If this ceiling is ever REACHED, that is a different fact from "no release matched", and the two
# get different messages below — a gate whose failure names the wrong cause sends the next reader
# upstream for nothing.
GAME_SKILLS_MAX_RELEASES="${GAME_SKILLS_MAX_RELEASES:-40}"

# Set by game_skill_fetch_releases so the assertion can NAME the window it actually searched rather
# than asserting over a set the reader cannot see.
GAME_SKILLS_WINDOW=""            # the versions actually COMPARED, newest-first, space-separated
GAME_SKILLS_PUBLISHED_COUNT=0    # how many versions the feed index listed
GAME_SKILLS_CEILING_HIT=0        # 1 when the ceiling stopped the walk early
GAME_SKILLS_SKIPPED=""           # versions the feed listed but this run could not download/unpack
# The one row #349 depends on: FS.GG.Game#552's Game.Core Fable lockstep skill, a declared blocker
# of this item. Named as a constant so a rename upstream reds HERE, where the dependency is
# recorded, rather than silently reducing the delivered set by one.
GAME_SKILLS_REQUIRED_ID="fs-gg-game-fable"

# game_skill_ids_from_report <scaffold-report.json>
# The materializer's OWN answer for which rows it delivered, read from
# `scaffold.materializedGameSkillPaths`. Deliberately not a directory listing: the composed product's
# .agents/skills/ also holds this repo's rows, the seeded fs-gg-sdd-* set and the template's own UI
# skills, and only the report can tell the owner-sourced rows apart from their co-tenants. Paths
# arrive once per skill ROOT (.agents/skills/ and .claude/skills/), so the ids are deduplicated.
game_skill_ids_from_report() {
  jq -r '(.scaffold.materializedGameSkillPaths // [])[]' "$1" 2>/dev/null |
    sed -nE 's#.*/skills/([^/]+)/SKILL\.md$#\1#p' | sort -u
}

# game_skill_release_match_local <materialized-skills-dir> <releases-dir> <id>...
# PURE, OFFLINE, and the reason the self-demonstration below can drive every outcome without a
# network or a scaffold. <releases-dir> holds one directory per candidate version, each laid out as
# the package is: <version>/game-skills/skills/<id>/SKILL.md.
#
# Prints EVERY matching version, newest first — not just the first. Two releases that are
# byte-identical over the materialized set genuinely cannot be told apart by these bytes, and
# printing one of them would be a precision the evidence does not support.
#   rc 0 = at least one release matches   rc 2 = no ids supplied   rc 3 = no release matches
game_skill_release_match_local() {
  local materialized="$1" releases="$2"; shift 2
  local -a ids=("$@")
  [[ ${#ids[@]} -gt 0 ]] || return 2

  local -a matched=()
  local version id want got
  while IFS= read -r version; do
    [[ -n "$version" ]] || continue
    local all=1
    for id in "${ids[@]}"; do
      want="$materialized/$id/SKILL.md"
      got="$releases/$version/game-skills/skills/$id/SKILL.md"
      if [[ ! -f "$want" || ! -f "$got" ]] ||
         [[ "$(sha256sum <"$want" | cut -d' ' -f1)" != "$(sha256sum <"$got" | cut -d' ' -f1)" ]]; then
        all=0; break
      fi
    done
    [[ "$all" == "1" ]] && matched+=("$version")
  done < <(find "$releases" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -Vr)

  [[ ${#matched[@]} -gt 0 ]] || return 3
  printf '%s\n' "${matched[@]}"
}

# game_skill_fetch_releases <dest-dir> [ceiling]
# Download and unpack EVERY published FS.GG.Game.Skills release, newest-first, into the layout
# game_skill_release_match_local expects — see GAME_SKILLS_MAX_RELEASES for why this is a full walk
# and not a window. Records what it searched in GAME_SKILLS_WINDOW / _PUBLISHED_COUNT / _CEILING_HIT
# so every failure arm can name the searched set instead of leaving the reader to guess it.
game_skill_fetch_releases() {
  local dest="$1" ceiling="${2:-$GAME_SKILLS_MAX_RELEASES}" version count=0
  mkdir -p "$dest"
  GAME_SKILLS_WINDOW=""; GAME_SKILLS_PUBLISHED_COUNT=0; GAME_SKILLS_CEILING_HIT=0; GAME_SKILLS_SKIPPED=""

  local index; index="$(curl -fsSL --max-time 30 "$GAME_SKILLS_FLATCONTAINER/index.json" 2>/dev/null)" || return 1
  local -a published=()
  mapfile -t published < <(printf '%s' "$index" | jq -r '.versions[]?' 2>/dev/null | sort -Vr)
  GAME_SKILLS_PUBLISHED_COUNT="${#published[@]}"

  for version in "${published[@]}"; do
    [[ -n "$version" ]] || continue
    if [[ "$count" -ge "$ceiling" ]]; then GAME_SKILLS_CEILING_HIT=1; break; fi
    local pkg="$dest/$version.nupkg"
    # A release this run could not FETCH is recorded, never merely skipped. Losing it here is what
    # let a one-release network blip masquerade as a complete search — see the completeness
    # predicate below (repair round 2).
    if ! curl -fsSL --max-time 60 \
         "$GAME_SKILLS_FLATCONTAINER/$version/fs.gg.game.skills.$version.nupkg" -o "$pkg" 2>/dev/null; then
      GAME_SKILLS_SKIPPED="${GAME_SKILLS_SKIPPED:+$GAME_SKILLS_SKIPPED }$version"; continue
    fi
    mkdir -p "$dest/$version"
    if ! unzip -q -o "$pkg" -d "$dest/$version" 2>/dev/null; then
      GAME_SKILLS_SKIPPED="${GAME_SKILLS_SKIPPED:+$GAME_SKILLS_SKIPPED }$version"; continue
    fi
    rm -f "$pkg"
    GAME_SKILLS_WINDOW="${GAME_SKILLS_WINDOW:+$GAME_SKILLS_WINDOW }$version"
    count=$((count+1))
  done
  [[ "$count" -gt 0 ]]
}

# game_skill_search_is_complete
# THE COMPLETENESS PREDICATE, and the reason it is a function rather than an inline test.
#
# Round 1 asked whether the CEILING had been hit. That is not the same question as whether the whole
# published set was compared, and the gap between them was a defect: `curl … || continue` skipped a
# release that failed to download WITHOUT setting the ceiling flag, so a run that compared 7 of 8
# releases took the complete-search branch and announced "all 7 published release(s)" — silently
# redefining "all" to mean "the ones that happened to download". Worse, the complete-search arm is
# the one that points UPSTREAM, so a transient network blip on a single release produced a confident
# accusation that FS.GG.SDD had been built against an unpublished Game Skills build. That is the
# exact misdirection round 1 existed to remove, reintroduced through a different door and carrying a
# stronger sentence than before.
#
# So completeness is now the only thing it can honestly be: the number of releases actually compared
# equals the number the feed index listed. Both numbers were already in scope; asking the wrong one
# was the whole bug. A zero published count is NOT complete either — that is "could not look".
game_skill_search_is_complete() {
  local searched; searched="$(game_skill_searched_count)"
  [[ "$GAME_SKILLS_PUBLISHED_COUNT" -gt 0 && "$searched" -eq "$GAME_SKILLS_PUBLISHED_COUNT" ]]
}

game_skill_searched_count() { printf '%s' "$GAME_SKILLS_WINDOW" | wc -w | tr -d ' '; }

# game_skill_window_description
# One phrase naming exactly what was searched. Three outcomes, not two, because "we stopped early at
# our own ceiling" and "some releases would not download" are different facts with different repairs,
# and neither is "we compared everything".
game_skill_window_description() {
  local searched; searched="$(game_skill_searched_count)"
  if game_skill_search_is_complete; then
    printf 'all %s published release(s) — %s' "$searched" "$GAME_SKILLS_WINDOW"
  elif [[ "$GAME_SKILLS_CEILING_HIT" == "1" ]]; then
    printf 'the newest %s of %s published release(s) — %s — TRUNCATED at the GAME_SKILLS_MAX_RELEASES=%s safety ceiling' \
      "$searched" "$GAME_SKILLS_PUBLISHED_COUNT" "$GAME_SKILLS_WINDOW" "$GAME_SKILLS_MAX_RELEASES"
  else
    printf '%s of %s published release(s) — %s — INCOMPLETE: could not download %s' \
      "$searched" "$GAME_SKILLS_PUBLISHED_COUNT" "$GAME_SKILLS_WINDOW" "${GAME_SKILLS_SKIPPED:-<unrecorded>}"
  fi
}

# assert_game_skill_materialization <product-root> <scaffold-report.json> <lane>
# The assertion #349's sixth acceptance criterion is discharged by.
assert_game_skill_materialization() {
  local product="$1" report="$2" lane="$3"

  if [[ ! -f "$report" ]]; then
    bad "$lane: no scaffold report at $report — the Game Skills materialization claim has NO evidence this run. The report is what distinguishes owner-sourced rows from their co-tenants in .agents/skills/, so without it a green here would cover nothing (#349)."
    return
  fi

  local -a ids=()
  mapfile -t ids < <(game_skill_ids_from_report "$report")

  if [[ ${#ids[@]} -eq 0 ]]; then
    bad "$lane: the production SDD materializer delivered NO Game Skills into the composed product — 'scaffold.materializedGameSkillPaths' is empty. The rendering provider defaults 'profile' to 'game' (providers/rendering.providers.yml), so every FS.GG.Game.Skills row's 'materializes-when: profile in [game, sample-pack]' should hold. This is the SILENT regression class: every other skill assertion in this suite grades the product against the manifest the materializer itself wrote, so a materializer delivering nothing writes a manifest declaring nothing and they all stay green. Check the resolved fsgg-sdd version printed by the composition workflow, and whether the provider still supplies 'profile' (#349)."
    return
  fi

  local have_required=0 id
  for id in "${ids[@]}"; do [[ "$id" == "$GAME_SKILLS_REQUIRED_ID" ]] && have_required=1; done
  if [[ "$have_required" != "1" ]]; then
    bad "$lane: the materializer delivered ${#ids[@]} Game Skill(s) but NOT '$GAME_SKILLS_REQUIRED_ID' — the FS.GG.Game#552 Game.Core Fable lockstep row, a declared blocker of #349. Delivered: ${ids[*]}. Either the row was renamed upstream (fix this constant in the same change that adopts the rename) or its predicate stopped holding for the rendering provider's 'profile=game' default (#349)."
    return
  fi

  local skills_root="$product/.agents/skills"
  if [[ ! -d "$skills_root" ]]; then
    bad "$lane: the scaffold report names ${#ids[@]} materialized Game Skill(s) but the composed product has no $skills_root to read them from (#349)."
    return
  fi

  local releases; releases="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-game-skills.XXXXXX")"
  if ! game_skill_fetch_releases "$releases"; then
    rm -rf "$releases"
    bad "$lane: could not read ANY published $GAME_SKILLS_PACKAGE_ID release from nuget.org, so the delivered bytes cannot be identified. This run FAILS rather than passing on the un-named half: an unreadable answer is 'could not look', and 'could not look' is never 'looked, and fine' (epic .github#266). The presence half above still holds. Note this job already restores from nuget.org, so this is very unlikely to be an isolated outage — check egress to api.nuget.org, and that curl/unzip/jq are present."
    return
  fi

  local -a matched=()
  mapfile -t matched < <(game_skill_release_match_local "$skills_root" "$releases" "${ids[@]}")
  local rc=$?
  rm -rf "$releases"

  if [[ "$rc" != "0" || ${#matched[@]} -eq 0 ]]; then
    local window; window="$(game_skill_window_description)"
    if ! game_skill_search_is_complete; then
      # The searched set was INCOMPLETE — the ceiling stopped the walk, or releases would not
      # download. Either way "no release matched" is not yet a statement about upstream at all: the
      # release that matches may be one this run never compared. Name that first, and name the
      # cause, rather than sending the reader upstream for an artifact of our own search.
      local why="the search was CUT SHORT by this file's own safety ceiling, so the release that matches may simply lie deeper than this run looked. Raise GAME_SKILLS_MAX_RELEASES (it is a guard against an absurd feed, not a search window; the full set was 8 releases / 3.2-4.2 MB / ~1-2s when this was written) and re-run"
      [[ "$GAME_SKILLS_CEILING_HIT" == "1" ]] || why="this run could not DOWNLOAD every published release (${GAME_SKILLS_SKIPPED:-<unrecorded>}), so the release that matches may be one it never compared. That is a fetch failure — most likely transient — not a fact about the bytes. Re-run, and check egress to api.nuget.org"
      bad "$lane: the ${#ids[@]} materialized Game Skill body(ies) match none of $window. This is NOT evidence of upstream drift: $why before concluding anything about $GAME_SKILLS_PACKAGE_ID. Delivered ids: ${ids[*]} (#349)."
    else
      # The COMPLETE published set was searched, so this genuinely is a statement about the bytes.
      bad "$lane: the ${#ids[@]} materialized Game Skill body(ies) match NO published $GAME_SKILLS_PACKAGE_ID release, having searched $window. The complete published set was compared, so this is not a search-depth artifact: the bytes a generated product is being handed correspond to no release anyone can name, and #349's criterion — the EXACT release, proven — cannot be satisfied. Most likely fsgg-sdd was built against an unpublished Game Skills build, or a body drifted between pack and publish. Delivered ids: ${ids[*]} (#349)."
    fi
    return
  fi

  # The searched set is named on the PASS arms too, not only the failures: "matched 0.7.0" means
  # something different when 8 releases were compared than when 3 were, and a reader cannot tell
  # which they are looking at unless the verdict says so.
  local resolved="${matched[0]}" window; window="$(game_skill_window_description)"
  if [[ ${#matched[@]} -gt 1 ]]; then
    ok "$lane: the production SDD materializer delivered ${#ids[@]} Game Skill(s) including '$GAME_SKILLS_REQUIRED_ID'; their bytes match published $GAME_SKILLS_PACKAGE_ID ${matched[*]} — indistinguishable over THIS set, so the release is named as the set rather than guessed at; searched $window (#349)"
  else
    ok "$lane: the production SDD materializer delivered ${#ids[@]} Game Skill(s) including '$GAME_SKILLS_REQUIRED_ID'; every body is byte-identical to published $GAME_SKILLS_PACKAGE_ID $resolved — the exact release reaching a game scaffold, resolved by content against $window (#349)"
  fi

  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      echo "### composition — Game Skills release reaching a game scaffold"
      echo
      echo "Resolved by content from the composed product, not declared here (#349, #317's float-and-name shape)."
      echo
      echo "| fact | value |"
      echo "|---|---|"
      echo "| package | \`$GAME_SKILLS_PACKAGE_ID\` |"
      echo "| resolved release | \`${matched[*]}\` |"
      echo "| rows delivered | ${#ids[@]} — \`${ids[*]}\` |"
      echo "| route | \`providers/rendering.providers.yml\` (\`profile\` defaults to \`game\`) |"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
}

# assert_game_skill_alarms_can_fire <lane>
# The self-demonstration. Every alarm above is driven offline over fixtures, because an assertion
# whose failure path has never executed is not evidence — the same discipline lane-coverage.sh and
# skill-union.sh already carry. It restores the PASS/FAIL counters afterwards so the demonstration
# scores exactly one verdict of its own.
assert_game_skill_alarms_can_fire() {
  local lane="$1" p0="$PASS" f0="$FAIL" fails=0
  local work; work="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-game-skills-demo.XXXXXX")"

  local mat="$work/materialized" rel="$work/releases"
  mkdir -p "$mat/fs-gg-game-fable" "$mat/fs-gg-mapcraft"
  printf 'lockstep body\n' >"$mat/fs-gg-game-fable/SKILL.md"
  printf 'mapcraft body v7\n' >"$mat/fs-gg-mapcraft/SKILL.md"

  # 0.7.0 carries both bodies as materialized; 0.8.0 differs in fs-gg-mapcraft ONLY — the real
  # 0.7.0/0.8.0 relationship, so the discriminating-row case is exercised, not imagined.
  mkdir -p "$rel/0.7.0/game-skills/skills/fs-gg-game-fable" "$rel/0.7.0/game-skills/skills/fs-gg-mapcraft"
  printf 'lockstep body\n' >"$rel/0.7.0/game-skills/skills/fs-gg-game-fable/SKILL.md"
  printf 'mapcraft body v7\n' >"$rel/0.7.0/game-skills/skills/fs-gg-mapcraft/SKILL.md"
  mkdir -p "$rel/0.8.0/game-skills/skills/fs-gg-game-fable" "$rel/0.8.0/game-skills/skills/fs-gg-mapcraft"
  printf 'lockstep body\n' >"$rel/0.8.0/game-skills/skills/fs-gg-game-fable/SKILL.md"
  printf 'mapcraft body v8\n' >"$rel/0.8.0/game-skills/skills/fs-gg-mapcraft/SKILL.md"

  local out rc

  # 1. The discriminating row resolves a UNIQUE release, and it is not the newest.
  out="$(game_skill_release_match_local "$mat" "$rel" fs-gg-game-fable fs-gg-mapcraft)"; rc=$?
  [[ "$rc" == "0" && "$out" == "0.7.0" ]] || { fails=$((fails+1)); }

  # 2. Drop the discriminator and the two releases are honestly indistinguishable — BOTH reported,
  #    newest first, rather than one of them guessed at.
  out="$(game_skill_release_match_local "$mat" "$rel" fs-gg-game-fable)"; rc=$?
  [[ "$rc" == "0" && "$out" == "$(printf '0.8.0\n0.7.0')" ]] || { fails=$((fails+1)); }

  # 3. No ids at all — the empty-materialization case, kept distinct from "matched nothing".
  game_skill_release_match_local "$mat" "$rel" >/dev/null 2>&1; rc=$?
  [[ "$rc" == "2" ]] || { fails=$((fails+1)); }

  # 4. A drifted body matches NO release (rc 3, not rc 0 with an empty list, and not rc 2).
  printf 'tampered\n' >"$mat/fs-gg-mapcraft/SKILL.md"
  game_skill_release_match_local "$mat" "$rel" fs-gg-game-fable fs-gg-mapcraft >/dev/null 2>&1; rc=$?
  [[ "$rc" == "3" ]] || { fails=$((fails+1)); }
  printf 'mapcraft body v7\n' >"$mat/fs-gg-mapcraft/SKILL.md"

  # 5. An id the materializer named but the product does not carry is a MISS, never a silent skip.
  game_skill_release_match_local "$mat" "$rel" fs-gg-game-fable fs-gg-absent >/dev/null 2>&1; rc=$?
  [[ "$rc" == "3" ]] || { fails=$((fails+1)); }

  # 6. The report reader: ids are deduplicated across the two skill roots, and a report carrying an
  #    empty array reads as zero ids rather than as one empty id.
  local report="$work/report.json"
  cat >"$report" <<'JSON'
{"scaffold":{"materializedGameSkillPaths":[
  ".agents/skills/fs-gg-game-fable/SKILL.md",".claude/skills/fs-gg-game-fable/SKILL.md",
  ".agents/skills/fs-gg-mapcraft/SKILL.md",".claude/skills/fs-gg-mapcraft/SKILL.md"]}}
JSON
  out="$(game_skill_ids_from_report "$report")"
  [[ "$out" == "$(printf 'fs-gg-game-fable\nfs-gg-mapcraft')" ]] || { fails=$((fails+1)); }
  printf '{"scaffold":{"materializedGameSkillPaths":[]}}' >"$report"
  [[ -z "$(game_skill_ids_from_report "$report")" ]] || { fails=$((fails+1)); }
  # A report with no scaffold section at all reads as zero ids rather than erroring the run.
  printf '{}' >"$report"
  [[ -z "$(game_skill_ids_from_report "$report")" ]] || { fails=$((fails+1)); }

  # 7. The window description tells a COMPLETE search from a TRUNCATED one, because the two carry
  #    different causes and different repairs (repair round 1). Driven over the globals directly:
  #    they are what every failure arm reads, so this is the assertion's own view of them.
  local w0="$GAME_SKILLS_WINDOW" c0="$GAME_SKILLS_PUBLISHED_COUNT" h0="$GAME_SKILLS_CEILING_HIT" s0="$GAME_SKILLS_SKIPPED"
  GAME_SKILLS_WINDOW="0.8.0 0.7.0"; GAME_SKILLS_PUBLISHED_COUNT=2; GAME_SKILLS_CEILING_HIT=0; GAME_SKILLS_SKIPPED=""
  out="$(game_skill_window_description)"
  [[ "$out" == "all 2 published release(s) — 0.8.0 0.7.0" ]] || { fails=$((fails+1)); }
  game_skill_search_is_complete || { fails=$((fails+1)); }
  GAME_SKILLS_PUBLISHED_COUNT=9; GAME_SKILLS_CEILING_HIT=1
  out="$(game_skill_window_description)"
  # It must say TRUNCATED, and it must name both the searched count and the published total — a
  # message that reported only "2 searched" would read as a complete search of a 2-release feed.
  [[ "$out" == *TRUNCATED* && "$out" == *"newest 2 of 9"* ]] || { fails=$((fails+1)); }
  ! game_skill_search_is_complete || { fails=$((fails+1)); }

  # THE GAP CASE — searched < published WITHOUT the ceiling being hit (repair round 2). This is what
  # a failed download actually produces, and the previous corpus could not reach it: every fixture
  # set the two counts EQUAL, so an implementation that asked `CEILING_HIT == 0`, or that printed
  # PUBLISHED_COUNT where it meant `searched`, was indistinguishable from a correct one (.github#2223
  # fixture shape). The counts are deliberately DIFFERENT and the skipped version is named.
  GAME_SKILLS_WINDOW="0.8.0 0.6.0"; GAME_SKILLS_PUBLISHED_COUNT=3; GAME_SKILLS_CEILING_HIT=0
  GAME_SKILLS_SKIPPED="0.7.0"
  out="$(game_skill_window_description)"
  # Not complete: a gap is not a complete search, however many releases were compared.
  ! game_skill_search_is_complete || { fails=$((fails+1)); }
  # Must NOT claim "all", must report 2 of 3 (NOT 3 of 3 — the mutation that survived round 1 was
  # printing PUBLISHED_COUNT where `searched` was meant, which only equal fixtures could hide), must
  # say INCOMPLETE rather than TRUNCATED, and must name the release it could not download.
  [[ "$out" != all* ]] || { fails=$((fails+1)); }
  [[ "$out" == "2 of 3 published release(s) — 0.8.0 0.6.0 — INCOMPLETE: could not download 0.7.0" ]] || { fails=$((fails+1)); }

  # An empty feed read is "could not look", never a complete search of nothing.
  GAME_SKILLS_WINDOW=""; GAME_SKILLS_PUBLISHED_COUNT=0; GAME_SKILLS_CEILING_HIT=0; GAME_SKILLS_SKIPPED=""
  ! game_skill_search_is_complete || { fails=$((fails+1)); }
  GAME_SKILLS_WINDOW="$w0"; GAME_SKILLS_PUBLISHED_COUNT="$c0"; GAME_SKILLS_CEILING_HIT="$h0"; GAME_SKILLS_SKIPPED="$s0"

  rm -rf "$work"
  PASS="$p0"; FAIL="$f0"
  if [[ "$fails" == "0" ]]; then
    ok "$lane: the Game Skills release resolver's alarms can FIRE — driven offline through a unique resolve on a discriminating row, an honestly ambiguous pair reported as both, the no-ids and no-match codes kept distinct, a drifted body, an absent body, the report reader's dedupe/empty/missing-section arms, and the completeness predicate across all four window shapes: complete, ceiling-truncated, a download GAP whose searched count is deliberately unequal to the published total, and an empty feed read (#349)"
  else
    bad "$lane: the Game Skills release resolver is BROKEN — $fails of its outcomes did not reproduce, so the release named below is not evidence of anything. Fix game_skill_release_match_local / game_skill_ids_from_report; do NOT delete this self-demonstration (#349)"
  fi
}
