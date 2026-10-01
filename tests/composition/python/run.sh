#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
: "${FSGG_PYTHON_COORDINATION_ROOT:?exact Coordination source checkout is required}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-python-composition.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
export DOTNET_CLI_HOME="$WORK/dotnet-home"

python3 "$ROOT/eng/portable-workspace/project-python-fixture.py" \
  --coordination-root "$FSGG_PYTHON_COORDINATION_ROOT" \
  --output "$WORK/projected" >"$WORK/projection.json"

LANE_REPO_ROOT="$ROOT"
# shellcheck source=tests/composition/lib/lane-package.sh
. "$ROOT/tests/composition/lib/lane-package.sh"
PACKAGE="$(lane_package_path "$WORK")"
dotnet new install "$PACKAGE" --force >/dev/null

dotnet new fs-gg-python -o "$WORK/direct" --productName DirectPython --lifecycle none >/dev/null
test ! -e "$WORK/direct/.fsgg"
for file in app.py build.py test.py; do
  cmp "$WORK/projected/python/$file" "$WORK/direct/python/$file"
done
cmp "$WORK/projected/python-fixture-source.json" "$WORK/direct/python-fixture-source.json"
test "$(python3 "$WORK/direct/python/app.py")" = "hello from portable python"
grep -Fq '"sourceRevision": "RECEIVER_COMMIT"' "$WORK/direct/portable-workspace-profile.template.json"
grep -Fq '"qualifiedImage": "QUALIFIED_IMAGE_REFERENCE"' "$WORK/direct/portable-workspace-profile.template.json"

mkdir -p "$WORK/sdd/.fsgg"
cp "$ROOT/providers/python.providers.yml" "$WORK/sdd/.fsgg/providers.yml"
lane_pin_provider_to_archive "$WORK/sdd/.fsgg/providers.yml" "$PACKAGE"
fsgg-sdd scaffold --root "$WORK/sdd" --provider python \
  --param productName=ReceiverPython --param lifecycle=sdd --no-update --json >"$WORK/scaffold.json"
jq -e '.outcome == "succeeded" and .scaffold.providerName == "python" and .scaffold.providerInvoked == true' "$WORK/scaffold.json" >/dev/null
test -f "$WORK/sdd/.fsgg/scaffold-provenance.json"
for file in app.py build.py test.py; do
  cmp "$WORK/projected/python/$file" "$WORK/sdd/python/$file"
done
cmp "$WORK/projected/python-fixture-source.json" "$WORK/sdd/python-fixture-source.json"
test "$(python3 "$WORK/sdd/python/app.py")" = "hello from portable python"
fsgg-sdd doctor --root "$WORK/sdd" --json >"$WORK/doctor.json"
jq -e '.outcome == "noChange" and (.diagnostics | length) == 0' "$WORK/doctor.json" >/dev/null

echo "PASS Python template projects canonical source, runs its real entry point, and composes through the generic SDD provider"
