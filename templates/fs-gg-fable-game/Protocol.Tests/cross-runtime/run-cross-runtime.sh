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
MODEL_TRACE="$WORKSPACE_ROOT/Conformance/arena-rules.trace"
TACTICAL_TRACE="$WORKSPACE_ROOT/Conformance/tactical-rules.trace"

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

# The cooperative arena's complete V2 state, including content geometry and round
# identity, receives the same bidirectional proof without weakening frozen V1.
for case_name in input sessionHello snapshot presence resyncRequest resyncSnapshot; do
  expect_ok "realtime-v2[$case_name]: net encode" net encode-realtime-v2 "$case_name" "$TMP/rt2-net-$case_name.json"
  expect_ok "realtime-v2[$case_name]: fable decodes net's encoding" fbl decode-realtime-v2 "$case_name" "$TMP/rt2-net-$case_name.json"
  expect_ok "realtime-v2[$case_name]: fable encode" fbl encode-realtime-v2 "$case_name" "$TMP/rt2-fable-$case_name.json"
  expect_ok "realtime-v2[$case_name]: net decodes fable's encoding" net decode-realtime-v2 "$case_name" "$TMP/rt2-fable-$case_name.json"
done

# V3 carries the authored immutable boundary and spawn in addition to all V2
# gameplay fields. Exercise every union case in both runtime directions.
for case_name in input sessionHello snapshot presence resyncRequest resyncSnapshot; do
  expect_ok "realtime-v3[$case_name]: net encode" net encode-realtime-v3 "$case_name" "$TMP/rt3-net-$case_name.json"
  expect_ok "realtime-v3[$case_name]: fable decodes net's encoding" fbl decode-realtime-v3 "$case_name" "$TMP/rt3-net-$case_name.json"
  expect_ok "realtime-v3[$case_name]: fable encode" fbl encode-realtime-v3 "$case_name" "$TMP/rt3-fable-$case_name.json"
  expect_ok "realtime-v3[$case_name]: net decodes fable's encoding" net decode-realtime-v3 "$case_name" "$TMP/rt3-fable-$case_name.json"
done

# The explicit rejected-arbitrary-DU-case proof, independently on both runtimes.
expect_ok "rejected cases: net rejects both malformed cases" net decode-rejected-cases
expect_ok "rejected cases: fable rejects both malformed cases" fbl decode-rejected-cases

expect_ok "arena rules/session/replay: net complete sequence" net write-arena-proof "$TMP/arena-net.txt"
expect_ok "arena rules/session/replay: net complete sequence under de-DE" net write-arena-proof-de "$TMP/arena-net-de.txt"
expect_ok "arena rules/session/replay: fable complete sequence" fbl write-arena-proof "$TMP/arena-fable.txt"
expect_ok "gameplay metadata identity: net fractional semantics" net write-gameplay-identity-proof "$TMP/identity-net.txt"
expect_ok "gameplay metadata identity: net de-DE fractional semantics" net write-gameplay-identity-proof-de "$TMP/identity-net-de.txt"
expect_ok "gameplay metadata identity: fable fractional semantics" fbl write-gameplay-identity-proof "$TMP/identity-fable.txt"
expect_ok "arena model correspondence: net reducer" net write-arena-model-correspondence "$MODEL_TRACE" "$TMP/model-net.txt"
expect_ok "arena model correspondence: fable reducer" fbl write-arena-model-correspondence "$MODEL_TRACE" "$TMP/model-fable.txt"
expect_ok "arcade arena-model correspondence/content refusal: net reducer" net write-arcade-proof "$MODEL_TRACE" "$TMP/arcade-net.txt"
expect_ok "arcade arena-model correspondence/content refusal: fable reducer" fbl write-arcade-proof "$MODEL_TRACE" "$TMP/arcade-fable.txt"
expect_ok "tactical model/rules: net reducer" net write-tactical-proof "$TACTICAL_TRACE" "$TMP/tactical-net.txt"
expect_ok "tactical model/rules: fable reducer" fbl write-tactical-proof "$TACTICAL_TRACE" "$TMP/tactical-fable.txt"
cmp "$TMP/arena-net.txt" "$TMP/arena-net-de.txt" || {
  echo "cross-runtime: FAILED - ArenaRules replay bytes depend on .NET culture" >&2
  diff -u "$TMP/arena-net.txt" "$TMP/arena-net-de.txt" >&2 || true
  exit 1
}
cmp "$TMP/arena-net.txt" "$TMP/arena-fable.txt" || {
  echo "cross-runtime: FAILED - ArenaRules/SessionContract replay bytes differ between .NET and Fable" >&2
  diff -u "$TMP/arena-net.txt" "$TMP/arena-fable.txt" >&2 || true
  exit 1
}
cmp "$TMP/identity-net.txt" "$TMP/identity-net-de.txt" || {
  echo "cross-runtime: FAILED - gameplay metadata identity depends on .NET culture" >&2
  exit 1
}
cmp "$TMP/identity-net.txt" "$TMP/identity-fable.txt" || {
  echo "cross-runtime: FAILED - gameplay metadata identity differs between .NET and Fable" >&2
  exit 1
}
cmp "$TMP/model-net.txt" "$TMP/model-fable.txt" || {
  echo "cross-runtime: FAILED - arena model/reducer correspondence differs between .NET and Fable" >&2
  exit 1
}
cmp "$TMP/arcade-net.txt" "$TMP/arcade-fable.txt" || {
  echo "cross-runtime: FAILED - arcade arena-model/reducer correspondence differs between .NET and Fable" >&2
  diff -u "$TMP/arcade-net.txt" "$TMP/arcade-fable.txt" >&2 || true
  exit 1
}
cmp "$TMP/tactical-net.txt" "$TMP/tactical-fable.txt" || {
  echo "cross-runtime: FAILED - tactical model/reducer differs between .NET and Fable" >&2
  diff -u "$TMP/tactical-net.txt" "$TMP/tactical-fable.txt" >&2 || true
  exit 1
}

# Compile isolated copies of the real reducer with three controlled rule faults.
# The model-derived trace must reject each implementation with a first-divergence
# diagnostic, so an unrelated build/crash cannot satisfy this negative control.
MUTATED_ROOT="$TMP/mutated-workspace"
MUTATION_EVIDENCE_DIR="${MODEL_MUTATION_EVIDENCE_DIR:-$TMP/mutation-evidence}"
mkdir -p "$MUTATION_EVIDENCE_DIR"
mkdir -p "$MUTATED_ROOT/Protocol.Tests/cross-runtime/CodecProbe.Net" "$MUTATED_ROOT/Conformance"
cp "$WORKSPACE_ROOT/Directory.Build.props" "$WORKSPACE_ROOT/NuGet.config" "$WORKSPACE_ROOT/global.json" "$MUTATED_ROOT/"
cp -a "$WORKSPACE_ROOT/.nuget" "$WORKSPACE_ROOT/Domain" "$WORKSPACE_ROOT/Protocol" "$MUTATED_ROOT/"
cp "$SCRIPT_DIR/Program.fs" "$MUTATED_ROOT/Protocol.Tests/cross-runtime/Program.fs"
cp "$NET_PROJECT" "$MUTATED_ROOT/Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj"
cp "$SCRIPT_DIR/CodecProbe.Net/packages.lock.json" "$MUTATED_ROOT/Protocol.Tests/cross-runtime/CodecProbe.Net/packages.lock.json"
cp "$WORKSPACE_ROOT/Conformance/SceneSchema.fs" "$MUTATED_ROOT/Conformance/SceneSchema.fs"

run_mutant() {
  local label="$1"
  cp "$WORKSPACE_ROOT/Domain/ArenaContent.fs" "$MUTATED_ROOT/Domain/ArenaContent.fs"
  cp "$WORKSPACE_ROOT/Domain/ArenaRules.fs" "$MUTATED_ROOT/Domain/ArenaRules.fs"
  case "$label" in
    faulty-mapping)
      sed -i 's/status\.Score + 100/status.Score + 99/' "$MUTATED_ROOT/Domain/ArenaContent.fs"
      grep -F 'status.Score + 99' "$MUTATED_ROOT/Domain/ArenaContent.fs" >/dev/null
      ;;
    wrong-precedence)
      python3 - "$MUTATED_ROOT/Domain/ArenaContent.fs" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
old = '''    elif not status.Collected && overlaps player collectible then
        { status with Collected = true; Score = status.Score + 100 }
    elif status.Collected && overlaps player content.Goal then { status with Outcome = "won" }
'''
new = '''    elif overlaps player content.Goal then { status with Outcome = "won" }
    elif not status.Collected && overlaps player collectible then
        { status with Collected = true; Score = status.Score + 100 }
'''
if text.count(old) != 1:
    raise SystemExit("wrong-precedence mutation target not found exactly once")
path.write_text(text.replace(old, new))
PY
      ;;
    stale-contact)
      sed -i 's/let entered = Set\.difference contacts state\.HazardContacts/let entered = contacts/' "$MUTATED_ROOT/Domain/ArenaRules.fs"
      grep -F 'let entered = contacts' "$MUTATED_ROOT/Domain/ArenaRules.fs" >/dev/null
      ;;
    stale-state-acceptance)
      sed -i 's/elif saved\.Value\.Definition\.SchemaVersion <> expectedDefinition\.SchemaVersion || saved\.Value\.Definition\.ContentId <> expectedDefinition\.ContentId then/elif false then/' "$MUTATED_ROOT/Domain/ArenaRules.fs"
      grep -F 'elif false then Error { Code = "arena.snapshot.content"' "$MUTATED_ROOT/Domain/ArenaRules.fs" >/dev/null
      ;;
  esac
  dotnet build "$MUTATED_ROOT/Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj" \
    -t:Rebuild -c Release -o "$TMP/mutated-net-$label" >"$MUTATION_EVIDENCE_DIR/$label-build.log" 2>&1
  set +e
  dotnet "$TMP/mutated-net-$label/CodecProbe.Net.dll" check-arena-model-correspondence "$MODEL_TRACE" \
    >"$MUTATION_EVIDENCE_DIR/$label-run.log" 2>&1
  local status=$?
  set -e
  local expected_failure='Quint/reducer first divergence at state'
  [[ $label == stale-state-acceptance ]] && expected_failure='stale authored state accepted'
  if [[ $status -eq 0 ]] || ! grep -F "$expected_failure" "$MUTATION_EVIDENCE_DIR/$label-run.log" >/dev/null; then
    echo "cross-runtime: FAILED - $label control lacked the expected correspondence divergence" >&2
    cat "$MUTATION_EVIDENCE_DIR/$label-run.log" >&2
    exit 1
  fi
  echo "cross-runtime: OK - model trace rejects isolated $label mutant"
}

run_mutant faulty-mapping
run_mutant wrong-precedence
run_mutant stale-contact
run_mutant stale-state-acceptance
echo "cross-runtime: OK - ArenaRules movement/contact/Interact/win/Restart and complete replay bytes match"
echo "cross-runtime: OK - gameplay metadata identity preserves fractional semantics across .NET/Fable"
echo "cross-runtime: OK - executed Quint trace matches both reducers"
echo "cross-runtime: OK - executed arena-model trace matches Arcade reducers and foreign content/session refusals in both runtimes"
echo "cross-runtime: OK - tactical Quint trace matches both portable reducers"

echo "cross-runtime: OK - DTO codecs and complete ArenaRules session/replay agree across .NET and Fable"
