#!/usr/bin/env bash
# Hydrate a local dev environment with the *published, coherent* package set the full
# composition test (tests/composition/run.sh, FSGG_COMPOSITION_FULL=1) needs — so the
# scaffold+build (Stage 5) and the SDD->Governance enforcement matrix (Stage 6) run for
# real instead of SKIPping on a stale box.
#
# This is NOT a republish. Per ADR-0002 the FS.GG products are independently versioned and
# already coherent where it matters: the FS.GG.UI.* family ships as one locked version set
# behind the immutable tag fs-gg-ui-template/v<ver>, and Governance/SDD are published on
# their own lines. What goes stale is the *local* picture — the local NuGet feed lags the
# UI pin, and the locally-installed fsgg-governance predates the spec-081 handoff consumer.
# This script pulls the coherent published set down to this box:
#
#   1. UI runtime set  — repacked from the FS.GG.Rendering source at the pinned version
#                        (dev-repack.fsx packs the 14 runtime projects as one coherent set).
#   2. UI Template pkg — packed separately (dev-repack does NOT cover .template.package).
#   3. fsgg-governance — pulled from the org GitHub Packages feed at a consumer-bearing,
#                        profile-aware version (>= 1.2.0: FS.GG.Governance#28 + #34).
#
# Steps 1-2 need the FS.GG.Rendering source checkout. Step 3 needs a GitHub PAT with
# read:packages; it SKIPs-with-reason (never silently) when no token is present.
#
# Usage:   scripts/hydrate-local-feed.sh
# Env:
#   FSGG_RENDERING_REPO  FS.GG.Rendering checkout (default: ../FS.GG.Rendering, then
#                        /home/developer/projects/FS.GG.Rendering)
#   NUGET_LOCAL_FEED     local feed dir to pack into (default: ~/.local/share/nuget-local)
#   GOV_CLI_VERSION      governance CLI version to install (default: 1.2.0)
#   GH_TOKEN / GITHUB_TOKEN   PAT with read:packages for the org feed (step 3)
#   GH_USERNAME          GitHub username for the feed credential (default: $USER, then
#                        whatever `gh` reports)
#   SKIP_GOVERNANCE=1    skip step 3 entirely (UI feed hydration only)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROV="$ROOT/providers/rendering.providers.yml"
FEED="${NUGET_LOCAL_FEED:-$HOME/.local/share/nuget-local}"
GOV_CLI_VERSION="${GOV_CLI_VERSION:-1.2.0}"
ORG_FEED="https://nuget.pkg.github.com/FS-GG/index.json"

step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
skip() { printf '  \033[33m–\033[0m SKIP: %s\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }

command -v dotnet >/dev/null || { echo "FATAL: dotnet not on PATH" >&2; exit 2; }

# The pin is the single source of truth — read it from the provider `source:` line, exactly
# as tests/composition/run.sh and bump-rendering-pin.sh do.
PIN="$(grep -oE 'FS\.GG\.UI\.Template::[^ ]+' "$PROV" | head -1 | sed 's/.*:://')"
[ -n "$PIN" ] || { echo "FATAL: could not read FS.GG.UI.Template pin from $PROV" >&2; exit 1; }
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
    echo "       tag fs-gg-ui-template/v$PIN in FS.GG.Rendering before hydrating." >&2
    exit 1
  fi
fi

# ── Step 3: governance CLI (consumer-bearing, profile-aware) ─────────────────
step "governance CLI — pull FS.GG.Governance.Cli@$GOV_CLI_VERSION from the org feed"
if [ "${SKIP_GOVERNANCE:-}" = "1" ]; then
  skip "SKIP_GOVERNANCE=1 — left fsgg-governance as-is (Stage 6 of the composition test will gate on what is installed)"
else
  TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  if [ -z "$TOKEN" ]; then
    skip "no GH_TOKEN/GITHUB_TOKEN with read:packages — the org GitHub Packages feed is private, so the consumer-bearing CLI can't be pulled here. Stage 6 will SKIP until fsgg-governance >= 1.2.0 is on PATH. (Set GH_TOKEN and re-run, or install it manually.)"
  else
    USER_NAME="${GH_USERNAME:-${USER:-}}"
    if [ -z "$USER_NAME" ] && command -v gh >/dev/null 2>&1; then
      USER_NAME="$(gh api user -q .login 2>/dev/null || true)"
    fi
    USER_NAME="${USER_NAME:-x-access-token}"   # any non-empty user works with a PAT
    # Register the org feed (idempotent — update if it already exists).
    if dotnet nuget list source 2>/dev/null | grep -q "$ORG_FEED"; then
      dotnet nuget update source fsgg-github --source "$ORG_FEED" \
        --username "$USER_NAME" --password "$TOKEN" --store-password-in-clear-text >/dev/null 2>&1 || true
    else
      dotnet nuget add source "$ORG_FEED" --name fsgg-github \
        --username "$USER_NAME" --password "$TOKEN" --store-password-in-clear-text >/dev/null 2>&1 || true
    fi
    # --ignore-failed-sources: tool resolution walks all sources; the org one is the only one
    # that serves this package, the rest are expected to miss.
    if dotnet tool update --global FS.GG.Governance.Cli --version "$GOV_CLI_VERSION" --ignore-failed-sources; then
      ok "fsgg-governance @ $GOV_CLI_VERSION installed (consumer-bearing + profile-aware: #28 + #34)"
    else
      skip "could not install FS.GG.Governance.Cli@$GOV_CLI_VERSION from the org feed (token lacks read:packages, or version not published) — Stage 6 will gate on the installed CLI"
    fi
  fi
fi

step "done"
echo "Local feed hydrated to the coherent published set @ $PIN."
echo "Run the full composition test:  FSGG_COMPOSITION_FULL=1 tests/composition/run.sh"
