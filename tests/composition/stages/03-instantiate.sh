# shellcheck shell=bash
# ── Stage 3: instantiate the populated governance overlay ────────────────────
# Uses APP, WORKDIR.
step "instantiate — dotnet new fs-gg-governance (appName=Acme, profile=strict)"
if dotnet new fs-gg-governance -o "$APP" --appName Acme --defaultProfile strict >"$WORKDIR/new.log" 2>&1; then
  ok "instantiation succeeded"
else
  bad "instantiation failed (see $WORKDIR/new.log)"; sed -n '$p' "$WORKDIR/new.log"; exit 1
fi
