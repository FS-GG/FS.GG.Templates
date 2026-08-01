#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts/test-results
(cd Web && npm ci && npm run build && npm test)
dotnet restore WebWorkspace.slnx --locked-mode
dotnet build WebWorkspace.slnx --no-restore
dotnet test Server.Tests/WebWorkspace.Server.Tests.fsproj --no-build --logger "trx;LogFileName=server.trx" --results-directory artifacts/test-results
dotnet publish Server/WebWorkspace.Server.fsproj -c Release --no-restore -o artifacts/publish
# CI may supply a disclosed browser executable; otherwise provision Playwright's pinned runtime.
(
  cd Browser.Tests
  npm ci
  if [[ -n "${PLAYWRIGHT_EXECUTABLE_PATH:-}" ]]; then
    test -x "$PLAYWRIGHT_EXECUTABLE_PATH"
    echo "browser runtime: external $PLAYWRIGHT_EXECUTABLE_PATH ($("$PLAYWRIGHT_EXECUTABLE_PATH" --version | head -1))"
  else
    echo "browser runtime: Playwright-pinned Chromium headless shell"
    export PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT="${PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT:-120000}"
    if command -v timeout >/dev/null 2>&1; then
      timeout "${PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS:-300}" npx playwright install --only-shell chromium
    else
      npx playwright install --only-shell chromium
    fi
  fi
  npm test
)
