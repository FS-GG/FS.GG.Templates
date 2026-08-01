#!/usr/bin/env bash
# Template-owned structural proof. Runtime calls require the consumer's selected npm package.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export DOTNET_CLI_HOME="$WORK/home" DOTNET_NOLOGO=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
mkdir -p "$DOTNET_CLI_HOME"

dotnet pack "$ROOT/FS.GG.Templates.csproj" -c Release -o "$WORK/feed" >/dev/null
dotnet new install "$WORK/feed"/*.nupkg >/dev/null
dotnet new fs-gg-fable-bindings -o "$WORK/product" --name AcmeBindings --productName AcmeBindings --rootNamespace AcmeBindings --npmPackage=@scope/library --npmVersion 1.2.3 --bindingTarget browser >/dev/null

for f in declaration-lock.json coverage-and-drift.json package.json src/AcmeBindings/AcmeBindings.fsproj tests/AcmeBindings.CompileTests/AcmeBindings.CompileTests.fsproj samples/Consumer/README.md; do test -f "$WORK/product/$f"; done
grep -Fq '"@scope/library": "1.2.3"' "$WORK/product/package.json"
grep -Fq '"package": "@scope/library"' "$WORK/product/declaration-lock.json"
grep -Fq '"version": "1.2.3"' "$WORK/product/declaration-lock.json"
grep -Fq 'module AcmeBindings.Bindings' "$WORK/product/src/AcmeBindings/Bindings.fs"
grep -Fq 'Generated output is a review proposal' "$WORK/product/scripts/generate-candidate.mjs"
grep -Fq 'review-required' "$WORK/product/coverage-and-drift.json"
echo 'PASS fable-bindings template materializes exact input and guarded maintenance artifacts'
