#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model="$root/models/svg-arena/arena-rules.md"
generated="$root/models/svg-arena/arena-rules.qnt"
identity="$root/Conformance/GeneratedArenaRuleModel.fs"
bindings="$root/models/svg-arena/arena-rules.bindings.json"
correspondence="$root/models/svg-arena/correspondence.qnt"
quint="${QUINT_BIN:-$(command -v quint || true)}"
temporary="$(mktemp)"
trace_json="$(mktemp)"
trace_projection="$(mktemp)"
combined="$(mktemp --suffix=.qnt)"
trap 'rm -f "$temporary" "$trace_json" "$trace_projection" "$combined"' EXIT
if [[ -z "$quint" || ! -x "$quint" ]]; then
  echo "QUINT_BIN must name the qualified Quint 0.32.0 executable" >&2
  exit 1
fi
[[ "$($quint --version)" == "0.32.0" ]]

awk '
  /^```quint arena-rules\.qnt \+=/ { inside=1; next }
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
  (.exports | length == 1) and
  (.actions | length == 9) and
  ([.exports[], .actions[]] | all(.source.path == "models/svg-arena/arena-rules.md"))
' "$bindings" >/dev/null
"$quint" typecheck "$generated"
cat "$generated" "$correspondence" > "$combined"
"$quint" typecheck "$combined"
"$quint" run "$combined" --main SvgArenaCorrespondence --max-samples=1 --max-steps=11 \
  --out-itf "$trace_json" --verbosity=0
jq -r '.states[].observed |
  "health:\(.health["#bigint"])|score:\(.score["#bigint"])|collected:\(.collected)|outcome:\(.outcome)|round:\(.round["#bigint"])|hazardContact:\(.hazardContact)"' \
  "$trace_json" > "$trace_projection"
cmp "$root/Conformance/arena-rules.trace" "$trace_projection"
"$quint" run "$generated" --main SvgArenaRules --max-samples=500 --max-steps=20 \
  --invariants healthBound scoreShape collectedScore wonRequiresCollection terminalOutcome hazardContactImpliesDamage \
  --witnesses witnessCollect witnessWin witnessLoss witnessRestart witnessHazardEntry witnessHazardStay witnessTerminalRefusal
