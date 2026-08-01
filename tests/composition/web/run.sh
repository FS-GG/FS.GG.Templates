#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fs-gg-web-composition.XXXXXX")"
trap 'rm -rf "$work"' EXIT
export DOTNET_CLI_HOME="$work/dotnet-home"
dotnet pack "$root/FS.GG.Templates.csproj" -o "$work/packages"
dotnet new install "$work/packages"/*.nupkg --force
dotnet new fs-gg-web -n CleanWeb -o "$work/scaffold"
test -f "$work/scaffold/Server/CleanWeb.Server.fsproj"
test -f "$work/scaffold/Web/package.json"
test -f "$work/scaffold/Browser.Tests/home.spec.ts"
dotnet build "$work/scaffold/CleanWeb.slnx"
test -f "$work/scaffold/Web/package-lock.json"
test -f "$work/scaffold/Browser.Tests/package-lock.json"
(
  cd "$work/scaffold"
  bash ./build.sh
  test -s artifacts/test-results/server.trx
  test -s artifacts/test-results/browser.junit.xml
)
echo "web composition: generated clean scaffold lanes"
