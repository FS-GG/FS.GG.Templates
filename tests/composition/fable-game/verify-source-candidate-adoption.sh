#!/usr/bin/env bash
#
# The complete adoption route against the SOURCE candidate (FS.GG.Templates#834).
#
# verify-svg-complete-adoption.sh runs the route with a published donor. The source tree is a candidate too, and
# the route replaces a retained workspace's managed project files with the candidate's, so a file the candidate's
# projects compile but the manifest does not manage reaches the receiver as a dangling reference (FS0225 at its
# first build). This gate takes the packed source archive, scaffolds the candidate from it and adopts a retained
# 0.10.0 workspace, and requires:
#
#   1. the historical baselines manifest REFUSES the candidate, naming the unmanaged compiled file (the closure
#      refusal), and a receiver is left untouched;
#   2. the current-reference manifest, with the candidate's own bytes admitted as its canonical digests, ACCEPTS it,
#      adds the successor-only files, and the adopted receiver's Client project restores locked and compiles with Fable.
#
# The current-reference manifest authenticates the published 0.19.3 source; admitting the candidate is what a
# successor release does, and is done here in a scratch copy so the committed manifest is not rewritten.
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

# 2. The current-reference manifest with the candidate admitted as its canonical digests.
python3 -I - "$root" "$current" "$out/candidate" "$out/admitted" <<'PY'
from pathlib import Path
import importlib.util, json, sys

root, current, candidate, admitted = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("adopter", root / "scripts/apply-svg-complete-workspace.py")
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)
product, namespace, _ = adopter.identity(candidate)
extension = json.loads(current.read_text())
for logical, digests in extension["candidateCanonicalDigests"].items():
    path = candidate / logical
    if path.is_file():
        digests[:] = sorted(set(digests) | adopter.canonical_variants(path.read_bytes(), product, namespace))
admitted.mkdir()
(admitted / "svg-current-reference-adoption.json").write_text(json.dumps(extension, indent=2) + "\n")
(admitted / "svg-complete-workspace-baselines.json").write_bytes((root / "scripts/svg-complete-workspace-baselines.json").read_bytes())
PY
manifest="$out/admitted/svg-current-reference-adoption.json"
if ! "$adopter" complete-inventory "$out/candidate" "$out/retained" "$manifest" \
  "$out/inventory.json" "$out/review.diff" >"$out/inventory.log" 2>&1; then
  cat "$out/inventory.log" >&2
  jq -c '.conflicts' "$out/inventory.json" >&2 || true
  fail 'the admitted candidate was not accepted'
fi
for added in Client/Renderers.fs Client/Conformance.fs Client/renderers.html \
  Browser.Tests/renderer-conformance.spec.ts Browser.Tests/playwright.renderers.config.ts; do
  jq -e --arg p "$added" '[.changes[] | select(.path==$p and .state=="add")] | length==1' "$out/inventory.json" >/dev/null \
    || fail "the inventory does not add $added"
done
"$adopter" complete-apply "$out/candidate" "$out/retained" "$manifest" "$out/inventory.json" "$out/backup" >"$out/apply.log"
[[ "$authored_before" == "$(sha256sum "$out/retained/authored/level.json")" ]] || fail 'authored file changed'
grep -F 'Retained0100' "$out/retained/Client/Renderers.fs" >/dev/null || fail 'the adopted renderers carry the receiver namespace'

# Every unconditional file the adopted Client project compiles exists in the receiver, and the project builds.
python3 -I - "$out/retained/Client/Client.fsproj" <<'PY'
from pathlib import Path
import sys, xml.etree.ElementTree as ET
project = Path(sys.argv[1]); missing = []
for group in ET.parse(project).getroot().iter("ItemGroup"):
    for item in group.findall("Compile"):
        include = item.get("Include")
        if include and item.get("Condition") is None and "$(" not in include and not (project.parent / include).is_file():
            missing.append(include)
if missing:
    raise SystemExit("adopted Client project compiles files the receiver lacks: " + ", ".join(missing))
PY
# The Fable client is built by Fable (its Protocol sources compile against Thoth.Json only under FABLE_COMPILER), so the
# receiver's Client project is restored locked and compiled to JavaScript, the way its own build.sh builds it.
(cd "$out/retained" && dotnet tool restore && dotnet restore Client/Client.fsproj --locked-mode \
  && cd Client && dotnet fable . -o "$out/client-output" --noCache) >"$out/client-build.log" 2>&1 \
  || { tail -n 60 "$out/client-build.log" >&2; fail 'the adopted receiver Client project does not compile with Fable'; }
test -s "$out/client-output/Renderers.js" && test -s "$out/client-output/Conformance.js" \
  || fail 'Fable did not emit the adopted renderers'
echo "source-candidate-adoption: baselines refusal named the unmanaged closure; admitted candidate adopted $old_version with 5 added files; Client restored locked and compiled with Fable"
