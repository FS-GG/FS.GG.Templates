# shellcheck shell=bash
# ── Stage 4: verify pins/links ───────────────────────────────────────────────
# Uses APP (Stage 3), REPO_ROOT, and read_pin (sourced by run.sh from scripts/lib/read-pin.sh).
# Sets PROV and PIN_VER for the build / standalone stages.
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
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet build Acme.slnx" "appName -> tooling build command"
assert_contains "$APP/.fsgg/tooling.yml"  "dotnet test Acme.slnx"  "appName -> tooling test command"
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
PIN_VER="$(read_pin "$PROV" || true)"
if [[ -n "$PIN_VER" ]]; then
  ok "provider pins FS.GG.UI.Template::$PIN_VER"
  # the file's own comment (and the README) must name the same version — guards 'bump both together'
  assert_contains "$PROV" "fs-gg-ui-template/v$PIN_VER" "provider comment tag matches the pinned version"
  assert_contains "$REPO_ROOT/README.md" "$PIN_VER" "README names the pinned template version"
else
  bad "could not parse FS.GG.UI.Template version pin from provider yml"
fi
# lifecycle=sdd (ADR-0002) and profile=game (game/rendering default starter, ADR
# FS.GG.Rendering 0010; flipped app->game per issue #39 / SDD#44) are the defaults.
if grep -A2 'key: lifecycle' "$PROV" | grep -q 'default: sdd';  then ok "provider default lifecycle=sdd (ADR-0002)"; else bad "provider lifecycle default is not 'sdd'"; fi
if grep -A4 'key: profile'   "$PROV" | grep -q 'default: game'; then ok "provider default profile=game";          else bad "provider profile default is not 'game'"; fi
