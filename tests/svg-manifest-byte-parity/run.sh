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
python3 "$repo_root/tests/svg-manifest-byte-parity/expected.py" "$scratch/observation.json" "$scratch/expected.json"
dotnet restore "$repo_root/tests/SvgSkillManifestMerge.Tests/SvgSkillManifestMerge.Tests.fsproj" --locked-mode
cd "$repo_root"
dotnet run --project tests/SvgSkillManifestMerge.Tests/SvgSkillManifestMerge.Tests.fsproj -c Release --no-restore -- "$scratch/expected.json"
