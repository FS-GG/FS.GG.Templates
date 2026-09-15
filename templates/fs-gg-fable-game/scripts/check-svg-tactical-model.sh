#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model="$root/models/svg-tactical/tactical-rules.md"
generated="$root/models/svg-tactical/tactical-rules.qnt"
identity="$root/Conformance/GeneratedTacticalRuleModel.fs"
bindings="$root/models/svg-tactical/tactical-rules.bindings.json"
quint="${QUINT_BIN:-$(command -v quint || true)}"
temporary="$(mktemp)"
combined="$(mktemp --suffix=.qnt)"
trace_json="$(mktemp)"
trace_projection="$(mktemp)"
trap 'rm -f "$temporary" "$combined" "$trace_json" "$trace_projection"' EXIT
if [[ -z "$quint" || ! -x "$quint" ]]; then
  echo "QUINT_BIN must name the qualified Quint 0.32.0 executable" >&2
  exit 1
fi
[[ "$($quint --version)" == "0.32.0" ]]
awk '
  /^```quint tactical-rules\.qnt \+=/ { inside=1; next }
  inside && /^```$/ { exit }
  inside { print }
' "$model" > "$temporary"
tail -n +2 "$generated" | cmp - "$temporary"
digest="$(sha256sum "$model" | cut -d ' ' -f 1)"
grep -F "let modelSha256 = \"$digest\"" "$identity" >/dev/null
grep -F 'let toolVersion = "0.32.0"' "$identity" >/dev/null
jq -e '
  .schema == "fsgg.quint.general-bindings/v1" and
  .profile == "fsgg-quint-profile/2" and
  (.exports | length == 1) and (.actions | length == 8) and
  ([.exports[], .actions[]] | all(.source.path == "models/svg-tactical/tactical-rules.md"))
' "$bindings" >/dev/null
"$quint" typecheck "$generated"
cat "$generated" "$root/models/svg-tactical/correspondence.qnt" > "$combined"
"$quint" run "$combined" --main SvgTacticalCorrespondence --max-samples=1 --max-steps=11 \
  --out-itf "$trace_json" --verbosity=0
jq -r '.states[].observed |
  "phase:\(.phase)|acceptedCol:\(.acceptedCol["#bigint"])|predictedCol:\(.predictedCol["#bigint"])|committedCol:\(.committedCol["#bigint"])|recorded:\(.recorded)"' \
  "$trace_json" > "$trace_projection"
cmp "$root/Conformance/tactical-rules.trace" "$trace_projection"
"$quint" run "$generated" --main SvgTacticalRules --max-samples=500 --max-steps=12 \
  --invariants columnsInBounds commitAgrees cancelPreservesAccepted reviewHasRecording \
  --witnesses witnessCompare witnessCancel witnessCommit witnessSimulate witnessReview
