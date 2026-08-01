#!/usr/bin/env bash
set -euo pipefail
dotnet restore WebWorkspace.slnx --locked-mode
dotnet build WebWorkspace.slnx --no-restore
dotnet run --project Server.Tests/WebWorkspace.Server.Tests.fsproj --no-build
(cd Web && npm ci && npm run build && npm test)
(cd Browser.Tests && npm ci && npm test)
