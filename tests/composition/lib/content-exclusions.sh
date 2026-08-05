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
#   3. each template's            — the engine excludes NEITHER directory. `.nuget/` it cannot know
#      `sources.exclude`            about (an MSBuild property creates it), and `node_modules/` it
#                                   simply does not exclude — see the measurement below. So every
#                                   template delivered both, whether it declared an `exclude` list
#                                   or not.
#
# `**/node_modules/**` IS NOT AN ENGINE DEFAULT, AND THE EVIDENCE THAT SAID SO WAS A FALSE POSITIVE.
# This matters enough to record, because the claim was load-bearing and wrong in the SAFE-sounding
# direction. #384's review read the engine's defaults with
# `strings -el .../Microsoft.TemplateEngine.Orchestrator.RunnableProjects.dll` and found, in order:
#
#     **/*   **/[Bb]in/**   **/[Oo]bj/**   **/.template.config/**   **/*.filelist   **/*.user
#     **/*.lock.json   **/node_modules/**          <- adjacent in the string POOL, not in the LIST
#
# Adjacency in a binary's string pool is not membership of the effective list. MEASURED instead of
# read (dotnet SDK 10.0.302), by building a template that declares NO `sources` block at all — so
# the defaults apply unreplaced — seeding one file per claimed pattern at two depths, installing the
# folder and instantiating it:
#
#     filtered:   bin/**  obj/**  *.filelist  *.user  packages.lock.json   (at BOTH depths)
#     DELIVERED:  node_modules/pkg/index.js   Sub/node_modules/pkg/index.js   .nuget/packages/...
#
# Corroborated on the real thing: a folder install of `templates/fs-gg-governance` — the one template
# here that declared no `sources` block — delivered BOTH directories into the product.
#
# So `**/node_modules/**` in these lists is NOT a restored default. It is a NEW guard that never
# existed, protecting two npm workspaces with five `package.json` roots between them. What #382 did
# was not "drop a default"; what it did was leave a hole that was already open. The four
# `template.json` comments said otherwise and are corrected on this branch.
#
# WHY THIS IS A GATE AND NOT A CODE COMMENT. All three filters are DECLARATIONS — one line each, in
# three different files, in three different languages, that nothing executes, justified by prose that
# was itself measurably wrong for two years of commits. Nothing in CI restores or installs inside
# `templates/` and the release gate packs from a clean checkout, so the published artifact was never
# at risk — which is exactly why no existing signal could ever have noticed. This gate manufactures
# the condition CI never produces.
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
#
# ── EVERY LEG PROVES IT HAD A SUBJECT AND A WORKING TOOL BEFORE IT REPORTS CLEAN ───────────────
# Three findings from independent review, all the same shape and all fixed here: an ABSENCE that
# looks exactly like a PASS.
#
#   * NO SUBJECT. Stubbing `content_exclusion_seed` to a no-op left all three legs green — the gate
#     could not distinguish "the filters worked" from "there was nothing to filter". Every leg now
#     grades its POSITIVE CONTROL first: leg 2 requires the seeded sentinels to be on disk in the
#     tree it is about to pack AND requires a file it knows IS packed to appear in the archive; leg
#     3 requires the sentinels in the template folder it is about to install. No subject is a RED.
#   * NO TOOL. Shimming `unzip` to `exit 127` made leg 2 print "the packed archive carries no
#     .nuget/ or node_modules/ entry" — a tool that could not run reporting a clean result, which is
#     the .github#266 class this suite already guards twice elsewhere
#     (`reference-gate-set-overlay.sh:34` preflights `unzip`; `game-skill-release.sh:280` cites #266).
#     Every external tool is preflighted, and `unzip`'s exit status is checked rather than assumed.
#   * NO DECLARATION. An `exclude` of `[]`, or a missing `sources` block, was graded as a SKIP — an
#     absent declaration read as a satisfied one. There is no exemption now: EVERY template must
#     name both patterns, and every template's product is scanned whatever its declaration says.

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

# Leg 2's POSITIVE CONTROL. A file this repository packs unconditionally and that no `Exclude` here
# touches, so its presence in the entry list proves the list is a real reading of a real archive.
# Without it, an `unzip` that exited 127 produced an empty list and leg 2 called that clean.
CONTENT_EXCLUSION_PACK_CONTROL='README.md'

# Every external tool this gate's verdict depends on. A missing one is a RED, never a clean report
# (.github#266) — the same preflight `reference-gate-set-overlay.sh` and `game-skill-release.sh`
# already apply in this suite.
CONTENT_EXCLUSION_TOOLS=(dotnet tar unzip python3 git find)

# content_exclusion_missing_tools — names the tools that are not runnable; rc 1 if any.
content_exclusion_missing_tools() {
  local t missing=''
  for t in "${CONTENT_EXCLUSION_TOOLS[@]}"; do
    command -v "$t" >/dev/null 2>&1 || missing+="$t "
  done
  [[ -n "$missing" ]] || return 0
  printf '%s\n' "${missing% }"
  return 1
}

# content_exclusion_unseeded <dir> — sentinels that are NOT on disk under <dir>; rc 1 if any. This is
# the "did this measurement have a subject at all" question, asked of the exact tree about to be
# packed or installed.
content_exclusion_unseeded() {
  local dir="$1" rel missing=''
  for rel in "${CONTENT_EXCLUSION_SENTINELS[@]}"; do
    [[ -f "$dir/$rel" ]] || missing+="$dir/$rel"$'\n'
  done
  [[ -n "$missing" ]] || return 0
  printf '%s' "$missing"
  return 1
}

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

# ce_grade_tools <label> — the .github#266 preflight, as a graded assertion so the demonstration can
# drive it. rc 1 when a tool is missing, and the caller must then REFUSE rather than measure.
ce_grade_tools() {
  local label="$1" tools
  if tools="$(content_exclusion_missing_tools)"; then
    ok "$label: every external tool this gate's verdict depends on is runnable (${CONTENT_EXCLUSION_TOOLS[*]})"
    return 0
  fi
  bad "$label: this gate needs [${CONTENT_EXCLUSION_TOOLS[*]}] and cannot run '$tools'. REFUSING rather than reporting the clean scan a missing tool produces anyway — an \`unzip\` that exits 127 leaves an empty listing, and an empty listing has no offenders in it (.github#266)"
  return 1
}

# ce_grade_measured <label> <what> <entry-list-file>
# The positive control, graded BEFORE the offender scan and separately from it. An entry list that is
# empty, or that lacks a file this repository packs unconditionally, is not evidence of a clean
# archive — it is evidence that nothing was read. `unzip` exiting 127 produced exactly that, and the
# offender scan below called it clean (.github#266).
ce_grade_measured() {
  local label="$1" what="$2" entries="$3"
  if [[ -s "$entries" ]] && grep -qxF -- "$CONTENT_EXCLUSION_PACK_CONTROL" "$entries" 2>/dev/null; then
    ok "$label: $what is a real reading — the archive lists its positive control ($CONTENT_EXCLUSION_PACK_CONTROL)"
  else
    bad "$label: $what carries no '$CONTENT_EXCLUSION_PACK_CONTROL' entry, so the archive was never read and the verdict below would be clean-by-absence, not clean (leg 2, .github#266)"
  fi
}

# ce_grade_seeded <label> <what> <dir>...
# The other positive control: this measurement had a SUBJECT. Stubbing the seeder to a no-op used to
# leave every leg green, because "the filters worked" and "there was nothing to filter" produce the
# same clean scan. Variadic so leg 2 can grade every template directory it is about to pack in one
# verdict, and leg 3 can grade the single directory it is about to install.
ce_grade_seeded() {
  local label="$1" what="$2"; shift 2
  local dir out missing='' n=0
  for dir in "$@"; do
    n=$((n + 1))
    out="$(content_exclusion_unseeded "$dir")" || missing+="$out"
  done
  if [[ "$n" == 0 ]]; then
    bad "$label: $what named NO directory to check, so the subject-presence control graded nothing (#386)"
  elif [[ -z "$missing" ]]; then
    ok "$label: $what carries the seeded .nuget/ and node_modules/ trees ($n dir(s)), so the scan below has a subject"
  else
    bad "$label: $what is MISSING its seeded sentinels, so any clean verdict from it is clean-by-absence — the gate would be grading nothing (#386):"$'\n'"$missing"
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

# ce_grade_declaration <label> <template-id> <newline-separated-exclude-list>
# EVERY template must name both patterns. There is no "declares none, so the engine's defaults cover
# it" arm any more, and there never should have been one: the engine excludes NEITHER directory
# (measured — see the header), so an absent or empty `exclude` is a template that delivers both.
ce_grade_declaration() {
  local label="$1" id="$2" excl="$3" missing=''
  grep -qxF -- '**/.nuget/**' <<<"$excl"       || missing+=' **/.nuget/**'
  grep -qxF -- '**/node_modules/**' <<<"$excl" || missing+=' **/node_modules/**'
  if [[ -z "$missing" ]]; then
    ok "$label: $id's sources.exclude names both .nuget/ and node_modules/"
  elif [[ -z "${excl//[[:space:]]/}" ]]; then
    bad "$label: $id declares no sources.exclude at all. The template engine excludes NEITHER .nuget/ nor node_modules/, so an absent declaration delivers both — it is not an exemption (#386):$missing"
  else
    bad "$label: $id's sources.exclude is missing$missing — declaring \`exclude\` REPLACES the engine default list wholesale, so an omission here is a silent narrowing (#386)"
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

  # Preflight FIRST and refuse, because every verdict below is a clean report when its tool is
  # absent: `unzip` exiting 127 wrote an empty entry list and leg 2 called that a clean archive
  # (.github#266). A `bad` + `return` is the only honest answer to "I cannot measure this".
  ce_grade_tools 'exclusions' || return

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

  local tdir seeded=()
  for tdir in "$src"/templates/*/; do
    [[ -d "$tdir" ]] || continue
    content_exclusion_seed "${tdir%/}"
    seeded+=("${tdir%/}")
  done
  if [[ "${#seeded[@]}" == 0 ]]; then
    bad "exclusions: the copy at $src contains no templates/*/ directory, so there is nothing to seed and every leg below would be clean-by-absence (#386)"
    return
  fi

  # Leg 2 — pack the seeded copy and read the archive. THREE things are graded, in order, and the
  # first two are what stop an absence from reading as a pass: the tree really carries the subject,
  # the archive was really read, and only then — is it clean.
  ce_grade_seeded 'exclusions' 'the tree about to be packed' "${seeded[@]}"
  if dotnet pack "$src/FS.GG.Templates.csproj" -c Release -o "$scratch/artifacts" \
       >"$log/pack.log" 2>&1; then
    local nupkg
    nupkg="$(ls -1 "$scratch/artifacts"/FS.GG.Workspace.Template.*.nupkg 2>/dev/null | head -1)"
    if [[ -f "$nupkg" ]]; then
      # `unzip`'s exit status is CHECKED, not assumed. A shimmed/absent unzip exits non-zero and
      # leaves an empty file; without this the offender scan reads that as "no offenders".
      if unzip -Z1 "$nupkg" >"$log/entries.txt" 2>"$log/unzip.err"; then
        ce_grade_measured 'exclusions' 'the packed archive listing' "$log/entries.txt"
        ce_grade_entries 'exclusions' "$log/entries.txt"
      else
        bad "exclusions: \`unzip -Z1\` failed on $nupkg (exit $?), so leg 2 read no archive and any clean verdict would be clean-by-absence (.github#266; see $log/unzip.err)"
      fi
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

    # NO EXEMPTION ARM. This used to `skip` a template that declared no `exclude`, on the false
    # premise that the engine's defaults covered `node_modules/`. They do not (see the header), so an
    # absent declaration is a template that delivers BOTH directories — and it is graded, and its
    # product is scanned, exactly like every other.
    ce_grade_declaration 'exclusions' "$id" "$excl"

    # The subject control for THIS template, so a leg-3 pass cannot come from an unseeded folder.
    ce_grade_seeded 'exclusions' "$id's source folder" "${tdir%/}"

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
  # The preflight's two outcomes. The absent case really does take PATH away — asserting the
  # refusal without removing the tools would be the easier-than-production fixture .github#2223
  # names. It runs in THIS shell (the FAIL counter must move), so PATH is restored immediately.
  _ce_tools_present() { ce_grade_tools "$label"; }
  _ce_tools_absent() {
    local saved_path="$PATH" rc
    PATH='/nonexistent/fsgg386-no-tools'
    ce_grade_tools "$label"; rc=$?
    PATH="$saved_path"
    return "$rc"
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

  # ── The three absence cases, added after independent review found each of them reporting a PASS.
  # These are the ones that matter most: an absent subject, an absent reading and an absent
  # declaration all LOOK like clean scans, so a demonstration that only drives dirty-vs-clean cannot
  # see them at all.

  # NO READING (M12). An empty listing is what a shimmed/absent `unzip` leaves behind; a listing
  # without the positive control is what reading the wrong file leaves behind. Both must red, and
  # note the offender scan on these very fixtures is CLEAN — that is the whole point.
  : >"$scratch/entries-empty.txt"
  printf 'content/templates/fs-gg-web/Web/Program.fs\n' >"$scratch/entries-nocontrol.txt"
  _ce_expect 0 ce_grade_measured "$label" 'fixture listing' "$scratch/entries-clean.txt"
  _ce_expect 1 ce_grade_measured "$label" 'fixture listing' "$scratch/entries-empty.txt"
  _ce_expect 1 ce_grade_measured "$label" 'fixture listing' "$scratch/entries-nocontrol.txt"
  _ce_expect 0 ce_grade_entries  "$label" "$scratch/entries-empty.txt"   # clean, and that is the trap

  # NO SUBJECT (M15). A seeded tree, an unseeded one, a half-seeded one, and the degenerate
  # no-directories-named call that a stubbed seeder loop would produce.
  mkdir -p "$scratch/seed-full" "$scratch/seed-none" "$scratch/seed-half"
  content_exclusion_seed "$scratch/seed-full"
  mkdir -p "$scratch/seed-half/$(dirname "${CONTENT_EXCLUSION_SENTINELS[0]}")"
  printf 'x\n' >"$scratch/seed-half/${CONTENT_EXCLUSION_SENTINELS[0]}"
  _ce_expect 0 ce_grade_seeded "$label" 'fixture tree' "$scratch/seed-full"
  _ce_expect 1 ce_grade_seeded "$label" 'fixture tree' "$scratch/seed-none"
  _ce_expect 1 ce_grade_seeded "$label" 'fixture tree' "$scratch/seed-half"
  _ce_expect 1 ce_grade_seeded "$label" 'fixture tree'

  # NO DECLARATION (M14). Both patterns, one pattern, the empty list, and whitespace-only — the last
  # two are the arm that used to SKIP.
  _ce_expect 0 ce_grade_declaration "$label" 'probe' '**/[Bb]in/**
**/.nuget/**
**/node_modules/**'
  _ce_expect 1 ce_grade_declaration "$label" 'probe' '**/[Bb]in/**
**/.nuget/**'
  _ce_expect 1 ce_grade_declaration "$label" 'probe' ''
  _ce_expect 1 ce_grade_declaration "$label" 'probe' '   '

  # NO TOOL (M12, the preflight itself). Driven through a PATH that contains none of them, so the
  # refusal is measured rather than asserted.
  _ce_expect 0 _ce_tools_present
  _ce_expect 1 _ce_tools_absent

  PASS="$saved_pass"; FAIL="$saved_fail"
  unset -f _ce_expect _ce_tools_present _ce_tools_absent
  if [[ "$fails" == 0 ]]; then
    ok "$label: the exclusion gate is demonstrated to fire — $n cases, every leg driven to both outcomes"
  else
    bad "$label: $fails of $n self-demonstration cases did NOT behave as declared. A gate that cannot fire is not a gate — legs 1/2/3 of #386 are not being enforced by this run."
  fi
}
