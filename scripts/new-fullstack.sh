#!/usr/bin/env bash
# Create a full-stack FS.GG product: SDD lifecycle + runnable Rendering app +
# Governance config, by composing the three products. This is the composition
# approach (see docs/design.md) — each product stays decoupled and independently
# owned; this script just glues them.
#
# Usage:
#   scripts/new-fullstack.sh <target-dir> <product-name> <rendering-template-source>
#
#   <rendering-template-source>  a local path or NuGet id for `dotnet new install`
#                                of FS.GG.Rendering's `fs-gg-ui` template.
set -euo pipefail

TARGET="${1:?target dir required}"
PRODUCT="${2:?product name required}"
RENDERING_SOURCE="${3:?rendering template source (path or nuget id) required}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$TARGET/.fsgg"

# 1. Register the Rendering provider so `fsgg-sdd scaffold` can drive it.
sed "s|__RENDERING_TEMPLATE_SOURCE__|$RENDERING_SOURCE|" \
    "$REPO_ROOT/providers/rendering.providers.yml" > "$TARGET/.fsgg/providers.yml"

# 2. SDD skeleton + full Rendering app, recorded in scaffold-provenance.
#    (fsgg-sdd installs/updates and runs the provider template; produced runtime
#    files are marked externally owned.)
fsgg-sdd scaffold --root "$TARGET" --provider rendering --param "productName=$PRODUCT"

# 3. Activate Governance: drop policy/capabilities/tooling config into the project.
#    Done after scaffold (not via the provider) so it is not flagged as a provider
#    writing into the SDD-owned .fsgg/ tree.
dotnet new install "$REPO_ROOT/templates/fs-gg-governance" >/dev/null 2>&1 || true
dotnet new fs-gg-governance -o "$TARGET"

echo "Full-stack product created in $TARGET (SDD + Rendering + Governance)."
echo "Next: cd $TARGET && dotnet build && dotnet run; then fsgg-sdd charter."
