#!/usr/bin/env bash
# Materialize/check the governance overlay from one immutable published authority.
# The pin and the only permitted template-specific transformations live beside
# template.json in reference-gate-set.json.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PIN_FILE="$ROOT/templates/fs-gg-governance/.template.config/reference-gate-set.json"
OVERLAY_ROOT="$ROOT/templates/fs-gg-governance"
OVERLAY_DIR="$OVERLAY_ROOT/.fsgg"

json_string() {
  local name="$1"
  sed -nE "s/^[[:space:]]*\"$name\":[[:space:]]*\"([^\"]+)\"[,]?$/\\1/p" "$PIN_FILE"
}

PACKAGE_ID="$(json_string packageId)"
PACKAGE_VERSION="$(json_string version)"
PACKAGE_SHA256="$(json_string publicPackageSha256)"
SOURCE_COMMIT="$(json_string sourceCommit)"

if [[ -z "$PACKAGE_ID" || -z "$PACKAGE_VERSION" || -z "$PACKAGE_SHA256" || -z "$SOURCE_COMMIT" ]]; then
  echo "reference-gate-set-overlay: malformed authority pin: $PIN_FILE" >&2
  exit 2
fi

mode="${1:---check}"
if [[ "$mode" != "--check" && "$mode" != "--write" ]]; then
  echo "usage: ${BASH_SOURCE[0]} [--check|--write]" >&2
  exit 2
fi

command -v curl >/dev/null || { echo "reference-gate-set-overlay: curl is required" >&2; exit 2; }
command -v unzip >/dev/null || { echo "reference-gate-set-overlay: unzip is required" >&2; exit 2; }

work="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-reference-gate-set.XXXXXX")"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

package_lower="${PACKAGE_ID,,}"
package="$work/$package_lower.$PACKAGE_VERSION.nupkg"
url="https://api.nuget.org/v3-flatcontainer/$package_lower/$PACKAGE_VERSION/$package_lower.$PACKAGE_VERSION.nupkg"
curl --fail --silent --show-error --location "$url" --output "$package"

actual_sha256="$(sha256sum "$package" | cut -d' ' -f1)"
if [[ "$actual_sha256" != "$PACKAGE_SHA256" ]]; then
  echo "reference-gate-set-overlay: $PACKAGE_ID $PACKAGE_VERSION archive digest mismatch" >&2
  echo "expected $PACKAGE_SHA256" >&2
  echo "actual   $actual_sha256" >&2
  exit 1
fi

unzip -q "$package" -d "$work/package"
package_fsgg="$work/package/contentFiles/any/any/.fsgg"
package_manifest="$work/package/contentFiles/any/any/schema-manifest.json"
stage="$work/stage"
mkdir -p "$stage/.fsgg"

files=(
  governance.yml
  capabilities.yml
  policy.yml
  tooling.yml
  controlled-imports.fsx
  controlled-imports.json
)

for file in "${files[@]}"; do
  source="$package_fsgg/$file"
  [[ -f "$source" ]] || {
    echo "reference-gate-set-overlay: pinned package is missing .fsgg/$file" >&2
    exit 1
  }
  cp "$source" "$stage/.fsgg/$file"
done

[[ -f "$package_manifest" ]] || {
  echo "reference-gate-set-overlay: pinned package is missing schema-manifest.json" >&2
  exit 1
}
cp "$package_manifest" "$stage/schema-manifest.json"

# The overlay is an item template. These are the complete, reviewable inverse-template
# transformations; capabilities, controlled imports, and schema generations stay verbatim.
sed -i 's/^id:.*/id: <App>/' "$stage/.fsgg/governance.yml"
sed -i 's/^defaultProfile:.*/defaultProfile: GOV_DEFAULT_PROFILE/' "$stage/.fsgg/policy.yml"

# Rendering emits a modern .slnx. Refuse upstream shapes we do not understand before
# adapting the known path-map and command strings; broad replacements must not hide drift.
grep -qF 'glob: "*.sln"' "$stage/.fsgg/capabilities.yml"
grep -qF 'command: "dotnet build <App>.sln"' "$stage/.fsgg/tooling.yml"
grep -qF 'command: "dotnet test <App>.sln"' "$stage/.fsgg/tooling.yml"
sed -i 's/glob: "\*\.sln"/glob: "*.slnx"/' "$stage/.fsgg/capabilities.yml"
sed -i 's/<App>\.sln"/<App>.slnx"/g' "$stage/.fsgg/tooling.yml"

if [[ "$mode" == "--write" ]]; then
  for file in "${files[@]}"; do
    cp "$stage/.fsgg/$file" "$OVERLAY_DIR/$file"
  done
  cp "$stage/schema-manifest.json" "$OVERLAY_ROOT/schema-manifest.json"
  echo "reference-gate-set-overlay: wrote $PACKAGE_ID $PACKAGE_VERSION from $SOURCE_COMMIT"
  exit 0
fi

drift=0
for file in "${files[@]}"; do
  if ! diff -u "$stage/.fsgg/$file" "$OVERLAY_DIR/$file"; then
    drift=1
  fi
done
if ! diff -u "$stage/schema-manifest.json" "$OVERLAY_ROOT/schema-manifest.json"; then
  drift=1
fi

if [[ "$drift" -ne 0 ]]; then
  echo "reference-gate-set-overlay: DRIFT from $PACKAGE_ID $PACKAGE_VERSION ($SOURCE_COMMIT)" >&2
  exit 1
fi

echo "reference-gate-set-overlay: exact $PACKAGE_ID $PACKAGE_VERSION payload verified ($SOURCE_COMMIT)"
