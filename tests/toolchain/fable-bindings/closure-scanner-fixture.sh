#!/usr/bin/env bash
# Closure-scanner fixture for scripts/lock-declarations.mjs (FS.GG.Templates#809).
# Usage: closure-scanner-fixture.sh <path-to-lock-declarations.mjs>
#
# The scanner follows the declaration edges TypeScript's pre-processor reports. The fixture
# reproduces the shapes the regex tracer could not lock in pixi.js@8 and pins each outcome:
#   - `/// <reference path>` mixins and `/// <reference types>` inside the artifact are followed;
#   - an extensionless folder import resolves to `dir/index.d.ts`;
#   - a bare import into the entry's own package is followed;
#   - an `import()` example inside a JSDoc comment is not an edge;
#   - a shader import (.frag) with no declaration is recorded as a non-declaration asset;
#   - bare modules outside the pinned artifacts (types and imports) are recorded, not followed;
#   - a genuinely missing declaration still fails the lock.
set -euo pipefail
lock_script="$1"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
lib="$fixture/node_modules/example/lib"
mkdir -p "$lib/gl" "$lib/types"
cat > "$lib/index.d.ts" <<'TS'
/// <reference path="./mixins.d.ts" />
/// <reference types="example/lib/types/globals" />
/// <reference types="@webgpu/types" />
import type { Gl } from "./gl";
import type { Other } from "example/lib/other.js";
import type { EventEmitter } from "eventemitter3";
import fragment from "./shader.frag";
/**
 * @example
 * const renderer = { load: () => import('./missing/init') };
 */
export declare const value: Gl | Other | EventEmitter | typeof fragment;
TS
printf '%s\n' 'declare global { interface ExampleMixin { mixed: true } }' 'export {};' > "$lib/mixins.d.ts"
printf '%s\n' 'declare interface ExampleGlobal { global: true }' > "$lib/types/globals.d.ts"
printf '%s\n' 'export interface Gl { gl: true }' > "$lib/gl/index.d.ts"
printf '%s\n' 'export interface Other { other: true }' > "$lib/other.d.ts"

node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" --write >/dev/null
jq -e '
  [.files[].path] == ["example/lib/gl/index.d.ts", "example/lib/index.d.ts", "example/lib/mixins.d.ts", "example/lib/other.d.ts", "example/lib/types/globals.d.ts"]
  and .nonDeclarationAssets == ["example/lib/shader.frag"]
  and .externalModules == ["@webgpu/types", "eventemitter3"]
  and all(.files[]; .sha256 | test("^[0-9a-f]{64}$"))
' "$fixture/lock.json" >/dev/null || { echo "closure scanner fixture produced an unexpected lock:" >&2; cat "$fixture/lock.json" >&2; exit 1; }
node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" >/dev/null

# A changed mixin reached only through `/// <reference path>` is drift.
printf '%s\n' 'declare global { interface ExampleMixin { mixed: false } }' 'export {};' > "$lib/mixins.d.ts"
if node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" >/dev/null 2>&1; then
  echo "drift in a /// <reference path> declaration unexpectedly passed" >&2; exit 1
fi
# A real (uncommented) import of a missing declaration is not an asset and must fail.
printf '%s\n' 'export * from "./absent.js";' > "$lib/broken.d.ts"
if node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/broken.d.ts --lock "$fixture/broken.json" --write >/dev/null 2>&1; then
  echo "an unresolved declaration import unexpectedly locked" >&2; exit 1
fi
echo "PASS closure scanner fixture"
