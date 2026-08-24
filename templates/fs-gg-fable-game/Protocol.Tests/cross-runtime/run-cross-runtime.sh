#!/usr/bin/env bash
#
# ADR-0073's "not optional" acceptance criterion, made executable: every request/
# response DTO is tested by encoding from .NET and decoding in the browser runtime
# (and the reverse), including a case expected to be rejected. This script builds
# `CodecProbe.Net.fsproj` (Thoth.Json.Net) and `CodecProbe.Fable.fsproj` (Thoth.Json,
# via `dotnet fable`, run under Node) from the *same* `Protocol/Http.fs` /
# `Protocol/Realtime.fs` source `Client.fsproj` and `Server.fsproj` use, and drives
# every DTO pair through both directions plus the two deliberately-malformed cases.
#
# "In the browser" here means the browser-target Fable compile, executed under Node
# rather than a headless browser -- Browser.Tests/two-client.spec.ts separately proves
# the same compiled JS runs correctly inside a real Chromium page. This script's job
# is the wire-format proof, not a second browser-startup proof.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NET_PROJECT="$SCRIPT_DIR/CodecProbe.Net/CodecProbe.Net.fsproj"
FABLE_PROJECT="$SCRIPT_DIR/CodecProbe.Fable/CodecProbe.Fable.fsproj"
FABLE_ENTRY="$SCRIPT_DIR/CodecProbe.Fable/Program.js"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "cross-runtime: building .NET codec probe"
dotnet build "$NET_PROJECT" -c Release -o "$TMP/net" >/dev/null
NET_DLL="$TMP/net/CodecProbe.Net.dll"

# `fable` is a LOCAL dotnet tool — `.config/dotnet-tools.json` pins it (FS.GG.Templates#392).
# A local tool is never reachable as a bare `fable`, on any machine, restored or not; it is
# reached as `dotnet fable`. And nothing has materialized the manifest by this point: `build.sh`
# runs this probe BEFORE `Client`'s npm build, and that npm `build` script was the template's only
# `dotnet tool restore`. So the restore belongs here, next to the use, which also lets this script
# stand alone rather than depending on a caller having built the client first.
#
# Both commands resolve the manifest by searching upward from the CURRENT directory, so anchor
# them at the workspace root instead of inheriting whatever directory the caller happened to be in.
echo "cross-runtime: building Fable codec probe (dotnet fable)"
rm -rf "$SCRIPT_DIR/CodecProbe.Fable/output" "$FABLE_ENTRY" "$SCRIPT_DIR/CodecProbe.Fable/Protocol"
(cd "$WORKSPACE_ROOT" && dotnet tool restore) >/dev/null
(cd "$WORKSPACE_ROOT" && dotnet fable "$FABLE_PROJECT" --outDir "$SCRIPT_DIR/CodecProbe.Fable/output" --noCache) >/dev/null
[[ -f $FABLE_ENTRY ]] || {
  echo "cross-runtime: expected Fable output was not produced: $FABLE_ENTRY" >&2
  exit 1
}

net() { dotnet "$NET_DLL" "$@"; }
fbl() { node "$FABLE_ENTRY" "$@"; }

expect_ok() {
  local label="$1"
  shift
  local output
  if ! output="$("$@" 2>&1)"; then
    echo "cross-runtime: FAILED ($label): $*" >&2
    echo "$output" >&2
    exit 1
  fi
  [[ $output == OK* || $output == WROTE* || $output == ALL-REJECTED-AS-EXPECTED* ]] || {
    echo "cross-runtime: unexpected output for $label: $output" >&2
    exit 1
  }
  echo "cross-runtime: OK - $label"
}

# .NET encodes, Fable (Node) decodes -- and the reverse -- for both HTTP DTOs.
expect_ok "bootstrap-request: net encode" net encode-bootstrap-request "$TMP/req-net.json"
expect_ok "bootstrap-request: fable decodes net's encoding" fbl decode-bootstrap-request "$TMP/req-net.json"
expect_ok "bootstrap-request: fable encode" fbl encode-bootstrap-request "$TMP/req-fable.json"
expect_ok "bootstrap-request: net decodes fable's encoding" net decode-bootstrap-request "$TMP/req-fable.json"

expect_ok "bootstrap-response: net encode" net encode-bootstrap-response "$TMP/res-net.json"
expect_ok "bootstrap-response: fable decodes net's encoding" fbl decode-bootstrap-response "$TMP/res-net.json"
expect_ok "bootstrap-response: fable encode" fbl encode-bootstrap-response "$TMP/res-fable.json"
expect_ok "bootstrap-response: net decodes fable's encoding" net decode-bootstrap-response "$TMP/res-fable.json"

# Every RealtimeV1.Message case, both directions -- this is the "arbitrary DU" boundary.
for case_name in input sessionHello snapshot presence resyncRequest resyncSnapshot; do
  expect_ok "realtime[$case_name]: net encode" net encode-realtime "$case_name" "$TMP/rt-net-$case_name.json"
  expect_ok "realtime[$case_name]: fable decodes net's encoding" fbl decode-realtime "$case_name" "$TMP/rt-net-$case_name.json"
  expect_ok "realtime[$case_name]: fable encode" fbl encode-realtime "$case_name" "$TMP/rt-fable-$case_name.json"
  expect_ok "realtime[$case_name]: net decodes fable's encoding" net decode-realtime "$case_name" "$TMP/rt-fable-$case_name.json"
done

# The explicit rejected-arbitrary-DU-case proof, independently on both runtimes.
expect_ok "rejected cases: net rejects both malformed cases" net decode-rejected-cases
expect_ok "rejected cases: fable rejects both malformed cases" fbl decode-rejected-cases

echo "cross-runtime: OK - every DTO round-tripped net<->fable in both directions, including the rejected-case proof on both runtimes"
