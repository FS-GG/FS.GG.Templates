#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
version=''; mode=''
usage() { echo "usage: $0 --mode templates|full|wasm --template-version 0.18.1 --sha256 HEX --descriptor-sha256 HEX --source-revision COMMIT --tag-revision COMMIT --sdd-version VERSION --sdd-sha256 HEX --sdd-source-revision COMMIT --wizard-version VERSION --wizard-sha256 HEX --wizard-source-revision COMMIT --evidence-dir ABSOLUTE [--preflight-only]" >&2; exit 2; }
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
[[ "$mode" == templates || "$mode" == full || "$mode" == wasm ]] || usage
if [[ "$mode" == wasm ]]; then
  [[ "$version" == 0.19.0 && -z "$sdd_version$sdd_sha$sdd_revision$wizard_version$wizard_sha$wizard_revision" ]] || usage
else
  [[ "$version" == 0.18.1 && "$sdd_version" == 2.1.0 ]] || usage
fi
if [[ "$mode" == full ]]; then
  [[ "$wizard_version" == 0.16.0 && "$wizard_sha" =~ ^[0-9a-f]{64}$ && "$wizard_revision" =~ ^[0-9a-f]{40}$ ]] || usage
else
  [[ -z "$wizard_version$wizard_sha$wizard_revision" ]] || usage
fi
tag="fs-gg-templates/v$version"
[[ "$sha" =~ ^[0-9a-f]{64}$ && "$descriptor_sha" =~ ^[0-9a-f]{64}$ && "$revision" =~ ^[0-9a-f]{40}$ && "$tag_revision" =~ ^[0-9a-f]{40}$ ]] || usage
if [[ "$mode" != wasm ]]; then
  [[ "$sdd_sha" =~ ^[0-9a-f]{64}$ && "$sdd_revision" =~ ^[0-9a-f]{40}$ ]] || usage
  [[ "$sdd_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$ ]] || usage
fi
[[ "$revision" == "$tag_revision" && "$evidence" = /* ]] || usage
$preflight && { [[ ! -e "$evidence" ]] || usage; echo 'fable-reference-public: preflight passed; live publication qualification not run'; exit 0; }
# Direct-only successor assertion. The caller admits the actual tool/browser profile,
# owns the original execution deadline and known-child cleanup. This branch acquires
# no SDK/compiler/browser: all supplied paths must be qualified before invocation.
if [[ "$mode" == wasm ]]; then
  : "${DOTNET_HOST_PATH:?qualified absolute dotnet host required}"
  : "${FSGG_WASM_SDK_ARCHIVE:?qualified public SDK 0.3 archive required}"
  : "${FSGG_WASM_WASI_ROOT:?qualified private WASI SDK 34 root required}"
  : "${FSGG_WASM_FABLE_CORE:?qualified private Fable 5.18 entrypoint required}"
  : "${FSGG_WASM_NUGET_CONFIG:?qualified closed application feed config required}"
  : "${FSGG_WASM_NPM_CACHE:?qualified npm cache required}"
  : "${PLAYWRIGHT_BROWSERS_PATH:?qualified own browser archive cache required}"
  : "${FSGG_WASM_FIREFOX_PROFILE:?explicit Firefox compatibility profile required}"
  case "$FSGG_WASM_FIREFOX_PROFILE" in
    content-sandbox-enabled) [[ -z "${MOZ_DISABLE_CONTENT_SANDBOX:-}" ]] || usage ;;
    content-sandbox-disabled) [[ "${MOZ_DISABLE_CONTENT_SANDBOX:-}" == 1 ]] || usage ;;
    *) usage ;;
  esac
  [[ "$DOTNET_HOST_PATH" = /* && -x "$DOTNET_HOST_PATH" && ! -L "$DOTNET_HOST_PATH" ]] || usage
  [[ "$FSGG_WASM_FABLE_CORE" = /* && -f "$FSGG_WASM_FABLE_CORE" && ! -L "$FSGG_WASM_FABLE_CORE" ]] || usage
  echo "b586190f1592c3352d7319008a99e1747267dacbc44d6e5bd3753c84390f47a4  $FSGG_WASM_FABLE_CORE" | sha256sum --check --strict
  [[ -d "$evidence" && "$(stat -c %a "$evidence")" == 700 && -f "$evidence/qualification.json" ]] || usage
  [[ "$(find "$evidence" -mindepth 1 -maxdepth 1 -printf x | wc -c)" -eq 1 ]] || usage
  mkdir "$evidence"/{feed,home,packages,http,direct,default}
  wasm_status=failed
  wasm_finish() {
    local rc=$?
    [[ $rc -eq 0 ]] && wasm_status=passed
    python3 - "$evidence/qualification.json" "$wasm_status" "$version" "$revision" "$tag_revision" "$sha" "$descriptor_sha" <<'WASM_RECEIPT'
import json, sys, os
path, status, version, revision, tag_revision, archive, descriptor = sys.argv[1:]
with open(path, 'w') as out:
    json.dump({'schema':'fable-reference-public/1','disposition':status,'mode':'wasm',
      'scope':'direct downloaded Complete WASM source consumer; no provider/Wizard/FourD/AT acceptance',
      'package':'FS.GG.Workspace.Template','version':version,'sourceRevision':revision,
      'tag':'fs-gg-templates/v'+version,'tagRevision':tag_revision,
      'archiveSha256':archive,'descriptorSha256':descriptor,
      'sdd':None,'wizard':None,'wizardQualification':'pending',
      'firefoxProfile':os.environ['FSGG_WASM_FIREFOX_PROFILE'],
      'workerCleanupBoundary':'wrapper handles/terminate-call receipts; native exit unknown'}, out, indent=2)
    out.write('\n')
WASM_RECEIPT
    exit "$rc"
  }
  trap wasm_finish EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  export DOTNET_CLI_HOME="$evidence/home" NUGET_PACKAGES="$evidence/packages" NUGET_HTTP_CACHE_PATH="$evidence/http"
  export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
  archive="$evidence/feed/FS.GG.Workspace.Template.$version.nupkg"
  descriptor="$evidence/fable-game.providers.yml"
  mapfile -t remote_refs < <(git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/$tag" "refs/tags/$tag^{}")
  resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 ~ /\^\{\}$/ {print $1}')"
  [[ -n "$resolved" ]] || resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 !~ /\^\{\}$/ {print $1}')"
  [[ "$resolved" == "$tag_revision" && "$(printf '%s\n' "$resolved" | wc -l)" -eq 1 ]] || { echo 'WASM public immutable tag mismatch' >&2; exit 1; }
  curl -q --fail --silent --show-error --location --retry 0 --max-time 15 --max-filesize 8388608 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$archive"
  curl -q --fail --silent --show-error --location --retry 0 --max-time 15 --max-filesize 1048576 "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$revision/providers/fable-game.providers.yml" -o "$descriptor"
  validator=("$DOTNET_HOST_PATH" run --project "$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj" -c Release --no-build --no-restore --)
  "${validator[@]}" reference-publication-check --template-version "$version" --archive "$archive" --descriptor "$descriptor" --sha256 "$sha" --source-revision "$revision" --tag-revision "$tag_revision" --descriptor-sha256 "$descriptor_sha"
  "$DOTNET_HOST_PATH" nuget verify "$archive" --all >"$evidence/template-signatures.log" 2>&1
  "$DOTNET_HOST_PATH" new install "$archive" >"$evidence/template-install.log"
  "$DOTNET_HOST_PATH" new fs-gg-fable-game -n ReferenceWasm -o "$evidence/direct" --bundle complete --lifecycle none
  "$DOTNET_HOST_PATH" new fs-gg-fable-game -n ReferenceDefault -o "$evidence/default" --lifecycle none
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/direct" --route direct --lifecycle none --sdd-version not-applicable --product-name ReferenceWasm
  [[ ! -e "$evidence/default/SvgFoundation/Examples/Wasm" && ! -e "$evidence/default/Browser.Tests/wasm-policy.spec.ts" ]] || { echo 'Default player unexpectedly contains optional WASM' >&2; exit 1; }
  # The default and Complete application caches must be genuinely fresh. Workspace
  # Directory.Build.props owns its .nuget path; NUGET_PACKAGES alone is insufficient.
  [[ ! -e "$evidence/direct/.nuget/packages" && ! -e "$evidence/default/.nuget/packages" ]] || { echo 'Generated application cache was not fresh' >&2; exit 1; }
  sha256sum "$evidence/direct/SvgFoundation/packages.lock.json" "$evidence/direct/SvgFoundation/Examples/Wasm/packages.lock.json" >"$evidence/locks.before.sha256"
  npm_args=(--offline --ignore-scripts --no-audit --no-fund --cache "$FSGG_WASM_NPM_CACHE")
  for receiver in default direct; do
    foundation="$evidence/$receiver/SvgFoundation"
    enabled=false; [[ "$receiver" != direct ]] || enabled=true
    if [[ "$enabled" == true ]]; then
      (cd "$foundation" && bash Examples/Wasm/build-guests.sh "$FSGG_WASM_SDK_ARCHIVE" "$FSGG_WASM_WASI_ROOT") >"$evidence/guests.log" 2>&1
    fi
    "$DOTNET_HOST_PATH" restore "$foundation/SvgFoundation.fsproj" --locked-mode --configfile "$FSGG_WASM_NUGET_CONFIG" -p:NuGetAudit=false -p:FsGgWasmPolicyExample="$enabled" -p:DisableImplicitLibraryPacksFolder=true >"$evidence/$receiver-restore.log" 2>&1
    "$DOTNET_HOST_PATH" msbuild "$foundation/SvgFoundation.fsproj" -p:FsGgWasmPolicyExample="$enabled" -getProperty:FsGgWasmPolicyExample,NuGetLockFilePath -getItem:PackageReference,ProjectReference,Compile >"$evidence/$receiver-evaluated.json"
    python3 - "$evidence/$receiver-evaluated.json" "$enabled" <<'WASM_GRAPH'
import json, sys
value=json.load(open(sys.argv[1])); enabled=sys.argv[2]=='true'
assert value['Properties']['FsGgWasmPolicyExample']==str(enabled).lower()
assert not value['Items']['ProjectReference'], 'repository/project source fallback refused'
refs={p['Identity']:p['Version'] for p in value['Items']['PackageReference']}
assert ('FS.GG.Wasm.Contracts' in refs)==enabled and ('FS.GG.Wasm.Browser' in refs)==enabled
if enabled:
    assert refs['FS.GG.Wasm.Contracts']==refs['FS.GG.Wasm.Browser']=='[0.3.0]'
    assert value['Properties']['NuGetLockFilePath'].endswith('/Examples/Wasm/packages.lock.json')
WASM_GRAPH
    if [[ "$enabled" == true ]]; then python3 "$foundation/Examples/Wasm/materialize-assets.py" "$foundation"; fi
    (cd "$evidence/$receiver" && FsGgWasmPolicyExample="$enabled" "$DOTNET_HOST_PATH" --fx-version 10.0.12 "$FSGG_WASM_FABLE_CORE" SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache --noRestore) >"$evidence/$receiver-fable.log" 2>&1
    (cd "$evidence/$receiver/Client" && npm ci "${npm_args[@]}") >"$evidence/$receiver-npm.log" 2>&1
    (cd "$evidence/$receiver" && FSGG_WASM_POLICY_EXAMPLE="$enabled" FsGgWasmPolicyExample="$enabled" ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js) >"$evidence/$receiver-vite.log" 2>&1
    if [[ "$enabled" == false ]]; then
      [[ ! -e "$foundation/dist/_content/FS.GG.Wasm.Browser" && ! -e "$foundation/dist/wasm-policy-guests" ]] || { echo 'Default build contains WASM assets' >&2; exit 1; }
    fi
  done
  sha256sum --check "$evidence/locks.before.sha256"
  # This private production configuration imports the GENERATED maintained config
  # and tests. It never imports the producer checkout's renderer or test source.
  cat >"$evidence/direct/Browser.Tests/wasm-public.generated.config.ts" <<'WASM_CONFIG'
import { defineConfig } from "@playwright/test";
import maintained from "./playwright.config";
const family = process.env.PLAYWRIGHT_BROWSER_FAMILY;
const results = process.env.FSGG_WASM_RESULTS;
if (!["chromium", "firefox", "webkit"].includes(family ?? "") || !results?.startsWith("/")) throw new Error("explicit family/results required");
if (process.env.FsGgWasmPolicyExample !== "true" || process.env.PLAYWRIGHT_EXECUTABLE_PATH) throw new Error("enabled own-archive profile required");
export default defineConfig({ ...maintained, testMatch: "wasm-policy.spec.ts", workers: 1, retries: 0,
  timeout: 30000, expect: { timeout: 5000 }, outputDir: `${results}/${family}/test-results`,
  reporter: [["line"], ["json", { outputFile: `${results}/${family}/report.json` }]],
  use: { ...maintained.use, trace: "on", screenshot: "only-on-failure", video: "off" },
  webServer: [{ command: "../Client/node_modules/.bin/vite preview --config vite.config.js --host 127.0.0.1 --port 5100 --strictPort",
    cwd: "../SvgFoundation", url: "http://127.0.0.1:5100/wasm-example/", timeout: 30000, reuseExistingServer: false }]
});
WASM_CONFIG
  (cd "$evidence/direct/Browser.Tests" && npm ci "${npm_args[@]}") >"$evidence/browser-npm.log" 2>&1
  export FsGgWasmPolicyExample=true FSGG_WASM_POLICY_EXAMPLE=true FSGG_WASM_RESULTS="$evidence/browser"
  mkdir "$evidence/browser"
  for family in chromium firefox webkit; do
    mkdir "$evidence/browser/$family"
    (cd "$evidence/direct/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" node node_modules/@playwright/test/cli.js test --config wasm-public.generated.config.ts --list --reporter=json) >"$evidence/browser/$family/list.json"
    python3 - "$evidence/browser/$family/list.json" "$family" <<'WASM_LIST'
import json, sys
def count(suites):
    return sum(sum(len(s.get('tests',[])) for s in suite.get('specs',[]))+count(suite.get('suites',[])) for suite in suites)
report=json.load(open(sys.argv[1])); family=sys.argv[2]
assert [p['name'] for p in report['config']['projects']]==[family], 'exact selected family required'
def tests(suites):
    return [t for suite in suites for spec in suite.get('specs',[]) for t in spec.get('tests',[])] + [t for suite in suites for t in tests(suite.get('suites',[]))]
selected=tests(report['suites'])
assert count(report['suites'])==9 and len(selected)==9, 'exact nine definitions required'
assert {t['projectName'] for t in selected}=={family} and {t['projectId'] for t in selected}=={family}, 'wrong selected project population'
WASM_LIST
  done
  for family in chromium firefox webkit; do
    # Compatibility remains a caller-selected profile, never an automatic disable.
    (cd "$evidence/direct/Browser.Tests" && PLAYWRIGHT_BROWSER_FAMILY="$family" node node_modules/@playwright/test/cli.js test --config wasm-public.generated.config.ts --workers=1 --retries=0 --max-failures=1) >"$evidence/browser/$family/browser.log" 2>&1
    python3 - "$evidence/browser/$family/report.json" "$family" <<'WASM_RESULT'
import json, sys
report=json.load(open(sys.argv[1])); stats=report['stats']; family=sys.argv[2]
assert [p['name'] for p in report['config']['projects']]==[family], 'runtime family differs'
assert stats['expected']==9 and stats['unexpected']==stats['flaky']==stats['skipped']==0, stats
WASM_RESULT
  done
  echo 'WASM public: direct default/opt-in source, production graph and 27 browser cases passed; retaining/provider/Wizard/AT/native-exit acceptance not claimed'
  exit 0
fi
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
