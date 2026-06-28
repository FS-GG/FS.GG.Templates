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
# governance.yml (NOT project.yml: SDD owns .fsgg/project.yml; the overlay uses its own
# file so it composes onto an SDD-scaffolded project without a write collision).
for f in governance.yml policy.yml capabilities.yml tooling.yml; do
  [[ -f "$APP/.fsgg/$f" ]] && ok ".fsgg/$f emitted" || bad ".fsgg/$f missing"
done

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
step "build — full fsgg-sdd scaffold + product build (gated)"
if command -v fsgg-sdd >/dev/null 2>&1; then
  RUN_FULL=1
elif [[ "${FSGG_COMPOSITION_FULL:-}" == "1" ]]; then
  bad "FSGG_COMPOSITION_FULL=1 requested but 'fsgg-sdd' is not on PATH"; RUN_FULL=0
else
  RUN_FULL=0
fi
if [[ "$RUN_FULL" == "1" ]]; then
  FULL="$WORKDIR/full"
  # No source override: exercise the self-pinned provider (FS.GG.UI.Template::$PIN_VER).
  # The fs-gg-ui product is FAKE-backed and ships NO root solution (projects live under
  # src/ and tests/), so `dotnet build <root>` cannot resolve a target. Build the emitted
  # app project directly — a faithful "does the composed product compile" smoke. (The
  # product's own full build is `./fake.sh build -t Dev`; that heavier path is not run here.)
  if "$REPO_ROOT/scripts/new-fullstack.sh" "$FULL" Acme >"$WORKDIR/scaffold.log" 2>&1; then
    APP_PROJ="$(find "$FULL/src" -name '*.fsproj' 2>/dev/null | head -1)"
    if [[ -n "$APP_PROJ" ]] && dotnet build "$APP_PROJ" >"$WORKDIR/build.log" 2>&1; then
      ok "scaffold + build of the composed product succeeded ($(basename "$APP_PROJ"))"
    else
      bad "composed product build failed (proj='${APP_PROJ:-<none found>}'; see $WORKDIR/build.log)"
    fi
  else
    bad "full scaffold failed (see $WORKDIR/scaffold.log)"
  fi
else
  skip "fsgg-sdd CLI not available — scaffold+build of the live rendering app not exercised here. Run with the SDD CLI installed (or FSGG_COMPOSITION_FULL=1) to require it. This stage validates the un-vendored composition path; the gate keeps CI honest rather than green-by-omission."
fi

# ── Summary ──────────────────────────────────────────────────────────────────
printf '\n\033[1m== summary ==\033[0m  \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
