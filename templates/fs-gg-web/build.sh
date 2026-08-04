#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts/test-results
(cd Web && npm ci && npm run build)
(cd Web.Tests && npm ci && npm test)

# ── The lockfiles must have SHIPPED with this workspace (FS.GG.Templates#380) ────
#
# `--locked-mode` with no lock file on disk does not fail: NuGet quietly AUTHORS one
# from whatever the ambient machine resolves, and every later restore then enforces
# that unreviewed lock. That is not a hypothetical — `dotnet new`'s default source
# exclude list contains `**/*.lock.json`, so for the whole of 0.8.0 every generated
# workspace arrived with zero lockfiles and silently invented its own. The symptom in
# the sibling fable-game template was `NU1403: Package content hash validation failed`,
# three steps downstream and nowhere near the cause; this template carried the same
# defect and merely had not been observed to red.
#
# So assert presence BEFORE restoring. A missing lock here means the template stopped
# delivering it, and the correct outcome is a loud red at the boundary that owns the
# guarantee — not a restore that succeeds by inventing the thing it was meant to check.
missing=()
for locked in Server Server.Tests; do
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

dotnet restore WebWorkspace.slnx --locked-mode
dotnet build WebWorkspace.slnx --no-restore
dotnet test Server.Tests/WebWorkspace.Server.Tests.fsproj --no-build --logger "trx;LogFileName=server.trx" --results-directory artifacts/test-results
dotnet publish Server/WebWorkspace.Server.fsproj -c Release --no-restore -o artifacts/publish
# CI may supply a disclosed browser executable; otherwise provision Playwright's pinned runtime.
(
  cd Browser.Tests
  npm ci
  if [[ -n "${PLAYWRIGHT_EXECUTABLE_PATH:-}" ]]; then
    test -x "$PLAYWRIGHT_EXECUTABLE_PATH"
    echo "browser runtime: external $PLAYWRIGHT_EXECUTABLE_PATH ($("$PLAYWRIGHT_EXECUTABLE_PATH" --version | head -1))"
  else
    echo "browser runtime: Playwright-pinned Chromium headless shell"
    export PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT="${PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT:-120000}"
    if command -v timeout >/dev/null 2>&1; then
      timeout "${PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS:-300}" npx playwright install --only-shell chromium
    else
      npx playwright install --only-shell chromium
    fi
  fi
  npm test
)
