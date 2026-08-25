#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
archive="${1:?usage: run-release-verification.sh <candidate.nupkg> [result.junit.xml]}"
result="${2:-$repo_root/work/436-workspace-template-0-10-0-release/release-verification.junit.xml}"
log="${result%.xml}.log"
candidate_sha="$(sha256sum "$archive" | awk '{print $1}')"

set +e
FSGG_TEMPLATES_NUPKG="$archive" \
COMPOSITION_LANES="console web fable-bindings fable-game" \
  "$repo_root/tests/composition/run.sh" 2>&1 | tee "$log"
suite_rc="${PIPESTATUS[0]}"
set -e

if [[ "$suite_rc" -eq 0 ]]; then
  failure_count=0
  failure=''
else
  failure_count=1
  failure='<failure message="full release composition failed; inspect the sibling log" />'
fi

mkdir -p "$(dirname "$result")"
printf '%s\n' \
  '<?xml version="1.0" encoding="utf-8"?>' \
  "<testsuite name=\"FS.GG.Templates.0.10.0.Release\" tests=\"1\" failures=\"$failure_count\" errors=\"0\" skipped=\"0\">" \
  "  <testcase classname=\"FS.GG.Templates.Release\" name=\"one prepared archive passes all composition and browser lanes\">$failure</testcase>" \
  "  <system-out>archive=$(basename "$archive") sha256=$candidate_sha; lanes=console,web,fable-bindings,fable-game; command=tests/composition/run.sh</system-out>" \
  '</testsuite>' >"$result"

exit "$suite_rc"
