#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
LANE_REPO_ROOT="$ROOT"
. "$ROOT/tests/composition/lib/lane-package.sh"
PACKAGE="$(lane_package_path "$WORK")"
# All four inventory joins use this one archive; no language-side repack or source fallback.
python3 -I -B "$ROOT/tests/composition/polyglot/verify-package.py" "$ROOT" "$PACKAGE"
