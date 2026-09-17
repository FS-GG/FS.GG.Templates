#!/usr/bin/env bash
set -euo pipefail

hub_ref="${1:-}"
[[ "$hub_ref" =~ ^[0-9a-f]{40}$ ]] || {
  printf '%s\n' 'wizard bridge qualification requires an explicit full 40-character hub adoption commit' >&2
  exit 2
}

scratch="$(mktemp -d "${TMPDIR:-/tmp}/templates-wizard-bridge.XXXXXX")"
trap '[[ "${KEEP_WORKDIR:-0}" == 1 ]] || rm -rf -- "$scratch"' EXIT
git -C "$scratch" init -q
git -C "$scratch" remote add origin https://github.com/FS-GG/.github.git
git -C "$scratch" fetch -q --depth=1 origin "$hub_ref"
git -C "$scratch" checkout -q --detach FETCH_HEAD
[[ "$(git -C "$scratch" rev-parse HEAD)" == "$hub_ref" ]]
git -C "$scratch" fetch -q origin main:refs/remotes/origin/main
git -C "$scratch" merge-base --is-ancestor "$hub_ref" refs/remotes/origin/main || {
  printf '%s\n' 'selected hub adoption commit is not reachable from protected main' >&2
  exit 1
}

python3 - "$scratch/docs/reports/gs2-08-8-bridge-adoption.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit("selected hub revision has no GS2-08.8 adoption report")
value = json.loads(path.read_text())
if value.get("schema") != "fsgg.gs2-08.8-receiver-adoption/1":
    raise SystemExit("selected hub revision has the wrong GS2-08.8 report schema")
if value.get("receiver") != "FS-GG/.github":
    raise SystemExit("selected hub revision is not the hub receiver adoption")
release = value.get("release", {})
expected_release = {
    "version": "0.90.0",
    "manifestSha256": "1bbb77f3de10ba3116f9de2ea1df3f5edee38be0de07fa0eaf7c173da3a8456a",
    "contentId": "sha256:52b2774de277855c16a3c0852bc5113deea13d9076b866e6a7de0acc84f4b9c4",
    "sourceCommit": "3adada5a9738464291088830c47a30a3a8fc9561",
    "sourceTree": "0f075e251d90a2d33efe556df1dac38394b0a388",
}
for key, expected in expected_release.items():
    if release.get(key) != expected:
        raise SystemExit(f"selected hub revision has wrong release {key}")
packages = {row.get("id"): row for row in value.get("packages", [])}
expected_packages = {
    "FS.GG.Coord.Cli": (
        "69a7100358e01c846216cedb3f5ce17f72e99e8328a23be8e75b077dfd82d3e6",
        "sha256:725b46203eeccbe1f73b42667d95ed07c6581dc2ca0886ac8011145c278ee481",
    ),
    "FS.GG.Kit": (
        "bea35100645f1acb459e385e303d0ef4ff7aa6576fa3f032ef8325cfef38b858",
        "sha256:f2a318f0b900d049c496618bfdd7c2def5f50ffd9e649d8998f5c6585384f1f4",
    ),
}
for package_id, (archive, payload) in expected_packages.items():
    row = packages.get(package_id, {})
    if (row.get("version"), row.get("publicArchiveSha256"), row.get("payloadSha256")) != ("0.90.0", archive, payload):
        raise SystemExit(f"selected hub revision has wrong public identity for {package_id}")
if set(expected_packages) - set(packages):
    raise SystemExit("selected hub revision does not adopt the coherent 0.90.0 bridge")
PY

# The hub owns wizard behavior. Its exact-revision selftest includes both clean creation and retrofit,
# asserts the generated 0.90.0 tool selection, and keeps fake loopback credentials behind the
# unavailable production fence. Templates consumes that proof only after the hub adoption is merged.
bash "$scratch/tests/new-sdd-workspace/run.sh"
printf 'wizard bridge qualification PASS at hub %s\n' "$hub_ref"
