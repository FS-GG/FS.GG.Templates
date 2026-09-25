#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
python3 "$repo_root/tests/svg-workspace-characterization/characterize.py" "$scratch/observation.json"
dotnet restore "$repo_root/tests/SvgWorkspaceCharacterization.Tests/SvgWorkspaceCharacterization.Tests.fsproj" --locked-mode
dotnet run --project "$repo_root/tests/SvgWorkspaceCharacterization.Tests/SvgWorkspaceCharacterization.Tests.fsproj" --no-restore -- "$scratch/observation.json"
