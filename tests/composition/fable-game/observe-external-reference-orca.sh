#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Consume the existing generated candidate once; never regenerate or retry it here.
exec /usr/bin/python3 -B "$script_dir/external-reference-orca.py" \
  "${1:?candidate qualification directory required}" \
  "${2:?authenticated native preflight required}"
