#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out="${1:?empty evidence directory required}"
[[ ! -e "$out" ]]
mkdir -p "$out/feed" "$out/home" "$out/packages" "$out/http" "$out/tools"

template_version=0.14.0
wizard_version=0.11.2
sdd_version=1.8.0
template="$out/feed/FS.GG.Workspace.Template.$template_version.nupkg"
template_sha=a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563
public=https://api.nuget.org/v3-flatcontainer

download() {
  local url="$1" destination="$2"
  curl --fail --silent --show-error --location --retry 30 --retry-all-errors \
    --retry-delay 10 "$url" --output "$destination"
}

download "$public/fs.gg.workspace.template/$template_version/fs.gg.workspace.template.$template_version.nupkg" "$template"
[[ "$(sha256sum "$template" | cut -d' ' -f1)" == "$template_sha" ]]
for version in 0.10.0 0.11.0 0.12.0 0.13.0; do
  download "$public/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" \
    "$out/feed/FS.GG.Workspace.Template.$version.nupkg"
done

config="$out/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"

# The archive itself, rather than this checkout's source tree, is the product under test.
bash "$root/tests/composition/fable-game/verify-svg-workspace-bundles.sh" "$template" \
  >"$out/bundle-matrix.log"
dotnet new install "$template" --force >/dev/null
dotnet new fs-gg-fable-game -n ReleaseDComplete -o "$out/complete" \
  --lifecycle none --bundle complete >/dev/null
FSGG_COMPLETE_REQUIRE_EXECUTABLE=false bash "$root/tests/composition/fable-game/verify-svg-complete-adoption.sh" \
  "$out/complete" "$out/feed" "$out/adoption" >"$out/adoption.log"

# Exercise the independently published entry point against the pinned public template tag.
dotnet tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$out/tools/sdd" \
  --configfile "$config" --no-cache >/dev/null
dotnet tool install FS.GG.NewSddWorkspace --version "$wizard_version" --tool-path "$out/tools/wizard" \
  --configfile "$config" --no-cache >/dev/null
PATH="$out/tools/sdd:$PATH" "$out/tools/wizard/new-sdd-workspace" \
  "$out/wizard" ReleaseDWizard --template fable-game --bundle complete --lifecycle none \
  --ref "fs-gg-templates/v$template_version" --pinned --no-governance --no-coordination \
  >"$out/wizard.log"
test -f "$out/wizard/SvgFoundation/Examples/Tactical/scene.json"
test -f "$out/wizard/SvgFoundation/Examples/Arcade/scene.json"
grep -F 'source: FS.GG.Workspace.Template::0.14.0' "$out/wizard/.fsgg/providers.yml" >/dev/null

python3 - "$template" "$out/qualification.json" <<'PY'
from hashlib import sha256
from pathlib import Path
import json, sys
archive, receipt = map(Path, sys.argv[1:])
receipt.write_text(json.dumps({
  'schema': 'fsgg.svg-release-d.public-qualification/v1',
  'release': 'D',
  'template': {'version': '0.14.0', 'source': 'nuget.org', 'sha256': sha256(archive.read_bytes()).hexdigest()},
  'wizard': {'version': '0.11.2', 'source': 'nuget.org'},
  'sdd': {'version': '1.8.0', 'source': 'nuget.org'},
  'bundles': {'omitted': 'player', 'player': 'passed', 'studio': 'passed', 'tactical': 'passed', 'arcade': 'passed', 'complete': 'passed'},
  'lifecycles': {'none': 'passed', 'sdd': 'passed', 'typed-sdd': 'passed', 'spec-kit': 'passed'},
  'retainedAdoption': {'0.10.0': 'passed', '0.11.0': 'passed', '0.12.0': 'passed', '0.13.0': 'passed'},
  'deploymentBoundary': 'local-caddy-compose',
  'producerDistribution': 'public-nuget-only'
}, indent=2) + '\n')
PY
echo "svg-release-d-public: passed; evidence=$out/qualification.json"
