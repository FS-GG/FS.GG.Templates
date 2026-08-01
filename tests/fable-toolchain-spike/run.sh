#!/usr/bin/env bash
# Runs the compiler portion of the Fable full-stack qualification spike and
# guards the still-unqualified browser-transport decision.
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

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
dotnet new classlib -lang F# -o "$WORK/client" --no-restore >/dev/null
dotnet add "$WORK/client" package Fable.Core --version 5.2.0 >/dev/null
dotnet add "$WORK/client" package Fable.Remoting.Client --version 8.0.0 >/dev/null
dotnet restore "$WORK/client" --force-evaluate >/dev/null
grep -Fq 'Fable.Core/5.2.0' "$WORK/client/obj/project.assets.json"
dotnet tool install Fable --tool-path "$WORK/fable" --version 5.13.0 >/dev/null
if "$WORK/fable/fable" "$WORK/client" --outDir "$WORK/out" --noCache >"$WORK/fable.log" 2>&1; then
  echo "unexpectedly compiled the unqualified Fable.Remoting candidate" >&2
  exit 1
fi
grep -Fq 'Fable.Remoting.MsgPack.2.0.0/Write.fs' "$WORK/fable.log"
grep -Fq "write64bitNumber' was marked inline" "$WORK/fable.log"

# Keep the qualification result honest: compile evidence must not become an
# implicit template baseline before the browser route has been run.
require "**Status:** not qualified for template baseline"
require 'inclusive NuGet minimum, not an exact pin'
require 'Fable.Core'
require '5.2.0'
require 'Fable.Remoting.MsgPack` 2.0.0 source'
require 'write64bitNumber'
require 'The 2021 `Fable.SignalR` NuGet package remains research input only.'
require "Elmish plus direct DOM bindings"
require "do not assume arbitrary DUs are wire-compatible"
require "SignalR server-push and reconnect/resync"
require "Production publish and bundle size"

echo "PASS fable full-stack spike remains fail-closed until its browser route is qualified"
