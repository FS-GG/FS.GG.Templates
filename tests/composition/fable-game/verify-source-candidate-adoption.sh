#!/usr/bin/env bash
#
# The complete adoption route against the SOURCE candidate (FS.GG.Templates#834 and #841).
#
# verify-svg-complete-adoption.sh runs the route with a published donor. The source tree is a candidate too, and
# the route replaces a retained workspace's managed files with the candidate's, so a file the candidate's projects
# name but the manifest does not manage reaches the receiver as a dangling reference (FS0225 at its first build), and
# a managed file whose bytes the manifest does not admit is refused. This gate takes the packed source archive,
# scaffolds the candidate from it and adopts a retained 0.10.0 workspace, with the COMMITTED manifests, and requires:
#
#   1. the historical baselines manifest REFUSES the candidate, naming the unmanaged compiled file (the closure
#      refusal), and a receiver is left untouched;
#   2. the committed current-reference manifest ACCEPTS it, adds every file of its optional sets, preserves the
#      receiver's authored files, and the adopted solution restores locked and builds with `dotnet build`, and its
#      Fable client compiles to JavaScript;
#   3. the manifest is what authenticates the candidate: a managed file edited after the manifest was written is
#      refused, and a candidate carrying only part of an optional set is refused, each leaving the receiver untouched.
#
# A change to a managed template file therefore needs its successor digest in scripts/svg-current-reference-adoption.json
# in the same change; this gate is what says so.
#
#   usage: verify-source-candidate-adoption.sh <source-template.nupkg> <empty evidence directory>
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
package="${1:?source template archive required}"
out="${2:?empty evidence directory required}"
[[ -f $package ]] || { echo "source-candidate-adoption: package not found: $package" >&2; exit 1; }
[[ ! -e $out ]]
mkdir -p "$out"
fail() { echo "source-candidate-adoption: $*" >&2; exit 1; }

adopter="$root/scripts/apply-svg-foundation-preview.sh"
baselines="$root/scripts/svg-complete-workspace-baselines.json"
current="$root/scripts/svg-current-reference-adoption.json"

old_version=0.10.0
old_sha="$(jq -r --arg v "$old_version" '.sourceArchives[] | select(.version==$v) | .sha256' "$baselines")"
[[ -n $old_sha ]] || fail "no pinned $old_version archive in the baselines manifest"
old_archive="$out/FS.GG.Workspace.Template.$old_version.nupkg"
curl --fail --silent --show-error --location --retry 12 --retry-all-errors --retry-delay 5 \
  "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$old_version/fs.gg.workspace.template.$old_version.nupkg" \
  --output "$old_archive"
[[ "$(sha256sum "$old_archive" | cut -d' ' -f1)" == "$old_sha" ]] || fail "public $old_version archive differs from its pin"

# The candidate: the packed source archive, complete bundle, as a product generated from it.
candidate_home="$out/home-candidate"
mkdir -p "$candidate_home"
DOTNET_CLI_HOME="$candidate_home" dotnet new install "$package" --force >/dev/null
DOTNET_CLI_HOME="$candidate_home" dotnet new fs-gg-fable-game -n SourceCandidate -o "$out/candidate" \
  --lifecycle none --bundle complete >/dev/null

# The retained receiver: a published 0.10.0 workspace with authored files the route must preserve.
old_home="$out/home-old"
mkdir -p "$old_home"
DOTNET_CLI_HOME="$old_home" dotnet new install "$old_archive" --force >/dev/null
DOTNET_CLI_HOME="$old_home" dotnet new fs-gg-fable-game -n Retained0100 -o "$out/retained" --lifecycle none >/dev/null
mkdir -p "$out/retained/authored"
printf '%s\n' '{"level":"retained"}' >"$out/retained/authored/level.json"
authored_before="$(sha256sum "$out/retained/authored/level.json")"
cp -a "$out/retained" "$out/untouched"
tree_sha() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1); }

# 1. The baselines manifest does not manage the files the candidate's Client project compiles: refused, untouched.
if "$adopter" complete-inventory "$out/candidate" "$out/retained" "$baselines" \
  "$out/refused-inventory.json" "$out/refused-review.diff" >"$out/refused.log" 2>&1; then
  fail 'the baselines manifest accepted a candidate that compiles unmanaged files'
fi
jq -e '.ready==false and ([.conflicts[] | select(.path=="Client/Client.fsproj" and (.reason|test("Client/Renderers.fs.*outside the managed closure")))] | length==1)' \
  "$out/refused-inventory.json" >/dev/null || fail 'the refusal does not name Client/Renderers.fs'
[[ "$(tree_sha "$out/untouched")" == "$(tree_sha "$out/retained")" ]] || fail 'a refused inventory changed the receiver'

# 2. The committed current-reference manifest.
manifest="$current"
if ! "$adopter" complete-inventory "$out/candidate" "$out/retained" "$manifest" \
  "$out/inventory.json" "$out/review.diff" >"$out/inventory.log" 2>&1; then
  cat "$out/inventory.log" >&2
  jq -c '.conflicts' "$out/inventory.json" >&2 2>/dev/null || true
  fail 'the committed manifest did not accept the source candidate (a managed file changed without its digest, or a project names an unmanaged file)'
fi
mapfile -t optional < <(jq -r '.candidateOptionalSets[][]' "$manifest")
[[ ${#optional[@]} -gt 0 ]] || fail 'the manifest declares no optional set'
for added in "${optional[@]}"; do
  jq -e --arg p "$added" '[.changes[] | select(.path==$p and .state=="add")] | length==1' "$out/inventory.json" >/dev/null \
    || fail "the inventory does not add $added"
done

# 3. The manifest authenticates the candidate. Both controls run before anything is applied.
cp -a "$out/candidate" "$out/candidate-edited"
printf '\n// edited after the manifest was written\n' >>"$out/candidate-edited/Client/App.fs"
if "$adopter" complete-inventory "$out/candidate-edited" "$out/retained" "$manifest" \
  "$out/edited-inventory.json" "$out/edited-review.diff" >"$out/edited.log" 2>&1; then
  fail 'an edited managed file was accepted'
fi
grep -F 'candidate differs from published source: Client/App.fs' "$out/edited.log" >/dev/null \
  || { cat "$out/edited.log" >&2; fail 'the refusal of an edited managed file does not name it'; }
cp -a "$out/candidate" "$out/candidate-partial"
rm "$out/candidate-partial/Client/Stage.fs"
if "$adopter" complete-inventory "$out/candidate-partial" "$out/retained" "$manifest" \
  "$out/partial-inventory.json" "$out/partial-review.diff" >"$out/partial.log" 2>&1; then
  fail 'a candidate carrying part of an optional set was accepted'
fi
jq -e '[.conflicts[] | select(.reason|test("only part of the optional set"))] | length>=1' "$out/partial-inventory.json" >/dev/null \
  || fail 'the refusal of a partial optional set does not say so'
[[ "$(tree_sha "$out/untouched")" == "$(tree_sha "$out/retained")" ]] || fail 'a refused inventory changed the receiver'

"$adopter" complete-apply "$out/candidate" "$out/retained" "$manifest" "$out/inventory.json" "$out/backup" >"$out/apply.log"
[[ "$authored_before" == "$(sha256sum "$out/retained/authored/level.json")" ]] || fail 'authored file changed'
grep -F 'Retained0100' "$out/retained/Client/Renderers.fs" >/dev/null || fail 'the adopted renderers carry the receiver namespace'

# The adopted solution restores locked and builds: every project of the receiver, not only the Fable client.
solution="$(cd "$out/retained" && ls ./*.slnx)"
(cd "$out/retained" && dotnet restore "$solution" --locked-mode && dotnet build "$solution" --no-restore) >"$out/solution-build.log" 2>&1 \
  || { tail -n 60 "$out/solution-build.log" >&2; fail 'the adopted receiver solution does not build'; }
# The Fable client is built by Fable (its Protocol sources compile against Thoth.Json only under FABLE_COMPILER), so the
# receiver's Client project is restored locked and compiled to JavaScript, the way its own build.sh builds it.
(cd "$out/retained" && dotnet tool restore && dotnet restore Client/Client.fsproj --locked-mode \
  && cd Client && dotnet fable . -o "$out/client-output" --noCache) >"$out/client-build.log" 2>&1 \
  || { tail -n 60 "$out/client-build.log" >&2; fail 'the adopted receiver Client project does not compile with Fable'; }
test -s "$out/client-output/Renderers.js" && test -s "$out/client-output/Conformance.js" \
  || fail 'Fable did not emit the adopted renderers'
echo "source-candidate-adoption: baselines refusal named the unmanaged closure; the committed manifest adopted $old_version with ${#optional[@]} added files; an edited file and a partial set were refused; the solution built and the Client compiled with Fable"
