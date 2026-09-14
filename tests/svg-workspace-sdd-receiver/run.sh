#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${TEMPLATES_CANDIDATE:?path to the exact FS.GG.Workspace.Template 0.14.0 candidate is required}"
: "${TEMPLATES_CANDIDATE_SHA256:?exact Templates candidate SHA-256 is required}"
: "${TEMPLATES_CANDIDATE_SOURCE:?exact Templates candidate source commit is required}"
: "${TEMPLATES_PROVIDER_DESCRIPTOR:?path to its exact fable-game.providers.yml is required}"

scratch="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-sdd-svg-receiver.XXXXXX")"
trap '[[ "${KEEP_WORKDIR:-0}" == 1 ]] || rm -rf -- "$scratch"' EXIT
export DOTNET_CLI_HOME="$scratch/home"
export NUGET_PACKAGES="$scratch/packages"
export NUGET_HTTP_CACHE_PATH="$scratch/http"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
mkdir -p "$DOTNET_CLI_HOME" "$NUGET_PACKAGES" "$NUGET_HTTP_CACHE_PATH" "$scratch/tool" "$scratch/owners"
cat >"$scratch/NuGet.Config" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="verified-public-sdd" value="$scratch/public-sdd" />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
  <packageSourceMapping>
    <packageSource key="verified-public-sdd"><package pattern="FS.GG.SDD.*" /></packageSource>
    <packageSource key="nuget.org"><package pattern="*" /></packageSource>
  </packageSourceMapping>
</configuration>
EOF
mkdir -p "$scratch/public-sdd"

download() {
  local url="$1" destination="$2"
  for attempt in $(seq 1 12); do
    if curl --fail --location --silent --show-error "$url" --output "$destination"; then return; fi
    [[ "$attempt" == 12 ]] && return 1
    sleep 5
  done
}

for package in fs.gg.sdd.artifacts fs.gg.sdd.cli; do
  download "https://api.nuget.org/v3-flatcontainer/$package/1.8.0/$package.1.8.0.nupkg" "$scratch/$package.1.8.0.nupkg"
done
printf '%s  %s\n' \
  '8eaff15a322f9455f1f7c4a8ef5644b78275ff6953ec373813f99ec6399ab204' "$scratch/fs.gg.sdd.artifacts.1.8.0.nupkg" \
  'c6bc7a1625941a809ca93f036a6f7a85aa44db342338a2efb9e9f64ed9167cc5' "$scratch/fs.gg.sdd.cli.1.8.0.nupkg" \
  | sha256sum --check --strict
cp "$scratch"/fs.gg.sdd.*.1.8.0.nupkg "$scratch/public-sdd/"
dotnet tool install FS.GG.SDD.Cli --version 1.8.0 --tool-path "$scratch/tool" \
  --configfile "$scratch/NuGet.Config" --no-cache >/dev/null
dotnet new install "$TEMPLATES_CANDIDATE" >/dev/null

owner_specs=(
  'fs.gg.game.skills 0.9.0'
  'fs.gg.rendering.skills 0.2.0'
  'fs.gg.audio.skills 0.1.0'
)
owner_archives=()
for spec in "${owner_specs[@]}"; do
  read -r package version <<<"$spec"
  archive="$scratch/owners/$package.$version.nupkg"
  download "https://api.nuget.org/v3-flatcontainer/$package/$version/$package.$version.nupkg" "$archive"
  owner_archives+=("$archive")
done

for bundle in player studio tactical arcade complete; do
  product="$scratch/$bundle"
  mkdir -p "$product/.fsgg"
  cp "$TEMPLATES_PROVIDER_DESCRIPTOR" "$product/.fsgg/providers.yml"
  "$scratch/tool/fsgg-sdd" scaffold --root "$product" --provider fable-game --no-update \
    --param productName="${bundle^}Audit" --param rootNamespace="${bundle^}Audit" \
    --param lifecycle=none --param bundle="$bundle" >"$scratch/$bundle.json"
  (cd "$product" && python tools/routine-delivery.py --help >/dev/null)
done

for value in true false; do
  product="$scratch/legacy-$value"
  mkdir -p "$product/.fsgg"
  cp "$TEMPLATES_PROVIDER_DESCRIPTOR" "$product/.fsgg/providers.yml"
  "$scratch/tool/fsgg-sdd" scaffold --root "$product" --provider fable-game --no-update \
    --param productName="Legacy${value^}Audit" --param rootNamespace="Legacy${value^}Audit" \
    --param lifecycle=none --param svgFoundation="$value" >"$scratch/legacy-$value.json"
done

cp -a "$scratch/player" "$scratch/upgrade"
printf '\n# retained user edit\n' >>"$scratch/upgrade/tools/routine-delivery.py"
sha256sum "$scratch/upgrade/tools/routine-delivery.py" | cut -d' ' -f1 >"$scratch/modified-helper.sha256"
python - "$scratch/upgrade/.github/workflows/routine-eligibility.yml" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[1]).unlink()
PY
"$scratch/tool/fsgg-sdd" upgrade --root "$scratch/upgrade" --yes >"$scratch/upgrade.json"

python "$repo_root/tests/svg-workspace-sdd-receiver/verify.py" \
  "$TEMPLATES_CANDIDATE" "$TEMPLATES_CANDIDATE_SHA256" "$TEMPLATES_CANDIDATE_SOURCE" "$scratch" \
  "${owner_archives[@]}"
if [[ "${KEEP_WORKDIR:-0}" == 1 ]]; then printf 'receiver audit retained at %s\n' "$scratch"; fi
