#!/usr/bin/env bash
set -euo pipefail

# ── The lockfiles must have SHIPPED with this workspace (FS.GG.Templates#384) ────
#
# `--locked-mode` with no lock file on disk does not fail: NuGet quietly AUTHORS one
# from whatever the ambient machine resolves, and every later restore then enforces
# that unreviewed lock. That is not a hypothetical — `dotnet new`'s default source
# exclude list contains `**/*.lock.json`, so for the whole of 0.8.0 every generated
# workspace arrived with zero lockfiles and silently invented its own, even though
# this template committed two reviewed ones. The symptom in the sibling fable-game
# template was `NU1403: Package content hash validation failed`, three steps
# downstream and nowhere near the cause; this template carried the same defect and
# merely had not been observed to red.
#
# So assert presence BEFORE restoring. A missing lock here means the template stopped
# delivering it, and the correct outcome is a loud red at the boundary that owns the
# guarantee — not a restore that succeeds by inventing the thing it was meant to check.
#
# The paths below carry the template's own project name; `dotnet new` rewrites it to
# the product's name on the way out, exactly as it does in `scripts/lifecycle-evidence.mjs`.
missing=()
for locked in src/BindingsProduct tests/BindingsProduct.CompileTests; do
  [[ -f "$locked/packages.lock.json" ]] || missing+=("$locked/packages.lock.json")
done
if (( ${#missing[@]} > 0 )); then
  {
    echo "build.sh: refusing to restore — this workspace shipped without NuGet lockfiles:"
    printf '  missing: %s\n' "${missing[@]}"
    echo "A --locked-mode restore would not fail on this; it would AUTHOR a lock from"
    echo "whatever this machine resolves, which is exactly how FS.GG.Templates#380"
    echo "produced NU1403. Regenerate the template's lockfiles, or repair the template's"
    echo "'sources' exclude list so they reach a generated product."
  } >&2
  exit 1
fi

dotnet restore BindingsProduct.slnx --locked-mode
dotnet build BindingsProduct.slnx --no-restore

# The npm half of this workspace: the pinned declaration closure, its drift gate, and
# the Node runtime smoke. `npm ci` is the lockfile-respecting install, for the same
# reason `--locked-mode` is above.
npm ci --ignore-scripts
npm run doctor
npm run check:drift
npm run test:runtime
