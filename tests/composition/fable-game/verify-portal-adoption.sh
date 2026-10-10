#!/usr/bin/env bash
# Qualification recipe only: exact candidate adoption into a separately inventoried public baseline.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
out=""; source=""; game=""; game_sha=""
while (($#)); do
  case "$1" in
    --output) out="$2"; shift 2 ;;
    --templates-source) source="$2"; shift 2 ;;
    --canonical-game-archive) game="$2"; shift 2 ;;
    --canonical-game-archive-sha256) game_sha="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "${FSGG_TEMPLATES_NUPKG:-}" && -n "${FSGG_TEMPLATES_NUPKG_SHA256:-}" ]] || { echo 'actual candidate archive required; no repack fallback' >&2; exit 2; }
[[ "$out" == /* && ! -e "$out" && ! -L "$out" && "$source" =~ ^[0-9a-f]{40}$ ]] || { echo 'new absolute output and exact source required' >&2; exit 2; }
[[ "$(git -C "$root" rev-parse HEAD)" == "$source" && -z "$(git -C "$root" status --porcelain=v1 --untracked-files=all)" ]] || { echo 'exact clean source required' >&2; exit 2; }
retained="${FSGG_PORTAL_RETAINED_ROOT:?new owned public baseline receiver required}"
inventory="${FSGG_PORTAL_RETAINED_INVENTORY:?full pre-adoption inventory required}"
inventory_sha="${FSGG_PORTAL_RETAINED_INVENTORY_SHA256:?inventory pin required}"
baseline="${FSGG_PORTAL_PUBLIC_BASELINE:?actual public 0.18.1 archive required}"
# Required candidate guard above makes lane-package's local pack fallback unreachable.
LANE_REPO_ROOT="$root"
. "$root/tests/composition/lib/lane-package.sh"
package="$(lane_package_path "$out")"
verify=(python3 "$root/tests/composition/fable-game/verify-portal-example.py" --canonical-game-archive "$game" --canonical-game-archive-sha256 "$game_sha")
"${verify[@]}" --source "$root" --archive "$package" --archive-sha256 "$FSGG_TEMPLATES_NUPKG_SHA256" --templates-source "$source"
python3 - "$retained" "$inventory" "$inventory_sha" "$baseline" "$out" <<'PYBASELINE'
from pathlib import Path
import hashlib,json,os,stat,sys
receiver,inventory=map(Path,sys.argv[1:3]);expected=sys.argv[3];archive,output=map(Path,sys.argv[4:6])
for root in (receiver,output):
    if not root.is_absolute() or any(p.is_symlink() for p in [root,*root.parents]):raise SystemExit('absolute unlinked owned roots required')
if output.is_relative_to(receiver) or receiver.is_relative_to(output):raise SystemExit('output and receiver must be disjoint')
for path in (inventory,archive):
    if not path.is_file() or any(p.is_symlink() for p in [path,*path.parents]):raise SystemExit('regular unlinked inventory/archive required')
raw=inventory.read_bytes()
if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('retained inventory digest differs')
v=json.loads(raw)
if v['schema']!='fsgg.portal.retained-baseline-inventory/1' or v['receiver']!=str(receiver) or v['label']!='retained-before-future-adoption':raise SystemExit('genuine retained inventory identity differs')
if hashlib.sha256(archive.read_bytes()).hexdigest()!='0d9395b028f14b2c06afe1f1de019610217774f0cb8b6a9618f2aed7d51790fe':raise SystemExit('public baseline archive differs')
if v['package']['sha256']!='0d9395b028f14b2c06afe1f1de019610217774f0cb8b6a9618f2aed7d51790fe':raise SystemExit('inventoried package differs')
rows=[]
for p in sorted(receiver.rglob('*')):
    info=p.lstat();row={'path':p.relative_to(receiver).as_posix(),'mode':stat.S_IMODE(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):raise SystemExit('retained path is linked')
    if stat.S_ISDIR(info.st_mode):row['kind']='directory'
    elif stat.S_ISREG(info.st_mode):
        b=p.read_bytes();h=hashlib.sha256(b).hexdigest();row.update(kind='file',sha256=h,bytes=len(b),object=h)
    else:raise SystemExit('retained path type differs')
    rows.append(row)
if rows!=v['rows'] or stat.S_IMODE(receiver.lstat().st_mode)!=v['rootMode'] or (receiver/'PortalExample').exists():raise SystemExit('retained receiver changed before adoption')
print('PASS actual public baseline original full bytes/modes and three authored fixtures; no Portal yet')
PYBASELINE
mkdir -m 700 "$out"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http-cache"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 MSBUILDDISABLENODEREUSE=1
stage() {
  local label="$1" code=0; shift
  printf '%s\tstarted\n' "$label" >>"$out/stages.tsv"
  "$@" >"$out/$label.log" 2>&1 || code=$?
  printf '%s\texit=%d\n' "$label" "$code" >>"$out/stages.tsv"
  [[ "$code" == 0 ]] || { echo "first stage failure: $label exit=$code; dependent stages stopped" >&2; exit "$code"; }
}
stage install-candidate dotnet new install "$package" --force
stage generate-candidate dotnet new fs-gg-fable-game -n Portal-RetainedBaseline --productName Portal-RetainedBaseline --rootNamespace PortalRetainedBaseline -o "$out/candidate" --bundle player --lifecycle none --portalExample true
"${verify[@]}" --generated "$out/candidate" --expected true
manage=(python3 "$out/candidate/PortalExample/manage.py")
preserve() {
  python3 - "$retained" "$inventory" <<'PYPRESERVE'
from pathlib import Path
import hashlib,json,stat,sys
root=Path(sys.argv[1]);v=json.loads(Path(sys.argv[2]).read_text())
actual=[]
for p in sorted(root.rglob('*')):
    rel=p.relative_to(root).as_posix()
    if rel=='PortalExample' or rel.startswith('PortalExample/'):continue
    info=p.lstat();r={'path':rel,'mode':stat.S_IMODE(info.st_mode)}
    if stat.S_ISDIR(info.st_mode):r['kind']='directory'
    elif stat.S_ISREG(info.st_mode):
        b=p.read_bytes();h=hashlib.sha256(b).hexdigest();r.update(kind='file',sha256=h,bytes=len(b),object=h)
    else:raise SystemExit('outside-Portal type changed')
    actual.append(r)
if actual!=v['rows'] or stat.S_IMODE(root.lstat().st_mode)!=v['rootMode']:raise SystemExit('outside-Portal original bytes/modes changed')
print('PASS all original generated and authored bytes/modes preserved; changes stay in PortalExample')
PYPRESERVE
}
stage inventory "${manage[@]}" portal-inventory "$out/candidate" "$retained" "$baseline" "$out/adopt.json" "$out/adopt.diff"
stage apply "${manage[@]}" portal-apply "$out/candidate" "$retained" "$baseline" "$out/adopt.json" "$out/adopt-backup"
stage preserve-after-apply preserve
cat >"$out/Public.NuGet.Config" <<'CONFIG'
<configuration><packageSources><clear/><add key="nuget.org" value="https://api.nuget.org/v3/index.json"/></packageSources><packageSourceMapping><clear/><packageSource key="nuget.org"><package pattern="*"/></packageSource></packageSourceMapping></configuration>
CONFIG
(
  cd "$retained/PortalExample"
  stage preflight python3 verify-package-boundary.py --presentation --preflight
  cp packages.lock.json "$out/original.lock.json"
  stage restore dotnet restore Consumer.fsproj --configfile "$out/Public.NuGet.Config" --no-cache --locked-mode --disable-parallel -p:RestorePackagesPath="$out/packages"
  cmp packages.lock.json "$out/original.lock.json"
  stage boundary python3 verify-package-boundary.py --presentation
  stage build dotnet build Consumer.fsproj -c Release --no-restore -m:1 --disable-build-servers -p:RestorePackagesPath="$out/packages"
  stage default dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll
  stage presentation dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll --presentation
  code=0; dotnet exec --fx-version 10.0.12 bin/Release/net10.0/Consumer.dll --invalid >"$out/invalid.log" 2>&1 || code=$?
  printf 'invalid\texit=%d\n' "$code" >>"$out/stages.tsv"
  [[ "$code" == 2 ]] && grep -qF 'Usage: Box2D.Portals [--presentation]' "$out/invalid.log"
)
[[ ! -e "$retained/PortalExample/foreign-authored.txt" ]]
printf '%s\n' 'user-owned foreign Portal sentinel' >"$retained/PortalExample/foreign-authored.txt"
sentinel_sha="$(sha256sum "$retained/PortalExample/foreign-authored.txt" | cut -d' ' -f1)"
stage removal-inventory "${manage[@]}" portal-inventory "$out/candidate" "$retained" "$baseline" "$out/remove.json" "$out/remove.diff" --remove
stage remove "${manage[@]}" portal-remove "$out/candidate" "$retained" "$baseline" "$out/remove.json" "$out/remove-backup"
[[ "$sentinel_sha" == "$(sha256sum "$retained/PortalExample/foreign-authored.txt" | cut -d' ' -f1)" ]]
stage preserve-after-remove preserve
stage recover-removal "${manage[@]}" portal-recover "$retained" "$out/remove-backup"
stage recover-initial-adoption "${manage[@]}" portal-recover "$retained" "$out/adopt-backup"
[[ "$sentinel_sha" == "$(sha256sum "$retained/PortalExample/foreign-authored.txt" | cut -d' ' -f1)" ]]
stage preserve-after-recovery preserve
printf '%s\n' 'PASS candidate retained adoption/removal/recovery with actual public baseline and authored preservation. Foreign sentinel and newly produced Portal bin/obj remain; no recursive cleanup. Public successor/provider/browser/performance remain separate.'
