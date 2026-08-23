#!/usr/bin/env bash
set -euo pipefail
mkdir -p artifacts/test-results

# ── The lockfiles must have SHIPPED with this workspace (FS.GG.Templates#380) ────
#
# `--locked-mode` with no lock file on disk does not fail: NuGet quietly AUTHORS one
# from whatever the ambient machine resolves, and every later restore then enforces
# that unreviewed lock. That is not a hypothetical — `dotnet new`'s default source
# exclude list contains `**/*.lock.json`, so for the whole of 0.8.0 every generated
# workspace arrived with zero lockfiles and silently invented its own. The symptom
# was `NU1403: Package content hash validation failed`, three steps downstream and
# nowhere near the cause.
#
# So assert presence BEFORE restoring. A missing lock here means the template stopped
# delivering it, and the correct outcome is a loud red at the boundary that owns the
# guarantee — not a restore that succeeds by inventing the thing it was meant to check.
missing=()
for locked in \
  Domain Domain.Tests Protocol Protocol.Tests Server Server.Tests Client \
  Protocol.Tests/cross-runtime/CodecProbe.Net Protocol.Tests/cross-runtime/CodecProbe.Fable
do
  [[ -f "$locked/packages.lock.json" ]] || missing+=("$locked/packages.lock.json")
done
for locked in Client/package-lock.json Browser.Tests/package-lock.json; do
  [[ -f "$locked" ]] || missing+=("$locked")
done
if (( ${#missing[@]} > 0 )); then
  {
    echo "build.sh: refusing to restore — this workspace shipped without required dependency lockfiles:"
    printf '  missing: %s\n' "${missing[@]}"
    echo "A --locked-mode restore would not fail on this; it would AUTHOR a lock from"
    echo "whatever this machine resolves, which is exactly how FS.GG.Templates#380"
    echo "produced NU1403. Regenerate the template's lockfiles, or repair the template's"
    echo "'sources' exclude list so they reach a generated product."
  } >&2
  exit 1
fi

# ── The local tool manifest must have SHIPPED too (FS.GG.Templates#392) ─────────
#
# `fable` is a LOCAL dotnet tool, pinned by `.config/dotnet-tools.json`. The cross-runtime
# codec proof below restores and invokes it as `dotnet fable`, so this file is now on the
# critical path of `build.sh` — not just of `Client`'s npm build, which used to be the only
# thing that touched it. It reaches a product through exactly the mechanism that dropped the
# lockfiles above for the whole of 0.8.0 (the template engine's `sources` exclude list), so it
# is asserted the same way and for the same reason: name the cause at the boundary that owns
# the guarantee, rather than let it surface as a restore error several steps downstream.
if [[ ! -f .config/dotnet-tools.json ]]; then
  {
    echo "build.sh: refusing to build — this workspace shipped without .config/dotnet-tools.json"
    echo "That manifest pins the 'fable' local tool that the cross-runtime codec proof and the"
    echo "Client build both invoke as 'dotnet fable'. Repair the template's 'sources' exclude"
    echo "list so it reaches a generated product."
  } >&2
  exit 1
fi

# The .NET-side wire boundary: shared Domain decisions, and every DTO/codec pair.
dotnet restore FableGameWorkspace.slnx --locked-mode
dotnet build FableGameWorkspace.slnx --no-restore
dotnet test Domain.Tests/Domain.Tests.fsproj --no-build --logger "trx;LogFileName=domain.trx" --results-directory artifacts/test-results
dotnet test Protocol.Tests/Protocol.Tests.fsproj --no-build --logger "trx;LogFileName=protocol.trx" --results-directory artifacts/test-results

# ADR-0073's "not optional" acceptance criterion: every DTO encoded from .NET and
# decoded in the Fable/browser runtime, and the reverse, including a rejected case.
bash Protocol.Tests/cross-runtime/run-cross-runtime.sh

dotnet test Server.Tests/Server.Tests.fsproj --no-build --logger "trx;LogFileName=server.trx" --results-directory artifacts/test-results

# The Fable/Elmish client: compile, then production-bundle with Vite.
(cd Client && npm ci && npm run build)

dotnet publish Server/Server.fsproj -c Release --no-restore -o artifacts/publish

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
