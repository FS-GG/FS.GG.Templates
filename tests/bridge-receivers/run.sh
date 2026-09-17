#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_commit=3adada5a9738464291088830c47a30a3a8fc9561
source_tree=0f075e251d90a2d33efe556df1dac38394b0a388
producer_commit=bc881a6ed1b4ce32e99d4c30a664b1db686280d3
scratch="$(mktemp -d "${TMPDIR:-/tmp}/templates-bridge-receiver.XXXXXX")"
trap '[[ "${KEEP_WORKDIR:-0}" == 1 ]] || rm -rf -- "$scratch"' EXIT
mkdir -p "$scratch/packages" "$scratch/hub"

for package in fs.gg.coord.cli fs.gg.kit; do
  curl --fail --location --retry 3 --silent --show-error \
    "https://api.nuget.org/v3-flatcontainer/$package/0.90.0/$package.0.90.0.nupkg" \
    --output "$scratch/packages/$package.0.90.0.nupkg"
done
python3 "$root/tests/bridge-receivers/verify.py" "$scratch/packages"

# The public Kit must close over the committed projection. A second materialization may write no
# tracked byte; this catches a stale receiver even when the pin itself looks current.
before="$(git -C "$root" status --short --untracked-files=no)"
dotnet build "$root/.config/kit/FS.GG.Kit.receiver.proj" -t:FsggKitMaterialize --nologo -v minimal
after="$(git -C "$root" status --short --untracked-files=no)"
[[ "$before" == "$after" ]] || {
  printf '%s\n' 'bridge-receivers: public Kit materialization changed tracked output' >&2
  diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") >&2 || true
  exit 1
}

# Reuse the producer-owned behavioral probe at the exact public source. This exercises the installed
# command, an unavailable production fence (zero provider mutations), eligible/frozen packed epochs,
# and duplicate-settlement refusal without inventing a receiver-owned copy of the bridge model.
git -C "$scratch/hub" init -q
git -C "$scratch/hub" remote add origin https://github.com/FS-GG/.github.git
git -C "$scratch/hub" fetch -q origin "$source_commit" "$producer_commit"
git -C "$scratch/hub" checkout -q --detach FETCH_HEAD
[[ "$(git -C "$scratch/hub" rev-parse HEAD)" == "$source_commit" ]]
[[ "$(git -C "$scratch/hub" rev-parse HEAD^{tree})" == "$source_tree" ]]
python3 "$scratch/hub/tests/bridge-package/run.py" describe \
  --package "$scratch/packages/fs.gg.coord.cli.0.90.0.nupkg" \
  --source-commit "$source_commit" --source-tree "$source_tree" >"$scratch/binding.json"
TMPDIR="$scratch" python3 "$scratch/hub/tests/bridge-package/run.py" verify \
  --package "$scratch/packages/fs.gg.coord.cli.0.90.0.nupkg" \
  --binding "$scratch/binding.json"

printf '%s\n' 'bridge-receivers: public install and fail-closed behavior PASS'
