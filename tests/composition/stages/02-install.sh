# shellcheck shell=bash
# ── Stage 2: install ─────────────────────────────────────────────────────────
# Uses NUPKG (Stage 1), WORKDIR. Installs into the isolated hive (DOTNET_CLI_HOME, set by run.sh).
step "install — dotnet new install <nupkg>"
dotnet new uninstall FS.GG.Templates >/dev/null 2>&1 || true
if dotnet new install "$NUPKG" >"$WORKDIR/install.log" 2>&1; then
  ok "dotnet new install succeeded"
else
  bad "dotnet new install failed (see $WORKDIR/install.log)"; sed -n '$p' "$WORKDIR/install.log"; exit 1
fi
if dotnet new list 2>/dev/null | grep -q 'fs-gg-governance'; then ok "template 'fs-gg-governance' registered"; else bad "'fs-gg-governance' not registered after install"; fi
