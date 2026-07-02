#!/usr/bin/env bash
# DEV-ONLY: repack the pinned FS.GG.UI.* set from a local FS.GG.Rendering checkout into the
# local NuGet cache, so the full composition test (tests/composition/run.sh,
# FSGG_COMPOSITION_FULL=1) can pick up an *unpublished* UI build before it lands on the org
# feed. This is a development convenience — it is NOT part of container provisioning.
#
# On a provisioned container you do NOT need this. The FS.GG org feed
# (https://nuget.pkg.github.com/FS-GG) serves the whole coherent FS.GG.UI.* set and both
# CLIs; ~/.nuget/NuGet/NuGet.Config binds FS.GG.* to that feed (packageSourceMapping); and the
# container entrypoint floats fsgg-sdd / fsgg-governance to the latest published version on
# every start. The scaffold's `dotnet new install FS.GG.UI.Template::<pin>` then resolves the
# whole set straight from the org feed. The governance/SDD CLIs are NO LONGER handled here —
# they come from the org feed (see the Containers/ provisioning).
#
# Use this only when iterating on FS.GG.Rendering locally: repack your working build here,
# then temporarily map FS.GG.UI.* to the local cache in NuGet.Config so the test consults it
# (the default packageSourceMapping otherwise pins FS.GG.* to the org feed, so a local repack
# is ignored until you opt the cache in).
#
# This is NOT a republish. Per ADR-0002 the FS.GG products are independently versioned and
# already coherent where it matters: the FS.GG.UI.* family ships as one locked version set
# behind the immutable tag fs-gg-ui-template/v<ver>. This script only repacks that set from
# source for local pre-publish testing:
#
#   1. UI runtime set  — repacked from the FS.GG.Rendering source at the pinned version
#                        (dev-repack.fsx packs the 14 runtime projects as one coherent set).
#   2. UI Template pkg — packed separately (dev-repack does NOT cover .template.package).
#
# Both steps need the FS.GG.Rendering source checkout.
#
# Usage:   scripts/dev-repack-ui-feed.sh
# Env:
#   FSGG_RENDERING_REPO  FS.GG.Rendering checkout (default: ../FS.GG.Rendering, then
#                        /home/developer/projects/FS.GG.Rendering)
#   NUGET_LOCAL_FEED     local feed dir to pack into (default: ~/.local/share/nuget-local)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROV="$ROOT/providers/rendering.providers.yml"
FEED="${NUGET_LOCAL_FEED:-$HOME/.local/share/nuget-local}"

# shellcheck source=scripts/lib/read-pin.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/read-pin.sh"

step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }

command -v dotnet >/dev/null || { echo "FATAL: dotnet not on PATH" >&2; exit 2; }

# The pin is the single source of truth — read it from the provider `source:` line via the
# shared helper (scripts/lib/read-pin.sh), exactly as run.sh and bump-rendering-pin.sh do.
PIN="$(read_pin "$PROV")" || { echo "FATAL: could not read FS.GG.UI.Template pin from $PROV" >&2; exit 1; }
echo "Pinned FS.GG.UI.Template version: $PIN"
echo "Local feed:                       $FEED"
mkdir -p "$FEED"

# Locate the FS.GG.Rendering source checkout.
REND="${FSGG_RENDERING_REPO:-}"
if [ -z "$REND" ]; then
  for cand in "$ROOT/../FS.GG.Rendering" "/home/developer/projects/FS.GG.Rendering"; do
    [ -d "$cand" ] && { REND="$(cd "$cand" && pwd)"; break; }
  done
fi
[ -n "$REND" ] && [ -d "$REND" ] || {
  echo "FATAL: FS.GG.Rendering checkout not found — set FSGG_RENDERING_REPO" >&2; exit 1; }
echo "Rendering source:                 $REND"

# ── Step 1: UI runtime set ───────────────────────────────────────────────────
step "UI runtime set — dev-repack.fsx @ $PIN"
if [ -f "$FEED/FS.GG.UI.$PIN.nupkg" ]; then
  ok "FS.GG.UI.$PIN already in feed (runtime set present) — skipping repack"
else
  ( cd "$REND" && dotnet fsi scripts/dev-repack.fsx --sample samples/SampleApps --version "$PIN" --no-restore )
  # dev-repack retargets the sample pins as a side-effect; revert so the source stays clean.
  ( cd "$REND" && git checkout -- samples/SampleApps )
  ok "repacked the 14 FS.GG.UI.* runtime packages @ $PIN (sample-pin side-effect reverted)"
fi

# ── Step 2: UI Template package ──────────────────────────────────────────────
step "UI Template package — dotnet pack .template.package @ $PIN"
if [ -f "$FEED/FS.GG.UI.Template.$PIN.nupkg" ]; then
  ok "FS.GG.UI.Template.$PIN already in feed — skipping pack"
else
  # The fsproj's <Version> tracks the pin; assert it before packing so we never silently
  # emit a differently-versioned template than the provider installs.
  TPROJ="$REND/.template.package/FS.GG.UI.Template.fsproj"
  if grep -q "<Version>$PIN</Version>" "$TPROJ"; then
    ( cd "$REND" && dotnet pack .template.package/FS.GG.UI.Template.fsproj -c Release -o "$FEED" >/dev/null )
    ok "packed FS.GG.UI.Template.$PIN into the feed"
  else
    echo "FATAL: $TPROJ <Version> != pin $PIN — repo is at a different snapshot; checkout the" >&2
    echo "       tag fs-gg-ui-template/v$PIN in FS.GG.Rendering before repacking." >&2
    exit 1
  fi
fi

step "done"
echo "Local UI feed repacked @ $PIN."
echo "To make the composition test consult this LOCAL build (instead of the org feed), map"
echo "FS.GG.UI.* to the local cache in ~/.nuget/NuGet/NuGet.Config, then run:"
echo "  FSGG_COMPOSITION_FULL=1 tests/composition/run.sh"
