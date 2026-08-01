#!/usr/bin/env bash
# Guards the fail-closed outcome of the Fable full-stack qualification spike.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/docs/reports/2026-08-01-fable-full-stack-toolchain-compatibility-spike.md"

test -f "$REPORT"

require() {
  grep -Fq -- "$1" "$REPORT" || {
    echo "missing required spike evidence: $1" >&2
    exit 1
  }
}

# Keep the qualification result honest: compile evidence must not become an
# implicit template baseline before the browser route has been run.
require "**Status:** not qualified for template baseline"
require 'inclusive NuGet minimum, not an exact pin'
require 'Fable.Core'
require '5.2.0'
require 'Fable 5.13.0 dotnet tool'
require 'compiled that'
require 'The 2021 `Fable.SignalR` NuGet package remains research input only.'
require "Elmish plus direct DOM bindings"
require "do not assume arbitrary DUs are wire-compatible"
require "SignalR server-push and reconnect/resync"
require "Production publish and bundle size"

echo "PASS fable full-stack spike remains fail-closed until its browser route is qualified"
