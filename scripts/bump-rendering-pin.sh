#!/usr/bin/env bash
# Re-pin the FS.GG.UI.Template version across the places that must agree: the provider `source:`
# value, the provider's `# pin-tag:` / `# pin-contract:` marker lines, and the two README
# "currently pinned at" mentions. The composition test (tests/composition/stages/04-verify.sh,
# "verify — rendering provider pin coherence") checks the provider comment and the README name the
# pinned version.
#
# This is the successor to the retired scripts/sync-from-rendering.sh "bump <Version>"
# step: instead of vendoring a fresh copy of the rendering payload, we now only move the
# single version pin that selects the published FS.GG.UI.Template package the scaffold
# installs. Renovate (.github/renovate.json) does this continuously; the
# upstream-bump workflow does it on an upstream release; this script is the shared,
# human-runnable primitive both lean on.
#
# WHY THIS IS NOT A WHOLE-FILE `sed s/OLD/NEW/g` ANY MORE.
#
#   The old implementation asserted: "the version token is specific enough that a literal,
#   whole-file replacement of OLD->NEW updates every coherence surface without touching anything
#   else." That is false. A version literal appears in two KINDS of sentence:
#
#     current  "the pin is `fs-gg-ui-template/v0.2.0-preview.1`"        <- must move
#     history  "0.2.0-preview.1 (2026-07-06, Rendering#155, run 28807190647): the FRAMEWORK
#               MAJOR ... this pin brings FS.GG.UI.* @ 0.2.0 down"      <- must NOT move
#
#   `sed` cannot tell them apart. On the real 0.2.0 -> 0.3.1 bump it rewrote the second kind,
#   leaving providers/rendering.providers.yml claiming that 0.3.1-preview.1 shipped on 2026-07-06
#   from FS.GG.Rendering#155 as the ADR-0022 P5 framework major, and that the pin drags
#   `FS.GG.UI.* @ 0.3.1` down — libraries that are at 0.3.0 and have no 0.3.1 on any feed. It even
#   left the words "RE-COUPLE at 0.2.0" beside "0.3.1-preview.1" on the same line, because the sed
#   matched only the full `0.2.0-preview.1` token. A self-contradicting line is the tell.
#
#   So: rewrite ONLY anchored, machine-owned sites; never free prose. Every substitution below is
#   anchored to a line pattern and verified afterwards. The PIN HISTORY block is off limits — we
#   hash it before and after and abort if a single byte moved.
#
# A bumper cannot know WHY a release happened, so it does not pretend to: it appends a
# `PIN HISTORY ENTRY REQUIRED` stub. The composition test fails while any stub remains, so the
# bot's PR stays red until a human writes the entry.
#
# Usage: scripts/bump-rendering-pin.sh <new-version>
#   e.g. scripts/bump-rendering-pin.sh 0.1.51-preview.1
set -euo pipefail

NEW="${1:?new FS.GG.UI.Template version required, e.g. 0.1.51-preview.1}"

# Validate before NEW reaches the sed calls below: they use `#` as the s-delimiter and do not
# escape the replacement, so a value containing `#`, `&`, or `\` would corrupt the provider yml /
# README. This guard closes that for every caller (upstream-bump.yml, a human run); Renovate edits
# the files directly and never calls here.
if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][A-Za-z0-9.]+)?$ ]]; then
  echo "error: '$NEW' is not a valid FS.GG.UI.Template version (expected e.g. 0.1.51-preview.1)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROV="$ROOT/providers/rendering.providers.yml"
README="$ROOT/README.md"

# The line that separates machine-owned tokens (above) from hand-authored history (below).
HISTORY_MARKER='# PIN HISTORY'
STUB_SENTINEL='PIN HISTORY ENTRY REQUIRED'

# shellcheck source=scripts/lib/read-pin.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/read-pin.sh"

# Current pin is the single source of truth; read it from the provider `source:` line.
OLD="$(read_pin "$PROV")" || { echo "error: could not read current pin from $PROV" >&2; exit 1; }

if [ "$OLD" = "$NEW" ]; then
  echo "already pinned at FS.GG.UI.Template::$NEW; nothing to do."
  exit 0
fi

grep -qF "$HISTORY_MARKER" "$PROV" || {
  echo "error: '$HISTORY_MARKER' marker missing from $PROV — refusing to edit a file whose" >&2
  echo "       machine-owned region cannot be delimited (fail closed; see this script's header)." >&2
  exit 1
}

fail() { echo "error: $1" >&2; exit 1; }

# Fingerprint the hand-authored region so a stray edit to it is a hard error, not a silent rewrite.
# The region runs from the marker to the first YAML key (`schemaVersion:`), NOT to end-of-file —
# `source:` lives below it and is machine-owned. (Getting this wrong is caught by the guard itself:
# the first run of this script tripped its own `history changed` check for exactly that reason.)
history_hash() {
  sed -n "\%^${HISTORY_MARKER}%,\%^schemaVersion:%p" "$PROV" | sed '$d' | sha256sum | cut -d' ' -f1
}
grep -q '^schemaVersion:' "$PROV" || fail "no 'schemaVersion:' key — cannot bound the PIN HISTORY region"
BEFORE="$(history_hash)"

OLD_RE="${OLD//./\\.}"

# Each substitution is anchored to its own line. `\%…%` addresses avoid escaping `/`.
sed -i -E "\%^[[:space:]]*source:[[:space:]]*FS\.GG\.UI\.Template::% s#(FS\.GG\.UI\.Template::)${OLD_RE}#\1${NEW}#" "$PROV"
sed -i -E "\%^# pin-tag:% s#(fs-gg-ui-template/v)${OLD_RE}#\1${NEW}#" "$PROV"
sed -i -E "\%^# pin-contract:% s#(fs-gg-ui-template@)${OLD_RE}#\1${NEW}#" "$PROV"
sed -i -E "\%currently .FS\.GG\.UI\.Template@% s#(FS\.GG\.UI\.Template@)${OLD_RE}#\1${NEW}#" "$README"
sed -i -E "\%immutable tag .fs-gg-ui-template/v% s#(fs-gg-ui-template/v)${OLD_RE}#\1${NEW}#" "$README"

# Verify, don't assume. Every machine-owned site must carry NEW; the history must be byte-identical.
[ "$(read_pin "$PROV")" = "$NEW" ]                          || fail "provider source: pin did not move to $NEW"
grep -qF "# pin-tag: fs-gg-ui-template/v${NEW}" "$PROV"     || fail "provider '# pin-tag:' line did not move to $NEW"
grep -qF "# pin-contract: fs-gg-ui-template@${NEW}" "$PROV" || fail "provider '# pin-contract:' line did not move to $NEW"
grep -qF "FS.GG.UI.Template@${NEW}" "$README"               || fail "README 'currently' pin did not move to $NEW"
grep -qF "fs-gg-ui-template/v${NEW}" "$README"              || fail "README immutable-tag mention did not move to $NEW"
[ "$(history_hash)" = "$BEFORE" ]                           || fail "the PIN HISTORY block changed — the bumper must never edit it"

# The story is not derivable from the version number. Force a human to supply it: insert a stub as
# the newest history entry (immediately above the previous newest one).
STUB="#
# ${NEW} — ${STUB_SENTINEL}. Describe what this release changed and why the pin moved: template-only
#   or a framework bump? which \$(FsGgUiVersion) do the FS.GG.UI.* libraries sit at? which Rendering
#   issue/PR and release run? Delete this notice once written — the composition test fails while it
#   remains. (Bumped from ${OLD} by scripts/bump-rendering-pin.sh; a bumper cannot know the story.)"

awk -v marker="$HISTORY_MARKER" -v stub="$STUB" '
  index($0, marker) == 1 { inhist = 1 }
  inhist && !done && /^# [0-9]+\.[0-9]+\.[0-9]+/ { print stub; done = 1 }
  { print }
  END { if (!done) { print "awk: no existing history entry to insert above" > "/dev/stderr"; exit 1 } }
' "$PROV" > "$PROV.tmp" || { rm -f "$PROV.tmp"; fail "could not insert the PIN HISTORY stub"; }
mv "$PROV.tmp" "$PROV"

grep -qF "$STUB_SENTINEL" "$PROV" || fail "failed to append the PIN HISTORY stub"

echo "Re-pinned FS.GG.UI.Template ${OLD} -> ${NEW} (providers/rendering.providers.yml, README.md)."
echo
echo "!! A '${STUB_SENTINEL}' stub was inserted into the PIN HISTORY block in:"
echo "     $PROV"
echo "   Replace it with the real story (template-only vs framework bump, the FS.GG.UI.* library"
echo "   version, the Rendering issue/PR and release run). tests/composition/run.sh fails until you do."
echo
echo "Next: write the history entry, commit + open a PR; tests/composition/run.sh verifies the locations agree."
