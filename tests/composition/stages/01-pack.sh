# shellcheck shell=bash
# ── Stage 1: pack ────────────────────────────────────────────────────────────
# Sourced by run.sh (review A3). Shares the run-globals: REPO_ROOT, ARTIFACTS, WORKDIR.
# Sets NUPKG for the install stage. FSGG_TEMPLATES_NUPKG lets the release gate exercise the exact
# package it later publishes instead of silently packing a second, potentially different archive.
# An `exit` here exits the whole run (sourced, same shell).
if [[ -n "${FSGG_TEMPLATES_NUPKG:-}" ]]; then
  step "package — use prebuilt FS.GG.Workspace.Template artifact"
  NUPKG="$FSGG_TEMPLATES_NUPKG"
  [[ -f "$NUPKG" ]] && ok "using prebuilt $(basename "$NUPKG")" || {
    bad "prebuilt package does not exist: $NUPKG"; exit 1
  }
else
  step "pack — dotnet pack FS.GG.Workspace.Template"
  if dotnet pack "$REPO_ROOT/FS.GG.Templates.csproj" -c Release -o "$ARTIFACTS" >"$WORKDIR/pack.log" 2>&1; then
    ok "dotnet pack succeeded"
  else
    bad "dotnet pack failed (see $WORKDIR/pack.log)"; sed -n '$p' "$WORKDIR/pack.log"; KEEP_WORKDIR=1; exit 1
  fi
  NUPKG="$(ls -1 "$ARTIFACTS"/FS.GG.Workspace.Template.*.nupkg 2>/dev/null | head -1)"
  [[ -f "$NUPKG" ]] && ok "produced $(basename "$NUPKG")" || {
    bad "no FS.GG.Workspace.Template nupkg produced"; exit 1
  }
fi

PACKAGE_ENTRIES="$(unzip -Z1 "$NUPKG")"
if grep -Fxq 'README.md' <<<"$PACKAGE_ENTRIES"; then
  ok "package contains the NuGet README.md declared by PackageReadmeFile"
else
  bad "package is missing root README.md (PackageReadmeFile contract)"
  exit 1
fi
