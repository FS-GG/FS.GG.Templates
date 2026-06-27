#!/usr/bin/env bash
# Maintainer update function: re-sync the vendored fs-gg-ui rendering payload inside
# the monolithic `fs-gg-fullstack` template from an upstream FS.GG.Rendering checkout.
# Preserves the SDD/Governance overlay (template/fsgg/) and the monolith's own
# template.json (identity, symbols, sources). After syncing, bump <Version> in
# FS.GG.Templates.csproj and `dotnet pack` so consumers get it via `dotnet new update`.
#
# Usage: scripts/sync-from-rendering.sh <path-to-FS.GG.Rendering-checkout>
set -euo pipefail

R="${1:?path to an FS.GG.Rendering checkout required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/templates/fs-gg-fullstack"

[ -f "$R/.template.config/template.json" ] || { echo "no fs-gg-ui template at $R" >&2; exit 1; }

# Refresh the upstream-derived payload only. template/fsgg/ (our overlay) and
# .template.config/template.json (our monolith manifest) are intentionally untouched.
rm -rf "$DEST/template/base" "$DEST/template/product-skills" "$DEST/template/design-system" \
       "$DEST/template/fragments" "$DEST/template/feedback" \
       "$DEST/.specify" "$DEST/.agents" "$DEST/.template.config/generated"

cp -r "$R/template/base"           "$DEST/template/base"
[ -d "$R/template/product-skills" ] && cp -r "$R/template/product-skills" "$DEST/template/product-skills" || true
[ -d "$R/template/design-system" ]  && cp -r "$R/template/design-system"  "$DEST/template/design-system"  || true
[ -d "$R/template/fragments" ]      && cp -r "$R/template/fragments"      "$DEST/template/fragments"       || true
[ -d "$R/template/feedback" ]       && cp -r "$R/template/feedback"       "$DEST/template/feedback"        || true
cp -r "$R/.specify"                 "$DEST/.specify"
cp -r "$R/.agents"                  "$DEST/.agents"
cp -r "$R/.template.config/generated" "$DEST/.template.config/generated"

echo "Synced rendering payload from $R."
echo "Next: bump <Version> in FS.GG.Templates.csproj, then 'dotnet pack -c Release -o ./artifacts'."
