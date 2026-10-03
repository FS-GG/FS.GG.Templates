# shellcheck shell=bash
# Installed-package lifecycle matrix shared by every provider lane (#432).

lifecycle_tree_manifest() {
  local root="$1" relative digest
  [[ -d "$root" ]] || return 1

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
        digest="$(sed -E 's/^([[:space:]]*id:).*/\1 <normalized-output-root>/' "$root/$relative" | sha256sum | cut -d' ' -f1)" || return 1
      else
        digest="$(sha256sum "$root/$relative" | cut -d' ' -f1)" || return 1
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
  explicit_manifest="$(mktemp)" || return 1
  omitted_manifest="$(mktemp)" || return 1
  lifecycle_tree_manifest "$explicit_root" >"$explicit_manifest" || return 1
  lifecycle_tree_manifest "$omitted_root" >"$omitted_manifest" || return 1
  if ! diff -u "$explicit_manifest" "$omitted_manifest" >"$output"; then
    echo "lifecycle matrix: omitted lifecycle tree differs from explicit selection (see $output)" >&2
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
  cp -a "$fixture_root/explicit/.fsgg/sdd.yml" "$fixture_root/omitted/.fsgg/sdd.yml" || return 1
  cp -a "$fixture_root/explicit/.fsgg/agents.yml" "$fixture_root/omitted/.fsgg/agents.yml" || return 1
  cp -a "$fixture_root/explicit/.agents/skills/example/SKILL.md" "$fixture_root/omitted/.agents/skills/example/SKILL.md" || return 1
  assert_lifecycle_trees_equivalent "$fixture_root/explicit" "$fixture_root/omitted" || return 1
  printf 'mutated: true\n' >>"$fixture_root/omitted/.fsgg/agents.yml"
  if assert_lifecycle_trees_equivalent "$fixture_root/explicit" "$fixture_root/omitted" "$fixture_root/mutation.diff" 2>/dev/null; then
    echo "lifecycle tree equivalence mutation unexpectedly passed" >&2
    return 1
  fi
  echo "PASS lifecycle tree equivalence can fire on content drift"
}

lifecycle_report() {
  local report="$1" status=0
  shift
  "$@" >"$report" || status=$?
  if [[ -n "${FSGG_COMPOSITION_DIAGNOSTICS:-}" ]]; then
    mkdir -p "$FSGG_COMPOSITION_DIAGNOSTICS" || return 1
    cp "$report" "$FSGG_COMPOSITION_DIAGNOSTICS/$(basename "$report")" || return 1
    python3 - "$status" "$@" >"$FSGG_COMPOSITION_DIAGNOSTICS/$(basename "$report").execution.json" <<'PYEXEC' || return 1
import json, sys
print(json.dumps({"exitCode": int(sys.argv[1]), "argv": sys.argv[2:]}))
PYEXEC
  fi
  if [[ "$status" != 0 ]]; then
    echo "lifecycle command failed with exit $status: $* (report $report)" >&2
    cat "$report" >&2
  fi
  return "$status"
}

lifecycle_git() {
  local status=0
  git "$@" || status=$?
  if [[ -n "${FSGG_COMPOSITION_DIAGNOSTICS:-}" ]]; then
    mkdir -p "$FSGG_COMPOSITION_DIAGNOSTICS" || return 1
    python3 - "$status" "$@" >>"$FSGG_COMPOSITION_DIAGNOSTICS/foreground-git.jsonl" <<'PYGITCOMMAND' || return 1
import json, sys
print(json.dumps({"exitCode": int(sys.argv[1]), "argv": ["git", *sys.argv[2:]]}))
PYGITCOMMAND
  fi
  return "$status"
}

initialize_completion_candidate() {
  local root="$1" work_id="$2" report_root="$3" lane="$4" top
  root="$(cd "$root" && pwd)" || return 1
  if [[ ! -e "$root/.git" ]]; then
    lifecycle_git -C "$root" init --quiet || return 1
  fi
  top="$(lifecycle_git -C "$root" rev-parse --show-toplevel)" || return 1
  [[ "$top" == "$root" && -d "$root/.git" ]] || return 1
  # Foreground caller initialization owns this generated tree; private caches and build outputs
  # must never become durable fixture evidence. Git configuration is scoped to this one command.
  lifecycle_git -C "$root" add -- . ':!.fsgg/cache' ':!.fsgg/cache/**' \
    ':!.fsgg/lifecycle-test-state.*' ':!.fsgg/lifecycle-test-state.*/**' \
    ':(glob,exclude)**/bin/**' ':(glob,exclude)**/obj/**' ':(glob,exclude)**/node_modules/**' || return 1
  lifecycle_git -C "$root" ls-files --error-unmatch -- "work/$work_id/lifecycle-evidence.junit.xml" >/dev/null || return 1
  if ! lifecycle_git -C "$root" diff --cached --quiet; then
    lifecycle_git -C "$root" -c user.name='FS-GG composition fixture' \
      -c user.email='composition-fixture@fs-gg.invalid' -c commit.gpgsign=false \
      commit --quiet -m "Initialize generated lifecycle fixture candidate" || return 1
  fi
  lifecycle_git -C "$root" rev-parse HEAD >"$report_root/$lane.initial-commit.txt" || return 1
  if [[ -n "${FSGG_COMPOSITION_DIAGNOSTICS:-}" ]]; then
    mkdir -p "$FSGG_COMPOSITION_DIAGNOSTICS" || return 1
    python3 - "$root" "$work_id" >"$FSGG_COMPOSITION_DIAGNOSTICS/$lane.initial-git.json" <<'PYGIT' || return 1
import json, subprocess, sys
root, work_id = sys.argv[1:]
run = lambda *args: subprocess.check_output(["git", "-C", root, *args], text=True).strip()
print(json.dumps({"head": run("rev-parse", "HEAD"),
                  "durableEvidence": run("ls-files", "--error-unmatch", "--", f"work/{work_id}/lifecycle-evidence.junit.xml"),
                  "trackedPaths": run("ls-files").splitlines()}))
PYGIT
  fi
}

assert_completion_refresh() {
  local report="$1" work_model="$2" previous_digest="$3" work_id="$4" command_status="${5:-0}" status current_digest
  status="$(jq -r '.refresh.status' "$report")" || return 1
  if [[ "$status" == partially-blocked ]]; then
    [[ "$command_status" == 1 ]] || return 1
    # Only transplanted downstream projections may be stale here. The canonical commands below
    # must still reach all terminal gates; an unrelated blocked refresh is never admitted.
    jq -e --arg base "readiness/$work_id/" '
      .outcome == "blocked" and
      (.refresh.refreshedViewIds | index("work-model") != null) and
      (.refresh.blockedViewIds | length > 0) and
      (.refresh.blockedViewIds | all(. == "analysis" or . == "governance-handoff" or
        . == "ship" or . == "ship-verdict" or . == "summary" or . == "verify")) and
      (.diagnostics | length > 0) and
      (.diagnostics | all(
        (.id == "refresh.staleView" and .severity == "warning" and
          (.artifact == ($base + "analysis.json") or .artifact == ($base + "ship.json") or
           .artifact == ($base + "ship-verdict.json") or .artifact == ($base + "verify.json"))) or
        (.id == "refresh.unrenderableSummary" and .severity == "error" and
          .artifact == ($base + "summary.md"))))
    ' "$report" >/dev/null || return 1
    current_digest="$(sha256sum "$work_model" | cut -d' ' -f1)" || return 1
    [[ "$current_digest" != "$previous_digest" ]] || return 1
  else
    [[ "$command_status" == 0 ]] || return 1
    jq -e '(.outcome == "noChange" or .outcome == "succeeded" or .outcome == "succeededWithWarnings") and
      (.refresh.status == "refreshed-current" or .refresh.readiness == "refreshReady") and
      (.diagnostics | all(.severity != "error"))' "$report" >/dev/null || return 1
  fi
}

assert_generated_product_restore_build_test() {
  local provider="$1" lane="$2" root="$3" solution
  root="$(cd "$root" && pwd)" || return 1
  solution="$(find "$root" -maxdepth 1 \( -name '*.slnx' -o -name '*.sln' \) -print -quit)"
  [[ -n "$solution" ]] || {
    echo "lifecycle matrix: $provider/$lane emitted no root solution for restore/build/test" >&2
    return 1
  }
  (
    cd "$root" || return 1
    dotnet restore "$(basename "$solution")" --locked-mode --nologo || return 1
    dotnet build "$(basename "$solution")" --no-restore --nologo || return 1
    local test_state test_data test_config
    test_state="$(mktemp -d "$root/.fsgg/lifecycle-test-state.XXXXXX")" || return 1
    test_data="$test_state/data"
    test_config="$test_state/config"
    mkdir -p "$test_data" "$test_config" || return 1
    XDG_DATA_HOME="$test_data" XDG_CONFIG_HOME="$test_config" \
      dotnet test "$(basename "$solution")" --no-build --nologo
  ) >"$root/.fsgg/lifecycle-build-test.log" 2>&1 || {
    echo "lifecycle matrix: $provider/$lane restore/build/test failed (see $root/.fsgg/lifecycle-build-test.log)" >&2
    tail -n 120 "$root/.fsgg/lifecycle-build-test.log" >&2
    return 1
  }
}

assert_generated_lifecycle_completion() {
  local provider="$1" lane="$2" root="$3" report_root="$4" effective_lane="${5:-$2}"
  local fixture="$LANE_REPO_ROOT/tests/composition/fixtures/lifecycle-completion"
  local work_id="typed-sdd-p4-templates"

  if [[ "$lane" == none ]]; then
    # FS.GG.SDD specs/031 FR-005 keeps the inert orchestrator skeleton/config/skills identical
    # across provider values; Freeform means no active specification process, not no platform files.
    # Therefore applicability is graded at the authored lifecycle boundary.
    ! find "$root/work" "$root/readiness" -mindepth 1 -print -quit | grep -q . || return 1
    ! find "$root" -name typed-authority.json -print -quit | grep -q . || return 1
    echo "PASS lifecycle completion: $provider/none is explicitly not applicable and owns no lifecycle state"
    return 0
  fi

  if [[ "$lane" == spec-kit ]]; then
    # Legacy Spec Kit remains a separately retiring compatibility lane. It does not own Standard
    # or Typed SDD work/readiness artifacts in this repository. The installed scaffolder must still
    # preserve its explicit wire value and materialize the product rather than reject or alias it;
    # retirement semantics remain owned upstream and are deliberately not widened by P4.
    ! find "$root/work" "$root/readiness" -mindepth 1 -print -quit 2>/dev/null | grep -q . || return 1
    echo "PASS lifecycle compatibility: $provider/spec-kit remains explicitly selectable and owns no Standard/Typed SDD work state"
    return 0
  fi

  mkdir -p "$root/work" "$root/readiness" || return 1
  cp -a "$fixture/work/$work_id" "$root/work/" || return 1
  cp -a "$fixture/readiness/$work_id" "$root/readiness/" || return 1
  if [[ "$effective_lane" == typed-sdd ]]; then
    # This historical P4 fixture exercises the retained F# authority. Release
    # D.5's omitted Quint backend has its separate installed source gate. SDD
    # 1.x only accepts the F# backend and has no --backend option; SDD 2.x
    # requires the explicit choice to avoid the new Quint default.
    local -a backend_args=()
    local observed_version
    observed_version="$(fsgg-sdd --version)" || return 1
    [[ "$observed_version" == 1.* ]] || backend_args=(--backend fsharp-specification-v1)
    lifecycle_report "$report_root/$lane.completion-migrate.json" fsgg-sdd typed-sdd migrate --root "$root" --work "$work_id" \
      --source "work/$work_id/spec.md" "${backend_args[@]}" \
      --accept || return 1
    jq -e '.outcome == "succeeded" and .classification == "Migrated"' "$report_root/$lane.completion-migrate.json" >/dev/null || return 1
    lifecycle_report "$report_root/$lane.completion-plan.json" fsgg-sdd plan --root "$root" --work "$work_id" --accept-upstream --json || return 1
    jq -e '.outcome == "succeeded" or .outcome == "succeededWithWarnings"' "$report_root/$lane.completion-plan.json" >/dev/null || return 1
  fi

  # A transplanted terminal fixture deliberately begins with stale generated views. Refresh may
  # report partially-blocked while updating work-model because downstream analysis/verify/ship
  # still bind the prior root; the immediately following canonical replay is what closes them.
  local work_model="$root/readiness/$work_id/work-model.json" work_model_before
  work_model_before="$(sha256sum "$work_model" | cut -d' ' -f1)" || return 1
  local refresh_status=0
  lifecycle_report "$report_root/$lane.completion-refresh.json" fsgg-sdd refresh --root "$root" --work "$work_id" --json || refresh_status=$?
  if ! assert_completion_refresh "$report_root/$lane.completion-refresh.json" "$work_model" "$work_model_before" "$work_id" "$refresh_status"; then
    cat "$report_root/$lane.completion-refresh.json" >&2
    return 1
  fi
  lifecycle_report "$report_root/$lane.completion-analyze.json" fsgg-sdd analyze --root "$root" --work "$work_id" --json || return 1
  jq -e '.analysis.status == "implementationReady"' "$report_root/$lane.completion-analyze.json" >/dev/null || return 1
  initialize_completion_candidate "$root" "$work_id" "$report_root" "$lane" || return 1
  lifecycle_report "$report_root/$lane.completion-evidence-sync.json" fsgg-sdd evidence --root "$root" --work "$work_id" \
    --sync-observed-run "work/$work_id/lifecycle-evidence.junit.xml" --json || return 1
  lifecycle_report "$report_root/$lane.completion-evidence.json" fsgg-sdd evidence --root "$root" --work "$work_id" --json || return 1
  jq -e '.evidence.status == "evidenceReady" and (.diagnostics | length) == 0' "$report_root/$lane.completion-evidence.json" >/dev/null || return 1
  lifecycle_report "$report_root/$lane.completion-verify.json" fsgg-sdd verify --root "$root" --work "$work_id" --json || return 1
  jq -e '.verification.status == "verificationReady"' "$report_root/$lane.completion-verify.json" >/dev/null || return 1
  lifecycle_report "$report_root/$lane.completion-ship.json" fsgg-sdd ship --root "$root" --work "$work_id" --json || return 1
  jq -e '.ship.status == "shipReady"' "$report_root/$lane.completion-ship.json" >/dev/null || return 1
  echo "PASS lifecycle completion: $provider/$lane reached shipReady"
}

assert_provider_lifecycle_matrix() {
  local provider="$1" archive="$2" matrix_root="$3"
  shift 3
  local -a provider_params=("$@")
  local lane root descriptor report actual direct_legacy
  local default_lane=sdd
  [[ "$provider" == fable-game ]] && default_lane=typed-sdd
  local explicit_default_parameters=""

  mkdir -p "$matrix_root" || return 1
  for lane in none sdd typed-sdd spec-kit omitted; do
    root="$matrix_root/$lane"
    mkdir -p "$root/.fsgg" || return 1
    descriptor="$root/.fsgg/providers.yml"
    cp "$LANE_REPO_ROOT/providers/$provider.providers.yml" "$descriptor" || return 1
    if [[ "$archive" != "published" ]]; then
      lane_pin_provider_to_archive "$descriptor" "$archive" || return 1
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
      test -d "$root/.specify" || return 1
    elif ! lifecycle_report "$report" fsgg-sdd scaffold "${args[@]}"; then
      echo "lifecycle matrix: $provider/$lane scaffold failed" >&2
      jq -r '.diagnostics[]? | "  \(.id): \(.message)"' "$report" >&2 || true
      return 1
    fi
    if [[ "$direct_legacy" == false ]]; then
      jq -e --arg provider "$provider" '.outcome == "succeeded" and .scaffold.providerName == $provider and .scaffold.providerInvoked == true' "$report" >/dev/null || return 1
      actual="$(jq -r '.effectiveParameters[] | select(.key == "lifecycle") | .value' "$root/.fsgg/scaffold-provenance.json")" || return 1
      local expected_lane="$lane"
      [[ "$lane" == omitted ]] && expected_lane="$default_lane"
      [[ "$actual" == "$expected_lane" ]] || {
        echo "lifecycle matrix: $provider/$lane recorded '$actual', expected '$expected_lane'" >&2
        return 1
      }
      # The descriptor used for this scaffold owns the floor. A retained v1 descriptor may
      # legitimately differ from the current v2 descriptor; never freeze yesterday's value here.
      if [[ -n "${FSGG_COMPOSITION_DIAGNOSTICS:-}" ]]; then
        mkdir -p "$FSGG_COMPOSITION_DIAGNOSTICS" || return 1
        cp "$descriptor" "$FSGG_COMPOSITION_DIAGNOSTICS/$lane.providers.yml" || return 1
        cp "$report" "$FSGG_COMPOSITION_DIAGNOSTICS/$lane.scaffold.json" || return 1
        cp "$root/.fsgg/scaffold-provenance.json" "$FSGG_COMPOSITION_DIAGNOSTICS/$lane.provenance.json" || return 1
      fi
      if ! python3 "$LANE_REPO_ROOT/tests/composition/lib/provenance-floor.py" \
        --repo "$LANE_REPO_ROOT" --provider "$provider" --descriptor "$descriptor" \
        --provenance "$root/.fsgg/scaffold-provenance.json"; then
        cat "$root/.fsgg/scaffold-provenance.json" >&2
        return 1
      fi
    fi

    if [[ "$lane" == "$default_lane" ]]; then
      explicit_default_parameters="$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" || return 1
    elif [[ "$lane" == omitted ]]; then
      [[ "$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" == "$explicit_default_parameters" ]] || {
        echo "lifecycle matrix: $provider omitted parameters differ from explicit $default_lane" >&2
        return 1
      }
      assert_lifecycle_trees_equivalent "$matrix_root/$default_lane" "$root" "$matrix_root/omitted-vs-$default_lane.diff" || return 1
    fi
  done

  root="$matrix_root/typed-sdd"
  local provenance_before
  provenance_before="$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" || return 1
  # The historical native matrix runs with SDD 1.x's F#-only CLI on the
  # protected composition gate; 2.x needs an explicit F# backend selection.
  local -a backend_args=()
  local observed_version
  observed_version="$(fsgg-sdd --version)" || return 1
  [[ "$observed_version" == 1.* ]] || backend_args=(--backend fsharp-specification-v1)
  if ! lifecycle_report "$matrix_root/typed-sdd.author.json" fsgg-sdd typed-sdd author --root "$root" --work matrix-spec --title "${provider} typed matrix" --agent composition --session "$provider" "${backend_args[@]}"; then
    echo "lifecycle matrix: $provider typed authoring failed" >&2
    return 1
  fi
  lifecycle_report "$matrix_root/typed-sdd.inspect.json" fsgg-sdd typed-sdd inspect --root "$root" --work matrix-spec || return 1
  jq -e '.outcome == "succeeded"' "$matrix_root/typed-sdd.inspect.json" >/dev/null || return 1
  test -f "$root/work/matrix-spec/specification.fsx" || return 1
  test -f "$root/work/matrix-spec/spec.md" || return 1
  test -f "$root/readiness/matrix-spec/specification.normalized.json" || return 1
  test -f "$root/readiness/matrix-spec/typed-authority.json" || return 1
  cmp "$root/.agents/skills/fs-gg-sdd-typed-author/SKILL.md" "$root/.claude/skills/fs-gg-sdd-typed-author/SKILL.md" || return 1
  lifecycle_report "$matrix_root/typed-sdd.refresh.json" fsgg-sdd refresh --root "$root" --work matrix-spec --json || return 1
  jq -e '.outcome == "noChange" and .refresh.status == "early-stage"' "$matrix_root/typed-sdd.refresh.json" >/dev/null || return 1
  lifecycle_report "$matrix_root/typed-sdd.upgrade.json" fsgg-sdd upgrade --root "$root" --yes --json || return 1
  jq -e '(.outcome == "noChange" or .outcome == "succeeded") and .upgrade.residualDrift == false' "$matrix_root/typed-sdd.upgrade.json" >/dev/null || return 1
  [[ "$(jq -cS '.effectiveParameters' "$root/.fsgg/scaffold-provenance.json")" == "$provenance_before" ]] || return 1
  lifecycle_report "$matrix_root/typed-sdd.post-upgrade-inspect.json" fsgg-sdd typed-sdd inspect --root "$root" --work matrix-spec || return 1
  jq -e '.outcome == "succeeded"' "$matrix_root/typed-sdd.post-upgrade-inspect.json" >/dev/null || return 1


  # Keep the first loop a clean-scaffold proof. Completion and builds intentionally run only after
  # omitted-vs-explicit default has compared the unpolluted file trees.
  for lane in none sdd typed-sdd spec-kit omitted; do
    root="$matrix_root/$lane"
    local effective_lane="$lane"
    [[ "$lane" == omitted ]] && effective_lane="$default_lane"
    assert_generated_lifecycle_completion "$provider" "$lane" "$root" "$matrix_root" "$effective_lane" || return 1
    assert_generated_product_restore_build_test "$provider" "$lane" "$root" || return 1
  done

  echo "PASS lifecycle matrix: $provider none/sdd/typed-sdd/spec-kit/omitted clean-create, compatibility/completion, restore, build, and test from installed package"
}

assert_typed_lifecycle_controls() {
  local source_root="$1" controls_root="$2" command_root manifest canonical digest control expected
  mkdir -p "$controls_root" || return 1

  for control in wrong-lifecycle stale-projection unsupported-extension direct-edit missing-compiler; do
    cp -a "$source_root" "$controls_root/$control" || return 1
  done

  manifest="$controls_root/wrong-lifecycle/readiness/matrix-spec/typed-authority.json"
  jq '.lifecycle="sdd"' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest" || return 1
  printf ' ' >>"$controls_root/stale-projection/readiness/matrix-spec/specification.normalized.json" || return 1
  manifest="$controls_root/unsupported-extension/readiness/matrix-spec/typed-authority.json"
  jq '.extensionIdentity="unsupported/v9"' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest" || return 1
  printf '\n// direct edit control\n' >>"$controls_root/direct-edit/work/matrix-spec/specification.fsx" || return 1
  canonical="$controls_root/missing-compiler/work/matrix-spec/specification.fsx"
  printf '\nfailwith "compiler unavailable control"\n' >>"$canonical" || return 1
  digest="$(sha256sum "$canonical" | cut -d' ' -f1)" || return 1
  manifest="$controls_root/missing-compiler/readiness/matrix-spec/typed-authority.json"
  jq --arg digest "$digest" '.canonicalSha256=$digest' "$manifest" >"$manifest.tmp" && mv "$manifest.tmp" "$manifest" || return 1

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
  jq -e '[.diagnostics[].id] | index("typedSdd.authoringAgentUnavailable") != null' "$controls_root/agent-unavailable.json" >/dev/null || return 1
  echo "PASS typed lifecycle controls: wrong lifecycle, stale projection, unsupported extension, direct edit, missing compiler, agent unavailable"
}
