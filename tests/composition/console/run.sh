#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export DOTNET_CLI_HOME="$WORK/dotnet-home"
mkdir -p "$DOTNET_CLI_HOME"

dotnet pack "$ROOT/FS.GG.Templates.csproj" -o "$WORK/feed" >/dev/null
dotnet new install "$WORK/feed/FS.GG.Workspace.Template.0.8.0.nupkg" >/dev/null
dotnet new fs-gg-console -o "$WORK/clean" --productName SignalConsole --rootNamespace SignalConsole >/dev/null

test -f "$WORK/clean/global.json"
test -f "$WORK/clean/SignalConsole.slnx"
test -f "$WORK/clean/src/SignalConsole/Program.fs"
test -f "$WORK/clean/tests/SignalConsole.Tests/ProgramTests.fs"
test ! -e "$WORK/clean/.fsgg"

(
  cd "$WORK/clean"
  dotnet restore SignalConsole.slnx --locked-mode
  dotnet fsi build.fsx build
  dotnet fsi build.fsx test

  stdout="$(dotnet run --project src/SignalConsole --no-build -- hello console)"
  test "$stdout" = "hello console"
  if dotnet run --project src/SignalConsole --no-build -- --fail >"$WORK/fail.out" 2>"$WORK/fail.err"; then
    echo "--fail unexpectedly succeeded" >&2
    exit 1
  fi
  if timeout --preserve-status -s INT 2 dotnet run --project src/SignalConsole --no-build -- --wait >"$WORK/wait.out" 2>"$WORK/wait.err"; then
    echo "--wait unexpectedly completed without cancellation" >&2
    exit 1
  fi
)
if [ ! -s "$WORK/fail.err" ]; then
  echo "--fail unexpectedly succeeded" >&2
  exit 1
fi
grep -Fxq "requested failure" "$WORK/fail.err"
grep -Fxq "cancelled" "$WORK/wait.err"

# The direct template deliberately owns no `.fsgg` files. Exercise the provider
# composition separately: SDD must retain ownership of its single lifecycle and
# provenance while the local packed artifact supplies the console product.
mkdir -p "$WORK/sdd/.fsgg"
cp "$ROOT/providers/console.providers.yml" "$WORK/sdd/.fsgg/providers.yml"
sed -i "s#FS.GG.Workspace.Template::0.8.0#$WORK/feed/FS.GG.Workspace.Template.0.8.0.nupkg#" "$WORK/sdd/.fsgg/providers.yml"
fsgg-sdd scaffold --root "$WORK/sdd" --provider console --param productName=SignalConsole --param rootNamespace=SignalConsole --no-update --json >"$WORK/scaffold.json"
jq -e '.outcome == "succeeded" and .scaffold.providerName == "console" and .scaffold.providerInvoked == true' "$WORK/scaffold.json" >/dev/null
test -f "$WORK/sdd/.fsgg/scaffold-provenance.json"
fsgg-sdd doctor --root "$WORK/sdd" --json >"$WORK/doctor.json"
jq -e '.outcome == "noChange" and (.diagnostics | length) == 0' "$WORK/doctor.json" >/dev/null
(
  cd "$WORK/sdd"
  dotnet restore SignalConsole.slnx --locked-mode
  dotnet fsi build.fsx build
  dotnet fsi build.fsx test
  test "$(dotnet run --project src/SignalConsole --no-build -- from-sdd)" = "from-sdd"
  if dotnet run --project src/SignalConsole --no-build -- --fail >"$WORK/sdd-fail.out" 2>"$WORK/sdd-fail.err"; then
    echo "SDD-composed --fail unexpectedly succeeded" >&2
    exit 1
  fi
  if timeout --preserve-status -s INT 2 dotnet run --project src/SignalConsole --no-build -- --wait >"$WORK/sdd-wait.out" 2>"$WORK/sdd-wait.err"; then
    echo "SDD-composed --wait unexpectedly completed without cancellation" >&2
    exit 1
  fi
)
grep -Fxq "requested failure" "$WORK/sdd-fail.err"
grep -Fxq "cancelled" "$WORK/sdd-wait.err"

echo "PASS console template packs, instantiates, restores, builds, tests, observes process seams, and composes one SDD lifecycle"
