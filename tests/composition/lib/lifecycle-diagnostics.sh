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
