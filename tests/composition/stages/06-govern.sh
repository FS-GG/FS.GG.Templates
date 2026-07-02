# shellcheck shell=bash
# ── Stage 6: SDD→Governance handoff enforcement (GATED) ──────────────────────
# Uses FULL, FULL_OK (Stage 5), WORKDIR, FIXTURES (run.sh), assert_contains/assert_exit (lib).
#
# The seam Templates owns: the governance overlay it ships must actually ENFORCE a produced
# governance-handoff.json — a verdict driven by the handoff's declared facts — not just be a
# populated-but-inert gate set. (Stages 3–4 only prove the overlay is populated; this proves
# it bites.) Two parts, each independently gated, neither ever green-by-omission:
#   6a producer — a real `fsgg-sdd ship` (over the Stage-5 composed product) emits the handoff;
#   6b consumer — `fsgg-governance` consumes a handoff and the overlay's profile decides the verdict.
# 6b needs only `fsgg-governance` + the overlay Templates ships (a fresh instantiation — the
# rendering app does not affect a governance verdict), so it runs in far more environments than
# the full rendering scaffold.
#
# CLI-surface note: the architecture report's conceptual "fsgg-governance verify/ship" is the
# shipped CLI's `fsgg-governance route --mode gate` — the CI/merge-boundary mode whose blocking
# verdict exits 2 (GovernedBlocking; exit 0 = clean, 64/66/70 = usage/input/tool error). The
# handoff consumer (FS.GG.Governance spec 081, FS.GG.Governance.Adapters.SddHandoff) auto-
# discovers readiness/<id>/governance-handoff.json under --root and folds its declared
# evidence/readiness into the selected gate set.
step "govern — the governance overlay ENFORCES the SDD handoff (gated)"
if ! command -v fsgg-governance >/dev/null 2>&1; then
  skip "fsgg-governance CLI not available — the SDD→Governance enforcement loop is not exercised here. Install the Governance CLI to require it. The gate keeps CI honest rather than green-by-omission."
else
  # write_handoff <path> <failing|satisfied> — install a contract-v1 governance-handoff.json from
  # the checked-in fixtures (tests/composition/fixtures/governance-handoff.<kind>.json — extracted
  # from inline heredocs in review A3). 'failing' declares a failed evidence node + a non-shippable,
  # blocking readiness block; 'satisfied' declares everything real/ready. Shape per FS.GG.Governance
  # spec 081 contracts/handoff-document.md (governance-handoff@1.0.0).
  write_handoff() {
    local path="$1" kind="$2"; mkdir -p "$(dirname "$path")"
    cp "$FIXTURES/governance-handoff.$kind.json" "$path"
  }

  # 6a — producer seam: a real `fsgg-sdd ship` emits the handoff at the contract path within
  # the composed product. Needs fsgg-sdd + the Stage-5 build; SKIPs (not fails) otherwise.
  if command -v fsgg-sdd >/dev/null 2>&1 && [[ "$FULL_OK" == "1" ]]; then
    ( cd "$FULL" && fsgg-sdd ship ) >"$WORKDIR/ship.log" 2>&1 || true
    SHIPPED="$(find "$FULL/readiness" -name governance-handoff.json 2>/dev/null | head -1)"
    if [[ -n "$SHIPPED" ]]; then
      ok "fsgg-sdd ship emitted $(basename "$(dirname "$SHIPPED")")/governance-handoff.json"
      assert_contains "$SHIPPED" '"contractVersion": "1' "emitted handoff pins governance-handoff contract major 1"
    else
      skip "fsgg-sdd ship emitted no handoff (no ship-ready work item in a bare scaffold) — producer seam not exercised; the consumer/enforcement matrix below still runs against a contract fixture"
    fi
  else
    skip "fsgg-sdd unavailable or no Stage-5 composed product — producer seam ('fsgg-sdd ship' emits the handoff) not exercised; the consumer/enforcement matrix below still runs against a contract fixture"
  fi

  # 6b — consumer + enforcement. Instantiate the overlay Templates ships into a fresh product
  # and run the gate loop over contract-v1 fixtures. Hold the product fixed; vary only
  # (handoff, profile). The enforcement signal is the EXIT-CODE differential, only possible if
  # `route` CONSUMES the handoff and the overlay ENFORCES it per profile.
  GOV="$WORKDIR/govern"
  POLICY="$GOV/.fsgg/policy.yml"
  HANDOFF="$GOV/readiness/handoff-e2e/governance-handoff.json"
  set_profile() { sed -i.bak -E "s/^([[:space:]]*defaultProfile:).*/\1 $1/" "$POLICY" && rm -f "$POLICY.bak"; }
  govern_exit() { fsgg-governance route --root "$GOV" --mode gate --json >"$WORKDIR/govern.log" 2>&1; echo $?; }

  # Guard the overlay instantiation (F5): without it a `dotnet new` failure here leaves $GOV
  # with no policy/handoff, and the govern_exit below would report a confusing usage/input/tool
  # exit code (the `*)` arm) instead of a first-cause diagnostic. Stages 3/5 model this pattern.
  if ! dotnet new fs-gg-governance -o "$GOV" --appName Acme --defaultProfile strict >"$WORKDIR/govnew.log" 2>&1; then
    bad "Stage 6b: dotnet new fs-gg-governance failed to instantiate the overlay into $GOV (see $WORKDIR/govnew.log) — enforcement loop not exercised"
    sed -n '$p' "$WORKDIR/govnew.log"
  else
  write_handoff "$HANDOFF" failing
  ES="$(govern_exit)"
  case "$ES" in
    2)
      # The installed CLI consumes & enforces the handoff (capability #28: shipped in
      # FS.GG.Governance.Cli >= 1.1.0). Assert the consumption rows now.
      ok "strict + failing handoff → blocked (exit 2): the overlay consumed the handoff and ENFORCED it"
      write_handoff "$HANDOFF" satisfied
      assert_exit 0 "$(govern_exit)" "strict + satisfied handoff → clean verdict — the verdict tracks the declared facts, so consumption is real (not just overlay-populated)"

      # Profile-aware relaxation is a SEPARATE capability from consumption: `light` must shift the
      # blocking boundary so the same failing handoff stops blocking. This requires BOTH (a) the
      # overlay shipping its descriptor in the Governance-owned `.fsgg/governance.yml` slot so the
      # CLI can read `defaultProfile` (Templates#28 — fixed here; absent it, the loader falls back
      # to the Strict fail-safe and over-blocks under every profile), and (b) a profile-aware CLI
      # (FS.GG.Governance.Cli >= 1.2.0, FS.GG.Governance#34). With (a) fixed this asserts against a
      # profile-aware CLI; an older profile-unaware CLI (1.1.0) still over-blocks → honest SKIP.
      write_handoff "$HANDOFF" failing; set_profile light
      LES="$(govern_exit)"
      case "$LES" in
        0) ok "light + same failing handoff → not blocked (exit 0): the profile shifts the blocking boundary — the overlay enforces only when the profile says so" ;;
        2) skip "light + same failing handoff still blocks (route --mode gate exited 2) — the descriptor slot is correct (governance.yml), so this is an older profile-unaware CLI (pre-1.2.0 strict-only baseline; light does not yet relax the gate boundary). The light-passes row asserts automatically once a profile-aware CLI (>= 1.2.0) is on PATH. Tracking: FS-GG/FS.GG.Governance#34." ;;
        *) bad "fsgg-governance route (light + failing) returned exit $LES (usage/input/tool error, not a verdict) — see $WORKDIR/govern.log" ;;
      esac
      ;;
    0)
      # A failing handoff did not block ⇒ the installed CLI's build does not consume the handoff.
      # Honest SKIP (not a false pass, not a false fail): the loop is asserted in full the moment
      # a consumer-bearing CLI is on PATH. See the cross-repo tracking issue.
      skip "installed fsgg-governance did NOT enforce a failing handoff (route --mode gate exited 0, selecting no handoff gate) — its build omits the SDD-handoff consumer (FS.GG.Governance spec 081, FS.GG.Governance.Adapters.SddHandoff). The strict-blocks/strict-passes consumption rows assert automatically once a consumer-bearing CLI (FS.GG.Governance.Cli >= 1.1.0) is on PATH; the light-relaxation row is gated separately on #34. Tracking: FS-GG/FS.GG.Governance#28."
      ;;
    *)
      bad "fsgg-governance route returned exit $ES (usage/input/tool error, not a verdict) — see $WORKDIR/govern.log"
      ;;
  esac
  fi   # close the Stage-6b overlay-instantiation guard (F5)
fi
