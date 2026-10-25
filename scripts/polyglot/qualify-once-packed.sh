#!/usr/bin/env bash
# Fixed four-product consumer under the canonical managed owner. No source/template
# install fallback, repack, arbitrary command port, or product runtime downloader.
set -euo pipefail
umask 077
: "${FSGG_QUALIFICATION_ROOT:?exclusive private operation root}"
: "${FSGG_ONCE_PACKED_ARCHIVE:?one qualified archive for all four products}"
: "${FSGG_QUALIFIED_DOTNET:?qualified SDK401 dotnet image}"
: "${FSGG_POLYGLOT_TOOL_DLL:?source-stage owned output}"
: "${FSGG_SDD_CLI_DLL:?qualified published SDD2.4 CLI}"
: "${FSGG_GOVERNANCE_CLI_DLL:?qualified published Governance1.15 CLI}"
: "${FSGG_SDD_SOURCE_ROOT:?immutable published SDD source including maintained driver}"
: "${FSGG_CATALOG_POLICY:?independently admitted complete catalog policy}"
: "${FSGG_CATALOG_PATH:?typed emitted catalog joined to archive}"
: "${FSGG_QUALIFICATION_WORK_END_MONOTONIC:?original outer work end}"
: "${FSGG_GOVERNANCE_CATALOG:?independently authored Governance workspace catalog directory}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
WORK="$FSGG_QUALIFICATION_ROOT"
[[ ! -e "$WORK" && ! -L "$WORK" ]] || exit 3
mkdir "$WORK"
sha256sum -- "$FSGG_ONCE_PACKED_ARCHIVE" > "$WORK/archive-before.sha256"
# The independently selected outer validates full input/native/toolchain/advisory
# identities and closes the environment before invoking this fixed source consumer.
python3 -I -B "$ROOT/tests/composition/polyglot/verify-package.py" "$ROOT" "$FSGG_ONCE_PACKED_ARCHIVE"
for provider in typescript-cli javascript-cli rust-cli go-cli; do
  private="$WORK/$provider"
  mkdir "$private" "$private/home" "$private/tmp" "$private/cache" "$private/nuget"
  # Actual HOME/CODEX_HOME stay unchanged; selected language homes remain private.
  export DOTNET_CLI_HOME="$private/home" NUGET_PACKAGES="$private/nuget" TMPDIR="$private/tmp"
  export NPM_CONFIG_CACHE="$private/cache/npm" npm_config_cache="$private/cache/npm" GOCACHE="$private/cache/go-build" GOMODCACHE="$private/cache/go-mod"
  if [[ "$provider" == typescript-cli || "$provider" == javascript-cli ]]; then
    : "${FSGG_NPM_INPUT_CACHE:?independently sealed offline npm/TypeScript cache required}"
    [[ -d "$FSGG_NPM_INPUT_CACHE" && ! -L "$FSGG_NPM_INPUT_CACHE" ]] || exit 3
    cp -R -- "$FSGG_NPM_INPUT_CACHE" "$private/cache/npm"
  fi
  # Rust's separately qualified prepopulated homes are supplied by the admitted
  # edge; do not create empty homes, copy global caches or auto-provision a toolchain.
  case "$provider" in
    rust-cli) advisory_role=FSGG_RUST_ADVISORY ;;
    go-cli) advisory_role=FSGG_GO_ADVISORY ;;
    *) advisory_role='' ;;
  esac
  if [[ -n "$advisory_role" ]]; then
    for field in ROOT MANIFEST MANIFEST_SHA256 SOURCE_COMMIT SOURCE_EPOCH; do
      input="${advisory_role}_$field"
      [[ -n "${!input:-}" ]] || { echo "missing independently qualified $input" >&2; exit 3; }
      export "FSGG_ADVISORY_$field=${!input}"
    done
  fi
  "$FSGG_QUALIFIED_DOTNET" exec --fx-version 10.0.12 "$FSGG_POLYGLOT_TOOL_DLL" fixture "$provider" "$FSGG_CATALOG_PATH" "$FSGG_CATALOG_POLICY" "$FSGG_ONCE_PACKED_ARCHIVE" "$private/request.json"
  python3 -I -B "$ROOT/scripts/polyglot/write-acceptance-config.py" "$provider" "$private"
  python3 -I -B "$FSGG_SDD_SOURCE_ROOT/scripts/catalog-cli-acceptance.py" --config "$private/config.json" --output "$private/catalog-acceptance" --case all
  target="$private/catalog-acceptance/positive-target"
  provenance="$target/.fsgg/scaffold-provenance.json"
  # Governance senses source state through git: the scaffolded product is a committed work tree.
  git -C "$target" init -q
  git -C "$target" add -A
  git -C "$target" -c user.name=fsgg-qualification -c user.email=qualification@invalid -c commit.gpgsign=false commit -q -m 'scaffolded product'
  cp -- "$FSGG_GOVERNANCE_CATALOG"/*.yml "$target/.fsgg/"
  git -C "$target" add -A
  git -C "$target" -c user.name=fsgg-qualification -c user.email=qualification@invalid -c commit.gpgsign=false commit -q -m 'governance workspace catalog'
  provenance_digest="$(sha256sum -- "$provenance")"; provenance_digest="${provenance_digest%% *}"
  policy_digest="$(sha256sum -- "$FSGG_CATALOG_POLICY")"; policy_digest="${policy_digest%% *}"
  # Recompute remaining time from the one original outer work clock. No per-product
  # clock renewal or declared unsupported/race skip can create a qualification.
  FSGG_VERIFY_WORK_SECONDS="$(python3 -I -B "$ROOT/scripts/polyglot/remaining-work.py")"
  # Governance measures both ends from one start: the cleanup end is the work end plus its grace.
  FSGG_VERIFY_CLEANUP_SECONDS=$((FSGG_VERIFY_WORK_SECONDS + 60))
  export FSGG_VERIFY_WORK_SECONDS FSGG_VERIFY_CLEANUP_SECONDS
  "$FSGG_QUALIFIED_DOTNET" exec --fx-version 10.0.12 "$FSGG_GOVERNANCE_CLI_DLL" verify --repo "$target" --json --verify-out "$private/verify.json" --cost-budget-out "$private/cost-budget.json" --provenance-out "$private/verify-provenance.json" --paths display-name.txt README.md toolchain-lock.json security-policy.json scripts/operations.sh scripts/security.sh scripts/security-result.py .gitignore --provider-provenance "$provenance" --provider-provenance-sha256 "$provenance_digest" --provider-policy "$FSGG_CATALOG_POLICY" --provider-policy-sha256 "$policy_digest" --provider-platform linux-x64 > "$private/governance-verify.stdout.json" 2> "$private/governance-verify.stderr.log"
  if [[ "$provider" == go-cli ]]; then
    : "${FSGG_ADVISORY_ROOT:?qualified Go database required}"
    python3 -I -B "$ROOT/scripts/polyglot/check-security-results.py" "$provider" "$target" "file://$FSGG_ADVISORY_ROOT"
  else
    python3 -I -B "$ROOT/scripts/polyglot/check-security-results.py" "$provider" "$target"
  fi
  sha256sum --check --strict "$WORK/archive-before.sha256"
done
# Passing fixed commands is not publication authority. The independent consumer
# must join every required capability/evidence decision, scanner finding set,
# source/packed/receiver provenance and original retirement before acceptance.
