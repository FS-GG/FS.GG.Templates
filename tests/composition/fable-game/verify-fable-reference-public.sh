#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
version=''; mode=''; current_inputs=''
usage() { echo "usage: $0 --mode templates|full|wasm --template-version 0.18.1 --sha256 HEX --descriptor-sha256 HEX --source-revision COMMIT --tag-revision COMMIT --sdd-version VERSION --sdd-sha256 HEX --sdd-source-revision COMMIT --wizard-version VERSION --wizard-sha256 HEX --wizard-source-revision COMMIT --evidence-dir ABSOLUTE [--preflight-only]" >&2; echo "       $0 --mode current-public --current-public-inputs ABSOLUTE_JSON --evidence-dir ABSOLUTE --preflight-only" >&2; exit 2; }
sha=''; descriptor_sha=''; revision=''; tag_revision=''; sdd_version=''; sdd_sha=''; sdd_revision=''; wizard_version=''; wizard_sha=''; wizard_revision=''; evidence=''; preflight=false
declare -A seen=()
while [[ $# -gt 0 ]]; do
  option="$1"
  [[ -z "${seen[$option]:-}" ]] || usage
  seen[$option]=1
  case "$option" in
    --current-public-inputs) current_inputs="${2:-}"; shift 2;;
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
# This route validates declared operation inputs and immutable source bytes only.
# It cannot fall through into the historical acquisition/runtime closure below.
if [[ "$mode" == current-public ]]; then
  [[ "$current_inputs" = /* && "$evidence" = /* && ! -e "$evidence" && ! -L "$evidence" ]] || usage
  [[ -z "$version$sha$descriptor_sha$revision$tag_revision$sdd_version$sdd_sha$sdd_revision$wizard_version$wizard_sha$wizard_revision" ]] || usage
  python3 - "$current_inputs" "$evidence" <<'CURRENT_PUBLIC'
import hashlib, json, pathlib, sys

def require(ok, message):
    if not ok:
        raise ValueError(message)

def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result

def read(path, limit):
    path = pathlib.Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), 'absolute regular input required')
    require(path.stat().st_size <= limit, 'input byte limit exceeded')
    with path.open('rb') as source:
        raw = source.read(limit + 1)
    require(len(raw) <= limit, 'input byte limit exceeded')
    return raw

try:
    value = json.loads(read(sys.argv[1], 32768), object_pairs_hook=unique)
    require(set(value) == {'schema', 'packages', 'sources', 'initialRegistration', 'selection', 'referenceRenderingVersion', 'defaults', 'parameterKeys'}, 'closed current-public input keys required')
    require(value['schema'] == 'fable-reference-current-public/1', 'current-public schema mismatch')
    # Select an entire published Wizard identity. Retained019 observations cannot
    # become020 evidence by changing a version scalar or one source declaration.
    wizard_packages = {
        '0.19.0': ['FS.GG.NewSddWorkspace', '0.19.0', 'cc1d3c12c1ed7e7128012063d7ab478c7198b523', '3c8150734814c3d5c4416535ff56f91a0570595bcc38cea6586012678a4e92b6'],
        '0.20.0': ['FS.GG.NewSddWorkspace', '0.20.0', '699f60851288f5f817b98856bdd3d220cf27dd09', 'ee8f4e33c0099b00888c50e4a5e32b3254a9d479211b39b44719fa8cf2925356'],
    }
    wizard = value['packages']['wizard']
    require(wizard in wizard_packages.values(), 'published Wizard version/source/archive mismatch')
    wizard_version = wizard[1]
    # These are independently published roles, not one compatible version tuple.
    packages = {
        'wizard': wizard,
        'sdd': ['FS.GG.SDD.Cli', '2.2.0', 'cf2f046a10497a336d6243c9a314c3f91fb15771', '46b4b172eac65df00db43f813bd3d3fbafac5c6376da62a6d3c08fb05750cf28'],
        'initialOverlay': ['FS.GG.Workspace.Template', '0.18.2', '20c009bc6728302f9ed06fdf49cb2e8bd19e417d', '496aad0e89496719bc543edc6ffbf829a82307862e630ba4e174e374ac11cc4e'],
        'provider': ['FS.GG.Workspace.Template', '0.19.0', '8952e1c5753b0abc972154c7596ddc8da772b271', '187c995806bb2f22db67c8a9a67c251f46f339bf6350b8051035935d308b497f'],
    }
    require(value['packages'] == packages, 'published package role/source/archive mismatch')
    require(value['initialRegistration'] == {'soleWorkspaceRegistration': True, 'package': packages['initialOverlay']}, 'sole initial 0.18.2 preflight custody declaration required')
    require(value['initialRegistration']['soleWorkspaceRegistration'] is True, 'initial custody flag must be boolean true')
    wizard_sources = {
        '0.19.0': ('cc1d3c12c1ed7e7128012063d7ab478c7198b523', 'scripts/NewSddWorkspace/Program.fs', '09060748f44b555b1859e0fd0b720d06cc0d362d9c239f1f652905fbf2e62965'),
        '0.20.0': ('699f60851288f5f817b98856bdd3d220cf27dd09', 'scripts/NewSddWorkspace/Program.fs', '4a4f3012f61a484ed09d3a14d923293c32d0ae8914ebdb53cc3abbde56ba0d06'),
    }
    sources = {
        'wizard': wizard_sources[wizard_version],
        'descriptor': ('f5fbd06ed9e6df40f9037c7acddf9eca3c6a14fc', 'providers/fable-game.providers.yml', 'd7207cbde78f2890a63bbebf23c80bbcae8ce7f2405c0ceacf602dc6c185942c'),
        'template': ('8952e1c5753b0abc972154c7596ddc8da772b271', 'templates/fs-gg-fable-game/.template.config/template.json', 'f0f81f93b923084a56a42e2f8d008eb6fd7c5078afbc84b3b3781cfcfc2ffcff'),
        'runtimeProject': ('8952e1c5753b0abc972154c7596ddc8da772b271', 'templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj', '76bf18c19864218054c2824449b68b98a1c1b88a0311c378a951666f638c3a0b'),
    }
    require(set(value['sources']) == set(sources), 'exact source input population required')
    for role, (revision, repository_path, digest) in sources.items():
        row = value['sources'][role]
        keys = {'revision', 'repositoryPath', 'sha256'} | ({'path'} if role == 'descriptor' else set())
        require(set(row) == keys, 'closed source input keys required')
        require((row['revision'], row['repositoryPath'], row['sha256']) == (revision, repository_path, digest), 'immutable source join mismatch: ' + role)
    # Only the descriptor is read in this metadata route. Other source declarations
    # are pinned observations, not a claim of re-reading packages or source files.
    descriptor = read(value['sources']['descriptor']['path'], 65536)
    require(hashlib.sha256(descriptor).hexdigest() == sources['descriptor'][2], 'immutable descriptor bytes mismatch')
    defaults = {'wizardLifecycle': 'sdd', 'providerLifecycle': 'typed-sdd', 'templateLifecycle': 'typed-sdd', 'bundle': 'player'}
    require(value['defaults'] == defaults, 'route lifecycle/bundle defaults drifted')
    require(value['parameterKeys'] == {'name': 'productName', 'identifier': 'rootNamespace'}, 'provider parameter key join drifted')
    selection = value['selection']
    require(set(selection) == {'lifecycle', 'bundle'}, 'closed lifecycle/bundle selection required')
    lifecycle, bundle = selection['lifecycle'], selection['bundle']
    require(lifecycle is None or lifecycle in ('none', 'sdd', 'typed-sdd', 'spec-kit'), 'unsupported lifecycle')
    require(bundle is None or bundle in ('player', 'studio', 'tactical', 'arcade', 'complete'), 'unsupported bundle')
    require(value['referenceRenderingVersion'] == '0.31.0', 'historical reference is not Rendering provider UI.Template 0.32.1')
    # Wizard019/020 forward the same sdd default: the omission rule names only015.
    effective_lifecycle = lifecycle if lifecycle is not None else 'sdd'
    effective_bundle = bundle if bundle is not None else 'player'
    argv = ['<qualified-installed-Wizard' + wizard_version + '>', str(pathlib.Path(sys.argv[2]) / 'wizard'), 'ReferenceCurrentPublic', '--template', 'fable-game', '--ref', sources['descriptor'][0], '--pinned', '--no-governance', '--no-coordination']
    if lifecycle is not None:
        argv += ['--lifecycle', lifecycle]
    if bundle is not None:
        argv += ['--bundle', bundle]
    print(json.dumps({
        'scope': 'immutable-source and declared-input preflight only; no archive/installed/runtime proof',
        'packages': packages, 'wizardArgv': argv,
        'wizardCohort': {'version': wizard_version, 'embeddedCoordVersion': '0.108.0',
                         'selection': 'selected020 source preparation' if wizard_version == '0.20.0' else 'retained019 source compatibility',
                         'receiverEvidence': 'must bind this exact Wizard; no019-to020 acceptance transfer'},
        'providerParameters': {'productName': 'ReferenceCurrentPublic', 'bundle': effective_bundle, 'lifecycle': effective_lifecycle},
        'defaults': defaults,
        'rendering': {'historicalReference': '0.31.0', 'providerUiTemplate': None, 'workspace019SvgLibraries': '0.32.1'},
        'runtimeDisposition': 'held',
        'remaining': ['qualify actual downloaded archives/signatures and installed tool/registration payloads',
                      'observe sole initial0182 Governance/knowledge preflight before target effects and actual provider019 registration transition',
                      'admit exact Gate/Governance operation and browser/native custody profiles with original deadlines/cleanup',
                      'execute genuine selected/default and explicit-none lifecycle/bundle receivers, knowledge/key/provenance assertions',
                      'qualify actual product builds, browser journeys and full4709 remaining acceptance; Complete WASM remains separately owned']
    }, sort_keys=True))
except (ValueError, TypeError, KeyError, OSError) as error:
    print('current-public preflight refused: ' + str(error), file=sys.stderr)
    sys.exit(2)
CURRENT_PUBLIC
  if ! $preflight; then
    echo 'current-public runtime held: downloaded/installed custody, pre-target Governance and admitted Gate/browser/native profiles remain required; inspect preflight assertion plan' >&2
    exit 2
  fi
  exit 0
fi
[[ -z "$current_inputs" ]] || usage
[[ "$mode" == templates || "$mode" == full || "$mode" == wasm ]] || usage
# Current public cohorts (FS-GG/.github#4709): published Workspace.Template archive, peeled tag/source
# revision and descriptor, each independently read back from nuget.org/GitHub. 0.19.2 (2026-10-22) is
# an accepted historical successor. 0.19.3 (FS.GG.Wasm 0.7.0 receiver; release run 39910502481, tag
# 386e32b7 -> 7be0bcf5, signed nuget.org archive byte-verified 2026-10-23) is the current public template.
# A version without a complete row refuses every route.
declare -A current_template_shas=([0.19.2]=ef5c5c2fb2de372a427c5abaf8bb4cdf91d7776b5628f07c016d4eb9ac87469a [0.19.3]=9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2)
declare -A current_template_revisions=([0.19.2]=d15f085ff4d64b7736e09ff263644b3c86a576a6 [0.19.3]=7be0bcf5886d39a8161b186beb8cc06e82415f1e)
declare -A current_descriptor_shas=([0.19.2]=e8dbf8958f90d522e577378ae36b0e131954e400991d542ae9709ac32c713e3b [0.19.3]=6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006)
current_public=false
if [[ -n "$version" && -n "${current_template_shas[$version]:-}" && -n "${current_template_revisions[$version]:-}" && -n "${current_descriptor_shas[$version]:-}" ]]; then
  current_public=true
fi
current_sdd_sha=1df2e74faebd388f90b813ed9d7497f4247f977718469c9247b37111d791921f
current_sdd_revision=c1fee66a34ec8d222586eb708ddff4973ad5594e
current_wizard_sha=caa91285e5370edc7a8a14a5a46f6cfef236d1db95f1e186357e6591b9ec7bd5
current_wizard_revision=6e6fb9b9f7677e26f0c7d58cab1646323e81df58
# Wizard 0.21.0+ pinned creation of the typed-sdd lifecycle (unchanged in 0.22.0, .github#4813) admits only the sole exact
# public Workspace.Template 0.18.2 project-knowledge registration before any target effect.
current_overlay_sha=496aad0e89496719bc543edc6ffbf829a82307862e630ba4e174e374ac11cc4e
if [[ "$mode" == wasm ]]; then
  # Workspace.Template 0.19.3 is the selected WASM receiver: it carries FS.GG.Wasm [0.7.0]
  # (FS-GG/FS.GG.Game#727), asserted below. 0.19.0 Complete scaffolds truncate guest/policy.c, and
  # 0.19.1/0.19.2 carry the 0.3.0 receiver whose policy deadline spans cold Worker startup.
  [[ "$version" == 0.19.3 && -z "$sdd_version$sdd_sha$sdd_revision$wizard_version$wizard_sha$wizard_revision" ]] || usage
else
  # Closed published cohorts. 0.18.1/SDD 2.1.0/Wizard 0.16.0 is historical; a current public
  # Workspace.Template with SDD 2.4.0/Wizard 0.22.0 is the default the documented install resolves
  # (FS-GG/.github#4709). The cohort binds every public archive/source identity here, not only inputs.
  [[ ( "$version" == 0.18.1 && "$sdd_version" == 2.1.0 ) \
     || ( "$current_public" == true && "$sha" == "${current_template_shas[$version]}" && "$revision" == "${current_template_revisions[$version]}" \
          && "$descriptor_sha" == "${current_descriptor_shas[$version]}" \
          && "$sdd_version" == 2.4.0 && "$sdd_sha" == "$current_sdd_sha" && "$sdd_revision" == "$current_sdd_revision" ) ]] || usage
fi
if [[ "$mode" == full ]]; then
  [[ "$wizard_sha" =~ ^[0-9a-f]{64}$ && "$wizard_revision" =~ ^[0-9a-f]{40}$ ]] || usage
  [[ ( "$version" == 0.18.1 && "$wizard_version" == 0.16.0 ) \
     || ( "$current_public" == true && "$wizard_version" == 0.22.0 && "$wizard_sha" == "$current_wizard_sha" && "$wizard_revision" == "$current_wizard_revision" ) ]] || usage
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
  : "${FSGG_WASM_SDK_ARCHIVE:?qualified public SDK 0.7 archive required}"
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
    [[ $rc -eq 0 ]] && wasm_status=source-passed
    python3 - "$evidence/qualification.json" "$wasm_status" "$version" "$revision" "$tag_revision" "$sha" "$descriptor_sha" <<'WASM_RECEIPT'
import json, sys, os
path, status, version, revision, tag_revision, archive, descriptor = sys.argv[1:]
with open(path, 'w') as out:
    json.dump({'schema':'fable-reference-public/1','disposition':status,'mode':'wasm',
      'scope':'direct downloaded Complete WASM source consumer and default WASM-off receiver; no provider/Wizard/FourD/AT acceptance',
      'browserCases':'managed-groups-in-caller',
      'package':'FS.GG.Workspace.Template','version':version,'sourceRevision':revision,
      'tag':'fs-gg-templates/v'+version,'tagRevision':tag_revision,
      'archiveSha256':archive,'descriptorSha256':descriptor,
      'sdd':None,'wizard':None,'wizardQualification':'pending',
      'firefoxProfile':os.environ['FSGG_WASM_FIREFOX_PROFILE'],
      'workerCleanupBoundary':'browser workers run in caller-managed groups, not by this checker'}, out, indent=2)
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
  # Read-only tag read: 3 bounded attempts (20 s each, 5 s kill grace, 5 s then 10 s backoff; at most
  # 100 s), so a transient error cannot spend a single-use admission. The result is still compared below.
  refs_text=''
  for attempt in 1 2 3; do
    if refs_text="$(timeout -k 5 20 git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/$tag" "refs/tags/$tag^{}")"; then break; fi
    refs_text=''
    [[ "$attempt" -lt 3 ]] || { echo 'WASM public tag read failed after 3 bounded attempts' >&2; exit 1; }
    sleep $((attempt * 5))
  done
  mapfile -t remote_refs <<<"$refs_text"
  resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 ~ /\^\{\}$/ {print $1}')"
  [[ -n "$resolved" ]] || resolved="$(printf '%s\n' "${remote_refs[@]}" | awk '$2 !~ /\^\{\}$/ {print $1}')"
  [[ "$resolved" == "$tag_revision" && "$(printf '%s\n' "$resolved" | wc -l)" -eq 1 ]] || { echo 'WASM public immutable tag mismatch' >&2; exit 1; }
  # Both fetches are idempotent GETs, retried (bounded: 15 s per attempt, 60 s retry window) so a transient
  # error cannot spend a single-use admission. Retries restart the output file; the bytes are then
  # hash-checked below (--sha256 / --descriptor-sha256) exactly as before.
  curl -q --fail --silent --show-error --location --retry 3 --retry-all-errors --retry-max-time 60 --max-time 15 --max-filesize 8388608 "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/$version/fs.gg.workspace.template.$version.nupkg" -o "$archive"
  curl -q --fail --silent --show-error --location --retry 3 --retry-all-errors --retry-max-time 60 --max-time 15 --max-filesize 1048576 "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$revision/providers/fable-game.providers.yml" -o "$descriptor"
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
    assert refs['FS.GG.Wasm.Contracts']==refs['FS.GG.Wasm.Browser']=='[0.7.0]'
    assert value['Properties']['NuGetLockFilePath'].endswith('/Examples/Wasm/packages.lock.json')
WASM_GRAPH
    if [[ "$enabled" == true ]]; then python3 "$foundation/Examples/Wasm/materialize-assets.py" "$foundation"; fi
    (cd "$evidence/$receiver" && FsGgWasmPolicyExample="$enabled" "$DOTNET_HOST_PATH" --fx-version 10.0.12 "$FSGG_WASM_FABLE_CORE" SvgFoundation/SvgFoundation.fsproj --outDir SvgFoundation/output --noCache --noRestore) >"$evidence/$receiver-fable.log" 2>&1
    (cd "$evidence/$receiver/Client" && npm ci "${npm_args[@]}") >"$evidence/$receiver-npm.log" 2>&1
    (cd "$evidence/$receiver" && FSGG_WASM_POLICY_EXAMPLE="$enabled" FsGgWasmPolicyExample="$enabled" ./Client/node_modules/.bin/vite build --config SvgFoundation/vite.config.js) >"$evidence/$receiver-vite.log" 2>&1
    if [[ "$enabled" == false ]]; then
      [[ ! -e "$foundation/dist/_content/FS.GG.Wasm.Browser" && ! -e "$foundation/dist/wasm-policy-guests" && ! -e "$foundation/dist/wasm-policy" && ! -e "$foundation/dist/wasm-package-assets.json" ]] || { echo 'Default build contains WASM assets' >&2; exit 1; }
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
  # WASM-off (disabled) browser path, FS-GG/.github#4710: the same pattern on the published DEFAULT
  # product built above with FsGgWasmPolicyExample=false. The generated cases observe the production
  # page in the browser: it renders without page errors, constructs no Worker/SharedWorker, compiles or
  # instantiates no WebAssembly (with a positive hook control), requests and serves no WASM/Worker/policy
  # asset, and mounts no policy UI. They import only the GENERATED maintained config.
  cat >"$evidence/default/Browser.Tests/wasm-off.generated.config.ts" <<'WASM_OFF_CONFIG'
import { defineConfig } from "@playwright/test";
import maintained from "./playwright.config";
const family = process.env.PLAYWRIGHT_BROWSER_FAMILY;
const results = process.env.FSGG_WASM_RESULTS;
if (!["chromium", "firefox", "webkit"].includes(family ?? "") || !results?.startsWith("/")) throw new Error("explicit family/results required");
if (process.env.FsGgWasmPolicyExample !== "false" || process.env.PLAYWRIGHT_EXECUTABLE_PATH) throw new Error("default WASM-off own-archive profile required");
export default defineConfig({ ...maintained, testMatch: "wasm-off.generated.spec.ts", workers: 1, retries: 0,
  timeout: 30000, expect: { timeout: 5000 }, outputDir: `${results}/${family}/test-results`,
  reporter: [["line"], ["json", { outputFile: `${results}/${family}/report.json` }]],
  use: { ...maintained.use, trace: "on", screenshot: "only-on-failure", video: "off" },
  webServer: [{ command: "../Client/node_modules/.bin/vite preview --config vite.config.js --host 127.0.0.1 --port 5100 --strictPort",
    cwd: "../SvgFoundation", url: "http://127.0.0.1:5100/", timeout: 30000, reuseExistingServer: false }]
});
WASM_OFF_CONFIG
  cat >"$evidence/default/Browser.Tests/wasm-off.generated.spec.ts" <<'WASM_OFF_SPEC'
import { expect, test, type Page } from "@playwright/test";

// The published default product, built with FsGgWasmPolicyExample=false: the WASM-off browser path.
const wasmAsset = /\.wasm(?:[?#]|$)|\/_content\/FS\.GG\.Wasm\.|module-worker\.mjs|worker-client\.mjs|\/wasm-policy\/|wasm-package-assets\.json/;

async function open(page: Page) {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("request", request => requests.push(request.url()));
  page.on("pageerror", error => errors.push(String(error)));
  await page.addInitScript(() => {
    const scope = globalThis as any;
    const counts = { worker: 0, sharedWorker: 0, wasm: 0, hooked: false };
    scope.__fsggWasmOff = counts;
    for (const [name, key] of [["Worker", "worker"], ["SharedWorker", "sharedWorker"]] as const) {
      const original = scope[name];
      if (typeof original === "function") {
        scope[name] = new Proxy(original, { construct(target, args, newTarget) { (counts as any)[key]++; return Reflect.construct(target, args, newTarget); } });
      }
    }
    const wasm = scope.WebAssembly;
    if (wasm) {
      for (const name of ["compile", "compileStreaming", "instantiate", "instantiateStreaming", "validate"]) {
        const original = wasm[name];
        if (typeof original === "function") wasm[name] = function (this: unknown, ...args: unknown[]) { counts.wasm++; return original.apply(this, args); };
      }
      for (const name of ["Module", "Instance"]) {
        const original = wasm[name];
        if (typeof original === "function") wasm[name] = new Proxy(original, { construct(target, args, newTarget) { counts.wasm++; return Reflect.construct(target, args, newTarget); } });
      }
    }
    counts.hooked = true;
  });
  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Cooperative SVG arena");
  await page.waitForLoadState("networkidle");
  return { requests, errors };
}

test.describe("default WASM-off product", () => {
  test("default production page renders its game surface without page errors", async ({ page }) => {
    const { errors } = await open(page);
    await expect(page.locator("svg").first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("no Worker or SharedWorker is constructed", async ({ page }) => {
    await open(page);
    expect(await page.evaluate(() => (globalThis as any).__fsggWasmOff)).toMatchObject({ hooked: true, worker: 0, sharedWorker: 0 });
    // Positive control: the hook observes a construction (an inert Blob Worker, terminated at once).
    expect(await page.evaluate(() => {
      const url = URL.createObjectURL(new Blob([""], { type: "text/javascript" }));
      new Worker(url).terminate();
      URL.revokeObjectURL(url);
      return (globalThis as any).__fsggWasmOff.worker;
    })).toBe(1);
  });

  test("no WebAssembly module is compiled, instantiated or validated on the page", async ({ page }) => {
    await open(page);
    expect(await page.evaluate(() => (globalThis as any).__fsggWasmOff)).toMatchObject({ hooked: true, wasm: 0 });
    // Positive control: the hook observes a call (validate creates no module or instance).
    expect(await page.evaluate(() => { WebAssembly.validate(new Uint8Array([0, 0x61, 0x73, 0x6d, 1, 0, 0, 0])); return (globalThis as any).__fsggWasmOff.wasm; })).toBe(1);
  });

  test("no WASM, Worker or policy asset is requested", async ({ page }) => {
    const { requests } = await open(page);
    expect(requests.filter(url => wasmAsset.test(url))).toEqual([]);
  });

  test("no WASM policy UI is mounted", async ({ page }) => {
    await open(page);
    await expect(page.locator("#wasm-policy-example")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Load policy", exact: true })).toHaveCount(0);
  });

  test("WASM package and guest assets are not served", async ({ page }) => {
    await open(page);
    for (const path of ["/_content/FS.GG.Wasm.Browser/module-worker.mjs", "/_content/FS.GG.Wasm.Browser/worker-client.mjs",
                        "/wasm-policy/c-normal.wasm", "/wasm-policy/modules.json", "/wasm-package-assets.json"]) {
      const response = await page.request.get(path);
      const type = response.headers()["content-type"] ?? "";
      const body = await response.body();
      const asset = response.ok() && (/javascript|wasm|json/.test(type) || body.subarray(0, 4).equals(Buffer.from([0, 0x61, 0x73, 0x6d])));
      expect(asset, `${path} -> ${response.status()} ${type}`).toBe(false);
    }
  });
});
WASM_OFF_SPEC
  (cd "$evidence/default/Browser.Tests" && npm ci "${npm_args[@]}") >"$evidence/browser-off-npm.log" 2>&1
  # Browser cases are not run here. The managed caller runs each Playwright --list/test
  # invocation as its own require-empty managed group and asserts 9 enabled cases and 6 WASM-off
  # cases per family.
  echo 'WASM public: direct default/opt-in source and production graph passed; the 27 enabled and 18 WASM-off browser cases run as managed groups in the caller; retaining/provider/Wizard/AT/native-exit acceptance not claimed'
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
wizard_home="$DOTNET_CLI_HOME"; wizard_none_home="$DOTNET_CLI_HOME"; wizard_default_lifecycle=typed-sdd
if [[ "$current_public" == true ]]; then
  # Fresh Wizard hives: the direct route above already registered the archive in the shared hive.
  # Wizard 0.21.0+ (unchanged in 0.22.0) pinned creation of an omitted or typed-sdd fable-game lifecycle admits only the
  # sole exact public 0.18.2 project-knowledge registration first; explicit none starts empty.
  # Every hive must end on the selected published current-public bytes.
  overlay="$evidence/feed/FS.GG.Workspace.Template.0.18.2.nupkg"
  curl --fail --silent --show-error --location "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.18.2/fs.gg.workspace.template.0.18.2.nupkg" -o "$overlay"
  [[ "$(sha256sum "$overlay" | cut -d' ' -f1)" == "$current_overlay_sha" ]] || { echo 'fable-reference-public: 0.18.2 overlay identity mismatch' >&2; exit 1; }
  wizard_home="$evidence/wizard-home"; wizard_none_home="$evidence/wizard-none-home"
  wizard_typed_home="$evidence/wizard-typed-home"; wizard_public_home="$evidence/wizard-public-home"
  mkdir "$wizard_home" "$wizard_none_home" "$wizard_typed_home" "$wizard_public_home"
  for hive in "$wizard_home" "$wizard_typed_home" "$wizard_public_home"; do
    DOTNET_CLI_HOME="$hive" "$DOTNET_HOST_PATH" new install "$overlay" >>"$evidence/wizard-overlay-install.log"
  done
fi
PATH="$evidence/tools/checked-sdd:$PATH" DOTNET_CLI_HOME="$wizard_home" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard" ReferenceWizard --template fable-game --bundle complete --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard.log"
PATH="$evidence/tools/checked-sdd:$PATH" DOTNET_CLI_HOME="$wizard_none_home" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard-none" ReferenceWizardNone --template fable-game --bundle complete --lifecycle none --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard-none.log"
if [[ "$current_public" == true ]]; then
  PATH="$evidence/tools/checked-sdd:$PATH" DOTNET_CLI_HOME="$wizard_typed_home" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard-typed" ReferenceWizardTyped --template fable-game --bundle complete --lifecycle typed-sdd --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard-typed.log"
  # The public default: no lifecycle and no bundle, exactly as a user omits them.
  PATH="$evidence/tools/checked-sdd:$PATH" DOTNET_CLI_HOME="$wizard_public_home" "$DOTNET_HOST_PATH" "$wizard_core" "$evidence/wizard-public" ReferenceWizardPublic --template fable-game --ref "$tag" --pinned --no-governance --no-coordination >"$evidence/wizard-public.log"
  for hive in "$wizard_home" "$wizard_none_home" "$wizard_typed_home" "$wizard_public_home"; do
    python3 - "$hive/.templateengine/packages.json" "$sha" "$version" <<'WIZARD_REGISTRY'
import hashlib, json, pathlib, sys
registry, sha, version = sys.argv[1:]
rows = [p for p in json.loads(pathlib.Path(registry).read_text(encoding='utf-8-sig'))['Packages'] if p['Details'].get('PackageId') == 'FS.GG.Workspace.Template']
assert len(rows) == 1, 'Wizard hive must end with one Workspace.Template registration'
assert rows[0]['Details'].get('Version') == version, 'Wizard hive did not resolve the selected public successor'
assert hashlib.sha256(pathlib.Path(rows[0]['MountPointUri']).read_bytes()).hexdigest() == sha, 'Wizard hive archive is not the published nuget.org bytes'
WIZARD_REGISTRY
    cp "$hive/.templateengine/packages.json" "$evidence/$(basename "$hive" -home)-registry.json"
  done
  python3 - "$evidence/wizard-public" <<'PUBLIC_DEFAULT'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
p = json.loads((root/'.fsgg/scaffold-provenance.json').read_text())
params = {x['key']: x['value'] for x in p['effectiveParameters']}
assert p['generator'] == {'id': 'FS.GG.SDD.Artifacts', 'version': '2.4.0'}, 'public default generator drifted'
assert params.get('lifecycle') == 'typed-sdd' and params.get('bundle') == 'player', 'public default lifecycle/bundle drifted: %r' % params
assert not (root/'SvgFoundation/Studio').exists() and not (root/'SvgFoundation/Examples/Wasm').exists(), 'player default must omit Studio and WASM'
assert re.search(r"'\$\(FsGgSvgInputVersion\)' == ''\">0\.32\.3<", (root/'SvgFoundation/SvgFoundation.fsproj').read_text()), 'public default SVG input is not Rendering 0.32.3'
assert (root/'ReferenceWizardPublic.slnx').is_file() and (root/'.fsgg/knowledge-guide.md').is_file()
PUBLIC_DEFAULT
fi
fi

"${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/direct" --route direct --lifecycle none --sdd-version "$sdd_version" --product-name ReferenceDirect
provider_routes=(provider); [[ "$mode" != full ]] || provider_routes+=(wizard)
for route in "${provider_routes[@]}"; do
  if [[ "$route" == provider ]]; then product=ReferenceProvider; none_product=ReferenceProviderNone; else product=ReferenceWizard; none_product=ReferenceWizardNone; fi
  expected_lifecycle=typed-sdd; [[ "$route" != wizard ]] || expected_lifecycle="$wizard_default_lifecycle"
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/$route" --route "$route" --lifecycle "$expected_lifecycle" --sdd-version "$sdd_version" --product-name "$product"
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/$route-none" --route "$route" --lifecycle none --sdd-version "$sdd_version" --product-name "$none_product"
done
if [[ "$mode" == full && "$current_public" == true ]]; then
  "${validator[@]}" reference-receiver-check --archive "$archive" --receiver "$evidence/wizard-typed" --route wizard --lifecycle typed-sdd --sdd-version "$sdd_version" --product-name ReferenceWizardTyped
  # Runtime of the exact public default workspace (player bundle, Wizard typed-sdd lifecycle).
  (cd "$evidence/wizard-public" && QUINT_BIN="$QUINT_BIN" bash build.sh) >"$evidence/wizard-public-build.log" 2>&1
fi
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
