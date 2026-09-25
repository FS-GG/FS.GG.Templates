#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
project="$root/src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
registry="${FSC05_REGISTRY:-$root/../.github/registry/dependencies.yml}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

dotnet build "$project" -c Release --nologo >/dev/null
tool=(dotnet run --no-build -c Release --project "$project" --)
pass=0

expect_pass() {
  local label="$1"; shift
  if "${tool[@]}" "$@" >"$work/out" 2>"$work/err"; then
    printf 'PASS %s\n' "$label"
    pass=$((pass + 1))
  else
    cat "$work/err" >&2
    printf 'FAIL %s\n' "$label" >&2
    exit 1
  fi
}

expect_fail() {
  local label="$1" pattern="$2"; shift 2
  if "${tool[@]}" "$@" >"$work/out" 2>"$work/err"; then
    printf 'FAIL %s: unexpectedly green\n' "$label" >&2
    exit 1
  elif grep -Fq "$pattern" "$work/err"; then
    printf 'PASS %s\n' "$label"
    pass=$((pass + 1))
  else
    cat "$work/err" >&2
    printf 'FAIL %s: diagnostic missing\n' "$label" >&2
    exit 1
  fi
}

expect_pass 'all checked-in descriptors mirror the current registry' \
  grade --providers "$root/providers" --registry "$registry"
python3 - "$registry" "$work/duplicate-registry-root.yml" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
Path(sys.argv[2]).write_text(source.rstrip('\n') + '\ncontracts:\n  - id: unrelated\n')
PY
expect_fail 'duplicate registry contracts root refuses stale first pin' 'duplicate registry contracts root' \
  grade --providers "$root/providers" --registry "$work/duplicate-registry-root.yml"
python3 - "$registry" "$work/duplicate-registry-floor.yml" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
contract = source.index('  - id: fs-gg-ui-template')
floor = source.index('    minimum-fsgg-sdd:\n', contract)
Path(sys.argv[2]).write_text(source[:floor] + '    minimum-fsgg-sdd:\n' + source[floor:])
PY
expect_fail 'duplicate selected registry floor block refuses second pin' 'duplicate selected registry minimum-fsgg-sdd block' \
  grade --providers "$root/providers" --registry "$work/duplicate-registry-floor.yml"
expect_pass 'checked-in generated summary is current' \
  effective-check --provider "$root/providers/rendering.providers.yml"
mkdir -p "$work/clean/.fsgg"
cp "$root/providers/console.providers.yml" "$work/clean/.fsgg/providers.yml"
expect_pass 'clean generated workspace descriptor is known' \
  workspace-check --providers "$root/providers" --workspace "$work/clean/.fsgg/providers.yml" --registry "$registry"

mkdir "$work/providers"
cp "$root/providers/"*.providers.yml "$work/providers/"
sed -i 's/^schemaVersion: 1$/schemaVersion: 2/' "$work/providers/rendering.providers.yml"
expect_fail 'unsupported descriptor schema is rejected' 'unsupported schemaVersion root' \
  grade --providers "$work/providers" --registry "$registry"
expect_fail 'workspace selection refuses an unsupported source schema' 'unsupported schemaVersion root' \
  workspace-check --providers "$work/providers" --workspace "$root/providers/rendering.providers.yml" --registry "$registry"
cp "$root/providers/rendering.providers.yml" "$work/providers/rendering.providers.yml"
sed -i '/^schemaVersion: 1$/d' "$work/providers/rendering.providers.yml"
expect_fail 'descriptor without schema is rejected' 'providers appear before schemaVersion: 1' \
  grade --providers "$work/providers" --registry "$registry"
cp "$root/providers/rendering.providers.yml" "$work/providers/rendering.providers.yml"
cat >>"$work/providers/rendering.providers.yml" <<'YAML'
schemaVersion: 1
YAML
expect_fail 'duplicate schema root is rejected' 'unsupported schemaVersion root' \
  grade --providers "$work/providers" --registry "$registry"
cp "$root/providers/rendering.providers.yml" "$work/providers/rendering.providers.yml"
python3 - "$work/providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
start = text.index('    minimumFsggSdd:\n')
end = text.index('    parameters:\n', start)
path.write_text(text[:start] + text[end:])
PY
expect_fail 'missing floor fails for the named provider' 'web: missing minimumFsggSdd.version' \
  grade --providers "$work/providers" --registry "$registry"

cat >>"$work/providers/web.providers.yml" <<'YAML'
extra:
    minimumFsggSdd:
      version: "1.4.0-preview.1"
YAML
expect_fail 'a root sibling cannot lend its floor to a provider' 'unsupported or duplicate descriptor root key' \
  grade --providers "$work/providers" --registry "$registry"

cat >"$work/providers/web.providers.yml" <<'YAML'
schemaVersion: 1
providers: [
  - name: web
    contractVersion: "1.1.0"
    templateId: fs-gg-web
    source: FS.GG.Workspace.Template::0.13.0
    minimumFsggSdd:
      version: "1.4.0-preview.1"
YAML
expect_fail 'malformed provider collection is rejected' 'providers must be a block sequence' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
cat >>"$work/providers/web.providers.yml" <<'YAML'
providers: []
YAML
expect_fail 'duplicate root providers key is rejected' 'repeats providers' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
sed -i 's/version: "1.4.0-preview.1"/version: 1.4.0-preview.1 garbage/' "$work/providers/web.providers.yml"
expect_fail 'unquoted floor with trailing YAML tokens is rejected' 'unsupported text after scalar value' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
sed -i 's/source: FS.GG.Workspace.Template::0.13.0/source: FS.GG.Workspace.Template::0.13.0 garbage/' "$work/providers/web.providers.yml"
expect_fail 'unquoted provider source with trailing YAML tokens is rejected' 'unsupported text after scalar value' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
python3 - "$work/providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('      version:', '     malformed: value\n      version:', 1))
PY
expect_fail 'odd indentation inside floor is rejected like Python' 'malformed minimumFsggSdd field' \
  grade --providers "$work/providers" --registry "$registry"

mkdir "$work/duplicate-floor-providers"
cp "$root/providers/"*.providers.yml "$work/duplicate-floor-providers/"
python3 - "$work/duplicate-floor-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
lines = path.read_text().splitlines()
index = next(i for i, line in enumerate(lines) if line.startswith('      requires:'))
lines.insert(index + 1, '      requires: "forged metadata"')
path.write_text('\n'.join(lines) + '\n')
PY
expect_fail 'duplicate non-version floor metadata refuses' 'repeated minimumFsggSdd field' \
  grade --providers "$work/duplicate-floor-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/duplicate-floor-providers/web.providers.yml"
python3 - "$work/duplicate-floor-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
lines = path.read_text().splitlines()
index = next(i for i, line in enumerate(lines) if line.startswith('      adr:'))
lines.insert(index + 1, '      adr: "forged ADR"')
path.write_text('\n'.join(lines) + '\n')
PY
expect_fail 'duplicate ADR floor metadata refuses' "repeated minimumFsggSdd field 'adr'" \
  grade --providers "$work/duplicate-floor-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/duplicate-floor-providers/web.providers.yml"
python3 - "$work/duplicate-floor-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
lines = path.read_text().splitlines()
index = next(i for i, line in enumerate(lines) if line.startswith('      version:'))
lines.insert(index + 1, '      version: "1.4.0-preview.1"')
path.write_text('\n'.join(lines) + '\n')
PY
expect_fail 'duplicate floor version keeps its named refusal' 'repeated minimumFsggSdd.version' \
  grade --providers "$work/duplicate-floor-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
python3 - "$work/providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('    templateId:', '    not-a-field\n    templateId:', 1))
PY
expect_fail 'malformed provider field is rejected like Python' 'malformed provider field' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
python3 - "$work/providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('    templateId: fs-gg-web\n',
    '    templateId: fs-gg-web\n      forged: ignored\n', 1))
PY
expect_fail 'nested content under scalar provider field refuses' 'unsupported provider indentation' \
  grade --providers "$work/providers" --registry "$registry"
expect_fail 'workspace descriptor nested content refuses' 'unsupported provider indentation' \
  workspace-check --providers "$root/providers" --workspace "$work/providers/web.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
python3 - "$work/providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('providers:\n',
    'providers:\n    orphan: before-first-provider\n', 1))
PY
expect_fail 'orphan mapping before first provider refuses' 'unsupported content before first provider' \
  grade --providers "$work/providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
rm "$work/providers/web.providers.yml"
mkdir "$work/providers/web.providers.yml"
expect_fail 'directory named as descriptor is not silently skipped' 'not a regular file' \
  grade --providers "$work/providers" --registry "$registry"
rmdir "$work/providers/web.providers.yml"
cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"

ln -s "$work/no-such-provider" "$work/providers/dangling.providers.yml"
expect_fail 'dangling descriptor path is refused' 'dangling.providers.yml' \
  grade --providers "$work/providers" --registry "$registry"
rm "$work/providers/dangling.providers.yml"

cat >"$work/unsupported.json" <<'JSON'
{"schemaVersion":1,"providers":[{"name":"web"}]}
JSON
expect_fail 'JSON is not silently treated as a provider descriptor' 'unsupported or duplicate descriptor root key' \
  workspace-check --providers "$root/providers" --workspace "$work/unsupported.json" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/providers/web.providers.yml"
cp "$root/providers/web.providers.yml" "$work/providers/duplicate.providers.yml"
expect_fail 'duplicate provider identity across descriptors is rejected' 'provider names must be unique across descriptors' \
  grade --providers "$work/providers" --registry "$registry"
rm "$work/providers/duplicate.providers.yml"

python3 - "$registry" "$root/providers/web.providers.yml" "$work/drift.yml" <<'PY'
from pathlib import Path
import re
import sys
source = Path(sys.argv[1]).read_text()
provider = Path(sys.argv[2]).read_text()
floor = re.search(r'minimumFsggSdd:\s*\n\s+version: "([^"]+)"', provider)
if floor is None:
    raise SystemExit('fixture provider floor shape changed')
needle = f'minimum-fsgg-sdd:\n      version: "{floor.group(1)}"'
if needle not in source:
    raise SystemExit('fixture registry shape changed')
Path(sys.argv[3]).write_text(source.replace(needle, 'minimum-fsgg-sdd:\n      version: "9.9.9"', 1))
PY
expect_fail 'live-registry drift fails mirrored descriptors' 'registry pin 9.9.9' \
  grade --providers "$work/providers" --registry "$work/drift.yml"
expect_fail 'workspace selection refuses even unselected owner floor drift' 'registry pin 9.9.9' \
  workspace-check --providers "$root/providers" --workspace "$work/clean/.fsgg/providers.yml" --registry "$work/drift.yml"

cat >"$work/providers/sixth.providers.yml" <<'YAML'
schemaVersion: 1
providers:
  - name: sixth
    contractVersion: "1.1.0"
    templateId: fs-gg-sixth
    source: Sixth.Template::1.0.0
    minimumFsggSdd:
      version: "9.9.9"
YAML
expect_fail 'a new sixth descriptor is enumerated' 'sixth: floor 9.9.9 != registry pin' \
  grade --providers "$work/providers" --registry "$registry"

cat >"$work/unknown.providers.yml" <<'YAML'
schemaVersion: 1
providers:
  - name: unknown
    contractVersion: "1.1.0"
    templateId: fs-gg-unknown
    source: Unknown.Template::1.0.0
    minimumFsggSdd:
      version: "1.4.0-preview.1"
YAML
expect_fail 'unknown workspace provider fails' "unknown provider 'unknown'" \
  workspace-check --providers "$root/providers" --workspace "$work/unknown.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
python3 - "$work/parameters.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
entry = "      - key: lifecycle\n        required: false\n"
path.write_text(text.replace(entry, entry + entry, 1))
PY
expect_fail 'duplicate parameter key refuses' "duplicate parameter key 'lifecycle'" \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
sed -i '0,/        required: true/s//        required: true\n        required: false/' "$work/parameters.providers.yml"
expect_fail 'duplicate required key refuses' "repeated parameter field 'required'" \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
sed -i '0,/        required: true/s//        required: true\n        mystery: yes/' "$work/parameters.providers.yml"
expect_fail 'unknown parameter field refuses' 'malformed parameter field' \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
sed -i 's/    nameParameter: productName/    mystery: yes\n    nameParameter: productName/' "$work/parameters.providers.yml"
expect_fail 'unknown provider field refuses' "unsupported provider field 'mystery'" \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
sed -i 's/        default: sdd/        default: none/' "$work/parameters.providers.yml"
expect_fail 'workspace parameter default drift refuses' "provider 'web' differs from source descriptor" \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/parameters.providers.yml"
sed -i 's/        default: sdd/        default: "sdd "/' "$work/parameters.providers.yml"
expect_fail 'quoted parameter default with trailing space refuses' "invalid parameter 'lifecycle'" \
  workspace-check --providers "$root/providers" --workspace "$work/parameters.providers.yml" --registry "$registry"

mkdir "$work/escaped-providers"
cp "$root/providers/"*.providers.yml "$work/escaped-providers/"
python3 - "$work/escaped-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('        default: sdd',
    '        default: "sdd\\nforged"', 1))
PY
expect_fail 'double-quoted YAML newline escape refuses instead of grading literal backslash' 'unsupported double-quoted escape' \
  grade --providers "$work/escaped-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/escaped-providers/web.providers.yml"
python3 - "$work/escaped-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('    contractVersion: "1.1.0"',
    '    contractVersion: "1.1.0\\u0020"', 1))
PY
expect_fail 'double-quoted YAML Unicode escape cannot change effective output bytes' 'unsupported double-quoted escape' \
  grade --providers "$work/escaped-providers" --registry "$registry"

mkdir "$work/null-providers"
cp "$root/providers/"*.providers.yml "$work/null-providers/"
sed -i 's/        default: sdd/        default: null/' "$work/null-providers/web.providers.yml"
expect_fail 'unquoted null default refuses absent YAML value' 'implicit YAML null scalar' \
  grade --providers "$work/null-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/null-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: ~/' "$work/null-providers/web.providers.yml"
expect_fail 'unquoted tilde default refuses absent YAML value' 'implicit YAML null scalar' \
  grade --providers "$work/null-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/null-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: NULL/' "$work/null-providers/web.providers.yml"
expect_fail 'uppercase unquoted null default refuses absent YAML value' 'implicit YAML null scalar' \
  grade --providers "$work/null-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/null-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: "null"/' "$work/null-providers/web.providers.yml"
expect_pass 'quoted literal null remains a valid string default' \
  grade --providers "$work/null-providers" --registry "$registry"

mkdir "$work/flow-providers"
cp "$root/providers/"*.providers.yml "$work/flow-providers/"
sed -i 's/        default: sdd/        default: []/' "$work/flow-providers/web.providers.yml"
expect_fail 'unquoted YAML flow sequence is not a string default' 'YAML flow indicator is not a string value' \
  grade --providers "$work/flow-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/flow-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: {}/' "$work/flow-providers/web.providers.yml"
expect_fail 'unquoted YAML flow mapping is not a string default' 'YAML flow indicator is not a string value' \
  grade --providers "$work/flow-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/flow-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: [sdd]/' "$work/flow-providers/web.providers.yml"
expect_fail 'populated YAML flow sequence is not a string default' 'YAML flow indicator is not a string value' \
  grade --providers "$work/flow-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/flow-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: "[]"/' "$work/flow-providers/web.providers.yml"
expect_pass 'quoted flow-looking default remains a string' \
  grade --providers "$work/flow-providers" --registry "$registry"

mkdir "$work/indicator-providers"
cp "$root/providers/"*.providers.yml "$work/indicator-providers/"
sed -i 's/        default: sdd/        default: |/' "$work/indicator-providers/web.providers.yml"
expect_fail 'bare YAML literal block marker is not a string default' 'unsupported YAML block or alias indicator' \
  grade --providers "$work/indicator-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/indicator-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: >-/' "$work/indicator-providers/web.providers.yml"
expect_fail 'bare YAML folded block marker is not a string default' 'unsupported YAML block or alias indicator' \
  grade --providers "$work/indicator-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/indicator-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: *missing/' "$work/indicator-providers/web.providers.yml"
expect_fail 'unknown YAML alias cannot be graded as literal string' 'unsupported YAML block or alias indicator' \
  grade --providers "$work/indicator-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/indicator-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: "|"/' "$work/indicator-providers/web.providers.yml"
expect_pass 'quoted block marker remains a literal string' \
  grade --providers "$work/indicator-providers" --registry "$registry"

cp "$root/providers/web.providers.yml" "$work/indicator-providers/web.providers.yml"
sed -i 's/        default: sdd/        default: "*missing"/' "$work/indicator-providers/web.providers.yml"
expect_pass 'quoted alias-looking value remains a literal string' \
  grade --providers "$work/indicator-providers" --registry "$registry"

mkdir "$work/empty-parameters-providers"
cp "$root/providers/"*.providers.yml "$work/empty-parameters-providers/"
python3 - "$work/empty-parameters-providers/web.providers.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
start = text.index('    parameters:\n')
path.write_text(text[:start] + '    parameters:\n')
PY
expect_fail 'present empty parameters block is YAML null, not an empty list' 'parameters must contain an entry' \
  grade --providers "$work/empty-parameters-providers" --registry "$registry"

cp "$root/providers/rendering.providers.yml" "$work/stale.providers.yml"
sed -i 's/# effective\[1\]:/# effective[99]:/' "$work/stale.providers.yml"
expect_fail 'stale generated summary fails' 'generated summary is stale' \
  effective-check --provider "$work/stale.providers.yml"

echo "provider-tool fixture: $pass passed"
