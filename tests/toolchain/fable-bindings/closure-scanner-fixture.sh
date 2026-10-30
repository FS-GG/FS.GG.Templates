#!/usr/bin/env bash
# Closure-scanner fixture for scripts/lock-declarations.mjs (FS.GG.Templates#809).
# Usage: closure-scanner-fixture.sh <path-to-lock-declarations.mjs>
#
# The scanner follows the module specifiers in the TypeScript syntax tree and the triple-slash
# references the pre-processor reports. The fixture
# reproduces the shapes the regex tracer could not lock in pixi.js@8 and pins each outcome:
#   - `/// <reference path>` mixins and `/// <reference types>` inside the artifact are followed;
#   - an extensionless folder import resolves to `dir/index.d.ts`;
#   - a bare import into the entry's own package is followed;
#   - an `import()` example inside a JSDoc comment is not an edge;
#   - a shader import (.frag) with no declaration is recorded as a non-declaration asset;
#   - bare modules outside the pinned artifacts (types and imports) are recorded, not followed;
#   - `export * as ns from` and `export type * as ns from` edges are followed (ts.preProcessFile
#     reports neither), so drift there is detected;
#   - a dotted module name that is not on the asset allowlist is an error, not a silent asset;
#   - a module reference in a form the scanner does not follow fails loudly instead of being omitted;
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
export * as starAs from "./star-as.js";
export type * as starAsType from "./star-as-type.js";
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
# Reachable only through `export * as` / `export type * as`.
printf '%s\n' 'export interface StarAs { starAs: true }' > "$lib/star-as.d.ts"
printf '%s\n' 'export interface StarAsType { starAsType: true }' > "$lib/star-as-type.d.ts"

node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" --write >/dev/null
jq -e '
  [.files[].path] == ["example/lib/gl/index.d.ts", "example/lib/index.d.ts", "example/lib/mixins.d.ts", "example/lib/other.d.ts", "example/lib/star-as-type.d.ts", "example/lib/star-as.d.ts", "example/lib/types/globals.d.ts"]
  and .nonDeclarationAssets == ["example/lib/shader.frag"]
  and .externalModules == ["@webgpu/types", "eventemitter3"]
  and all(.files[]; .sha256 | test("^[0-9a-f]{64}$"))
' "$fixture/lock.json" >/dev/null || { echo "closure scanner fixture produced an unexpected lock:" >&2; cat "$fixture/lock.json" >&2; exit 1; }
node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" >/dev/null

# Drift in a file reachable only through `export * as` is detected.
printf '%s\n' 'export interface StarAs { starAs: false }' > "$lib/star-as.d.ts"
if node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/index.d.ts --lock "$fixture/lock.json" >/dev/null 2>&1; then
  echo "drift in an export * as declaration unexpectedly passed" >&2; exit 1
fi
printf '%s\n' 'export interface StarAs { starAs: true }' > "$lib/star-as.d.ts"
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
# A dotted module name that is not an allowlisted asset extension must not pass as an asset.
printf '%s\n' 'import type { Y } from "./not-an-asset.weird";' 'export type Z = Y;' > "$lib/dotted.d.ts"
if node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/dotted.d.ts --lock "$fixture/dotted.json" --write 2>"$fixture/dotted.err" >/dev/null; then
  echo "an unresolved dotted module unexpectedly locked as an asset" >&2; exit 1
fi
grep -q "unresolved declaration reference" "$fixture/dotted.err" || { echo "dotted module failed for the wrong reason:" >&2; cat "$fixture/dotted.err" >&2; exit 1; }
# A module reference the scanner cannot read as a string literal must fail, not be skipped.
printf '%s\n' 'declare const name: string;' 'export type Dynamic = import(name);' > "$lib/unsupported.d.ts"
if node "$lock_script" --declarations-root "$fixture/node_modules" --entry example/lib/unsupported.d.ts --lock "$fixture/unsupported.json" --write 2>"$fixture/unsupported.err" >/dev/null; then
  echo "an unsupported module specifier form unexpectedly locked" >&2; exit 1
fi
grep -q "unsupported module specifier syntax" "$fixture/unsupported.err" || { echo "unsupported form failed for the wrong reason:" >&2; cat "$fixture/unsupported.err" >&2; exit 1; }
echo "PASS closure scanner fixture"
