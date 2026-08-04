# shellcheck shell=bash
# Resolve the FS.GG workspace-template archive a per-identity lane must install.
#
# WHY THIS EXISTS (FS.GG.Templates#349). `.github/workflows/release.yml` packs the release
# ONCE, checksums it, uploads it as an immutable artifact, and then re-downloads and
# checksum-verifies it in the gate job — whose whole premise is that the composition suite runs
# "against those exact downloaded bytes". Stage 01 honoured that via FSGG_TEMPLATES_NUPKG. The
# per-identity lanes did not: each ran its own `dotnet pack` from the checkout, so the artifact
# every identity was actually proved against was a SECOND archive that no checksum covered and
# that nothing published. The release could therefore ship bytes whose identities had never been
# instantiated, while the gate reported that they had.
#
# The lanes also hard-coded the archive's FILENAME (`FS.GG.Workspace.Template.0.8.0.nupkg`), which
# made every one of them a place a version bump had to be remembered, and a place a rename would
# break silently. Resolving the path from what is on disk removes both.
#
# Usage:  lane_package_path <workdir>   → echoes an absolute .nupkg path, or exits non-zero.
#
# FSGG_TEMPLATES_NUPKG set   → use exactly those bytes; a path that does not exist is a hard
#                              failure, never a quiet fall back to packing (that fallback is
#                              precisely how a gate reports on an archive nobody shipped).
# unset                      → pack the checkout into <workdir>/feed, the ordinary local/CI path.
lane_package_path() {
  local workdir="$1" feed produced count
  if [[ -n "${FSGG_TEMPLATES_NUPKG:-}" ]]; then
    if [[ ! -f "$FSGG_TEMPLATES_NUPKG" ]]; then
      echo "lane-package: FSGG_TEMPLATES_NUPKG is set to '$FSGG_TEMPLATES_NUPKG' but no such file exists. Refusing to pack a substitute — the caller asked for a specific archive." >&2
      return 1
    fi
    printf '%s\n' "$FSGG_TEMPLATES_NUPKG"
    return 0
  fi

  feed="$workdir/feed"
  mkdir -p "$feed"
  if ! dotnet pack "$LANE_REPO_ROOT/FS.GG.Templates.csproj" -c Release -o "$feed" >"$workdir/lane-pack.log" 2>&1; then
    echo "lane-package: dotnet pack failed; see $workdir/lane-pack.log" >&2
    tail -20 "$workdir/lane-pack.log" >&2
    return 1
  fi
  # Exactly one archive, whatever it is called. Globbing for a literal id is how release.yml came
  # to look for `FS.GG.Templates.*.nupkg` long after <PackageId> had become FS.GG.Workspace.Template.
  count="$(find "$feed" -maxdepth 1 -name '*.nupkg' | wc -l)"
  if [[ "$count" -ne 1 ]]; then
    echo "lane-package: expected exactly one .nupkg in $feed, found $count" >&2
    find "$feed" -maxdepth 1 -name '*.nupkg' >&2
    return 1
  fi
  produced="$(find "$feed" -maxdepth 1 -name '*.nupkg' -print -quit)"
  printf '%s\n' "$produced"
}

# Rewrite a copied provider descriptor's `source:` pin to a local archive path, whatever version
# the descriptor names. The lanes used to `sed` a hard-coded `FS.GG.Workspace.Template::0.8.0`
# literal, which silently matched nothing the moment the pin moved — leaving the descriptor
# pointing at a package the scaffold would try to resolve from a feed instead of from the archive
# under test, and turning the lane's provider route into a proof about a published version rather
# than about the candidate. Matching the KEY rather than the VALUE cannot rot that way, and an
# unmatched pin is a hard failure.
lane_pin_provider_to_archive() {
  local descriptor="$1" archive="$2"
  if ! grep -qE '^[[:space:]]*source:[[:space:]]*FS\.GG\.Workspace\.Template::' "$descriptor"; then
    echo "lane-package: $descriptor has no 'source: FS.GG.Workspace.Template::<version>' pin to redirect at the archive under test" >&2
    return 1
  fi
  sed -i -E "s#^([[:space:]]*source:[[:space:]]*)FS\.GG\.Workspace\.Template::.*\$#\1$archive#" "$descriptor"
  grep -qF "$archive" "$descriptor" || {
    echo "lane-package: failed to repoint $descriptor at $archive" >&2
    return 1
  }
}
