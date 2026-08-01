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

# Keep the qualification result honest: this report must not become an implicit
# template baseline before the browser route has been run against a coherent set.
require "**Status:** not qualified for template baseline"
require 'Fable.Remoting.Client` 8.0.0 nuspec depends on `Fable.Core` 3.1.5'
require 'Fable.Core 5.2.0'
require 'The 2021 `Fable.SignalR` NuGet package remains research input only.'
require "Elmish plus direct DOM bindings"
require "do not assume arbitrary DUs are wire-compatible"
require "SignalR server-push and reconnect/resync"
require "Production publish and bundle size"

echo "PASS fable full-stack spike remains fail-closed until its browser route is qualified"
