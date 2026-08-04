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

dotnet pack "$root/FS.GG.Templates.csproj" -o "$work/packages"
dotnet new install "$work/packages"/*.nupkg --force
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
sed -i "s#FS.GG.Workspace.Template::0.8.0#$work/packages/FS.GG.Workspace.Template.0.8.0.nupkg#" "$work/sdd/.fsgg/providers.yml"
fsgg-sdd scaffold --root "$work/sdd" --provider fable-game --param productName=Rogue-FableGame --param rootNamespace=RogueFableGame --no-update --json >"$work/scaffold.json"
jq -e '.outcome == "succeeded" and .scaffold.providerName == "fable-game" and .scaffold.providerInvoked == true' "$work/scaffold.json" >/dev/null
test -f "$work/sdd/.fsgg/scaffold-provenance.json"
test -f "$work/sdd/Rogue-FableGame.slnx"
test -f "$work/sdd/Server/Server.fsproj"
test -f "$work/sdd/Server.Tests/Server.Tests.fsproj"
grep -q '^namespace RogueFableGame.Server$' "$work/sdd/Server/Program.fs"
fsgg-sdd doctor --root "$work/sdd" --json >"$work/doctor.json"
jq -e '.outcome == "noChange" and (.diagnostics | length) == 0' "$work/doctor.json" >/dev/null
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
