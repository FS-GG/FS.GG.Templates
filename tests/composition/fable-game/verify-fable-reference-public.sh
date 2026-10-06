#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
version=''; mode=''
usage() { echo "usage: $0 --mode templates|full --template-version 0.18.1 --sha256 HEX --descriptor-sha256 HEX --source-revision COMMIT --tag-revision COMMIT --sdd-version VERSION --sdd-sha256 HEX --sdd-source-revision COMMIT --wizard-version VERSION --wizard-sha256 HEX --wizard-source-revision COMMIT --evidence-dir ABSOLUTE [--preflight-only]" >&2; exit 2; }
sha=''; descriptor_sha=''; revision=''; tag_revision=''; sdd_version=''; sdd_sha=''; sdd_revision=''; wizard_version=''; wizard_sha=''; wizard_revision=''; evidence=''; preflight=false
declare -A seen=()
while [[ $# -gt 0 ]]; do
  option="$1"
  [[ -z "${seen[$option]:-}" ]] || usage
  seen[$option]=1
  case "$option" in
    --mode) mode="${2:-}"; shift 2;;
    --template-version) version="${2:-}"; shift 2;;
    --sha256) sha="${2:-}"; shift 2;;
    --descriptor-sha256) descriptor_sha="${2:-}"; shift 2;;
    --source-revision) revision="${2:-}"; shift 2;;
    --tag-revision) tag_revision="${2:-}"; shift 2;;
    --sdd-version) sdd_version="${2:-}"; shift 2;;
    --sdd-sha256) sdd_sha="${2:-}"; shift 2;;
    --sdd-source-revision) sdd_revision="${2:-}"; shift 2;;
    --wizard-version) wizard_version="${2:-}"; shift 2;;
    --wizard-sha256) wizard_sha="${2:-}"; shift 2;;
    --wizard-source-revision) wizard_revision="${2:-}"; shift 2;;
    --evidence-dir) evidence="${2:-}"; shift 2;;
    --preflight-only) preflight=true; shift;;
    *) usage;;
  esac
done
[[ "$mode" == templates || "$mode" == full ]] || usage
[[ "$version" == 0.18.1 && "$sdd_version" == 2.1.0 ]] || usage
if [[ "$mode" == full ]]; then
  [[ "$wizard_version" == 0.16.0 && "$wizard_sha" =~ ^[0-9a-f]{64}$ && "$wizard_revision" =~ ^[0-9a-f]{40}$ ]] || usage
else
  [[ -z "$wizard_version$wizard_sha$wizard_revision" ]] || usage
fi
tag="fs-gg-templates/v$version"
[[ "$sha" =~ ^[0-9a-f]{64}$ && "$descriptor_sha" =~ ^[0-9a-f]{64}$ && "$revision" =~ ^[0-9a-f]{40}$ && "$tag_revision" =~ ^[0-9a-f]{40}$ ]] || usage
[[ "$sdd_sha" =~ ^[0-9a-f]{64}$ && "$sdd_revision" =~ ^[0-9a-f]{40}$ ]] || usage
[[ "$sdd_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$ ]] || usage
[[ "$revision" == "$tag_revision" && "$evidence" = /* ]] || usage
$preflight && { [[ ! -e "$evidence" ]] || usage; echo 'fable-reference-public: preflight passed; live publication qualification not run'; exit 0; }
: "${QUINT_BIN:?set QUINT_BIN to qualified Quint 0.32.0}"
: "${DOTNET_HOST_PATH:?set DOTNET_HOST_PATH to the qualified absolute dotnet host}"
[[ "$DOTNET_HOST_PATH" = /* && -x "$DOTNET_HOST_PATH" && ! -L "$DOTNET_HOST_PATH" ]] || { echo 'fable-reference-public: dotnet host custody mismatch' >&2; exit 1; }
[[ -x "$QUINT_BIN" ]] || { echo 'fable-reference-public: Quint executable missing' >&2; exit 1; }
[[ "$(sha256sum "$QUINT_BIN" | cut -d' ' -f1)" == 939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f ]] || { echo 'fable-reference-public: Quint identity mismatch' >&2; exit 1; }
[[ "$($QUINT_BIN --version)" == 0.32.0 ]] || { echo 'fable-reference-public: Quint version mismatch' >&2; exit 1; }

[[ -d "$evidence" && "$(stat -c %a "$evidence")" == 700 && -f "$evidence/qualification.json" ]] || usage
[[ "$(find "$evidence" -mindepth 1 -maxdepth 1 -printf x | wc -c)" -eq 1 ]] || usage
mkdir "$evidence"/{feed,home,packages,http,tools,direct,provider,provider-none}
[[ "$mode" != full ]] || mkdir "$evidence"/{wizard,wizard-none}
status=failed
finish() {
  rc=$?
  [[ $rc -eq 0 ]] && status=passed
  python3 - "$evidence/qualification.json" "$status" "$mode" "$version" "$revision" "$tag" "$tag_revision" "$sha" "$descriptor_sha" "$sdd_version" "$sdd_sha" "$sdd_revision" "$wizard_version" "$wizard_sha" "$wizard_revision" <<'RECEIPT'
import json,sys
path,status,mode,version,revision,tag,tag_revision,sha,descriptor_sha,sdd_version,sdd_sha,sdd_revision,wizard_version,wizard_sha,wizard_revision=sys.argv[1:]
value={'schema':'fable-reference-public/1','disposition':status,'mode':mode,'package':'FS.GG.Workspace.Template','version':version,'sourceRevision':revision,'tag':tag,'tagRevision':tag_revision,'archiveSha256':sha,'descriptorSha256':descriptor_sha,'sdd':{'version':sdd_version,'archiveSha256':sdd_sha,'sourceRevision':sdd_revision},'wizard':({'version':wizard_version,'archiveSha256':wizard_sha,'sourceRevision':wizard_revision} if mode=='full' else None),'wizardQualification':('passed' if mode=='full' and status=='passed' else 'pending')}
with open(path,'w') as f: json.dump(value,f,indent=2);f.write('\n')
RECEIPT
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

config="$evidence/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
export DOTNET_CLI_HOME="$evidence/home" NUGET_PACKAGES="$evidence/packages" NUGET_HTTP_CACHE_PATH="$evidence/http"
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
archive="$evidence/feed/FS.GG.Workspace.Template.$version.nupkg"
descriptor="$evidence/fable-game.providers.yml"
sdd_archive="$evidence/feed/FS.GG.SDD.Cli.$sdd_version.nupkg"
wizard_archive="$evidence/feed/FS.GG.NewSddWorkspace.$wizard_version.nupkg"

mapfile -t remote_refs < <(git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/$tag" "refs/tags/$tag^{}")
resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 ~ /\^\{\}$/ {print $1}')"
[[ -n "$resolved" ]] || resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 !~ /\^\{\}$/ {print $1}')"
[[ "$resolved" == "$tag_revision" && "$(printf '%s\n' "$resolved" | wc -l)" -eq 1 ]] || { echo 'fable-reference-public: immutable tag revision mismatch' >&2; exit 1; }

curl --fail --silent --show-error --location "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$archive"
curl --fail --silent --show-error --location "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$revision/providers/fable-game.providers.yml" -o "$descriptor"
curl --fail --silent --show-error --location "https://api.nuget.org/v3-flatcontainer/fs.gg.sdd.cli/$sdd_version/fs.gg.sdd.cli.$sdd_version.nupkg" -o "$sdd_archive"
if [[ "$mode" == full ]]; then
  curl --fail --silent --show-error --location "https://api.nuget.org/v3-flatcontainer/fs.gg.newsddworkspace/$wizard_version/fs.gg.newsddworkspace.$wizard_version.nupkg" -o "$wizard_archive"
fi
validator=("$DOTNET_HOST_PATH" run --project "$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj" --no-restore --)
"${validator[@]}" reference-publication-check --template-version "$version" --archive "$archive" --descriptor "$descriptor" --sha256 "$sha" --source-revision "$revision" --tag-revision "$tag_revision" --descriptor-sha256 "$descriptor_sha"
"${validator[@]}" published-tool-check --archive "$sdd_archive" --sha256 "$sdd_sha" --package-id FS.GG.SDD.Cli --version "$sdd_version" --source-revision "$sdd_revision"
if [[ "$mode" == full ]]; then
  "${validator[@]}" published-tool-check --archive "$wizard_archive" --sha256 "$wizard_sha" --package-id FS.GG.NewSddWorkspace --version "$wizard_version" --source-revision "$wizard_revision"
fi

"$DOTNET_HOST_PATH" new install "$archive" --force >"$evidence/template-install.log"
"$DOTNET_HOST_PATH" tool install FS.GG.SDD.Cli --version "$sdd_version" --tool-path "$evidence/tools/sdd" --configfile "$config" --no-cache
if [[ "$mode" == full ]]; then
  "$DOTNET_HOST_PATH" tool install FS.GG.NewSddWorkspace --version "$wizard_version" --tool-path "$evidence/tools/wizard" --configfile "$config" --no-cache
fi
sdd_core="$("${validator[@]}" installed-tool-check --archive "$sdd_archive" --tool-root "$evidence/tools/sdd" --sha256 "$sdd_sha" --package-id FS.GG.SDD.Cli --version "$sdd_version" --source-revision "$sdd_revision" --command-name fsgg-sdd)"
if [[ "$mode" == full ]]; then
  wizard_core="$("${validator[@]}" installed-tool-check --archive "$wizard_archive" --tool-root "$evidence/tools/wizard" --sha256 "$wizard_sha" --package-id FS.GG.NewSddWorkspace --version "$wizard_version" --source-revision "$wizard_revision" --command-name new-sdd-workspace)"
fi
[[ "$sdd_core" = "$evidence/tools/sdd/.store/"* ]] || { echo 'fable-reference-public: admitted tool core escaped owned store' >&2; exit 1; }
[[ "$mode" != full || "${wizard_core:-}" = "$evidence/tools/wizard/.store/"* ]] || { echo 'fable-reference-public: wizard core escaped owned store' >&2; exit 1; }
mkdir "$evidence/tools/checked-sdd"
cat >"$evidence/tools/checked-sdd/fsgg-sdd" <<'ADAPTER'
#!/usr/bin/env bash
set -euo pipefail
exec "$CHECKED_DOTNET_HOST" "$CHECKED_SDD_CORE" "$@"
ADAPTER
chmod 700 "$evidence/tools/checked-sdd/fsgg-sdd"
export CHECKED_DOTNET_HOST="$DOTNET_HOST_PATH" CHECKED_SDD_CORE="$sdd_core"

# Omitted lifecycle must resolve to typed-sdd; explicit none remains none for every public route.
"$DOTNET_HOST_PATH" new fs-gg-fable-game -n ReferenceDirect -o "$evidence/direct" --bundle complete --lifecycle none
for receiver in provider provider-none; do mkdir -p "$evidence/$receiver/.fsgg"; cp "$descriptor" "$evidence/$receiver/.fsgg/providers.yml"; done
"$DOTNET_HOST_PATH" "$sdd_core" scaffold --root "$evidence/provider" --provider fable-game --param productName=ReferenceProvider --param bundle=complete --no-update --json >"$evidence/provider.json"
"$DOTNET_HOST_PATH" "$sdd_core" scaffold --root "$evidence/provider-none" --provider fable-game --param productName=ReferenceProviderNone --param bundle=complete --param lifecycle=none --no-update --json >"$evidence/provider-none.json"
if [[ "$mode" == full ]]; then
PATH="$evidence/tools/checked-sdd:$PATH" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard" ReferenceWizard --template fable-game --bundle complete --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard.log"
PATH="$evidence/tools/checked-sdd:$PATH" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard-none" ReferenceWizardNone --template fable-game --bundle complete --lifecycle none --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard-none.log"
fi

"${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/direct" --route direct --lifecycle none --sdd-version "$sdd_version" --product-name ReferenceDirect
provider_routes=(provider); [[ "$mode" != full ]] || provider_routes+=(wizard)
for route in "${provider_routes[@]}"; do
  if [[ "$route" == provider ]]; then product=ReferenceProvider; none_product=ReferenceProviderNone; else product=ReferenceWizard; none_product=ReferenceWizardNone; fi
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/$route" --route "$route" --lifecycle typed-sdd --sdd-version "$sdd_version" --product-name "$product"
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/$route-none" --route "$route" --lifecycle none --sdd-version "$sdd_version" --product-name "$none_product"
done
receiver_routes=(direct provider); [[ "$mode" != full ]] || receiver_routes+=(wizard)
for route in "${receiver_routes[@]}"; do
  (cd "$evidence/$route" && QUINT_BIN="$QUINT_BIN" bash build.sh) >"$evidence/$route-build.log" 2>&1
  (cd "$evidence/$route/Browser.Tests" && npm ci && npm test -- --grep 'FourD reference' --workers=1) >"$evidence/$route-browser.log" 2>&1
  grep -Eq '[1-9][0-9]* passed' "$evidence/$route-browser.log"
  ! grep -Eq '[1-9][0-9]* skipped' "$evidence/$route-browser.log"
done
sha256sum "$archive" "$descriptor" "$sdd_archive" >"$evidence/readback.sha256"
[[ "$mode" != full ]] || sha256sum "$wizard_archive" >>"$evidence/readback.sha256"
echo "fable-reference-public: passed; evidence=$evidence"
