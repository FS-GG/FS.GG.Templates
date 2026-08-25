#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export DOTNET_CLI_HOME="$WORK/dotnet-home"
mkdir -p "$DOTNET_CLI_HOME"

LANE_REPO_ROOT="$ROOT"
# shellcheck source=tests/composition/lib/lane-package.sh
. "$ROOT/tests/composition/lib/lane-package.sh"
# shellcheck source=tests/composition/lib/lifecycle-matrix.sh
. "$ROOT/tests/composition/lib/lifecycle-matrix.sh"
# The release gate sets FSGG_TEMPLATES_NUPKG to the downloaded, checksum-verified artifact, so this
# lane proves the console identity against the bytes that are about to be published rather than
# against a second archive packed here (FS.GG.Templates#349).
PACKAGE="$(lane_package_path "$WORK")"
echo "console composition: installing $PACKAGE"
dotnet new install "$PACKAGE" >/dev/null
assert_provider_lifecycle_matrix console "$PACKAGE" "$WORK/lifecycle-matrix" productName=MatrixConsole rootNamespace=MatrixConsole
assert_typed_lifecycle_controls "$WORK/lifecycle-matrix/typed-sdd" "$WORK/lifecycle-controls"
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
lane_pin_provider_to_archive "$WORK/sdd/.fsgg/providers.yml" "$PACKAGE"
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
