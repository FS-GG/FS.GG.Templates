#!/usr/bin/env bash
# Public receiver proof for the exact FS.GG.Workspace.Template 0.14.0 archive.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:-$(mktemp -d)}"
mkdir -p "$out/feed" "$out/dotnet-home"
export DOTNET_CLI_HOME="$out/dotnet-home" DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
version=0.14.0
expected_sha=a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563
archive="$out/feed/FS.GG.Workspace.Template.$version.nupkg"
curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$archive"
test "$(sha256sum "$archive" | cut -d' ' -f1)" = "$expected_sha"
unzip -Z1 "$archive" | rg '^content/templates/fs-gg-fable-bindings/' | rg '(xantham|Xantham)' | sort >"$out/xantham-members.txt"
test "$(wc -l <"$out/xantham-members.txt")" -eq 20
dotnet new install "$archive" --force >/dev/null
dotnet new fs-gg-fable-bindings -o "$out/product" -n PublicBindings --productName PublicBindings --rootNamespace PublicBindings --lifecycle none >/dev/null
bash "$root/tests/toolchain/fable-bindings/installed-xantham-qualification.sh" "$out/product" "$out/qualification.json" --live-assessment

# Exercise an owner-retained public 0.13.0 workspace. The bounded adopter
# preserves unrelated edits and refuses a changed managed file before writing.
old_version=0.13.0
old_sha=ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c
old_archive="$out/feed/FS.GG.Workspace.Template.$old_version.nupkg"
curl -fsSL --retry 3 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$old_version/fs.gg.workspace.template.$old_version.nupkg" -o "$old_archive"
test "$(sha256sum "$old_archive" | cut -d' ' -f1)" = "$old_sha"
old_home="$out/old-dotnet-home"; mkdir -p "$old_home"
DOTNET_CLI_HOME="$old_home" dotnet new install "$old_archive" --force >/dev/null
DOTNET_CLI_HOME="$old_home" dotnet new fs-gg-fable-bindings -o "$out/old-baseline" -n PublicBindings --productName PublicBindings --rootNamespace PublicBindings --lifecycle none >/dev/null
cp -a "$out/old-baseline" "$out/retained"
printf '\nOwner-retained note.\n' >>"$out/retained/README.md"
readme_before="$(sha256sum "$out/retained/README.md")"
members="$root/tests/toolchain/fable-bindings/xantham-public-members-0.14.0.txt"
bash "$root/tests/toolchain/fable-bindings/adopt-installed-xantham.sh" "$out/old-baseline" "$out/product" "$out/retained" "$members" >/dev/null
test "$readme_before" = "$(sha256sum "$out/retained/README.md")"
bash "$root/tests/toolchain/fable-bindings/installed-xantham-qualification.sh" "$out/retained" "$out/retained-qualification.json"

cp -a "$out/old-baseline" "$out/collision"
printf '\n// owner edit\n' >>"$out/collision/scripts/run-xantham.mjs"
collision_before="$(find "$out/collision" -type f -printf '%P\n' | sort | while read -r path; do sha256sum "$out/collision/$path"; done | sha256sum)"
if bash "$root/tests/toolchain/fable-bindings/adopt-installed-xantham.sh" "$out/old-baseline" "$out/product" "$out/collision" "$members" >"$out/collision.log" 2>&1; then
  echo 'retained managed-file collision unexpectedly adopted' >&2; exit 1
fi
grep -Fq 'adoption refused before writes: managed path changed: scripts/run-xantham.mjs' "$out/collision.log"
test "$collision_before" = "$(find "$out/collision" -type f -printf '%P\n' | sort | while read -r path; do sha256sum "$out/collision/$path"; done | sha256sum)"

jq --arg version "$version" --arg sha "$expected_sha" --arg old_version "$old_version" --arg old_sha "$old_sha" '. + {publicTemplate:{package:"FS.GG.Workspace.Template",version:$version,source:"nuget.org",sha256:$sha,xanthamMembers:20},receiver:{template:"fs-gg-fable-bindings",lifecycle:"none",deliveredFilesOnly:true},retainedAdoption:{baselineVersion:$old_version,baselineSha256:$old_sha,payloadMembers:20,ownerEdits:"preserved",managedCollision:"refused-before-write",qualification:"passed"}}' "$out/qualification.json" >"$out/qualification.tmp"
mv "$out/qualification.tmp" "$out/qualification.json"
echo "PASS public installed fs-gg-fable-bindings 0.14.0; evidence=$out/qualification.json"
