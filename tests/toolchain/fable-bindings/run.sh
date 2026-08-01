#!/usr/bin/env bash
# Reproducible qualification gate for declaration-to-curated-Fable workflow.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPIKE="$ROOT/spikes/fable-bindings"
DOC="$ROOT/docs/fable-bindings-toolchain.md"

test "$(dotnet --version)" = "10.0.302"
test "$(node --version)" = "v26.5.0"
test "$(npm --version)" = "12.0.1"
test -f "$SPIKE/package-lock.json"
test -f "$SPIKE/declaration-lock.json"
grep -Fq '"@babylonjs/core": "9.19.0"' "$SPIKE/package.json"
grep -Fq 'sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==' "$SPIKE/package-lock.json"
grep -Fq 'Glutinum.Template@1.1.1' "$DOC"
grep -Fq 'ts2fable is legacy comparison input only' "$DOC"
grep -Fq 'can never overwrite' "$DOC"
grep -Fq 'advance the declaration lock' "$DOC"

(cd "$SPIKE" && npm ci --ignore-scripts >/dev/null && npm run check:drift && npm run test:runtime)

# Fable compilation is the emitted-import proof; Node executes that exact output.
(cd "$SPIKE" && dotnet tool restore >/dev/null && dotnet fable runtime/RuntimeSmoke.fsproj --outDir runtime/dist --noCache >/dev/null && node runtime/dist/Program.js)

candidate="$SPIKE/generated-candidates/BabylonBindings.generated.fs"
before="$(sha256sum "$SPIKE/src/BabylonBindings.fs" "$SPIKE/declaration-lock.json")"
(cd "$SPIKE" && npm run generate:candidate >/dev/null)
after="$(sha256sum "$SPIKE/src/BabylonBindings.fs" "$SPIKE/declaration-lock.json")"
test "$before" = "$after"
test -f "$candidate"

echo "PASS fable bindings declaration lock, runtime smoke, and candidate non-overwrite gate"
