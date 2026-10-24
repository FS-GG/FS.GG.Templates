# Fixed product security commands, not a transport executor or policy/admission authority.
# The independent native edge must authenticate these task-private input roles BEFORE dispatch.
security_image() {
  image=$1
  expected=$2
  case "$image" in /*) ;; *) echo 'absolute qualified scanner image required' >&2; return 3;; esac
  [ -f "$image" ] && [ ! -L "$image" ] && [ -x "$image" ] || return 3
  case "$expected" in *[!0-9a-f]*|'') return 3;; esac
  [ "${#expected}" -eq 64 ] || return 3
  observed=$(sha256sum -- "$image")
  [ "${observed%% *}" = "$expected" ] || { echo 'qualified scanner image differs' >&2; return 3; }
}
security_advisory() {
  : "${FSGG_ADVISORY_ROOT:?qualified advisory directory required}" "${FSGG_ADVISORY_MANIFEST:?qualified manifest required}" "${FSGG_ADVISORY_MANIFEST_SHA256:?independent manifest digest required}" "${FSGG_ADVISORY_SOURCE_COMMIT:?immutable source commit required}" "${FSGG_ADVISORY_SOURCE_EPOCH:?source timestamp required}"
  [ -d "$FSGG_ADVISORY_ROOT" ] && [ -f "$FSGG_ADVISORY_MANIFEST" ] && [ ! -L "$FSGG_ADVISORY_MANIFEST" ] || return 3
  case "$FSGG_ADVISORY_SOURCE_COMMIT" in *[!0-9a-f]*|'') return 3;; esac
  [ "${#FSGG_ADVISORY_SOURCE_COMMIT}" -eq 40 ] || return 3
  case "$FSGG_ADVISORY_SOURCE_EPOCH" in *[!0-9]*|'') return 3;; esac
  observed=$(sha256sum -- "$FSGG_ADVISORY_MANIFEST")
  [ "${observed%% *}" = "$FSGG_ADVISORY_MANIFEST_SHA256" ] || return 3
  now=$(date -u +%s)
  [ "$now" -ge "$FSGG_ADVISORY_SOURCE_EPOCH" ] && [ "$((now-FSGG_ADVISORY_SOURCE_EPOCH))" -le 604800 ] || { echo 'future/stale advisory inputs refused' >&2; return 3; }
  # Manifest paths are independently qualified contained regular inputs; no live database fallback.
  (cd "$FSGG_ADVISORY_ROOT" && sha256sum --check --strict "$FSGG_ADVISORY_MANIFEST")
}
security() {
  case "$FSGG_POLYGLOT_PROVIDER" in
    typescript-cli|javascript-cli)
      # info is the lowest severity: every reported vulnerability blocks, never audit fix.
      npm audit --json --audit-level=info --ignore-scripts --userconfig=/dev/null --globalconfig=/dev/null --registry=https://registry.npmjs.org > security-audit.json
      ;;
    rust-cli)
      : "${FSGG_CARGO_AUDIT:?qualified cargo-audit image required}" "${FSGG_CARGO_AUDIT_SHA256:?qualified image digest required}"
      security_image "$FSGG_CARGO_AUDIT" "$FSGG_CARGO_AUDIT_SHA256"
      [ "$("$FSGG_CARGO_AUDIT" --version)" = 'cargo-audit 0.22.2' ] || return 3
      security_advisory
      "$FSGG_CARGO_AUDIT" audit --db "$FSGG_ADVISORY_ROOT" --no-fetch --deny warnings --json > security-audit.json
      ;;
    go-cli)
      : "${FSGG_GOVULNCHECK:?qualified govulncheck image required}" "${FSGG_GOVULNCHECK_SHA256:?qualified image digest required}"
      security_image "$FSGG_GOVULNCHECK" "$FSGG_GOVULNCHECK_SHA256"
      security_advisory
      "$FSGG_GOVULNCHECK" -json -db "file://$FSGG_ADVISORY_ROOT" ./... > security-audit.json
      ;;
    *) echo 'closed provider security binding required' >&2; return 3;;
  esac
  [ -s security-audit.json ] || { echo 'missing raw security result refused' >&2; return 3; }
  # Qualification additionally parses the exact retained raw format and source/database joins.
}
