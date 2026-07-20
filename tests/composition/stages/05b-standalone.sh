# shellcheck shell=bash
# ── Stage 5b: standalone spec-kit lane skill-union (GATED) ───────────────────
# Uses PIN_VER (Stage 4), WORKDIR, RUN_FULL (Stage 5), installed_template_version + assert_skill_union
# (libs). Sets STAND, INSTALLED_UI_VER.
#
# The OTHER lane ADR-0014 covers: a direct `dotnet new fs-gg-ui` (no fsgg-sdd) on the
# spec-kit lifecycle. ADR-0056 (2026-07-20) flipped the template default lifecycle
# spec-kit -> sdd and reclassified spec-kit as legacy (frozen, still emitted), so this
# lane must REQUEST `--lifecycle spec-kit` explicitly — the bare default now yields an
# sdd product with no `.specify/` tree, which has no materialize step to exercise.
# Here the template itself must produce the union via its ONE
# materialize step (the vendored Fsgg.SkillMirror byte-equivalent, run by the
# FsGgMaterializeSkillRoots MSBuild target on first build; `--enforce` for gates). We run
# that producer step directly, then assert the union with the same shared assertion.
# Needs only dotnet + the published template package; gated on the pin being installable
# (already satisfied when Stage 5 ran — fsgg-sdd installs the same pin).
step "standalone — spec-kit lane: one materialize step + skill-union (ADR-0014 P3.T3.2, gated)"
STAND="$WORKDIR/standalone"
# F2 guard (issue #55): an empty pin (Stage-4 parse failure) must NOT fall into the install line
# below — `FS.GG.UI.Template::` fails to install and the `||` fallback would then accept any
# already-installed fs-gg-ui, asserting the union against an unknown version. Fail explicitly.
if [[ -z "$PIN_VER" ]]; then
  bad "standalone lane: no FS.GG.UI.Template pin parsed in Stage 4 — cannot install a version-coherent payload (an empty pin would otherwise accept any installed fs-gg-ui, F2)"
elif dotnet new install "FS.GG.UI.Template::$PIN_VER" >"$WORKDIR/standalone-install.log" 2>&1 \
     || dotnet new list 2>/dev/null | grep -q 'fs-gg-ui'; then
  # F2: the `||` fallback reuses whatever fs-gg-ui the (isolated, F3) hive already holds — e.g.
  # from Stage 5's `fsgg-sdd scaffold`, which shares this run's DOTNET_CLI_HOME and installs the
  # same pin. That reuse is only sound if the INSTALLED version IS the pin; otherwise the lane
  # would assert the skill-union against an off-pin payload — a hole in the exact version-
  # coherence invariant this repo guards. Verify it before instantiating.
  INSTALLED_UI_VER="$(installed_template_version FS.GG.UI.Template)"
  if [[ "$INSTALLED_UI_VER" != "$PIN_VER" ]]; then
    bad "standalone lane: installed FS.GG.UI.Template is '${INSTALLED_UI_VER:-<none>}', not the pinned $PIN_VER — refusing to assert the skill-union against an off-pin payload (F2; see $WORKDIR/standalone-install.log)"
  elif dotnet new fs-gg-ui -o "$STAND" --name Acme --lifecycle spec-kit >"$WORKDIR/standalone-new.log" 2>&1; then
    ok "standalone fs-gg-ui instantiation succeeded at the pinned $PIN_VER (explicit spec-kit lifecycle; ADR-0056 default is now sdd)"
    MAT="$STAND/.specify/scripts/fs-gg/materialize-skill-roots.fsx"
    if [[ -f "$MAT" ]]; then
      if (cd "$STAND" && dotnet fsi .specify/scripts/fs-gg/materialize-skill-roots.fsx --enforce) >"$WORKDIR/materialize.log" 2>&1; then
        ok "producer-side materialize+verify green (materialize-skill-roots.fsx --enforce — the one standalone materialize step)"
      else
        bad "materialize-skill-roots.fsx --enforce failed — per-skill drift below (see $WORKDIR/materialize.log)"
        tail -n 30 "$WORKDIR/materialize.log" 2>/dev/null | sed 's/^/  | /'
      fi
      assert_skill_union "$STAND" "standalone" 'speckit-*'
    else
      bad "standalone product lacks .specify/scripts/fs-gg/materialize-skill-roots.fsx — FS.GG.UI.Template >= 0.1.61-preview.1 ships the one materialize step in the spec-kit lane (ADR-0014 P2)"
    fi
  else
    bad "standalone fs-gg-ui instantiation failed (see $WORKDIR/standalone-new.log)"
    sed -n '$p' "$WORKDIR/standalone-new.log"
  fi
elif [[ "$RUN_FULL" == "1" || "${FSGG_COMPOSITION_FULL:-}" == "1" ]]; then
  bad "cannot install FS.GG.UI.Template::$PIN_VER for the standalone lane (see $WORKDIR/standalone-install.log) — with the full environment present this lane is required"
else
  skip "FS.GG.UI.Template::$PIN_VER not installable here (no feed access) — the standalone-lane union is not exercised. CI (and any host with feed access) asserts it; the gate keeps CI honest rather than green-by-omission."
fi
