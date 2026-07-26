# shellcheck shell=bash
# ── Stage 4: verify pins/links ───────────────────────────────────────────────
# Uses APP (Stage 3), REPO_ROOT, and read_pin (sourced by run.sh from scripts/lib/read-pin.sh).
# Sets PROV and PIN_VER for the build / standalone stages.
step "verify — emitted files"
# The governance descriptor lives in the Governance-owned `.fsgg/governance.yml` slot
# (ADR-0005; registry `governance-descriptor` surface) — NOT the SDD-owned `.fsgg/project.yml`,
# which it would otherwise collide with in a composed product's shared `.fsgg/`.
for f in governance.yml policy.yml capabilities.yml tooling.yml controlled-imports.fsx controlled-imports.json; do
  [[ -f "$APP/.fsgg/$f" ]] && ok ".fsgg/$f emitted" || bad ".fsgg/$f missing"
done
[[ -f "$APP/schema-manifest.json" ]] && ok "schema-manifest.json emitted beside .fsgg" || bad "schema-manifest.json missing"
# Guard the ADR-0005 slot: the overlay must NOT write the SDD-owned project.yml.
[[ -f "$APP/.fsgg/project.yml" ]] && bad ".fsgg/project.yml present — overlay wrote the SDD-owned slot (ADR-0005 violation)" || ok "no stray .fsgg/project.yml (SDD slot left to SDD)"

step "verify — parameter substitution (no stray tokens)"
assert_absent "$APP/.fsgg" "<App>"             "appName token '<App>' fully substituted"
assert_absent "$APP/.fsgg" "GOV_DEFAULT_PROFILE" "profile token 'GOV_DEFAULT_PROFILE' fully substituted"
assert_contains "$APP/.fsgg/governance.yml"  "id: Acme"          "appName -> governance.yml id"
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet build Acme.slnx" "appName -> tooling build command"
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet test Acme.slnx"  "appName -> tooling test command"
assert_contains "$APP/.fsgg/policy.yml"   "defaultProfile: strict" "defaultProfile -> policy default"

step "verify — governance gate set is POPULATED (not inert)"
# The P3/P4 deliverable: capabilities.checks and tooling.commands must be non-empty.
assert_contains "$APP/.fsgg/capabilities.yml" "id: build"    "capabilities: build check present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: test"     "capabilities: test check present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: evidence" "capabilities: evidence check present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: fr-covered" "capabilities: gameplay FR-coverage floor present"
assert_contains "$APP/.fsgg/capabilities.yml" "id: production-journey" "capabilities: production-journey floor present"
assert_contains "$APP/.fsgg/capabilities.yml" 'glob: "*.slnx"' "capabilities: build path map follows the emitted .slnx"
assert_contains "$APP/.fsgg/tooling.yml"      "id: dotnet-build"   "tooling: dotnet-build command present"
assert_contains "$APP/.fsgg/tooling.yml"      "id: dotnet-test"    "tooling: dotnet-test command present"
assert_contains "$APP/.fsgg/tooling.yml"      "id: build-evidence" "tooling: build-evidence command present"
if grep -Eq '^\s*checks:\s*\[\s*\]' "$APP/.fsgg/capabilities.yml"; then bad "capabilities still ships inert 'checks: []'"; else ok "capabilities.checks is not the inert empty list"; fi
if grep -Eq '^\s*commands:\s*\[\s*\]' "$APP/.fsgg/tooling.yml";    then bad "tooling still ships inert 'commands: []'"; else ok "tooling.commands is not the inert empty list"; fi

assert_command_free_gameplay_floor() {
  local id="$1"
  local block
  block="$(
    awk -v target="$id" '
      /^  - id: / {
        if (capture) exit
        capture = ($0 == "  - id: " target)
      }
      capture { print }
    ' "$APP/.fsgg/capabilities.yml"
  )"

  if [[ "$block" == *"domain: gameplay"* &&
        "$block" == *"maturity: block-on-ship"* &&
        "$block" != *"command:"* ]]; then
    ok "capabilities: gameplay:$id is command-free and block-on-ship"
  else
    bad "capabilities: gameplay:$id must be command-free and block-on-ship"
  fi
}

assert_command_free_gameplay_floor fr-covered
assert_command_free_gameplay_floor production-journey

if dotnet fsi "$APP/.fsgg/controlled-imports.fsx" -- --root "$APP" >"$WORKDIR/controlled-imports.log" 2>&1; then
  ok "controlled-import verifier accepts the emitted empty pinned manifest"
else
  bad "controlled-import verifier rejected the emitted manifest (see $WORKDIR/controlled-imports.log)"
fi

assert_contains "$APP/schema-manifest.json" '"governance": 1'   "schema manifest records governance generation 1"
assert_contains "$APP/schema-manifest.json" '"capabilities": 2' "schema manifest records capabilities generation 2"
assert_contains "$APP/schema-manifest.json" '"policy": 1'        "schema manifest records policy generation 1"
assert_contains "$APP/schema-manifest.json" '"tooling": 1'       "schema manifest records tooling generation 1"

step "verify — governance overlay matches its immutable published authority"
if "$COMPOSITION_DIR/lib/reference-gate-set-overlay.sh" --check >"$WORKDIR/reference-gate-set.log" 2>&1; then
  ok "overlay matches FS.GG.Governance.ReferenceGateSet 1.5.0 with only declared template transforms"
else
  bad "overlay drifted from pinned FS.GG.Governance.ReferenceGateSet authority (see $WORKDIR/reference-gate-set.log)"
  sed -n '1,160p' "$WORKDIR/reference-gate-set.log"
fi

step "verify — rendering provider pin coherence"
PROV="$REPO_ROOT/providers/rendering.providers.yml"
if "$REPO_ROOT/tests/effective-providers/run.sh"; then
  ok "effective-provider generator forward fixture passes"
else
  bad "effective-provider generator forward fixture failed"
fi
if "$REPO_ROOT/scripts/generate-effective-providers.py" --provider "$PROV" --check; then
  ok "effective-provider summary is deterministic, unique, and ordered"
else
  bad "effective-provider summary is stale or structurally invalid"
fi
PIN_VER="$(read_pin "$PROV" || true)"
if [[ -n "$PIN_VER" ]]; then
  ok "provider pins FS.GG.UI.Template::$PIN_VER"
  # the file's own comment (and the README) must name the same version — guards 'bump both together'
  assert_contains "$PROV" "fs-gg-ui-template/v$PIN_VER" "provider comment tag matches the pinned version"
  assert_contains "$REPO_ROOT/README.md" "$PIN_VER" "README names the pinned template version"
  # scripts/bump-rendering-pin.sh moves the pin but cannot know WHY the release happened, so it
  # leaves a stub in the provider's PIN HISTORY block. Fail while one remains: an unexplained pin
  # is how the file came to claim 0.3.1-preview.1 was the ADR-0022 framework major (it was not).
  assert_absent "$PROV" "PIN HISTORY ENTRY REQUIRED" "provider PIN HISTORY has no unwritten entry"
else
  bad "could not parse FS.GG.UI.Template version pin from provider yml"
fi
# lifecycle=sdd (ADR-0002) and profile=game (game/rendering default starter, ADR
# FS.GG.Rendering 0010; flipped app->game per issue #39 / SDD#44) are the defaults.
if grep -A2 'key: lifecycle' "$PROV" | grep -q 'default: sdd';  then ok "provider default lifecycle=sdd (ADR-0002)"; else bad "provider lifecycle default is not 'sdd'"; fi
if grep -A4 'key: profile'   "$PROV" | grep -q 'default: game'; then ok "provider default profile=game";          else bad "provider profile default is not 'game'"; fi
