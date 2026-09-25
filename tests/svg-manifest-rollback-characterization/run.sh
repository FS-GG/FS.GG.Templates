#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
scratch="$(mktemp -d)"
cleanup() {
  python3 - "$scratch" <<'PY'
from pathlib import Path
import shutil
import sys
shutil.rmtree(Path(sys.argv[1]))
PY
}
trap cleanup EXIT
python3 "$repo_root/tests/svg-manifest-rollback-characterization/characterize.py" "$scratch/observation.json"
dotnet restore "$repo_root/tests/SvgManifestRollbackCharacterization.Tests/SvgManifestRollbackCharacterization.Tests.fsproj" --locked-mode
cd "$repo_root"
dotnet run --project tests/SvgManifestRollbackCharacterization.Tests/SvgManifestRollbackCharacterization.Tests.fsproj -c Release --no-restore -- "$scratch/observation.json"
