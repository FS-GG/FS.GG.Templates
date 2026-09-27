# shellcheck shell=bash
# Installed-package lifecycle matrix shared by every provider lane (#432).

ensure_typed_sdd_cache() {
  local report_root="$1"
  local quint_sha=939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f
  local lmt_sha=37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10
  local lmt_source_sha=88bc47acae2c26919ab96a5cafa80b12fac762092c57840a2baad1afcc7feda3
  local go_archive_sha=cb2396bae64183cdccf81a9a6df0aea3bce9511fc21469fb89a0c00470088073
  local cache="${FSGG_TYPED_SDD_CACHE:-$DOTNET_CLI_HOME/typed-sdd-cache}"
  local tools="${FSGG_TYPED_SDD_TOOLS:-$DOTNET_CLI_HOME/typed-sdd-tools}"
  local quint="${FSGG_TYPED_SDD_QUINT_BIN:-${QUINT_BIN:-}}"
  local lmt="${FSGG_TYPED_SDD_LMT_BIN:-${LMT_BIN:-}}"

  mkdir -p "$cache" "$tools"
  if [[ -z "$quint" && -f "$cache/objects/$quint_sha" ]]; then
    quint="$cache/objects/$quint_sha"
  fi
  if [[ -z "$lmt" && -f "$cache/objects/$lmt_sha" ]]; then
    lmt="$cache/objects/$lmt_sha"
  fi

  if [[ -z "$quint" ]]; then
    command -v curl >/dev/null || {
      echo "lifecycle matrix: curl is required to acquire the qualified Quint object" >&2
      return 1
    }
    quint="$tools/quint-linux-amd64"
    curl --fail --location --retry 3 \
      https://github.com/quint-co/quint/releases/download/v0.32.0/quint-linux-amd64 \
      --output "$quint"
  fi

  if [[ -z "$lmt" ]]; then
    command -v curl >/dev/null || {
      echo "lifecycle matrix: curl is required to acquire the qualified lmt build inputs" >&2
      return 1
    }
    command -v tar >/dev/null || {
      echo "lifecycle matrix: tar is required to extract the qualified Go toolchain" >&2
      return 1
    }

    local build_inputs="$cache/build-inputs"
    local go_archive="$build_inputs/$go_archive_sha"
    local go_root go
    mkdir -p "$build_inputs"

    if [[ -f "$go_archive" ]]; then
      if ! printf '%s  %s\n' "$go_archive_sha" "$go_archive" | sha256sum --check --strict --status; then
        echo "lifecycle matrix: selected cache contains a conflicting Go 1.24.1 archive object" >&2
        return 1
      fi
    else
      local downloaded_go
      downloaded_go="$(mktemp "$build_inputs/.go1.24.1.linux-amd64.XXXXXX")"
      curl --fail --location --retry 3 --retry-all-errors --silent --show-error \
        https://go.dev/dl/go1.24.1.linux-amd64.tar.gz --output "$downloaded_go"
      if ! printf '%s  %s\n' "$go_archive_sha" "$downloaded_go" | sha256sum --check --strict --status; then
        echo "lifecycle matrix: downloaded Go 1.24.1 archive failed checksum verification" >&2
        rm -f "$downloaded_go"
        return 1
      fi
      mv "$downloaded_go" "$go_archive"
    fi
    if ! printf '%s  %s\n' "$go_archive_sha" "$go_archive" | sha256sum --check --strict --status; then
      echo "lifecycle matrix: cached Go 1.24.1 archive failed checksum verification" >&2
      return 1
    fi

    # Extract anew from the verified content-addressed archive. Reusing an extracted tree
    # would trust mutable cached files that are not covered by the archive checksum.
    go_root="$(mktemp -d "$tools/go1.24.1-linux-amd64.XXXXXX")"
    tar -xzf "$go_archive" -C "$go_root"
    go="$go_root/go/bin/go"
    if [[ "$(GOTOOLCHAIN=local "$go" version)" != 'go version go1.24.1 linux/amd64' ]]; then
      echo "lifecycle matrix: selected cache Go toolchain is not exact go1.24.1 linux/amd64" >&2
      return 1
    fi

    curl --fail --location --retry 3 \
      https://raw.githubusercontent.com/driusan/lmt/62fe18f2f6a6e11c158ff2b2209e1082a4fcd59c/main.go \
      --output "$tools/lmt-main.go"
    if ! printf '%s  %s\n' "$lmt_source_sha" "$tools/lmt-main.go" | sha256sum --check --strict --status; then
      echo "lifecycle matrix: downloaded lmt source failed checksum verification" >&2
      return 1
    fi
    GOTOOLCHAIN=local GO111MODULE=off CGO_ENABLED=1 "$go" build -trimpath \
      -ldflags '-buildid=IvXAt1kJ-3iINki1alCT/Ut12KGabgkWIkwVpw-xO/c4zkZMLAubfWHvjZOY8o/8-oR_8tNNndNgfMVoD8F -B 0x03d1703027f57ed4dd2ba90b7cdfc8cdea2815da' \
      -o "$tools/lmt" "$tools/lmt-main.go"
    lmt="$tools/lmt"
    if ! printf '%s  %s\n' "$lmt_sha" "$lmt" | sha256sum --check --strict --status; then
      echo "lifecycle matrix: exact Go 1.24.1 lmt build produced unqualified bytes" >&2
      return 1
    fi
  fi

  if ! fsgg-sdd typed-sdd provision --cache "$cache" --quint "$quint" --lmt "$lmt" \
    >"$report_root/typed-sdd-provision.json"; then
    echo "lifecycle matrix: exact typed SDD cache provisioning failed" >&2
    jq -r '.diagnostics[]? | "  \(.id): \(.message)"' "$report_root/typed-sdd-provision.json" >&2 || true
    return 1
  fi
  jq -e --arg cache "$(cd "$cache" && pwd)" \
    '.outcome == "succeeded" and .profile == "fsgg-quint-profile/2" and .cacheRoot == $cache and (.objects | length) == 2' \
    "$report_root/typed-sdd-provision.json" >/dev/null
  TYPED_SDD_CACHE="$cache"
}

lifecycle_tree_manifest() {
  local root="$1" relative digest

  # Compare the complete clean scaffold, not a hand-picked lifecycle allowlist. project.id is
  # derived from the output folder name (`sdd` vs
  # `omitted`), so normalize only that field before hashing. Everything else — AGENTS/CLAUDE guidance,
  # all .fsgg policy/config, tool manifests, every skill root, work/readiness, and product bytes — is
  # required to have the same path and content.
  while IFS= read -r relative; do
    if [[ -d "$root/$relative" ]]; then
      printf 'd  %s\n' "$relative"
    elif [[ -L "$root/$relative" ]]; then
      printf 'l  %s -> %s\n' "$relative" "$(readlink "$root/$relative")"
    else
      if [[ "$relative" == .fsgg/project.yml ]]; then
        digest="$(sed -E 's/^([[:space:]]*id:).*/\1 <normalized-output-root>/' "$root/$relative" | sha256sum | cut -d' ' -f1)"
      else
        digest="$(sha256sum "$root/$relative" | cut -d' ' -f1)"
      fi
      printf 'f  %s  %s\n' "$digest" "$relative"
    fi
  done < <(cd "$root" && find . -mindepth 1 \
    -not -path './.git/*' -not -path './.git' \
    -print | sed 's#^./##' | LC_ALL=C sort)
}

assert_lifecycle_trees_equivalent() {
  local explicit_root="$1" omitted_root="$2" output="${3:-/dev/null}"
  local explicit_manifest omitted_manifest
  explicit_manifest="$(mktemp)"
  omitted_manifest="$(mktemp)"
  lifecycle_tree_manifest "$explicit_root" >"$explicit_manifest"
  lifecycle_tree_manifest "$omitted_root" >"$omitted_manifest"
  if ! diff -u "$explicit_manifest" "$omitted_manifest" >"$output"; then
    echo "lifecycle matrix: omitted lifecycle tree differs from explicit sdd (see $output)" >&2
    return 1
  fi
}

assert_lifecycle_tree_equivalence_can_fire() {
  local fixture_root="$1"
  mkdir -p "$fixture_root/explicit/.fsgg" "$fixture_root/explicit/.agents/skills/example" \
    "$fixture_root/omitted/.fsgg" "$fixture_root/omitted/.agents/skills/example"
  printf 'schemaVersion: 1\nlifecycle: sdd\n' >"$fixture_root/explicit/.fsgg/sdd.yml"
  printf 'schemaVersion: 1\nagents: []\n' >"$fixture_root/explicit/.fsgg/agents.yml"
  printf 'fixture skill\n' >"$fixture_root/explicit/.agents/skills/example/SKILL.md"
  cp -a "$fixture_root/explicit/.fsgg/sdd.yml" "$fixture_root/omitted/.fsgg/sdd.yml"
  cp -a "$fixture_root/explicit/.fsgg/agents.yml" "$fixture_root/omitted/.fsgg/agents.yml"
  cp -a "$fixture_root/explicit/.agents/skills/example/SKILL.md" "$fixture_root/omitted/.agents/skills/example/SKILL.md"
  assert_lifecycle_trees_equivalent "$fixture_root/explicit" "$fixture_root/omitted"
  printf 'mutated: true\n' >>"$fixture_root/omitted/.fsgg/agents.yml"
  if assert_lifecycle_trees_equivalent "$fixture_root/explicit" "$fixture_root/omitted" "$fixture_root/mutation.diff" 2>/dev/null; then
    echo "lifecycle tree equivalence mutation unexpectedly passed" >&2
    return 1
  fi
  echo "PASS lifecycle tree equivalence can fire on content drift"
}

assert_generated_product_restore_build_test() {
  local provider="$1" lane="$2" root="$3" solution
  solution="$(find "$root" -maxdepth 1 \( -name '*.slnx' -o -name '*.sln' \) -print -quit)"
  [[ -n "$solution" ]] || {
    echo "lifecycle matrix: $provider/$lane emitted no root solution for restore/build/test" >&2
    return 1
  }
  (
    cd "$root"
    dotnet restore "$(basename "$solution")" --locked-mode --nologo
    dotnet build "$(basename "$solution")" --no-restore --nologo
    dotnet test "$(basename "$solution")" --no-build --nologo
  ) >"$root/.fsgg/lifecycle-build-test.log" 2>&1 || {
    echo "lifecycle matrix: $provider/$lane restore/build/test failed (see $root/.fsgg/lifecycle-build-test.log)" >&2
    tail -n 120 "$root/.fsgg/lifecycle-build-test.log" >&2
    return 1
  }
}

assert_generated_lifecycle_completion() {
  local provider="$1" lane="$2" root="$3" report_root="$4"
  local fixture="$LANE_REPO_ROOT/tests/composition/fixtures/lifecycle-completion"
  local work_id="typed-sdd-p4-templates"

  if [[ "$lane" == none ]]; then
    # FS.GG.SDD specs/031 FR-005 keeps the inert orchestrator skeleton/config/skills identical
    # across provider values; Freeform means no active specification process, not no platform files.
    # Therefore applicability is graded at the authored lifecycle boundary.
    ! find "$root/work" "$root/readiness" -mindepth 1 -print -quit | grep -q .
    ! find "$root" -name typed-authority.json -print -quit | grep -q .
    echo "PASS lifecycle completion: $provider/none is explicitly not applicable and owns no lifecycle state"
    return 0
  fi

  if [[ "$lane" == spec-kit ]]; then
    # Legacy Spec Kit remains a separately retiring compatibility lane. It does not own Standard
    # or Typed SDD work/readiness artifacts in this repository. The installed scaffolder must still
    # preserve its explicit wire value and materialize the product rather than reject or alias it;
    # retirement semantics remain owned upstream and are deliberately not widened by P4.
    ! find "$root/work" "$root/readiness" -mindepth 1 -print -quit 2>/dev/null | grep -q .
    echo "PASS lifecycle compatibility: $provider/spec-kit remains explicitly selectable and owns no Standard/Typed SDD work state"
    return 0
  fi

  mkdir -p "$root/work" "$root/readiness"
  cp -a "$fixture/work/$work_id" "$root/work/"
  cp -a "$fixture/readiness/$work_id" "$root/readiness/"
  # SDD 2.x requires a passing local report to belong to the exact Git candidate it supports.
  # The generated matrix workspace is disposable and starts without a repository, so record the
  # transplanted terminal fixture before replaying it. Later lifecycle writes remain visible as
  # candidate changes; this commit only establishes honest provenance for the copied report bytes.
  git -C "$root" init -q
  git -C "$root" add "work/$work_id" "readiness/$work_id"
  git -C "$root" -c user.name=composition -c user.email=composition@example.invalid \
    commit -qm 'test: seed lifecycle completion fixture'
  if [[ "$lane" == typed-sdd ]]; then
    # The terminal fixture is a manifest-v1 F# authority. Keep its migration on that explicit
    # backend; the clean matrix-spec authoring above exercises the installed Quint default with
    # the caller-selected cache. Letting a CLI default change reinterpret this historical fixture
    # as a v2 Quint migration would test a different semantic payload.
    fsgg-sdd typed-sdd migrate --root "$root" --work "$work_id" \
      --source "work/$work_id/spec.md" --backend fsharp-specification-v1 \
      --accept >"$report_root/$lane.completion-migrate.json"
    jq -e '.outcome == "succeeded" and .classification == "Migrated"' "$report_root/$lane.completion-migrate.json" >/dev/null
    fsgg-sdd plan --root "$root" --work "$work_id" --accept-upstream --json >"$report_root/$lane.completion-plan.json"
    jq -e '.outcome == "succeeded" or .outcome == "succeededWithWarnings"' "$report_root/$lane.completion-plan.json" >/dev/null
  fi

  # A transplanted terminal fixture deliberately begins with stale generated views. Refresh may
  # report partially-blocked while updating work-model because downstream analysis/verify/ship
  # still bind the prior root; the immediately following canonical replay is what closes them.
  fsgg-sdd refresh --root "$root" --work "$work_id" --json >"$report_root/$lane.completion-refresh.json" || true
  jq -e '.refresh.status == "refreshed-current" or .refresh.readiness == "refreshReady"' "$report_root/$lane.completion-refresh.json" >/dev/null
  fsgg-sdd analyze --root "$root" --work "$work_id" --json >"$report_root/$lane.completion-analyze.json"
  jq -e '.analysis.status == "implementationReady"' "$report_root/$lane.completion-analyze.json" >/dev/null
  fsgg-sdd evidence --root "$root" --work "$work_id" \
    --sync-observed-run "work/$work_id/lifecycle-evidence.junit.xml" --json >"$report_root/$lane.completion-evidence-sync.json"
  fsgg-sdd evidence --root "$root" --work "$work_id" --json >"$report_root/$lane.completion-evidence.json"
  jq -e '.evidence.status == "evidenceReady" and (.diagnostics | length) == 0' "$report_root/$lane.completion-evidence.json" >/dev/null
  fsgg-sdd verify --root "$root" --work "$work_id" --json >"$report_root/$lane.completion-verify.json"
  jq -e '.verification.status == "verificationReady"' "$report_root/$lane.completion-verify.json" >/dev/null
  fsgg-sdd ship --root "$root" --work "$work_id" --json >"$report_root/$lane.completion-ship.json"
  jq -e '.ship.status == "shipReady"' "$report_root/$lane.completion-ship.json" >/dev/null
  echo "PASS lifecycle completion: $provider/$lane reached shipReady"
}

assert_provider_lifecycle_matrix() {
  local provider="$1" archive="$2" matrix_root="$3"
  shift 3
  local -a provider_params=("$@")
  local lane root descriptor report actual direct_legacy
  local explicit_sdd_parameters=""

  mkdir -p "$matrix_root"
  ensure_typed_sdd_cache "$matrix_root"
  for lane in none sdd typed-sdd spec-kit omitted; do
    root="$matrix_root/$lane"
    mkdir -p "$root/.fsgg"
    descriptor="$root/.fsgg/providers.yml"
    cp "$LANE_REPO_ROOT/providers/$provider.providers.yml" "$descriptor"
    if [[ "$archive" != "published" ]]; then
      lane_pin_provider_to_archive "$descriptor" "$archive"
    fi

    direct_legacy=false
    local -a args=(--root "$root" --provider "$provider" --no-update --json)
    local parameter
    for parameter in "${provider_params[@]}"; do
      args+=(--param "$parameter")
    done
    if [[ "$lane" != omitted ]]; then
      args+=(--param "lifecycle=$lane")
    fi

    report="$matrix_root/$lane.scaffold.json"
    if [[ "$provider" == rendering && "$lane" == spec-kit && "$archive" == published ]]; then
      # Rendering's retiring Spec Kit payload predates the SDD provider ownership contract and
      # intentionally owns AGENTS.md plus .claude skills. The modern provider wrapper correctly
      # refuses that overlap after seeding its own skeleton, so compatibility must be proved at
      # the published template's native boundary. The four Templates-owned providers above still
      # exercise spec-kit through fsgg-sdd scaffold and its provenance contract.
      direct_legacy=true
      local -a legacy_args=(dotnet new fs-gg-ui -o "$root" --force --lifecycle spec-kit)
      for parameter in "${provider_params[@]}"; do
        legacy_args+=("--${parameter%%=*}" "${parameter#*=}")
      done
      if ! "${legacy_args[@]}" >"$report" 2>&1; then
        echo "lifecycle matrix: $provider/$lane native legacy scaffold failed" >&2
        tail -n 80 "$report" >&2
        return 1
      fi
      test -d "$root/.specify"
    elif ! fsgg-sdd scaffold "${args[@]}" >"$report"; then
      echo "lifecycle matrix: $provider/$lane scaffold failed" >&2
      jq -r '.diagnostics[]? | "  \(.id): \(.message)"' "$report" >&2 || true
      return 1
    fi
    if [[ "$direct_legacy" == false ]]; then
      jq -e --arg provider "$provider" '.outcome == "succeeded" and .scaffold.providerName == $provider and .scaffold.providerInvoked == true' "$report" >/dev/null
      actual="$(jq -r '.effectiveParameters[] | select(.key == "lifecycle") | .value' "$root/.fsgg/scaffold-provenance.json")"
      [[ "$actual" == "${lane/omitted/sdd}" ]] || {
        echo "lifecycle matrix: $provider/$lane recorded '$actual', expected '${lane/omitted/sdd}'" >&2
        return 1
      }
      jq -e '.requiredMinimumCliVersion == "1.4.0-preview.1"' "$root/.fsgg/scaffold-provenance.json" >/dev/null
    fi

    if [[ "$lane" == sdd ]]; then
      explicit_sdd_parameters="$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")"
    elif [[ "$lane" == omitted ]]; then
      [[ "$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" == "$explicit_sdd_parameters" ]] || {
        echo "lifecycle matrix: $provider omitted parameters differ from explicit sdd" >&2
        return 1
      }
      assert_lifecycle_trees_equivalent "$matrix_root/sdd" "$root" "$matrix_root/omitted-vs-sdd.diff"
    elif [[ "$lane" == typed-sdd ]]; then
      local provenance_before
      provenance_before="$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")"
      if ! fsgg-sdd typed-sdd author --root "$root" --work matrix-spec --title "${provider} typed matrix" \
        --agent composition --session "$provider" --backend fsharp-specification-v1 >"$matrix_root/$lane.author.json"; then
        echo "lifecycle matrix: $provider typed authoring failed" >&2
        return 1
      fi
      fsgg-sdd typed-sdd inspect --root "$root" --work matrix-spec >"$matrix_root/$lane.inspect.json"
      jq -e '.outcome == "succeeded"' "$matrix_root/$lane.inspect.json" >/dev/null
      test -f "$root/work/matrix-spec/specification.fsx"
      test -f "$root/work/matrix-spec/spec.md"
      test -f "$root/readiness/matrix-spec/specification.normalized.json"
      test -f "$root/readiness/matrix-spec/typed-authority.json"
      cmp "$root/.agents/skills/fs-gg-sdd-typed-author/SKILL.md" "$root/.claude/skills/fs-gg-sdd-typed-author/SKILL.md"
      fsgg-sdd refresh --root "$root" --work matrix-spec --json >"$matrix_root/$lane.refresh.json"
      jq -e '.outcome == "noChange" and .refresh.status == "early-stage"' "$matrix_root/$lane.refresh.json" >/dev/null
      fsgg-sdd upgrade --root "$root" --yes --json >"$matrix_root/$lane.upgrade.json"
      jq -e '(.outcome == "noChange" or .outcome == "succeeded") and .upgrade.residualDrift == false' "$matrix_root/$lane.upgrade.json" >/dev/null
      [[ "$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" == "$provenance_before" ]]
      fsgg-sdd typed-sdd inspect --root "$root" --work matrix-spec >"$matrix_root/$lane.post-upgrade-inspect.json"
      jq -e '.outcome == "succeeded"' "$matrix_root/$lane.post-upgrade-inspect.json" >/dev/null
      # Installed SDD 2.x defaults new typed authority to Quint and requires an explicit cache.
      # Exercise that boundary separately from the historical manifest-v1 completion fixture so
      # its backend does not change merely because the installed CLI's default did.
      if ! fsgg-sdd typed-sdd author --root "$root" --work matrix-quint-cache \
        --title "${provider} Quint cache matrix" --agent composition --session "$provider-quint" \
        --cache "$TYPED_SDD_CACHE" >"$matrix_root/$lane.quint-author.json"; then
        echo "lifecycle matrix: $provider cached Quint authoring failed" >&2
        return 1
      fi
      fsgg-sdd typed-sdd inspect --root "$root" --work matrix-quint-cache >"$matrix_root/$lane.quint-inspect.json"
      jq -e '.outcome == "succeeded" and .classification == "quint-specification-v1"' \
        "$matrix_root/$lane.quint-inspect.json" >/dev/null
      jq -e '.schemaVersion == 2 and .backend == "quint-specification-v1" and .profileIdentity == "fsgg-quint-profile/1"' \
        "$root/readiness/matrix-quint-cache/typed-authority.json" >/dev/null
    fi

  done


  # Keep the first loop a clean-scaffold proof. Completion and builds intentionally run only after
  # omitted-vs-explicit SDD has compared the unpolluted file trees.
  for lane in none sdd typed-sdd spec-kit omitted; do
    root="$matrix_root/$lane"
    assert_generated_lifecycle_completion "$provider" "$lane" "$root" "$matrix_root"
    assert_generated_product_restore_build_test "$provider" "$lane" "$root"
  done

  echo "PASS lifecycle matrix: $provider none/sdd/typed-sdd/spec-kit/omitted clean-create, compatibility/completion, restore, build, and test from installed package"
}

assert_typed_lifecycle_controls() {
  local source_root="$1" controls_root="$2" command_root manifest canonical digest control expected
  mkdir -p "$controls_root"

  for control in wrong-lifecycle stale-projection unsupported-extension direct-edit missing-compiler; do
    cp -a "$source_root" "$controls_root/$control"
  done

  manifest="$controls_root/wrong-lifecycle/readiness/matrix-spec/typed-authority.json"
  jq '.lifecycle="sdd"' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest"
  printf ' ' >>"$controls_root/stale-projection/readiness/matrix-spec/specification.normalized.json"
  manifest="$controls_root/unsupported-extension/readiness/matrix-spec/typed-authority.json"
  jq '.extensionIdentity="unsupported/v9"' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest"
  printf '\n// direct edit control\n' >>"$controls_root/direct-edit/work/matrix-spec/specification.fsx"
  canonical="$controls_root/missing-compiler/work/matrix-spec/specification.fsx"
  printf '\nfailwith "compiler unavailable control"\n' >>"$canonical"
  digest="$(sha256sum "$canonical" | cut -d' ' -f1)"
  manifest="$controls_root/missing-compiler/readiness/matrix-spec/typed-authority.json"
  jq --arg digest "$digest" '.canonicalSha256=$digest' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest"

  while read -r control expected; do
    command_root="$controls_root/$control"
    if fsgg-sdd specify --root "$command_root" --work matrix-spec --input $'value: control\nscope: control\nrequirement: control' --json >"$controls_root/$control.json"; then
      echo "typed lifecycle control '$control' unexpectedly passed" >&2
      return 1
    fi
    jq -e --arg expected "$expected" '[.diagnostics[].id] | index($expected) != null' "$controls_root/$control.json" >/dev/null || {
      echo "typed lifecycle control '$control' failed without $expected" >&2
      return 1
    }
  done <<'EOF'
wrong-lifecycle typedSdd.wrongLifecycle
stale-projection typedSdd.staleProjection
unsupported-extension typedSdd.extensionIdentityMismatch
direct-edit typedSdd.directCanonicalEdit
missing-compiler typedSdd.compilerUnavailable
EOF

  if fsgg-sdd typed-sdd author --root "$controls_root/agent-unavailable" --work control >"$controls_root/agent-unavailable.json"; then
    echo "typed lifecycle agent-unavailable control unexpectedly passed" >&2
    return 1
  fi
  jq -e '[.diagnostics[].id] | index("typedSdd.authoringAgentUnavailable") != null' "$controls_root/agent-unavailable.json" >/dev/null
  echo "PASS typed lifecycle controls: wrong lifecycle, stale projection, unsupported extension, direct edit, missing compiler, agent unavailable"
}
