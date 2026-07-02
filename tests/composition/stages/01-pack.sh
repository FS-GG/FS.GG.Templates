# shellcheck shell=bash
# ── Stage 1: pack ────────────────────────────────────────────────────────────
# Sourced by run.sh (review A3). Shares the run-globals: REPO_ROOT, ARTIFACTS, WORKDIR.
# Sets NUPKG for the install stage. An `exit` here exits the whole run (sourced, same shell).
step "pack — dotnet pack FS.GG.Templates"
if dotnet pack "$REPO_ROOT/FS.GG.Templates.csproj" -c Release -o "$ARTIFACTS" >"$WORKDIR/pack.log" 2>&1; then
  ok "dotnet pack succeeded"
else
  bad "dotnet pack failed (see $WORKDIR/pack.log)"; sed -n '$p' "$WORKDIR/pack.log"; KEEP_WORKDIR=1; exit 1
fi
NUPKG="$(ls -1 "$ARTIFACTS"/FS.GG.Templates.*.nupkg 2>/dev/null | head -1)"
[[ -f "$NUPKG" ]] && ok "produced $(basename "$NUPKG")" || { bad "no FS.GG.Templates nupkg produced"; exit 1; }
