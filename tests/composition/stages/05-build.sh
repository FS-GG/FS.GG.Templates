# shellcheck shell=bash
# ── Stage 5: full scaffold + build (GATED) ───────────────────────────────────
# Uses REPO_ROOT, WORKDIR, and (via the inlined compose_full scaffold) the isolated hive. Sets RUN_FULL,
# FULL, FULL_OK for the standalone (5b) and govern (6) stages. Uses assert_skill_union (lib).
step "build — full fsgg-sdd scaffold + dotnet build (gated)"
if command -v fsgg-sdd >/dev/null 2>&1; then
  RUN_FULL=1
elif [[ "${FSGG_COMPOSITION_FULL:-}" == "1" ]]; then
  bad "FSGG_COMPOSITION_FULL=1 requested but 'fsgg-sdd' is not on PATH"; RUN_FULL=0
else
  RUN_FULL=0
fi
FULL="$WORKDIR/full"   # the composed product; reused by the governance-enforcement stage
FULL_OK=0

# Compose a full-stack product inline. This was scripts/new-fullstack.sh, now retired — the
# checkout-free FS-GG/.github scripts/new-sdd-fullstack.sh is the sole full-stack scaffolder, but it
# fetches the descriptor over the network and so cannot drive this repo's hermetic, LOCAL-providers.yml
# composition test. So the test carries the ADR-0002 composition-by-scaffold steps directly: register the
# provider-pinned descriptor -> fsgg-sdd scaffold -> governance overlay AFTER (so it is not flagged writing
# into the SDD-owned .fsgg/ tree). Runs in a subshell with `set -e` so ANY step failing fails the compose
# (the fail-fast the standalone script gave us) without touching run.sh's shell. The dev-only --source pin
# override retired with the script; this test never passed it.
compose_full() (
  set -euo pipefail
  target="$1"; product="$2"
  mkdir -p "$target/.fsgg"
  cp "$REPO_ROOT/providers/rendering.providers.yml" "$target/.fsgg/providers.yml"
  fsgg-sdd scaffold --root "$target" --provider rendering --param "productName=$product"
  dotnet new install "$REPO_ROOT/templates/fs-gg-governance" >/dev/null 2>&1 || true
  dotnet new fs-gg-governance -o "$target" --appName "$product"
)

if [[ "$RUN_FULL" == "1" ]]; then
  if compose_full "$FULL" Acme >"$WORKDIR/scaffold.log" 2>&1; then
    if dotnet build "$FULL" >"$WORKDIR/build.log" 2>&1; then
      ok "scaffold + dotnet build of the composed product succeeded"; FULL_OK=1

      # Family-agnostic default-entrypoint governance expectation (FS-GG/FS.GG.Templates#36).
      # The fs-gg-ui `game` default starter relaxes the durable entrypoint assertion: the
      # composed product's default launch must be satisfiable by BOTH the unmodified minimal
      # skeleton AND a developer's Pong swap. So accept EITHER family's governed entrypoint —
      # game `Viewer.runApp viewerOptions generatedHost` OR controls
      # `ControlsElmish.runInteractiveApp viewerOptions interactiveHost` — and require that NO
      # `-- pong`-style flag is a precondition for the default launch (FR-002/FR-003/FR-008).
      # This is the composition-layer projection of the assertion the generated product carries
      # upstream; it accepts the current controls default AND the future game default, so it does
      # not need to wait on the `fs-gg-ui-template` republish that flips the default app->game
      # (owned by FS-GG/FS.GG.SDD#44; registry FS-GG/.github#77).
      PROG="$(find "$FULL" -path '*/src/*/Program.fs' 2>/dev/null | head -1)"
      if [[ -n "$PROG" ]]; then
        if grep -qE 'Viewer\.runApp viewerOptions generatedHost|ControlsElmish\.runInteractiveApp viewerOptions interactiveHost' "$PROG"; then
          ok "composed product default launch uses an accepted family entrypoint (game Viewer.runApp generatedHost | controls runInteractiveApp interactiveHost)"
        else
          bad "composed product default launch is neither accepted family entrypoint — durable assertion not family-agnostic (#36, see $PROG)"
        fi
        assert_absent "$PROG" "-- pong" "no '-- pong'-style flag gates the default launch (entrypoint relaxation, #36)"
      else
        bad "could not locate the composed product's src/<Product>/Program.fs to check the default entrypoint (#36)"
      fi

      # A4 (issue #59, report §5) — governed commands must be RUNNABLE against the composed
      # product, not merely present in the overlay. tooling.yml governs `dotnet build <App>.slnx`,
      # `dotnet test <App>.slnx` (capabilities build/test, block-on-ship) and `dotnet fsi build.fsx
      # -- evidence` (evidence, warn). Stages 3–4 prove the overlay is *populated* and Stage 6b that
      # it *enforces* — but neither proves the Stage-5 scaffold actually PRODUCES the artifacts those
      # commands resolve. If it ships neither, the overlay governs phantom commands and the first
      # real check-run in a scaffolded product fails. We derive the governed names from the composed
      # product's OWN .fsgg/tooling.yml (so the check tracks --appName, not a hardcoded 'Acme') and
      # require each at the product root — the directory the governed command runs from. A red here
      # is the intended signal: it graduates into a cross-repo ask on FS.GG.Rendering (fs-gg-ui ships
      # the artifact) or an overlay change (govern what the scaffold produces).
      step "verify — governed commands are runnable against the composed product (A4, #59)"
      GOV_TOOLING="$FULL/.fsgg/tooling.yml"
      if [[ ! -f "$GOV_TOOLING" ]]; then
        bad "composed product lacks .fsgg/tooling.yml — cannot check governed-command runnability (A4)"
      else
        # dotnet-build / dotnet-test → the governed solution (block-on-ship). Parse the exact name
        # the overlay governs — classic `.sln` OR the modern `.slnx` the fs-gg-ui scaffold ships —
        # then require it where `dotnet build <App>.slnx` would resolve it (the `x?` keeps the check
        # honest to whichever extension the overlay names, so it can't silently truncate `.slnx`).
        GOV_SLN="$(grep -oE 'dotnet build [^ "]+\.slnx?' "$GOV_TOOLING" 2>/dev/null | head -1 | awk '{print $3}')"
        if [[ -z "$GOV_SLN" ]]; then
          bad "could not parse the governed 'dotnet build <App>.slnx' solution from $GOV_TOOLING (A4)"
        elif [[ -f "$FULL/$GOV_SLN" ]]; then
          ok "governed solution '$GOV_SLN' exists at the composed-product root — dotnet-build/dotnet-test are runnable, not phantom (A4)"
        else
          bad "governed solution '$GOV_SLN' is ABSENT from the composed-product root — the overlay governs a phantom 'dotnet build/test $GOV_SLN' and the first check-run in a scaffolded product would fail (A4). Fix upstream (FS.GG.Rendering fs-gg-ui ships the solution) or the overlay (govern what the scaffold produces — e.g. the '.slnx' the current fs-gg-ui ships)."
        fi
        # build-evidence → `dotnet fsi build.fsx -- evidence` (evidence gate, maturity warn). Only
        # assert when the overlay actually governs it, so dropping the command also drops this check.
        if grep -q 'dotnet fsi build.fsx' "$GOV_TOOLING" 2>/dev/null; then
          if [[ -f "$FULL/build.fsx" ]]; then
            ok "governed 'build.fsx' exists at the composed-product root — the evidence gate is runnable out-of-the-box (A4)"
          else
            bad "governed 'build.fsx' is ABSENT from the composed-product root — the evidence gate ('dotnet fsi build.fsx -- evidence') governs a phantom script (A4). Fix upstream (fs-gg-ui ships build.fsx) or drop/rehome the evidence command."
          fi
        fi
      fi

      # T3.2 (ADR-0014 P3, issue #49) — orchestrated lane: fsgg-sdd (>= 0.4.0, the sole mirror
      # authority per Feature 056) fanned the union (seeded fs-gg-sdd-* ∪ provider
      # .agents/skills/*) into .claude/.codex/.agents. Assert it, content-checked.
      step "verify — skill-union (orchestrated lane, ADR-0014 P3.T3.2)"
      assert_skill_union "$FULL" "orchestrated" 'fs-gg-sdd-*'
    else
      bad "scaffold succeeded but dotnet build of the composed product failed (see $WORKDIR/build.log)"
      tail -n 60 "$WORKDIR/build.log" 2>/dev/null | sed 's/^/  | /'
    fi
  else
    # The former "grep scaffold.providerFailed|scaffold.providerWroteSddTree and SKIP" lockstep
    # (#47) is RETIRED (T3.2): FS.GG.UI.Template >= 0.1.61-preview.1 emits UI skills into
    # .agents/skills/ ONLY on the sdd path, and fsgg-sdd >= 0.4.0 owns the 3-root fan-out — so
    # ANY scaffold failure, including a provider writing into an SDD-owned tree, is now a hard
    # composition failure, not an acknowledged upstream defect.
    bad "full scaffold failed (see $WORKDIR/scaffold.log) — provider-defect SKIPs are retired (#49); a recurrence of scaffold.providerWroteSddTree is a regression"
    sed 's/^/  | /' "$WORKDIR/scaffold.log" 2>/dev/null
  fi
else
  skip "fsgg-sdd CLI not available — scaffold+build of the live rendering app not exercised here. Run with the SDD CLI installed (or FSGG_COMPOSITION_FULL=1) to require it. This stage validates the un-vendored composition path; the gate keeps CI honest rather than green-by-omission."
fi
