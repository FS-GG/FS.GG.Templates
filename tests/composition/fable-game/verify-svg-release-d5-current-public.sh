#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
helper="$root/tests/composition/fable-game/d5-current-public.py"
[[ $# -ge 2 && $# -le 3 ]] || { echo 'usage: current-public.sh ABSOLUTE_PINS NEW_ABSOLUTE_EVIDENCE [--preflight-only|--rehearsal|--full]' >&2; exit 2; }
pins="$1"; out="$2"; scope=rehearsal
[[ "$pins" = /* && "$out" = /* && ! -e "$out" && ! -L "$out" ]] || exit 2
[[ $# == 2 || "$3" == --preflight-only || "$3" == --rehearsal || "$3" == --full ]] || exit 2
python3 "$helper" observe "$pins"
[[ "${3:-}" != --preflight-only ]] || { echo 'Bounded input read only; typed qualification NOT RUN; runtime admission None'; exit 0; }
[[ "${3:-}" != --full ]] || scope=full
fail() { echo "current D.5: $*" >&2; exit 1; }
# Mechanically held source: exact source/main/attempt1/resource admission and
# maintained process-owner retirement are not assembled. No caller flag bypass.
readonly ADMISSION=None
[[ "$ADMISSION" != None ]] || { echo 'HELD: runtime admission None; retirement unqualified' >&2; exit 3; }
# Both entries keep a source literal hold. No caller flag or environment enables it.
python3 "$root/tests/composition/fable-game/d5-managed-runtime.py" --check-admission
[[ "$out" == "${RUNNER_TEMP:?}/current-d5-${RUN_ID:?}-1" ]] || fail 'canonical private evidence root differs'
export SCOPE="$scope"
PUBLIC_PINS="$(cat "$pins")"; export PUBLIC_PINS
exec python3 -I -B "$root/tests/composition/fable-game/d5-managed-runtime.py" --run
