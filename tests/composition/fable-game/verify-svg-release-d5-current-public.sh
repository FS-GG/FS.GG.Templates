#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
helper="$root/tests/composition/fable-game/d5-current-public.py"
[[ $# -ge 2 && $# -le 3 ]] || { echo 'usage: current-public.sh ABSOLUTE_PINS NEW_ABSOLUTE_EVIDENCE [--preflight-only|--rehearsal|--full]' >&2; exit 2; }
pins="$1"; out="$2"; scope=rehearsal
[[ "$pins" = /* && "$out" = /* && ! -e "$out" && ! -L "$out" ]] || exit 2
[[ $# == 2 || "$3" == --preflight-only || "$3" == --rehearsal || "$3" == --full ]] || exit 2
python3 "$helper" preflight "$pins"
[[ "${3:-}" != --preflight-only ]] || { echo 'PASS current identity preflight; no acquisition or product invocation'; exit 0; }
[[ "${3:-}" != --full ]] || scope=full
fail() { echo "current D.5: $*" >&2; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
: "${DOTNET_HOST_PATH:?qualified absolute dotnet host required}"
: "${QUINT_BIN:?qualified Quint profile-2 binary required}"
: "${LMT_BIN:?qualified lmt profile-2 binary required}"
[[ "$DOTNET_HOST_PATH" = /* && -x "$DOTNET_HOST_PATH" && ! -L "$DOTNET_HOST_PATH" ]] || fail 'dotnet host custody'
[[ -x "$QUINT_BIN" && "$(sha "$QUINT_BIN")" == 939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f ]] || fail 'Quint identity'
[[ -x "$LMT_BIN" && "$(sha "$LMT_BIN")" == 37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10 ]] || fail 'lmt identity'
umask 077
mkdir "$out"; mkdir "$out"/{feed,home,packages,http,tools,hives}
cp "$pins" "$out/pins.json"; pins="$out/pins.json"
python3 "$helper" preflight "$pins" # Validate the frozen copy before any acquisition.
status=failed
finish() {
  local rc=$?
  trap - EXIT
  python3 - "$out" "$scope" "$status" "$rc" "$root" <<'RECEIPT'
import hashlib,json,pathlib,subprocess,sys
out,scope,status,rc,source=sys.argv[1:];out=pathlib.Path(out);source=pathlib.Path(source)
if status=='passed':
 rows=[line.split('\t') for line in (out/'cases.tsv').read_text().splitlines()]
 assert len(rows)==(42 if scope=='full' else 2) and all(len(row)==4 for row in rows)
 expected={'raw-omitted'}|{row[0] for row in rows}
 assert len(expected)==len(rows)+1 and {p.stem for p in out.glob('*.checked')}==expected
receipt={'schema':'fsgg.svg-release-d5.current-public-receiver/1','result':status,'exitCode':int(rc),'scope':scope,
 'pins':json.loads((out/'pins.json').read_text()),'publicOnly':True,
 'matrix':'complete' if status=='passed' and scope=='full' else 'pending-full-matrix',
 'rawOmittedPlayer':'passed' if (out/'raw-omitted.checked').exists() else 'unproved',
 'completedCases':sorted(p.stem for p in out.glob('*.checked')),
 'defaultBackendReceivers':['provider-omitted','wizard-omitted'] if status=='passed' else [],
 'backend':'quint-specification-v1','profile':'fsgg-quint-profile/2',
 'buildBrowserReuse':'no product build/browser rerun; helper validator compilation only; prior39988246429 remains separately scoped',
 'authorInspectArtifactHashes':'passed' if status=='passed' else 'unproved',
 'wrongProfileRefusalAndOwnerPreservation':'passed' if status=='passed' else 'unproved',
 'implementationAcceptance':'root independent review of actual evidence required',
 'source':{'head':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
           'dirty':bool(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip())}}
receipt['evidenceSha256']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
 for p in out.iterdir() if p.is_file() and p.suffix in ('.json','.log','.yml','.checked')}
receipt['determiningSourceSha256']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in (
 'tests/composition/fable-game/verify-svg-release-d5-current-public.sh',
 'tests/composition/fable-game/d5-current-public.py', 'tests/composition/fable-game/d5-public-pins.py',
 'src/FS.GG.Templates.ProviderTool/Program.fs')}
(out/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
RECEIPT
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
config="$out/NuGet.Config"
printf '%s\n' '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' >"$config"
cd "$out"
fetch() {
  local key="$1" id="$2" version
  version="$(jq -r --arg key "$key" '.[$key].version' "$pins")"
  curl --fail --silent --show-error --location --max-time 120 --max-filesize 134217728 \
    "https://api.nuget.org/v3-flatcontainer/${id,,}/$version/${id,,}.$version.nupkg" -o "$out/feed/$id.$version.nupkg"
  python3 "$helper" archive "$pins" "$key" "$out/feed/$id.$version.nupkg"
}
fetch templates FS.GG.Workspace.Template
fetch overlay FS.GG.Workspace.Template
fetch sdd FS.GG.SDD.Cli
fetch wizard FS.GG.NewSddWorkspace
template="$out/feed/FS.GG.Workspace.Template.0.19.3.nupkg"
overlay="$out/feed/FS.GG.Workspace.Template.0.18.2.nupkg"
provider="$out/fable-game.providers.yml"
tag=fs-gg-templates/v0.19.3
revision=7be0bcf5886d39a8161b186beb8cc06e82415f1e
git ls-remote --tags https://github.com/FS-GG/FS.GG.Templates.git "refs/tags/$tag" "refs/tags/$tag^{}" >"$out/tag-refs.log"
python3 - "$out/tag-refs.log" "$tag" "$revision" <<'TAG'
import pathlib,sys
refs={ref:sha for sha,ref in (line.split() for line in pathlib.Path(sys.argv[1]).read_text().splitlines())}
name='refs/tags/'+sys.argv[2];assert refs.get(name+'^{}',refs.get(name))==sys.argv[3]
TAG
curl --fail --silent --show-error --location --max-time 120 --max-filesize 1048576 "https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/$revision/providers/fable-game.providers.yml" -o "$provider"
[[ "$(sha "$provider")" == 6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006 ]] || fail 'descriptor identity'
# Reuse the maintained archive/installed-tool validator, not a new tool-store decoder.
tool_project="$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
"$DOTNET_HOST_PATH" restore "$tool_project" --configfile "$config" >"$out/validator-restore.log"
"$DOTNET_HOST_PATH" build "$tool_project" --no-restore >"$out/validator-build.log"
validator=("$DOTNET_HOST_PATH" run --project "$tool_project" --no-build --no-restore --)
"${validator[@]}" reference-publication-check --archive "$template" --descriptor "$provider" --template-version 0.19.3 \
  --sha256 9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2 --source-revision "$revision" --tag-revision "$revision" \
  --descriptor-sha256 6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006 >"$out/template-check.log"
for key in sdd wizard; do
  id=FS.GG.SDD.Cli; command=fsgg-sdd
  [[ "$key" != wizard ]] || { id=FS.GG.NewSddWorkspace; command=new-sdd-workspace; }
  version="$(jq -r --arg key "$key" '.[$key].version' "$pins")"
  digest="$(jq -r --arg key "$key" '.[$key].sha256' "$pins")"
  source="$(jq -r --arg key "$key" '.[$key].sourceCommit' "$pins")"
  archive="$out/feed/$id.$version.nupkg"
  "${validator[@]}" published-tool-check --archive "$archive" --sha256 "$digest" --package-id "$id" --version "$version" --source-revision "$source" >"$out/$key-package-check.log"
  "$DOTNET_HOST_PATH" tool install "$id" --version "$version" --tool-path "$out/tools/$key" --configfile "$config" --add-source "$out/feed" --no-cache >"$out/$key-install.log"
  core="$("${validator[@]}" installed-tool-check --archive "$archive" --tool-root "$out/tools/$key" --sha256 "$digest" --package-id "$id" --version "$version" --source-revision "$source" --command-name "$command")"
  [[ "$core" = "$out/tools/$key/.store/"* ]] || fail 'installed tool core escaped owned store'
  if [[ "$key" == sdd ]]; then sdd_core="$core"; else wizard_core="$core"; fi
done
mkdir "$out/tools/checked-sdd"
cat >"$out/tools/checked-sdd/fsgg-sdd" <<'ADAPTER'
#!/usr/bin/env bash
set -euo pipefail
exec "$CHECKED_DOTNET_HOST" "$CHECKED_SDD_CORE" "$@"
ADAPTER
chmod 700 "$out/tools/checked-sdd/fsgg-sdd"
export CHECKED_DOTNET_HOST="$DOTNET_HOST_PATH" CHECKED_SDD_CORE="$sdd_core"
export PATH="$out/tools/checked-sdd:$PATH"
"$DOTNET_HOST_PATH" new install "$template" >"$out/template-install.log"
"$DOTNET_HOST_PATH" new fs-gg-fable-game -n CurrentD5Raw -o "$out/raw-omitted" >"$out/raw-omitted.log"
python3 "$helper" tree "$out/raw-omitted" omitted omitted raw
touch "$out/raw-omitted.checked"
python3 "$helper" cases "$scope" >"$out/cases.tsv"
while IFS=$'\t' read -r name route lifecycle bundle; do
  destination="$out/$name"; effective="$lifecycle"
  [[ "$effective" != omitted ]] || effective=typed-sdd
  if [[ "$route" == provider ]]; then
    mkdir -p "$destination/.fsgg"; cp "$provider" "$destination/.fsgg/providers.yml"
    args=(scaffold --root "$destination" --provider fable-game --no-update --json --param "productName=D5${name//-/}")
    [[ "$lifecycle" == omitted ]] || args+=(--param "lifecycle=$lifecycle")
    [[ "$bundle" == omitted ]] || args+=(--param "bundle=$bundle")
    "$DOTNET_HOST_PATH" "$sdd_core" "${args[@]}" >"$out/$name.json"
    jq -e '.outcome=="succeeded" and .scaffold.providerInvoked==true' "$out/$name.json" >/dev/null
  else
    # Every Wizard case owns a new hive. Pinned omitted/typed creation requires
    # the sole exact public0.18.2 knowledge registration before any target effect.
    hive="$out/hives/$name"; mkdir "$hive"
    if [[ "$effective" == typed-sdd ]]; then DOTNET_CLI_HOME="$hive" "$DOTNET_HOST_PATH" new install "$overlay" >"$out/$name-overlay.log"; fi
    args=("$destination" "D5${name//-/}" --template fable-game --ref "$tag" --pinned --no-governance --no-coordination)
    [[ "$lifecycle" == omitted ]] || args+=(--lifecycle "$lifecycle")
    [[ "$bundle" == omitted ]] || args+=(--bundle "$bundle")
    DOTNET_CLI_HOME="$hive" "$DOTNET_HOST_PATH" "$wizard_core" "${args[@]}" >"$out/$name.log"
    python3 - "$hive/.templateengine/packages.json" "$template" <<'REGISTRY'
import hashlib,json,pathlib,sys
rows=[p for p in json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8-sig'))['Packages'] if p['Details'].get('PackageId')=='FS.GG.Workspace.Template']
assert len(rows)==1 and rows[0]['Details']['Version']=='0.19.3'
assert hashlib.sha256(pathlib.Path(rows[0]['MountPointUri']).read_bytes()).digest()==hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).digest()
REGISTRY
    cp "$hive/.templateengine/packages.json" "$out/$name-registry.json"
  fi
  python3 "$helper" tree "$destination" "$lifecycle" "$bundle"
  touch "$out/$name.checked"
done <"$out/cases.tsv"
"$DOTNET_HOST_PATH" "$sdd_core" typed-sdd provision --cache "$out/cache" --quint "$QUINT_BIN" --lmt "$LMT_BIN" >"$out/provision.json"
jq -e '.outcome=="succeeded"' "$out/provision.json" >/dev/null
for name in provider-omitted wizard-omitted; do
  destination="$out/$name"
  python3 "$helper" model "$template" "$destination/models/svg-arena"
  "$DOTNET_HOST_PATH" "$sdd_core" typed-sdd author --root "$destination" --work d5-default --title 'Current public default' \
    --agent composition --session current-public --cache "$out/cache" --profile fsgg-quint-profile/2 \
    --source models/svg-arena/arena-rules.md --bindings models/svg-arena/arena-rules.bindings.json >"$out/$name-author.json"
  "$DOTNET_HOST_PATH" "$sdd_core" typed-sdd inspect --root "$destination" --work d5-default >"$out/$name-inspect.json"
  for action in author inspect; do jq -e '.outcome=="succeeded" and .classification=="quint-specification-v1"' "$out/$name-$action.json" >/dev/null; done
  python3 "$helper" authority "$destination"
  python3 - "$destination/models/svg-arena/arena-rules.bindings.json" <<'WRONG'
import pathlib,json,sys
p=pathlib.Path(sys.argv[1]);value=json.loads(p.read_text());value['profile']='fsgg-quint-profile/1';p.with_name('refused.bindings.json').write_text(json.dumps(value)+'\n')
WRONG
  python3 "$helper" snapshot "$destination" "$out/$name-owner-before.json"
  if "$DOTNET_HOST_PATH" "$sdd_core" typed-sdd author --root "$destination" --work d5-refused --title 'Current public refusal' \
    --agent composition --session current-refused --cache "$out/cache" --profile fsgg-quint-profile/2 \
    --source models/svg-arena/arena-rules.md --bindings models/svg-arena/refused.bindings.json >"$out/$name-refused.json"; then fail 'wrong-profile bindings accepted'; fi
  jq -e '.outcome=="blocked" and .changedPaths==[] and any(.diagnostics[];.id=="QUINT-PROFILE-IDENTITY")' "$out/$name-refused.json" >/dev/null
  python3 "$helper" preserved "$destination" "$out/$name-owner-before.json"
  python3 "$helper" snapshot "$destination" "$out/$name-owner-after.json"
  cp "$destination/readiness/d5-default/typed-authority.json" "$out/$name-authority.json"
done
status=passed
