# shellcheck shell=bash
# Retain bounded actual generated lifecycle reports before a lane removes its private product.
retain_lifecycle_diagnostics() {
  local product="$1" status="$2" destination="${FSGG_COMPOSITION_DIAGNOSTICS:-}"
  [[ -n "$destination" && -d "$product/reports" ]] || return 0
  python3 - "$product" "$destination" "$status" <<'PY'
import json, pathlib, shutil, stat, sys
product, destination = map(pathlib.Path, sys.argv[1:3])
status = int(sys.argv[3]); destination = destination / 'product-lifecycle'
destination.mkdir(parents=True, exist_ok=True)
reports = sorted((product / 'reports').glob('sdd-*.json'))
if len(reports) > 64:
    raise SystemExit('lifecycle diagnostics exceeded the 64-report bound')
retained = []
for source in reports:
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4 * 1024 * 1024:
        raise SystemExit(f'lifecycle diagnostics refused unsafe/oversized report {source.name}')
    shutil.copyfile(source, destination / source.name)
    retained.append(source.name)
    if status:
        try:
            report = json.loads(source.read_text())
        except (ValueError, UnicodeError):
            print(f'lifecycle failed: unreadable actual {source.name}', file=sys.stderr)
            continue
        if report.get('outcome') in ('blocked', 'failed') or any(d.get('severity') == 'error' for d in report.get('diagnostics', [])):
            print(f'lifecycle failed: actual {source.name}: {json.dumps(report)}', file=sys.stderr)
(destination / 'child-status.json').write_text(json.dumps({'exitCode': status, 'retainedReports': retained}) + '\n')
PY
}

cleanup_lifecycle_product() {
  local work="$1" status="$2"
  retain_lifecycle_diagnostics "$work/product" "$status" || { [[ "$status" != 0 ]] || status=1; }
  rm -rf "$work"
  exit "$status"
}

track_bindings_lifecycle_evidence() {
  local root="$1" relative=reports/bindings.junit.xml top head blob
  root="$(cd "$root" && pwd)" || return 1
  [[ -d "$root/.git" && -f "$root/$relative" && ! -L "$root/$relative" ]] || return 1
  top="$(lifecycle_git -C "$root" rev-parse --show-toplevel)" || return 1
  [[ "$top" == "$root" ]] || return 1
  # The generated report is ignored build output until the foreground caller explicitly owns
  # this one durable evidence artifact. Never stage caches or the whole generated product here.
  lifecycle_git -C "$root" add --force -- "$relative" || return 1
  lifecycle_git -C "$root" -c user.name='FS-GG composition fixture' \
    -c user.email='composition-fixture@fs-gg.invalid' -c commit.gpgsign=false \
    commit --quiet --only -m 'Record actual bindings lifecycle evidence' -- "$relative" || return 1
  head="$(lifecycle_git -C "$root" rev-parse HEAD)" || return 1
  blob="$(lifecycle_git -C "$root" rev-parse "HEAD:$relative")" || return 1
  [[ "$blob" == "$(lifecycle_git -C "$root" hash-object "$root/$relative")" ]] || return 1
  if [[ -n "${FSGG_COMPOSITION_DIAGNOSTICS:-}" ]]; then
    mkdir -p "$FSGG_COMPOSITION_DIAGNOSTICS" || return 1
    python3 - "$root/$relative" "$head" "$blob" >"$FSGG_COMPOSITION_DIAGNOSTICS/bindings-evidence-git.json" <<'PY'
import hashlib, json, pathlib, sys
file = pathlib.Path(sys.argv[1])
print(json.dumps({'path': 'reports/bindings.junit.xml', 'head': sys.argv[2], 'blob': sys.argv[3],
                  'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}))
PY
  fi
}
