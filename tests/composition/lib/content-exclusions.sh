# shellcheck shell=bash
# ── The template source tree's own build output stays out of git, the package, and the product ──
#                                                          (FS.GG.Templates#386)
#
# THE DEFECT THIS CLOSES. `templates/fs-gg-*/` are not inert file trees — each one is a working
# solution, and each one's README documents a regeneration command that must be run IN that
# directory. Two such commands write a build-output directory INSIDE the template source:
#
#   .nuget/        every one of the four workspace templates sets
#                  `<RestorePackagesPath>$(MSBuildThisFileDirectory).nuget/packages</RestorePackagesPath>`
#                  (#380/#382/#384 — a workspace-private package folder is what makes a committed
#                  `contentHash` enforceable), so the documented
#                  `dotnet restore <Workspace>.slnx --force-evaluate` materializes it: 118M for
#                  fable-game, 75M for web.
#   node_modules/  fs-gg-web and fs-gg-fable-game are npm workspaces with five package.json roots
#                  between them; `npm install` in any of them writes a Playwright/Vite/@babylonjs
#                  closure of hundreds of megabytes.
#
# THREE independent filters constrain what leaves this repository, and before #386 each of them
# admitted at least one of those directories:
#
#   1. `.gitignore`               — named neither, so the documented maintenance action left an
#                                   unignored tree that `git add -A` stages. (`*.nupkg` hides only
#                                   the archives inside such a folder, never the folder: the
#                                   .nuspec/.sha512/lib payload beside them is what git reported.)
#   2. the pack `Exclude`         — `FS.GG.Templates.csproj`'s `templates/**/*` content glob
#                                   excluded only bin/obj, and `NoDefaultExcludes` is `true`, so a
#                                   LOCAL `dotnet pack` after that action packs the tree.
#   3. each template's            — declaring `exclude` REPLACES the engine's default list
#      `sources.exclude`            wholesale. #382's restatement dropped `**/node_modules/**`,
#                                   which the engine HAD; no restatement ever named `.nuget/`,
#                                   which the engine cannot know about because it is created by an
#                                   MSBuild property.
#
# WHY THIS IS A GATE AND NOT A CODE COMMENT. All three filters are DECLARATIONS — one line each, in
# three different files, in three different languages, that nothing executes. `**/node_modules/**`
# is the proof that they rot silently: it was an engine default that a restatement omitted by
# silence, and every check in this repository stayed green. Nothing in CI restores or installs
# inside `templates/` and the release gate packs from a clean checkout, so the published artifact
# was never at risk — which is exactly why no existing signal could ever have noticed. This gate
# manufactures the condition CI never produces.
#
# THE THREE LEGS ARE GRADED INDEPENDENTLY, AND THAT IS DELIBERATE. They are defence in depth: leg 2
# now filters `.nuget/` out of the archive, so a package packed from THIS repository can no longer
# carry one — and a delivery-leg test driven through that archive would therefore pass vacuously,
# for the wrong reason, forever. Leg 3 is instead driven through a FOLDER install
# (`dotnet new install <template-dir>`), which is the same template engine reading the same
# `.template.config/template.json` with leg 2 taken out of the path. Kill either declaration alone
# and exactly one leg reds.
#
# HERMETIC AND NON-MUTATING. The seeded trees are written into a COPY of the working tree under the
# run's WORKDIR (3.9MB, so the copy is cheaper than being clever), never into the caller's checkout;
# the hive is the run's isolated DOTNET_CLI_HOME. Leg 1 needs no files at all — `git check-ignore`
# grades PATHS, so it asks the real repository the real question without writing anything.

# The directory names, and a payload file for each that no OTHER rule already filters. The `.nuget`
# sentinel is deliberately a `.sha512` and not the `.nupkg` beside it in a real package folder:
# `.gitignore`'s `*.nupkg` would hide the archive and leg 1 would then pass without the entry it is
# supposed to be testing (measured — the first sentinel written here did exactly that).
CONTENT_EXCLUSION_SENTINELS=(
  '.nuget/packages/fsgg386.sentinel/1.0.0/fsgg386.sentinel.1.0.0.nupkg.sha512'
  'node_modules/fsgg386-sentinel/index.js'
)
# Anchored on a path SEGMENT: `content/templates/x/.nuget/…` and `Client/node_modules/…` both match,
# a file merely NAMED `nuget-cache` does not.
CONTENT_EXCLUSION_RE='(^|/)(\.nuget|node_modules)/'

# content_exclusion_seed <dir> — write every sentinel under <dir>. Idempotent.
content_exclusion_seed() {
  local dir="$1" rel
  for rel in "${CONTENT_EXCLUSION_SENTINELS[@]}"; do
    mkdir -p "$dir/$(dirname "$rel")"
    printf 'FS.GG.Templates#386 sentinel — this file must never leave the template source tree.\n' \
      >"$dir/$rel"
  done
}

# content_exclusion_entry_offenders <entry-list-file> — package entries that carry an excluded
# directory. Prints them; rc 1 when there is at least one.
content_exclusion_entry_offenders() {
  local hits
  hits="$(grep -E "$CONTENT_EXCLUSION_RE" -- "$1" 2>/dev/null)" || true
  [[ -n "$hits" ]] || return 0
  printf '%s\n' "$hits"
  return 1
}

# content_exclusion_tree_offenders <dir> — excluded directories delivered under <dir>. Prints them;
# rc 1 when there is at least one. It names the DIRECTORY rather than globbing for files inside it,
# so a product carrying an EMPTY `.nuget/` — still the delivery of a directory that must not be
# delivered, and what the engine produces when the folder held only filtered files — is caught.
content_exclusion_tree_offenders() {
  local hits
  hits="$(find "$1" \( -name '.nuget' -o -name 'node_modules' \) -print 2>/dev/null)" || true
  [[ -n "$hits" ]] || return 0
  printf '%s\n' "$hits"
  return 1
}

# content_exclusion_ignore_offenders <repo-root> — sentinel paths under templates/ that git would
# NOT ignore. Prints them; rc 1 when there is at least one. Grades paths, writes nothing.
content_exclusion_ignore_offenders() {
  local root="$1" tdir rel probe missing=''
  for tdir in "$root"/templates/*/; do
    [[ -d "$tdir" ]] || continue
    for rel in "${CONTENT_EXCLUSION_SENTINELS[@]}"; do
      probe="templates/$(basename "$tdir")/$rel"
      git -C "$root" check-ignore -q "$probe" || missing+="$probe"$'\n'
    done
  done
  [[ -n "$missing" ]] || return 0
  printf '%s' "$missing"
  return 1
}

# ── The graded assertions. Every one takes ALREADY-MEASURED input, so the self-demonstration below
# drives these exact functions — including their `else bad` arms — rather than a parallel copy of
# the predicate that a fail-open mutation would leave untouched (the #379 lesson).

# ce_grade_ignores <label> <repo-root>
ce_grade_ignores() {
  local label="$1" root="$2" out
  if out="$(content_exclusion_ignore_offenders "$root")"; then
    ok "$label: .gitignore covers .nuget/ and node_modules/ under every template (leg 1)"
  else
    bad "$label: .gitignore does NOT cover these paths, so the regeneration each template's README documents leaves a tree \`git add -A\` will commit (leg 1, #386):"$'\n'"$out"
  fi
}

# ce_grade_entries <label> <entry-list-file>
ce_grade_entries() {
  local label="$1" entries="$2" out
  if out="$(content_exclusion_entry_offenders "$entries")"; then
    ok "$label: the packed archive carries no .nuget/ or node_modules/ entry (leg 2)"
  else
    bad "$label: the packed archive carries restore/install output — FS.GG.Templates.csproj's content \`Exclude\` stopped filtering it (leg 2, #386):"$'\n'"$out"
  fi
}

# ce_grade_tree <label> <product-dir>
ce_grade_tree() {
  local label="$1" dir="$2" out
  if out="$(content_exclusion_tree_offenders "$dir")"; then
    ok "$label: no .nuget/ or node_modules/ reached the generated product (leg 3)"
  else
    bad "$label: restore/install output reached the generated product — this template's sources.exclude stopped filtering it (leg 3, #386):"$'\n'"$out"
  fi
}

# ── assert_content_exclusions <repo-root> <workdir> ────────────────────────────────────────────
# The real measurement. Costs one `dotnet pack` plus one folder install and one instantiation per
# template that declares a `sources.exclude`; entirely local, no network, no token.
assert_content_exclusions() {
  local root="$1" workdir="$2"
  local scratch="$workdir/content-exclusions" src="$workdir/content-exclusions/src"
  local out="$workdir/content-exclusions/out" log="$workdir/content-exclusions/log"

  # Leg 1 — asked of the REAL repository, and asked first: it needs neither dotnet nor the copy, so
  # a host that cannot pack still gets this verdict.
  ce_grade_ignores 'exclusions' "$root"

  rm -rf "$scratch"; mkdir -p "$src" "$out" "$log"
  # A copy, not the caller's checkout. --exclude bin/obj/artifacts keeps a previously built tree
  # from making the pack leg's evidence ambiguous.
  if ! tar -C "$root" --exclude=.git --exclude=bin --exclude=obj --exclude=artifacts \
       --exclude=.claude -cf - . 2>/dev/null | tar -C "$src" -xf - 2>/dev/null; then
    bad "exclusions: could not copy the working tree to $src, so legs 2 and 3 measured nothing"
    return
  fi

  local tdir
  for tdir in "$src"/templates/*/; do
    [[ -d "$tdir" ]] && content_exclusion_seed "${tdir%/}"
  done

  # Leg 2 — pack the seeded copy and read the archive.
  if dotnet pack "$src/FS.GG.Templates.csproj" -c Release -o "$scratch/artifacts" \
       >"$log/pack.log" 2>&1; then
    local nupkg
    nupkg="$(ls -1 "$scratch/artifacts"/FS.GG.Workspace.Template.*.nupkg 2>/dev/null | head -1)"
    if [[ -f "$nupkg" ]]; then
      unzip -Z1 "$nupkg" >"$log/entries.txt" 2>/dev/null
      ce_grade_entries 'exclusions' "$log/entries.txt"
    else
      bad "exclusions: the seeded pack produced no nupkg, so leg 2 measured nothing (see $log/pack.log)"
    fi
  else
    bad "exclusions: the seeded pack FAILED, so leg 2 measured nothing (see $log/pack.log)"
  fi

  # Leg 3 — folder install, deliberately bypassing leg 2 (see the header note), one template at a
  # time so a red names the template whose declaration rotted.
  local dir id excl
  for tdir in "$src"/templates/*/; do
    [[ -f "${tdir}.template.config/template.json" ]] || continue
    dir="$(basename "${tdir%/}")"
    # The engine dispatches on `shortName`, not on the directory name, so read it rather than
    # assuming the two agree — a template whose folder and short name diverge would otherwise make
    # `dotnet new` red for "template not found" and be reported as a delivery failure.
    id="$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1])).get("shortName") or "")
' "${tdir}.template.config/template.json" 2>/dev/null)"
    excl="$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
s=d.get("sources") or []
print("\n".join(s[0].get("exclude",[])) if s else "")
' "${tdir}.template.config/template.json" 2>/dev/null)"
    if [[ -z "$id" ]]; then
      bad "exclusions: $dir/.template.config/template.json declares no shortName, so leg 3 cannot instantiate it (#386)"
      continue
    fi
    if [[ -z "$excl" ]]; then
      # No `exclude` declaration means the engine's own defaults apply UNREPLACED — which already
      # carry `**/node_modules/**`. `.nuget/` is not an engine default, but such a template also
      # sets no `RestorePackagesPath` and can only be reached through the packed archive, where
      # leg 2 is the guard. Named, not silently passed.
      skip "exclusions: $id declares no sources.exclude, so it inherits the engine defaults unreplaced; leg 2 is its .nuget/ guard (#386)"
      continue
    fi
    local missing=''
    grep -qxF -- '**/.nuget/**' <<<"$excl"      || missing+=' **/.nuget/**'
    grep -qxF -- '**/node_modules/**' <<<"$excl" || missing+=' **/node_modules/**'
    if [[ -n "$missing" ]]; then
      bad "exclusions: $id's sources.exclude is missing$missing — declaring \`exclude\` REPLACES the engine default list wholesale, so an omission here is a silent narrowing (#386)"
    else
      ok "exclusions: $id's sources.exclude names both .nuget/ and node_modules/"
    fi

    if ! dotnet new install "${tdir%/}" >"$log/install-$id.log" 2>&1; then
      bad "exclusions: $id did not install from its source folder, so leg 3 measured nothing for it (see $log/install-$id.log)"
      continue
    fi
    if ! ( cd "$out" && dotnet new "$id" -n "Probe386" -o "$id" ) >"$log/new-$id.log" 2>&1; then
      bad "exclusions: $id did not instantiate, so leg 3 measured nothing for it (see $log/new-$id.log)"
      continue
    fi
    ce_grade_tree "exclusions/$id" "$out/$id"
  done
}

# ── assert_content_exclusions_can_fire <label> <scratch> ───────────────────────────────────────
# #386's own "a gate that is DEMONSTRATED to fire" (the #379 shape, reused): drive each graded
# assertion through BOTH outcomes on every run, against fixtures, offline and in milliseconds. The
# green cases prove the gate is not stuck red; the red cases prove it is not stuck green — and they
# call the ASSERTIONS, requiring the FAIL counter to move, because a mutation of an `else bad` arm
# to `else ok` is precisely the fail-open a predicate-only demonstration cannot see.
assert_content_exclusions_can_fire() {
  local label="$1" scratch="$2" fails=0 n=0
  local saved_pass="$PASS" saved_fail="$FAIL"
  rm -rf "$scratch"; mkdir -p "$scratch"

  # _ce_expect <expected-fail-delta> <assertion> <args...>
  _ce_expect() {
    local want="$1"; shift
    local before="$FAIL"
    n=$((n + 1))
    "$@" >/dev/null 2>&1
    [[ $((FAIL - before)) == "$want" ]] || fails=$((fails + 1))
  }

  # Leg 2 fixtures — entry lists, the exact shape `unzip -Z1` emits.
  printf 'content/templates/fs-gg-web/Web/Program.fs\ncontent/templates/fs-gg-web/nuget-cache-notes.md\nREADME.md\n' \
    >"$scratch/entries-clean.txt"
  printf 'content/templates/fs-gg-web/Web/Program.fs\ncontent/templates/fs-gg-web/.nuget/packages/x/1.0.0/x.sha512\n' \
    >"$scratch/entries-nuget.txt"
  printf 'content/templates/fs-gg-fable-game/Client/node_modules/x/index.js\n' \
    >"$scratch/entries-node.txt"
  _ce_expect 0 ce_grade_entries "$label" "$scratch/entries-clean.txt"
  _ce_expect 1 ce_grade_entries "$label" "$scratch/entries-nuget.txt"
  _ce_expect 1 ce_grade_entries "$label" "$scratch/entries-node.txt"

  # Leg 3 fixtures — product trees. The clean one carries a `nuget-cache/` decoy so a loosened
  # segment anchor reds here instead of shipping.
  mkdir -p "$scratch/prod-clean/src" "$scratch/prod-clean/nuget-cache"
  printf 'x\n' >"$scratch/prod-clean/src/Program.fs"
  mkdir -p "$scratch/prod-nuget/.nuget/packages/x/1.0.0"
  mkdir -p "$scratch/prod-node/Web/node_modules/x"
  _ce_expect 0 ce_grade_tree "$label" "$scratch/prod-clean"
  _ce_expect 1 ce_grade_tree "$label" "$scratch/prod-nuget"
  _ce_expect 1 ce_grade_tree "$label" "$scratch/prod-node"

  # Leg 1 fixtures — throwaway git repos, one ignoring both directories and one ignoring neither.
  local repo
  for repo in ignore-good ignore-bad; do
    mkdir -p "$scratch/$repo/templates/probe"
    git -C "$scratch/$repo" init -q 2>/dev/null
  done
  printf '.nuget/\nnode_modules/\n' >"$scratch/ignore-good/.gitignore"
  printf 'bin/\nobj/\n*.nupkg\n'    >"$scratch/ignore-bad/.gitignore"
  _ce_expect 0 ce_grade_ignores "$label" "$scratch/ignore-good"
  _ce_expect 1 ce_grade_ignores "$label" "$scratch/ignore-bad"

  PASS="$saved_pass"; FAIL="$saved_fail"
  unset -f _ce_expect
  if [[ "$fails" == 0 ]]; then
    ok "$label: the exclusion gate is demonstrated to fire — $n cases, every leg driven to both outcomes"
  else
    bad "$label: $fails of $n self-demonstration cases did NOT behave as declared. A gate that cannot fire is not a gate — legs 1/2/3 of #386 are not being enforced by this run."
  fi
}
