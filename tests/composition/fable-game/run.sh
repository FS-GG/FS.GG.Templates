#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-fable-game-composition.XXXXXX")"
trap 'rm -rf "$work"' EXIT
export DOTNET_CLI_HOME="$work/dotnet-home"
for browser in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$browser" >/dev/null 2>&1; then
    export PLAYWRIGHT_EXECUTABLE_PATH="$(command -v "$browser")"
    echo "fable-game composition: selected system browser $PLAYWRIGHT_EXECUTABLE_PATH"
    break
  fi
done

LANE_REPO_ROOT="$root"
# shellcheck source=tests/composition/lib/lane-package.sh
. "$root/tests/composition/lib/lane-package.sh"
# The release gate sets FSGG_TEMPLATES_NUPKG to the downloaded, checksum-verified artifact, so this
# lane proves the fable-game identity against the bytes that are about to be published rather than
# against a second archive packed here (FS.GG.Templates#349).
package="$(lane_package_path "$work")"
echo "fable-game composition: installing $package"
dotnet new install "$package" --force
dotnet new fs-gg-fable-game -n CleanFableGame -o "$work/scaffold"
test -f "$work/scaffold/Domain/Domain.fsproj"
test -f "$work/scaffold/Server/Server.fsproj"
test -f "$work/scaffold/Client/Client.fsproj"
test -f "$work/scaffold/Client/package.json"
test -f "$work/scaffold/Browser.Tests/two-client.spec.ts"
test -f "$work/scaffold/Protocol.Tests/cross-runtime/run-cross-runtime.sh"

# ── Owner-sourced product skills reach the PACKED product (FS.GG.Templates#347) ────────────────
# Asserted here, against the scaffold produced from the packed-and-installed nupkg above, because
# that is the only place the producer delivery contract is observable end to end. Its round-1
# review failure was precisely that every source-side check stayed green while the catalog sat in
# a tree no package item referenced, so no generated product received a single declared skill.
#
# The assertion reads the manifest the PRODUCT shipped and grades the product's own skill root
# against it, so it reds on an absent selected skill, a materialized skill the manifest does not
# select for this template, an undeclared (dangling) skill directory, a digest that does not match
# the shipped bytes, and a missing or non-canonical producer manifest. Every one of those lanes was
# demonstrated to fire before this line was written.
dotnet fsi "$root/scripts/generate-skill-manifest.fsx" --assert-product "$work/scaffold" --template fs-gg-fable-game
test -f "$work/scaffold/CleanFableGame.slnx"
# No `rootNamespace` was supplied, so the identifier falls back to the product name
# (the same coalesce `effectiveIdentifier` uses for fs-gg-web / fs-gg-console).
grep -q '^namespace CleanFableGame.Server$' "$work/scaffold/Server/Program.fs"

dotnet build "$work/scaffold/CleanFableGame.slnx"
test -f "$work/scaffold/Server/packages.lock.json"
test -f "$work/scaffold/Client/package-lock.json"
test -f "$work/scaffold/Browser.Tests/package-lock.json"

(
  cd "$work/scaffold"
  bash ./build.sh
  test -f artifacts/publish/wwwroot/index.html
  test -s artifacts/test-results/domain.trx
  test -s artifacts/test-results/protocol.trx
  test -s artifacts/test-results/server.trx
  test -s artifacts/test-results/browser.junit.xml
)

# Prove the declared provider contract through SDD with distinct raw and identifier
# names. This is the integration surface consumed by generated products, not an
# alias for direct `dotnet new` instantiation.
mkdir -p "$work/sdd/.fsgg"
cp "$root/providers/fable-game.providers.yml" "$work/sdd/.fsgg/providers.yml"
lane_pin_provider_to_archive "$work/sdd/.fsgg/providers.yml" "$package"
fsgg-sdd scaffold --root "$work/sdd" --provider fable-game --param productName=Rogue-FableGame --param rootNamespace=RogueFableGame --no-update --json >"$work/scaffold.json"
jq -e '.outcome == "succeeded" and .scaffold.providerName == "fable-game" and .scaffold.providerInvoked == true' "$work/scaffold.json" >/dev/null
test -f "$work/sdd/.fsgg/scaffold-provenance.json"
test -f "$work/sdd/Rogue-FableGame.slnx"
test -f "$work/sdd/Server/Server.fsproj"
test -f "$work/sdd/Server.Tests/Server.Tests.fsproj"
grep -q '^namespace RogueFableGame.Server$' "$work/sdd/Server/Program.fs"
fsgg-sdd doctor --root "$work/sdd" --json >"$work/doctor.json"
jq -e '.outcome == "noChange" and (.diagnostics | length) == 0' "$work/doctor.json" >/dev/null
# The ownership assertion's changed arm needs a real producer-emitted subject. Public SDD 1.2.4
# supplies this Rendering row with an off-Templates supplier namespace; without this liveness leg,
# deleting the only foreign product row would make the ownership arm vacuous while the lane stayed
# green. Exercise the same predicate against a removed-row mutation so the liveness gate proves it
# can red rather than merely predicting that it would.
assert_feedback_report_manifest_subject() {
  jq -e '[.skills[] | select(.id == "fs-gg-feedback-report" and .scope == "product" and ."supplied-by" == "template/feedback-report/skill/")] | length == 1' "$1" >/dev/null
}
provider_manifest="$work/sdd/.agents/skills/skill-manifest.json"
assert_feedback_report_manifest_subject "$provider_manifest" || {
  echo "fable-game composition: public SDD provider emitted no uniquely supplier-attributed fs-gg-feedback-report product row" >&2
  exit 1
}
jq 'del(.skills[] | select(.id == "fs-gg-feedback-report"))' "$provider_manifest" >"$work/provider-manifest-without-feedback-report.json"
if assert_feedback_report_manifest_subject "$work/provider-manifest-without-feedback-report.json"; then
  echo "fable-game composition: feedback-report manifest-subject removal mutation unexpectedly passed" >&2
  exit 1
fi
# The orchestrated lane is a SECOND delivery route, not a rerun of the first: SDD resolves the
# provider descriptor and drives `dotnet new` itself. A package item that survives direct
# instantiation but not the provider route would leave products scaffolded the supported way with
# no skills at all, so the same contract is asserted on this product too.
#
# `--co-tenants` because this root is SHARED: fsgg-sdd seeds its own `fs-gg-sdd-*` process skills
# and the five `always` `.github` driver skills (registry/driver-skill-manifest.json) into the same
# `.agents/skills/`. Those belong to other producers and this manifest must not declare them; a
# skill belonging to nobody still reds.
dotnet fsi "$root/scripts/generate-skill-manifest.fsx" --assert-product "$work/sdd" --template fs-gg-fable-game \
  --co-tenants 'fs-gg-sdd-* work-board work-board-best work-board-normal work-roadmap padd-item'

echo "fable-game composition: generated clean scaffold production lifecycle, including cross-runtime codec proof, the Playwright two-client scenario, and owner-sourced product-skill delivery through both the direct and provider routes"
