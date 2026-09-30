#!/usr/bin/env bash
set -euo pipefail
umask 077

source_root=/source/examples/language-routes/typescript-todo
output_root=/output
module_root=/opt/fsgg/typescript-todo/node_modules
browser_root=/ms-playwright
headless_shell="$browser_root/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
headless_license="$browser_root/chromium_headless_shell-1243/chrome-headless-shell-linux64/LICENSE.headless_shell"

test -d "$source_root"
test ! -w "$source_root"
test -x "$headless_shell"
test -f "$headless_license"
install -d -m 0700 "$output_root/dist" "$output_root/reports" "$output_root/cache" \
  "$output_root/home" "$output_root/tmp" "$output_root/harness/tests"

export HOME="$output_root/home"
export XDG_CACHE_HOME="$output_root/cache"
export TMPDIR="$output_root/tmp"
export PLAYWRIGHT_BROWSERS_PATH="$browser_root"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
export TYPESCRIPT_TODO_MODULE_ROOT="$module_root"
export TYPESCRIPT_TODO_TYPESCRIPT_BIN="$module_root/typescript/bin/tsc"
export TYPESCRIPT_TODO_DIST_DIR="$output_root/dist"
export TYPESCRIPT_TODO_REPORT_DIR="$output_root/reports"
export TYPESCRIPT_TODO_NODE=/usr/local/bin/node
export TYPESCRIPT_TODO_SERVE_SCRIPT="$source_root/scripts/serve.mjs"
export TYPESCRIPT_TODO_CHROMIUM_NO_SANDBOX=1

test "$(node --version)" = "v24.8.0"
node "$source_root/scripts/check-toolchain.mjs"
node "$source_root/scripts/build.mjs"
node --test "$source_root/tests/domain.test.mjs" "$source_root/tests/storage.test.mjs" "$source_root/tests/toolchain.test.mjs"

cp "$source_root/playwright.config.mjs" "$output_root/harness/playwright.config.mjs"
cp "$source_root/tests/browser.spec.mjs" "$output_root/harness/tests/browser.spec.mjs"
ln -s "$module_root" "$output_root/harness/node_modules"
(
  cd "$output_root/harness"
  node "$module_root/@playwright/test/cli.js" test --config="$output_root/harness/playwright.config.mjs"
)

export FSGG_BROWSER_EXECUTABLE_SHA256="$(sha256sum "$headless_shell" | cut -d' ' -f1)"
export FSGG_BROWSER_LICENSE_SHA256="$(sha256sum "$headless_license" | cut -d' ' -f1)"
node -e '
  const fs = require("node:fs");
  const result = {
    schema: "fsgg.typescript-todo-image-operation/1",
    node: process.versions.node,
    typescript: "5.9.2",
    playwright: "1.63.0",
    containerUid: process.getuid(),
    containerGid: process.getgid(),
    chromium: { version: "153.0.8010.12", revision: "1243", executableSha256: process.env.FSGG_BROWSER_EXECUTABLE_SHA256, licenseSha256: process.env.FSGG_BROWSER_LICENSE_SHA256 },
    sourceMount: "read-only",
    network: "container-loopback-only",
    outputs: { dist: "/output/dist", reports: "/output/reports", cache: "/output/cache", retainedBrowserState: "/output/tmp" },
    journey: { add: "passed", edit: "passed", complete: "passed", filter: "passed", delete: "passed", reload: "passed", malformedRetainedState: "passed" }
  };
  fs.writeFileSync("/output/result.json", JSON.stringify(result) + "\n", { mode: 0o600 });
'
