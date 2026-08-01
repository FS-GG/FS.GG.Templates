#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts/test-results
dotnet restore WebWorkspace.slnx --locked-mode
dotnet build WebWorkspace.slnx --no-restore
dotnet test Server.Tests/WebWorkspace.Server.Tests.fsproj --no-build --logger "trx;LogFileName=server.trx" --results-directory artifacts/test-results
(cd Web && npm ci && npm run build && npm test)
(cd Browser.Tests && npm ci && npm test)
