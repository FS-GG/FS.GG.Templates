#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
version=0.17.0
usage() { echo "usage: $0 --sha256 HEX --source-revision COMMIT --sdd-version VERSION --wizard-version VERSION --evidence-dir ABSOLUTE [--preflight-only]" >&2; exit 2; }
sha=''; revision=''; sdd_version=''; wizard_version=''; evidence=''; preflight=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha256) sha="${2:-}"; shift 2;;
    --source-revision) revision="${2:-}"; shift 2;;
    --sdd-version) sdd_version="${2:-}"; shift 2;;
    --wizard-version) wizard_version="${2:-}"; shift 2;;
    --evidence-dir) evidence="${2:-}"; shift 2;;
    --preflight-only) preflight=true; shift;;
    *) usage;;
  esac
done
[[ "$sha" =~ ^[0-9a-f]{64}$ && "$revision" =~ ^[0-9a-f]{40}$ ]] || usage
[[ "$sdd_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$wizard_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || usage
[[ "$evidence" = /* && ! -e "$evidence" ]] || usage
$preflight && { echo 'fable-reference-public: preflight passed'; exit 0; }

mkdir -m 700 "$evidence"
mkdir "$evidence"/{feed,home,packages,http,tools,direct,provider,wizard}
config="$evidence/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
export DOTNET_CLI_HOME="$evidence/home" NUGET_PACKAGES="$evidence/packages" NUGET_HTTP_CACHE_PATH="$evidence/http"
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
archive="$evidence/feed/FS.GG.Workspace.Template.$version.nupkg"
descriptor="$evidence/fable-game.providers.yml"
curl --fail --silent --show-error --location "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$archive"
curl --fail --silent --show-error --location "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$revision/providers/fable-game.providers.yml" -o "$descriptor"
dotnet run --project "$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj" --no-restore -- \
  reference-publication-check --archive "$archive" --descriptor "$descriptor" --sha256 "$sha" --source-revision "$revision"
dotnet new install "$archive" --force >"$evidence/template-install.log"
dotnet tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$evidence/tools/sdd" --configfile "$config" --no-cache
dotnet tool install FS.GG.NewSddWorkspace --version "$wizard_version" --tool-path "$evidence/tools/wizard" --configfile "$config" --no-cache
dotnet new fs-gg-fable-game -n ReferenceDirect -o "$evidence/direct" --bundle complete --lifecycle none
mkdir -p "$evidence/provider/.fsgg"; cp "$descriptor" "$evidence/provider/.fsgg/providers.yml"
"$evidence/tools/sdd/fsgg-sdd" scaffold --root "$evidence/provider" --provider fable-game --param productName=ReferenceProvider --param bundle=complete --param lifecycle=none --no-update --json >"$evidence/provider.json"
PATH="$evidence/tools/sdd:$PATH" "$evidence/tools/wizard/new-sdd-workspace" "$evidence/wizard" ReferenceWizard --template fable-game --bundle complete --lifecycle none --ref "fs-gg-templates/v$version" --pinned --no-governance --no-coordination >"$evidence/wizard.log"
for receiver in direct provider wizard; do
  test -f "$evidence/$receiver/SvgFoundation/FourDReference.fs"
  test -f "$evidence/$receiver/SvgFoundation/Examples/FourD/reference.json"
  test -f "$evidence/$receiver/SvgFoundation/build.sh"
done
(cd "$evidence/direct" && bash build.sh)
(cd "$evidence/direct/Browser.Tests" && npm ci && npm test -- --grep 'FourD reference' --workers=1) | tee "$evidence/fourd-reference-browser.log"
grep -Eq '[1-9][0-9]* passed' "$evidence/fourd-reference-browser.log"
! grep -Eq '[1-9][0-9]* skipped' "$evidence/fourd-reference-browser.log"
sha256sum "$archive" "$descriptor" >"$evidence/readback.sha256"
echo "fable-reference-public: passed; evidence=$evidence"
