#!/usr/bin/env bash
# Runs the compiler portion of the Fable full-stack qualification spike and
# guards the still-unqualified browser-transport decision. It also guards a
# second, independently-discovered fact (FS.GG.Templates#370): the compile
# failure is an upstream Fable.Remoting.MsgPack defect (not a pin-selection
# problem), and a Fable-compiler-downgrade workaround compiles where the
# currently declared pin does not. Neither fact makes this guard pass green —
# it still asserts the toolchain is not qualified for template baseline.
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

# The currently declared pin (Fable 5.13.0) must still fail to compile this
# candidate. If it ever starts compiling, the report's "not qualified" status
# and this guard are both stale and must be revisited together.
dotnet tool install Fable --tool-path "$WORK/fable" --version 5.13.0 >/dev/null
if "$WORK/fable/fable" "$WORK/client" --outDir "$WORK/out" --noCache >"$WORK/fable.log" 2>&1; then
  echo "unexpectedly compiled the unqualified Fable.Remoting candidate" >&2
  exit 1
fi
grep -Fq 'Fable.Remoting.MsgPack.2.0.0/Write.fs' "$WORK/fable.log"
grep -Fq "write64bitNumber' was marked inline" "$WORK/fable.log"

# The #370 requalification found that Fable 5.4.0 (the last version before
# fable-compiler/Fable#4701's stricter inline-accessibility check) compiles
# the SAME candidate. This is a workaround for an upstream defect, not an
# adopted pin — guard it so the finding stays reproducible and doesn't
# silently bit-rot into an unverified claim in the report.
dotnet tool install Fable --tool-path "$WORK/fable-5.4.0" --version 5.4.0 >/dev/null
if ! "$WORK/fable-5.4.0/fable" "$WORK/client" --outDir "$WORK/out-5.4.0" --noCache >"$WORK/fable-5.4.0.log" 2>&1; then
  echo "the #370 workaround finding no longer reproduces: Fable 5.4.0 now fails to compile the candidate it previously compiled" >&2
  cat "$WORK/fable-5.4.0.log" >&2
  exit 1
fi

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

# #370 requalification evidence: root cause, upstream tracking, and the
# bounded runtime validation of the workaround must stay documented.
require "Zaid-Ajaj/Fable.Remoting#396"
require "fable-compiler/Fable#4701"
require "Downgrading the Fable compiler to 5.4.0 is"
require "enough to work around this issue until a proper fix can be implemented."
require "PING_RESULT=6"
require "SIGNALR_RECONNECTED=1"
require "Three options exist and none of them is this"
require "report's to choose unilaterally"

echo "PASS fable full-stack spike remains fail-closed until its browser route is qualified (workaround pin characterized, not adopted; see #370)"
