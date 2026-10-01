#!/usr/bin/env bash

# Make the canonical Python fixture available to SVG source qualifications that
# pack the complete Templates archive. The package target verifies the revision,
# tree and file hashes again; this helper only acquires the exact public source
# when the calling workflow has not already supplied a checkout.
prepare_svg_source_python_fixture() {
  local root="$1" evidence_root="$2" manifest revision checkout projection
  manifest="$root/eng/portable-workspace/python-fixture-source.json"
  projection="$evidence_root/python-fixture-preflight"

  if [[ -z "${FSGG_PYTHON_COORDINATION_ROOT:-}" ]]; then
    revision="$(python3 - "$manifest" <<'PY'
from pathlib import Path
import json, re, sys

value = json.loads(Path(sys.argv[1]).read_text())
if value.get("schema") != "fsgg.templates.python-fixture-source/1":
    raise SystemExit("python fixture source schema refused")
if value.get("repository") != "FS-GG/FS.GG.Coordination":
    raise SystemExit("python fixture source repository refused")
revision = value.get("revision")
if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
    raise SystemExit("python fixture source revision refused")
print(revision)
PY
)"
    checkout="$evidence_root/python-fixture-coordination"
    mkdir -p "$checkout"
    /usr/bin/git -C "$checkout" init --quiet
    /usr/bin/git -C "$checkout" remote add origin https://github.com/FS-GG/FS.GG.Coordination.git
    /usr/bin/git -C "$checkout" config core.sparseCheckout true
    printf '%s\n' \
      tests/portable-workspace/image/fixture/python/app.py \
      tests/portable-workspace/image/fixture/python/build.py \
      tests/portable-workspace/image/fixture/python/test.py \
      >"$checkout/.git/info/sparse-checkout"
    GIT_TERMINAL_PROMPT=0 /usr/bin/git -c credential.helper= -C "$checkout" \
      fetch --quiet --no-tags --depth=1 origin "$revision"
    /usr/bin/git -C "$checkout" checkout --quiet --detach FETCH_HEAD
    FSGG_PYTHON_COORDINATION_ROOT="$checkout"
    export FSGG_PYTHON_COORDINATION_ROOT
  fi

  python3 "$root/eng/portable-workspace/project-python-fixture.py" \
    --coordination-root "$FSGG_PYTHON_COORDINATION_ROOT" \
    --output "$projection" >"$evidence_root/python-fixture-projection.json"
}
