#!/usr/bin/env bash
# Re-pin the FS.GG.UI.Template version across every place the composition test
# (tests/composition/run.sh, "verify — rendering provider pin coherence") requires to
# agree: the provider `source` pin, the provider comment's `fs-gg-ui-template/v<ver>` and
# `fs-gg-ui-template@<ver>` tags, and the README mentions.
#
# This is the successor to the retired scripts/sync-from-rendering.sh "bump <Version>"
# step: instead of vendoring a fresh copy of the rendering payload, we now only move the
# single version pin that selects the published FS.GG.UI.Template package the scaffold
# installs. Renovate (.github/renovate.json) does this continuously; the
# upstream-bump workflow does it on an upstream release; this script is the shared,
# human-runnable primitive both lean on.
#
# Usage: scripts/bump-rendering-pin.sh <new-version>
#   e.g. scripts/bump-rendering-pin.sh 0.1.51-preview.1
set -euo pipefail

NEW="${1:?new FS.GG.UI.Template version required, e.g. 0.1.51-preview.1}"

# Validate before NEW reaches the sed below: its `s#...#${NEW}#g` uses `#` as the
# delimiter and does not escape the replacement, so a value containing `#`, `&`, or `\`
# would corrupt the provider yml / README. This guard closes that for every caller
# (upstream-bump.yml, a human run); Renovate edits the files directly and never calls here.
if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][A-Za-z0-9.]+)?$ ]]; then
  echo "error: '$NEW' is not a valid FS.GG.UI.Template version (expected e.g. 0.1.51-preview.1)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROV="$ROOT/providers/rendering.providers.yml"
README="$ROOT/README.md"

# Current pin is the single source of truth; read it from the provider `source:` line.
OLD="$(grep -oE 'FS\.GG\.UI\.Template::[^ ]+' "$PROV" | head -1 | sed 's/.*:://')"
[ -n "$OLD" ] || { echo "error: could not read current pin from $PROV" >&2; exit 1; }

if [ "$OLD" = "$NEW" ]; then
  echo "already pinned at FS.GG.UI.Template::$NEW; nothing to do."
  exit 0
fi

# The version token is specific enough (e.g. 0.1.50-preview.1) that a literal,
# whole-file replacement of OLD->NEW updates every coherence surface — the `::`, `@`,
# and `/v` forms in both files — without touching anything else. Escape dots for sed.
OLD_RE="${OLD//./\\.}"
sed -i "s#${OLD_RE}#${NEW}#g" "$PROV" "$README"

echo "Re-pinned FS.GG.UI.Template ${OLD} -> ${NEW} (providers/rendering.providers.yml, README.md)."
echo "Next: commit + open a PR; tests/composition/run.sh verifies the locations agree."
