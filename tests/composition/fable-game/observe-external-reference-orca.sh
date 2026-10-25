#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Consume the existing generated candidate once; never regenerate or retry it here.
mode="${3:-external-reference}"
[[ "$#" -le 3 ]]
args=()
case "$mode" in
  external-reference) ;;
  current-public-local-save) args=(--current-public-local-save) ;;
  *) echo "unknown AT journey" >&2; exit 2 ;;
esac
exec /usr/bin/python3 -B "$script_dir/external-reference-orca.py" "${args[@]}" \
  "${1:?candidate qualification directory required}" \
  "${2:?authenticated native preflight required}"
