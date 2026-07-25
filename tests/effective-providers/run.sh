#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/scripts/generate-effective-providers.py"
SOURCE="$ROOT/providers/rendering.providers.yml"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0
ok() { echo "PASS  $1"; pass=$((pass + 1)); }
bad() { echo "FAIL  $1"; fail=$((fail + 1)); }

if "$GEN" --provider "$SOURCE" --check >/dev/null; then
  ok "the checked-in effective-provider summary is current"
else
  bad "the checked-in effective-provider summary is stale"
fi

STALE="$WORK/stale.yml"
cp "$SOURCE" "$STALE"
sed -i 's/# effective\[1\]:/# effective[99]:/' "$STALE"
if "$GEN" --provider "$STALE" --check >"$WORK/stale.out" 2>"$WORK/stale.err"; then
  bad "a stale generated summary passed"
elif grep -q "generated summary is stale" "$WORK/stale.err"; then
  ok "a stale generated summary fails with its repair"
else
  bad "a stale summary failed without the generated-summary diagnostic"
fi

history_hash() {
  sed -n '/^# PIN HISTORY/,/^schemaVersion:/p' "$1" | sed '$d' | sha256sum | cut -d' ' -f1
}
before="$(history_hash "$STALE")"
"$GEN" --provider "$STALE" --write >/dev/null
after="$(history_hash "$STALE")"
if "$GEN" --provider "$STALE" --check >/dev/null && [ "$before" = "$after" ]; then
  ok "--write repairs only the generated view and preserves PIN HISTORY byte-for-byte"
else
  bad "--write did not converge or changed PIN HISTORY"
fi

DUPLICATE="$WORK/duplicate.yml"
cp "$SOURCE" "$DUPLICATE"
cat >>"$DUPLICATE" <<'EOF'
  - name: rendering
    contractVersion: "9.9.9"
    templateId: duplicate
    source: Duplicate.Template::9.9.9
EOF
if "$GEN" --provider "$DUPLICATE" --check >"$WORK/duplicate.out" 2>"$WORK/duplicate.err"; then
  bad "duplicate provider names passed"
elif grep -q "provider names must be unique; duplicate(s): rendering" "$WORK/duplicate.err"; then
  ok "duplicate provider names fail closed"
else
  bad "duplicate provider names failed without the uniqueness diagnostic"
fi

UNORDERED="$WORK/unordered.yml"
cp "$SOURCE" "$UNORDERED"
cat >>"$UNORDERED" <<'EOF'
  - name: audio
    contractVersion: "1.0.0"
    templateId: fs-gg-audio
    source: FS.GG.Audio.Template::1.0.0
EOF
if "$GEN" --provider "$UNORDERED" --check >"$WORK/unordered.out" 2>"$WORK/unordered.err"; then
  bad "out-of-order providers passed"
elif grep -q "providers must be ordered by name" "$WORK/unordered.err"; then
  ok "out-of-order providers fail closed"
else
  bad "out-of-order providers failed without the ordering diagnostic"
fi

echo "effective-providers fixture: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
