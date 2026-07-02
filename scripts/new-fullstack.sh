#!/usr/bin/env bash
# Create a full-stack FS.GG product: SDD lifecycle + runnable Rendering app +
# Governance config, by composing the three products. This is the composition
# approach (see docs/design.md) — each product stays decoupled and independently
# owned; this script just glues them.
#
# Usage:
#   scripts/new-fullstack.sh <target-dir> <product-name> [--source <path-or-nuget-id>]
#
#   --source <path-or-nuget-id>  OPTIONAL override of the Rendering `fs-gg-ui`
#                                template `fsgg-sdd scaffold` installs. Defaults to the
#                                published, version-pinned package in
#                                providers/rendering.providers.yml — the single source of
#                                truth per ADR-0002. Point it at a local path or an
#                                unpublished build only for the dev-repack flow.
set -euo pipefail

TARGET="${1:?target dir required}"
PRODUCT="${2:?product name required}"
shift 2

RENDERING_SOURCE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)   RENDERING_SOURCE="${2:?--source requires a path or nuget id}"; shift 2 ;;
    --source=*) RENDERING_SOURCE="${1#--source=}"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$TARGET/.fsgg"

# 1. Register the Rendering provider so `fsgg-sdd scaffold` can drive it. The provider
#    yml carries the published, version-pinned template source (ADR-0002 single source of
#    truth); --source rewrites that `source:` line in place for the dev-repack flow only.
if [[ -n "$RENDERING_SOURCE" ]]; then
  sed "s|^\( *source:\).*|\1 $RENDERING_SOURCE|" \
      "$REPO_ROOT/providers/rendering.providers.yml" > "$TARGET/.fsgg/providers.yml"
else
  cp "$REPO_ROOT/providers/rendering.providers.yml" "$TARGET/.fsgg/providers.yml"
fi

# 2. SDD skeleton + full Rendering app, recorded in scaffold-provenance.
#    (fsgg-sdd installs/updates and runs the provider template; produced runtime
#    files are marked externally owned.)
fsgg-sdd scaffold --root "$TARGET" --provider rendering --param "productName=$PRODUCT"

# 3. Activate Governance: drop policy/capabilities/tooling config into the project.
#    Done after scaffold (not via the provider) so it is not flagged as a provider
#    writing into the SDD-owned .fsgg/ tree.
dotnet new install "$REPO_ROOT/templates/fs-gg-governance" >/dev/null 2>&1 || true
# Pass --appName so the governed command strings (e.g. 'dotnet build <App>.slnx') name the
# solution this scaffold actually produces — otherwise the overlay would govern a phantom
# 'App.slnx' instead of "$PRODUCT".slnx. (The fs-gg-ui scaffold ships the solution in the
# modern XML '.slnx' format; the overlay governs that — see the overlay tooling.yml, #59/A4.)
dotnet new fs-gg-governance -o "$TARGET" --appName "$PRODUCT"

echo "Full-stack product created in $TARGET (SDD + Rendering + Governance)."
echo "Next: cd $TARGET && dotnet build && dotnet run; then fsgg-sdd charter."
