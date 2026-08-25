# shellcheck shell=bash
# Installed-package lifecycle matrix shared by every provider lane (#432).

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

  mkdir -p "$root/work" "$root/readiness"
  cp -a "$fixture/work/$work_id" "$root/work/"
  cp -a "$fixture/readiness/$work_id" "$root/readiness/"
  if [[ "$lane" == typed-sdd ]]; then
    fsgg-sdd typed-sdd migrate --root "$root" --work "$work_id" \
      --source "work/$work_id/spec.md" --accept >"$report_root/$lane.completion-migrate.json"
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
  local lane root descriptor report actual
  local explicit_sdd_parameters=""

  mkdir -p "$matrix_root"
  for lane in none sdd typed-sdd omitted; do
    root="$matrix_root/$lane"
    mkdir -p "$root/.fsgg"
    descriptor="$root/.fsgg/providers.yml"
    cp "$LANE_REPO_ROOT/providers/$provider.providers.yml" "$descriptor"
    if [[ "$archive" != "published" ]]; then
      lane_pin_provider_to_archive "$descriptor" "$archive"
    fi

    local -a args=(--root "$root" --provider "$provider" --no-update --json)
    local parameter
    for parameter in "${provider_params[@]}"; do
      args+=(--param "$parameter")
    done
    if [[ "$lane" != omitted ]]; then
      args+=(--param "lifecycle=$lane")
    fi

    report="$matrix_root/$lane.scaffold.json"
    if ! fsgg-sdd scaffold "${args[@]}" >"$report"; then
      echo "lifecycle matrix: $provider/$lane scaffold failed" >&2
      jq -r '.diagnostics[]? | "  \(.id): \(.message)"' "$report" >&2 || true
      return 1
    fi
    jq -e --arg provider "$provider" '.outcome == "succeeded" and .scaffold.providerName == $provider and .scaffold.providerInvoked == true' "$report" >/dev/null
    actual="$(jq -r '.effectiveParameters[] | select(.key == "lifecycle") | .value' "$root/.fsgg/scaffold-provenance.json")"
    [[ "$actual" == "${lane/omitted/sdd}" ]] || {
      echo "lifecycle matrix: $provider/$lane recorded '$actual', expected '${lane/omitted/sdd}'" >&2
      return 1
    }
    jq -e '.requiredMinimumCliVersion == "1.4.0-preview.1"' "$root/.fsgg/scaffold-provenance.json" >/dev/null

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
      if ! fsgg-sdd typed-sdd author --root "$root" --work matrix-spec --title "${provider} typed matrix" --agent composition --session "$provider" >"$matrix_root/$lane.author.json"; then
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
    fi

  done


  # Keep the first loop a clean-scaffold proof. Completion and builds intentionally run only after
  # omitted-vs-explicit SDD has compared the unpolluted file trees.
  for lane in none sdd typed-sdd omitted; do
    root="$matrix_root/$lane"
    assert_generated_lifecycle_completion "$provider" "$lane" "$root" "$matrix_root"
    assert_generated_product_restore_build_test "$provider" "$lane" "$root"
  done

  echo "PASS lifecycle matrix: $provider none/sdd/typed-sdd/omitted clean-create, complete, restore, build, and test from installed package"
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
