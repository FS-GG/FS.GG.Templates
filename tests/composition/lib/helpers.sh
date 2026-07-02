# shellcheck shell=bash
# Composition-test assertion helpers — the shared prelude sourced by run.sh before any stage.
# Split out of run.sh (review A3): the counters and ok/bad/skip/step/assert_* live here so the
# stage files (stages/NN-*.sh) and the skill-union lib share one definition. Sourced, not
# executed — every function mutates the run-global PASS/FAIL counters in the caller's shell.

PASS=0 FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m–\033[0m SKIP: %s\n' "$1"; }
step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
# assert_contains <file> <substring> <message>
assert_contains() { if grep -qF -- "$2" "$1" 2>/dev/null; then ok "$3"; else bad "$3 (missing: '$2' in $1)"; fi; }
# assert_absent <file-or-dir> <substring> <message>  (recursive for dirs)
assert_absent() { if grep -rqF -- "$2" "$1" 2>/dev/null; then bad "$3 (found stray '$2' in $1)"; else ok "$3"; fi; }
# assert_exit <expected-code> <actual-code> <message>  — exact match (so a usage/input/tool
# error, e.g. 64/66/70, can never masquerade as a governed-blocking '2' or a clean '0').
assert_exit() { if [[ "$2" == "$1" ]]; then ok "$3 (exit $2)"; else bad "$3 (expected exit $1, got $2)"; fi; }
# installed_template_version <package-id> — echo the version of an installed `dotnet new` template
# package (empty if not installed). Parses `dotnet new uninstall` (no args), which prints each
# installed package id followed by an indented `Version: <v>` line. Used to verify the standalone
# lane runs against the *pinned* FS.GG.UI.Template, not whatever the hive happens to hold (F2).
installed_template_version() {
  dotnet new uninstall 2>/dev/null | awk -v pkg="$1" '
    $1==pkg      { inpkg=1; next }
    inpkg && $1=="Version:" { print $2; exit }'
}
