#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-web-composition.XXXXXX")"
trap 'rm -rf "$work"' EXIT
export DOTNET_CLI_HOME="$work/dotnet-home"
for browser in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$browser" >/dev/null 2>&1; then
    export PLAYWRIGHT_EXECUTABLE_PATH="$(command -v "$browser")"
    echo "web composition: selected system browser $PLAYWRIGHT_EXECUTABLE_PATH"
    break
  fi
done
dotnet pack "$root/FS.GG.Templates.csproj" -o "$work/packages"
dotnet new install "$work/packages"/*.nupkg --force
dotnet new fs-gg-web -n CleanWeb -o "$work/scaffold"
test -f "$work/scaffold/Server/CleanWeb.Server.fsproj"
test -f "$work/scaffold/Web/package.json"
test -f "$work/scaffold/Web.Tests/message.test.ts"
test -f "$work/scaffold/Browser.Tests/home.spec.ts"
dotnet build "$work/scaffold/CleanWeb.slnx"
test -f "$work/scaffold/Web/package-lock.json"
test -f "$work/scaffold/Browser.Tests/package-lock.json"
(
  cd "$work/scaffold"
  bash ./build.sh
  test -f artifacts/publish/wwwroot/index.html
  grep -q 'id="message"' artifacts/publish/wwwroot/index.html
  test -s artifacts/test-results/server.trx
  test -s artifacts/test-results/browser.junit.xml
)

# Prove the declared provider contract through SDD with distinct raw and identifier
# names. This is the integration surface consumed by generated products, not an
# alias for direct `dotnet new` instantiation.
mkdir -p "$work/sdd/.fsgg"
cp "$root/providers/web.providers.yml" "$work/sdd/.fsgg/providers.yml"
sed -i "s#FS.GG.Workspace.Template::0.8.0#$work/packages/FS.GG.Workspace.Template.0.8.0.nupkg#" "$work/sdd/.fsgg/providers.yml"
fsgg-sdd scaffold --root "$work/sdd" --provider web --param productName=Rogue-Web --param rootNamespace=RogueWeb --no-update --json >"$work/scaffold.json"
jq -e '.outcome == "succeeded" and .scaffold.providerName == "web" and .scaffold.providerInvoked == true' "$work/scaffold.json" >/dev/null
test -f "$work/sdd/.fsgg/scaffold-provenance.json"
test -f "$work/sdd/Rogue-Web.slnx"
test -f "$work/sdd/Server/Rogue-Web.Server.fsproj"
test -f "$work/sdd/Server.Tests/Rogue-Web.Server.Tests.fsproj"
test -f "$work/sdd/Web.Tests/message.test.ts"
grep -q '^namespace RogueWeb.Server$' "$work/sdd/Server/Program.fs"
fsgg-sdd doctor --root "$work/sdd" --json >"$work/doctor.json"
jq -e '.outcome == "noChange" and (.diagnostics | length) == 0' "$work/doctor.json" >/dev/null
(
  cd "$work/sdd"
  bash ./build.sh
  test -f artifacts/publish/wwwroot/index.html
  grep -q 'id="message"' artifacts/publish/wwwroot/index.html
  test -s artifacts/test-results/server.trx
  test -s artifacts/test-results/browser.junit.xml
)
echo "web composition: generated clean scaffold production lifecycle"
