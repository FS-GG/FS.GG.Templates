#!/usr/bin/env bash
# Generate the fs-gg-governance overlay from the pinned FS.GG.Governance.ReferenceGateSet
# content package — the single, published, versioned source of truth for the governance gate
# set (governance.yml, capabilities.yml, policy.yml, tooling.yml). FS.GG.Templates#14 (H3).
#
# Why this exists: the overlay under templates/fs-gg-governance/.fsgg/ used to be a HAND-COPY of
# the governance reference gate set, which silently drifts whenever Governance evolves its gates.
# This script kills that gap: the overlay is GENERATED from the package's contentFiles, so a
# regenerate + `git diff --exit-code` (the CI drift gate, tests/composition/run.sh) proves the
# committed overlay is byte-for-byte the pinned reference set — re-parameterized into the two
# template tokens and nothing else.
#
# Generation = pinned package content  →  reverse-parameterize two fields into template tokens:
#   governance.yml   id:              <ref id>  ->  <App>                 (template.json: appName)
#   policy.yml       defaultProfile:  <ref val> ->  GOV_DEFAULT_PROFILE   (template.json: defaultProfile)
# capabilities.yml and tooling.yml are copied verbatim (tooling already uses the literal `<App>`
# token in the reference set, so it carries through unchanged). The two substitutions above are
# the EXACT inverse of the two `dotnet new` parameter `replaces` rules in
# templates/fs-gg-governance/.template.config/template.json — so an instantiated project re-derives
# the concrete reference values, and a regenerated overlay re-derives the tokenized template.
#
# The package is consumed via NuGet restore (genuine consumption, not a path copy): it is fetched
# from a configured source into the global packages cache, then its contentFiles are read from
# there. Locally that source is the SDD/Governance local feed (~/.local/share/nuget-local);
# once published it is nuget.org. Offline with neither, the script fails loud (the drift gate that
# calls it is itself gated on restorability, so CI skips rather than fails — see run.sh).
#
# Usage:
#   scripts/generate-governance-overlay.sh            # write the overlay in place
#   scripts/generate-governance-overlay.sh --check    # generate to a temp dir + diff; non-mutating
#
# Env:
#   GATE_SET_VERSION   override the pinned ReferenceGateSet version (default below)
set -euo pipefail

# ── The pin ──────────────────────────────────────────────────────────────────
# FS.GG.Governance.ReferenceGateSet uses a derived version: "{governance}.{capabilities}.{policy}.
# {tooling}" schemaVersions (see Governance pack-reference-gate-set.fsx). 1.2.1.1 = the reference
# set whose capabilities.yml is at schemaVersion 2 and the other three at 1. Bumping this pin is
# the deliberate, reviewable act of adopting a new governance gate set.
GATE_SET_VERSION="${GATE_SET_VERSION:-1.2.1.1}"
PACKAGE_ID="FS.GG.Governance.ReferenceGateSet"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVERLAY_DIR="$ROOT/templates/fs-gg-governance/.fsgg"
FILES=(governance.yml capabilities.yml policy.yml tooling.yml)

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

command -v dotnet >/dev/null || { echo "generate-governance-overlay: FATAL: dotnet not on PATH" >&2; exit 2; }

# ── Restore the pinned package into the global cache ─────────────────────────
# Restore a throwaway project that PackageReferences the pin; NuGet extracts the package (content
# packages included) under $NUGET_PACKAGES/<id-lowercased>/<version>/. We read contentFiles from
# there — the same bytes a consumer's restore would materialize.
NUGET_PACKAGES="${NUGET_PACKAGES:-$HOME/.nuget/packages}"
PKG_DIR="$NUGET_PACKAGES/$(echo "$PACKAGE_ID" | tr '[:upper:]' '[:lower:]')/$GATE_SET_VERSION"
CONTENT_DIR="$PKG_DIR/contentFiles/any/any/.fsgg"

if [[ ! -d "$CONTENT_DIR" ]]; then
  echo "generate-governance-overlay: restoring $PACKAGE_ID $GATE_SET_VERSION …"
  TMP_PROJ="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-gateset-restore.XXXXXX")"
  trap 'rm -rf "$TMP_PROJ"' EXIT
  cat >"$TMP_PROJ/restore.csproj" <<EOF
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ManagePackageVersionsCentrally>false</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="$PACKAGE_ID" Version="$GATE_SET_VERSION" />
  </ItemGroup>
</Project>
EOF
  if ! dotnet restore "$TMP_PROJ/restore.csproj" >"$TMP_PROJ/restore.log" 2>&1; then
    echo "generate-governance-overlay: FATAL: could not restore $PACKAGE_ID $GATE_SET_VERSION." >&2
    echo "  The package is on the SDD/Governance local feed (~/.local/share/nuget-local) or, once" >&2
    echo "  published, nuget.org. Register a source that serves it, then re-run." >&2
    sed -n '$p' "$TMP_PROJ/restore.log" >&2
    exit 1
  fi
fi
[[ -d "$CONTENT_DIR" ]] || { echo "generate-governance-overlay: FATAL: $CONTENT_DIR not found after restore" >&2; exit 1; }

# ── Generate ─────────────────────────────────────────────────────────────────
# Materialize into a staging dir first so a failure never leaves a half-written overlay.
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-overlay-gen.XXXXXX")"
cleanup_stage() { rm -rf "$STAGE"; }
trap cleanup_stage EXIT

for f in "${FILES[@]}"; do
  src="$CONTENT_DIR/$f"
  [[ -f "$src" ]] || { echo "generate-governance-overlay: FATAL: package is missing .fsgg/$f" >&2; exit 1; }
  cp "$src" "$STAGE/$f"
done

# Re-parameterize: the inverse of template.json's two `replaces` rules. Whole-line anchored so we
# tokenize the FIELD (whatever concrete value the pinned reference set ships) rather than a fixed
# literal — robust if Governance changes the reference id or default profile in a future pin.
sed -i 's|^id:.*|id: <App>|'                                "$STAGE/governance.yml"
sed -i 's|^defaultProfile:.*|defaultProfile: GOV_DEFAULT_PROFILE|' "$STAGE/policy.yml"

# ── Emit or check ────────────────────────────────────────────────────────────
if [[ "$CHECK" == "1" ]]; then
  drift=0
  for f in "${FILES[@]}"; do
    if ! diff -u "$OVERLAY_DIR/$f" "$STAGE/$f" >/dev/null 2>&1; then
      echo "generate-governance-overlay: DRIFT in $f:"
      diff -u "$OVERLAY_DIR/$f" "$STAGE/$f" || true
      drift=1
    fi
  done
  if [[ "$drift" == "0" ]]; then
    echo "generate-governance-overlay: overlay is in sync with $PACKAGE_ID $GATE_SET_VERSION (no drift)."
  fi
  exit "$drift"
fi

mkdir -p "$OVERLAY_DIR"
for f in "${FILES[@]}"; do
  cp "$STAGE/$f" "$OVERLAY_DIR/$f"
done
echo "generate-governance-overlay: wrote $OVERLAY_DIR from $PACKAGE_ID $GATE_SET_VERSION."
