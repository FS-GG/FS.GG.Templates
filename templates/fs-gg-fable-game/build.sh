#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts/test-results

# The .NET-side wire boundary: shared Domain decisions, and every DTO/codec pair.
dotnet restore FableGameWorkspace.slnx --locked-mode
dotnet build FableGameWorkspace.slnx --no-restore
dotnet test Domain.Tests/Domain.Tests.fsproj --no-build --logger "trx;LogFileName=domain.trx" --results-directory artifacts/test-results
dotnet test Protocol.Tests/Protocol.Tests.fsproj --no-build --logger "trx;LogFileName=protocol.trx" --results-directory artifacts/test-results

# ADR-0073's "not optional" acceptance criterion: every DTO encoded from .NET and
# decoded in the Fable/browser runtime, and the reverse, including a rejected case.
bash Protocol.Tests/cross-runtime/run-cross-runtime.sh

dotnet test Server.Tests/Server.Tests.fsproj --no-build --logger "trx;LogFileName=server.trx" --results-directory artifacts/test-results

# The Fable/Elmish client: compile, then production-bundle with Vite.
(cd Client && npm ci && npm run build)

dotnet publish Server/Server.fsproj -c Release --no-restore -o artifacts/publish

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
