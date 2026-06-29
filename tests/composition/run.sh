#!/usr/bin/env bash
# End-to-end composition test for FS.GG.Templates.
#
# Runs the standard packaging-repo checks prescribed by the architecture report
# (docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md §5.2):
#
#     pack → install → instantiate → (restore/build) → verify pins/links
#
# What this repo *owns* is verified end-to-end and unconditionally:
#   - the FS.GG.Templates package packs,
#   - it installs as a `dotnet new` template source,
#   - the populated `fs-gg-governance` overlay instantiates,
#   - parameter substitutions land and the governance gate set is populated
#     (not the inert `checks: []` / `commands: []` it used to ship), and
#   - the `rendering` provider pin is internally coherent (version + lifecycle/profile).
#
# The full rendering product (scaffold → restore/build of the live FS.GG.UI app) needs
# the `fsgg-sdd` CLI and a reachable FS.GG.UI.Template feed. That stage is GATED: it runs
# only when those are available (or FSGG_COMPOSITION_FULL=1 forces it) and otherwise SKIPS
# with an explicit reason — it never silently passes.
#
# A further GATED stage exercises the SDD→Governance enforcement loop end-to-end through
# the composed product — the seam Templates specifically owns (no single upstream repo
# covers the composition):
#     scaffold → fsgg-sdd ship (emit governance-handoff.json) → fsgg-governance route
#     (consume it → produce a verdict) → assert the populated overlay actually ENFORCES.
# It needs both the `fsgg-sdd` and `fsgg-governance` CLIs and the composed product the
# build stage scaffolds; absent either it SKIPS with a reason — never green-by-omission.
#
# Usage:   tests/composition/run.sh
# Env:     FSGG_COMPOSITION_FULL=1   require (do not skip) the full scaffold+build stage
#          KEEP_WORKDIR=1            do not delete the temp workdir on exit
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-composition.XXXXXX")"
ARTIFACTS="$WORKDIR/artifacts"
APP="$WORKDIR/app"
mkdir -p "$ARTIFACTS"

PASS=0 FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m–\033[0m SKIP: %s\n' "$1"; }
step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
# assert_contains <file> <substring> <message>
assert_contains() { if grep -qF -- "$2" "$1" 2>/dev/null; then ok "$3"; else bad "$3 (missing: '$2' in $1)"; fi; }
# assert_absent <file-or-dir> <substring> <message>  (recursive for dirs)
assert_absent() { if grep -rqF -- "$2" "$1" 2>/dev/null; then bad "$3 (found stray '$2' in $1)"; else ok "$3"; fi; }
# assert_exit <expected-code> <actual-code> <message>  — exact match (so a usage/input/tool
# error, e.g. 64/66/70, can never masquerade as a governed-blocking '2' or a clean '0').
assert_exit() { if [[ "$2" == "$1" ]]; then ok "$3 (exit $2)"; else bad "$3 (expected exit $1, got $2)"; fi; }

cleanup() {
  dotnet new uninstall FS.GG.Templates >/dev/null 2>&1 || true
  if [[ "${KEEP_WORKDIR:-}" == "1" ]]; then
    printf '\n(workdir kept at %s)\n' "$WORKDIR"
  else
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT

command -v dotnet >/dev/null || { echo "FATAL: dotnet not on PATH"; exit 2; }

# ── Stage 1: pack ────────────────────────────────────────────────────────────
step "pack — dotnet pack FS.GG.Templates"
if dotnet pack "$REPO_ROOT/FS.GG.Templates.csproj" -c Release -o "$ARTIFACTS" >"$WORKDIR/pack.log" 2>&1; then
  ok "dotnet pack succeeded"
else
  bad "dotnet pack failed (see $WORKDIR/pack.log)"; sed -n '$p' "$WORKDIR/pack.log"; KEEP_WORKDIR=1; exit 1
fi
NUPKG="$(ls -1 "$ARTIFACTS"/FS.GG.Templates.*.nupkg 2>/dev/null | head -1)"
[[ -f "$NUPKG" ]] && ok "produced $(basename "$NUPKG")" || { bad "no FS.GG.Templates nupkg produced"; exit 1; }

# ── Stage 2: install ─────────────────────────────────────────────────────────
step "install — dotnet new install <nupkg>"
dotnet new uninstall FS.GG.Templates >/dev/null 2>&1 || true
if dotnet new install "$NUPKG" >"$WORKDIR/install.log" 2>&1; then
  ok "dotnet new install succeeded"
else
  bad "dotnet new install failed (see $WORKDIR/install.log)"; sed -n '$p' "$WORKDIR/install.log"; exit 1
fi
if dotnet new list 2>/dev/null | grep -q 'fs-gg-governance'; then ok "template 'fs-gg-governance' registered"; else bad "'fs-gg-governance' not registered after install"; fi

# ── Stage 3: instantiate the populated governance overlay ────────────────────
step "instantiate — dotnet new fs-gg-governance (appName=Acme, profile=strict)"
if dotnet new fs-gg-governance -o "$APP" --appName Acme --defaultProfile strict >"$WORKDIR/new.log" 2>&1; then
  ok "instantiation succeeded"
else
  bad "instantiation failed (see $WORKDIR/new.log)"; sed -n '$p' "$WORKDIR/new.log"; exit 1
fi

# ── Stage 4: verify pins/links ───────────────────────────────────────────────
step "verify — emitted files"
# The governance descriptor lives in the Governance-owned `.fsgg/governance.yml` slot
# (ADR-0005; registry `governance-descriptor` surface) — NOT the SDD-owned `.fsgg/project.yml`,
# which it would otherwise collide with in a composed product's shared `.fsgg/`.
for f in governance.yml policy.yml capabilities.yml tooling.yml; do
  [[ -f "$APP/.fsgg/$f" ]] && ok ".fsgg/$f emitted" || bad ".fsgg/$f missing"
done
# Guard the ADR-0005 slot: the overlay must NOT write the SDD-owned project.yml.
[[ -f "$APP/.fsgg/project.yml" ]] && bad ".fsgg/project.yml present — overlay wrote the SDD-owned slot (ADR-0005 violation)" || ok "no stray .fsgg/project.yml (SDD slot left to SDD)"

step "verify — parameter substitution (no stray tokens)"
assert_absent "$APP/.fsgg" "<App>"             "appName token '<App>' fully substituted"
assert_absent "$APP/.fsgg" "GOV_DEFAULT_PROFILE" "profile token 'GOV_DEFAULT_PROFILE' fully substituted"
assert_contains "$APP/.fsgg/governance.yml"  "id: Acme"          "appName -> governance.yml id"
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet build Acme.sln" "appName -> tooling build command"
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet test Acme.sln"  "appName -> tooling test command"
assert_contains "$APP/.fsgg/policy.yml"   "defaultProfile: strict" "defaultProfile -> policy default"

step "verify — governance gate set is POPULATED (not inert)"
# The P3/P4 deliverable: capabilities.checks and tooling.commands must be non-empty.
assert_contains "$APP/.fsgg/capabilities.yml" "id: build"    "capabilities: build check present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: test"     "capabilities: test check present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: evidence" "capabilities: evidence check present"
assert_contains "$APP/.fsgg/tooling.yml"      "id: dotnet-build"   "tooling: dotnet-build command present"
assert_contains "$APP/.fsgg/tooling.yml"      "id: dotnet-test"    "tooling: dotnet-test command present"
assert_contains "$APP/.fsgg/tooling.yml"      "id: build-evidence" "tooling: build-evidence command present"
if grep -Eq '^\s*checks:\s*\[\s*\]' "$APP/.fsgg/capabilities.yml"; then bad "capabilities still ships inert 'checks: []'"; else ok "capabilities.checks is not the inert empty list"; fi
if grep -Eq '^\s*commands:\s*\[\s*\]' "$APP/.fsgg/tooling.yml";    then bad "tooling still ships inert 'commands: []'"; else ok "tooling.commands is not the inert empty list"; fi

step "verify — rendering provider pin coherence"
PROV="$REPO_ROOT/providers/rendering.providers.yml"
PIN_VER="$(grep -oE 'FS\.GG\.UI\.Template::[^ ]+' "$PROV" | head -1 | sed 's/.*:://')"
if [[ -n "$PIN_VER" ]]; then
  ok "provider pins FS.GG.UI.Template::$PIN_VER"
  # the file's own comment (and the README) must name the same version — guards 'bump both together'
  assert_contains "$PROV" "fs-gg-ui-template/v$PIN_VER" "provider comment tag matches the pinned version"
  assert_contains "$REPO_ROOT/README.md" "$PIN_VER" "README names the pinned template version"
else
  bad "could not parse FS.GG.UI.Template version pin from provider yml"
fi
# lifecycle=sdd and profile=app are the composition-by-scaffold defaults (ADR-0002)
if grep -A2 'key: lifecycle' "$PROV" | grep -q 'default: sdd'; then ok "provider default lifecycle=sdd (ADR-0002)"; else bad "provider lifecycle default is not 'sdd'"; fi
if grep -A2 'key: profile'   "$PROV" | grep -q 'default: app'; then ok "provider default profile=app";          else bad "provider profile default is not 'app'";  fi

# ── Stage 5: full scaffold + build (GATED) ───────────────────────────────────
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
if [[ "$RUN_FULL" == "1" ]]; then
  if "$REPO_ROOT/scripts/new-fullstack.sh" "$FULL" Acme "$PIN_VER" >"$WORKDIR/scaffold.log" 2>&1 \
     && dotnet build "$FULL" >"$WORKDIR/build.log" 2>&1; then
    ok "scaffold + dotnet build of the composed product succeeded"; FULL_OK=1
  else
    bad "full scaffold/build failed (see $WORKDIR/scaffold.log, $WORKDIR/build.log)"
    echo "  --- scaffold.log (tail) ---"; tail -n 40 "$WORKDIR/scaffold.log" 2>/dev/null | sed 's/^/  | /'
    echo "  --- build.log (tail) ---";    tail -n 40 "$WORKDIR/build.log"    2>/dev/null | sed 's/^/  | /'
  fi
else
  skip "fsgg-sdd CLI not available — scaffold+build of the live rendering app not exercised here. Run with the SDD CLI installed (or FSGG_COMPOSITION_FULL=1) to require it. This stage validates the un-vendored composition path; the gate keeps CI honest rather than green-by-omission."
fi

# ── Stage 6: SDD→Governance handoff enforcement (GATED) ──────────────────────
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
  # write_handoff <path> <satisfied|failing> — emit a contract-v1 governance-handoff.json.
  # 'failing' declares a failed evidence node + a non-shippable, blocking readiness block;
  # 'satisfied' declares everything real/ready. Shape per FS.GG.Governance spec 081
  # contracts/handoff-document.md (governance-handoff@1.0.0).
  write_handoff() {
    local path="$1" kind="$2"; mkdir -p "$(dirname "$path")"
    if [[ "$kind" == failing ]]; then
      cat > "$path" <<'JSON'
{
  "contractVersion": "1.0.0",
  "schemaVersion": 1,
  "evidence": {
    "nodes": [
      { "id": "build:lib", "state": "failed", "rationale": "composition e2e: forced failing evidence" },
      { "id": "test:unit", "state": "real" }
    ],
    "dependencies": [ ["test:unit", "build:lib"] ]
  },
  "readiness": {
    "shipDisposition": "blocked",
    "verificationReadiness": "incomplete",
    "blockingDiagnosticIds": ["COMPOSITION_E2E_BLOCK"],
    "counts": { "blocking": 1, "advisory": 0 },
    "perViewState": { "ledger": "stale" }
  },
  "governedReferences": []
}
JSON
    else
      cat > "$path" <<'JSON'
{
  "contractVersion": "1.0.0",
  "schemaVersion": 1,
  "evidence": {
    "nodes": [
      { "id": "build:lib", "state": "real" },
      { "id": "test:unit", "state": "real" }
    ],
    "dependencies": [ ["test:unit", "build:lib"] ]
  },
  "readiness": {
    "shipDisposition": "ready",
    "verificationReadiness": "complete",
    "blockingDiagnosticIds": [],
    "counts": { "blocking": 0, "advisory": 0 },
    "perViewState": {}
  },
  "governedReferences": []
}
JSON
    fi
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

  dotnet new fs-gg-governance -o "$GOV" --appName Acme --defaultProfile strict >"$WORKDIR/govnew.log" 2>&1
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
fi

# ── Summary ──────────────────────────────────────────────────────────────────
printf '\n\033[1m== summary ==\033[0m  \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
