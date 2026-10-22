# shellcheck shell=bash
# ── Packaged C sources reach a scaffold byte-for-byte ────────────────────────────────────────────
#                                                          (FS.GG.Templates#729)
#
# THE DEFECT THIS CLOSES. The .NET template engine runs a built-in, extension-keyed conditional
# processor over every file it copies; for `*.c`/`*.h` that is C-style `#if`/`#elif`/`#else`/`#endif`
# processing. A template that declares `specialCustomOperations` only for `**/*.fs` (which is how
# the fable-game template and its legacy sibling were configured) therefore rewrites its C sources:
# the published FS.GG.Workspace.Template 0.19.0 scaffolds
# `SvgFoundation/Examples/Wasm/guest/policy.c` at 1130 bytes against 1308 packaged, with the
# `POLICY_TRAP` / `POLICY_LOOP` / `POLICY_MALFORMED` blocks that `build-guests.sh` selects with
# `-DPOLICY_<VARIANT>` deleted. Nothing else noticed: the file still compiled, the scaffold exited 0,
# and every source-side check compares the repository tree, never what the engine delivers.
#
# WHAT IS GRADED. The archive under test (the exact `FSGG_TEMPLATES_NUPKG` the release gate hands
# the lane, or the freshly packed one) is installed into an isolated hive and scaffolded for EVERY
# composition that selects `SvgFoundation/`:
#
#   fs-gg-fable-game                --bundle player | studio | tactical | arcade | complete
#   fs-gg-fable-game (legacy group) --svgFoundation true | false
#
# For each, every file the archive ships is compared byte-for-byte with the file the engine
# delivered. Files the engine rewrites BY DESIGN (the `FableGameWorkspace` source-name token in the
# path or content) are the only exemption, counted and printed rather than hidden; a C-family source
# that carries the token is itself a red, because this gate's contract is that C sources are exact.
#
# WHY EVERY FILE AND NOT JUST `policy.c`. The same engine default governs every extension, so the
# narrowest honest check is "nothing token-free was altered", not "this one file was". Measured on
# the defective configuration: `policy.c` was the only token-free file that differed in the
# `bundle=complete` scaffold.
#
# WHY THE `.h` HALF IS PROBED. No header is packaged today (`fsgg-wasm-guest.h` is materialised by
# `build-guests.sh`'s asset step), but the configuration fix covers `**/*.h` and a rule with no
# subject is a rule nothing keeps alive. `source-fidelity.py seed` therefore injects a `.c` and a `.h`
# probe, carrying every directive the engine's conditional recognises, into a DERIVED copy of the
# archive (the archive on disk is never modified).
#
# THE CAUSAL CONTROL RUNS EVERY TIME, NOT ONCE IN A PR DESCRIPTION. `source-fidelity.py strip`
# derives a second archive whose template.json files lack the `**/*.c` / `**/*.h` entries, i.e. the
# exact configuration this gate exists to prevent, installs it into its own hive, scaffolds
# `bundle=complete`, and REQUIRES the same comparison to fail naming `policy.c` and both probes. A
# gate whose control stays green is a gate that grades nothing (.github#266); a control that has no
# subject (nothing mismatched) is itself a red.
#
# SCOPE LIMIT, STATED. The subject is the template engine's delivery, which is also what
# `fsgg-sdd scaffold` forwards to; this gate drives `dotnet new` directly and does not install or
# invoke the SDD CLI, so it needs no network and runs wherever `composition` runs.

SOURCE_FIDELITY_TOOLS=(dotnet unzip python3)
SOURCE_FIDELITY_PRODUCT=Probe729
SOURCE_FIDELITY_POLICY_C='SvgFoundation/Examples/Wasm/guest/policy.c'
SOURCE_FIDELITY_SEEDS=('SvgFoundation/fsgg729-seed.c' 'SvgFoundation/fsgg729-seed.h')
# "<label>|<archive template dir>|<dotnet new arguments>|<space-separated required subjects>"
SOURCE_FIDELITY_MATRIX=(
  "bundle=player|fs-gg-fable-game|--bundle player|${SOURCE_FIDELITY_SEEDS[*]}"
  "bundle=studio|fs-gg-fable-game|--bundle studio|${SOURCE_FIDELITY_SEEDS[*]}"
  "bundle=tactical|fs-gg-fable-game|--bundle tactical|${SOURCE_FIDELITY_SEEDS[*]}"
  "bundle=arcade|fs-gg-fable-game|--bundle arcade|${SOURCE_FIDELITY_SEEDS[*]}"
  "bundle=complete|fs-gg-fable-game|--bundle complete|${SOURCE_FIDELITY_SEEDS[*]} $SOURCE_FIDELITY_POLICY_C"
  "legacy svgFoundation=true|fs-gg-fable-game-legacy|--svgFoundation true|${SOURCE_FIDELITY_SEEDS[*]}"
  "legacy svgFoundation=false|fs-gg-fable-game-legacy|--svgFoundation false|"
)

# sf_scaffold <hive> <out-dir> <dotnet new args...> — instantiate in an isolated hive. rc = dotnet's.
sf_scaffold() {
  local hive="$1" out="$2"; shift 2
  DOTNET_CLI_HOME="$hive" dotnet new fs-gg-fable-game -n "$SOURCE_FIDELITY_PRODUCT" -o "$out" \
    --lifecycle none "$@"
}

# sf_compare <packaged-dir> <scaffold-dir> [required-subject...] — the comparison, output on stdout.
sf_compare() {
  local packaged="$1" scaffold="$2"; shift 2
  local args=() rel
  for rel in "$@"; do args+=(--require "$rel"); done
  python3 -I "$COMPOSITION_DIR/lib/source-fidelity.py" compare --packaged "$packaged" --scaffold "$scaffold" "${args[@]}"
}

# sf_grade_combo <label> <packaged-dir> <scaffold-dir> <required-subjects-string>
sf_grade_combo() {
  local label="$1" packaged="$2" scaffold="$3" required="$4" out rc summary
  # shellcheck disable=SC2086 # the subject list is intentionally word-split
  out="$(sf_compare "$packaged" "$scaffold" $required)"; rc=$?
  summary="$(sed -n '1p' <<<"$out")"
  if [[ "$rc" == 0 ]]; then
    ok "source-fidelity $label: every packaged file the engine delivered is byte-identical ($summary)"
  else
    bad "source-fidelity $label: the engine altered or lost packaged source on the way to the scaffold (FS.GG.Templates#729): $summary"$'\n'"$(sed '1d' <<<"$out")"
  fi
}

# sf_grade_control <label> <control-output> — the control must have failed AND named its subjects.
sf_grade_control() {
  local label="$1" out="$2" rc="$3" missing='' rel
  if [[ "$rc" == 0 ]]; then
    bad "$label: the comparison PASSED on the configuration without the C-family entries, so the gate cannot tell the defect from a fix (a control that stays green grades nothing, .github#266)"
    return
  fi
  for rel in "$SOURCE_FIDELITY_POLICY_C" "${SOURCE_FIDELITY_SEEDS[@]}"; do
    grep -qF "MISMATCH $rel:" <<<"$out" || missing+=" $rel"
  done
  if [[ -z "$missing" ]]; then
    ok "$label: without the **/*.c and **/*.h entries the same comparison fails and names policy.c and both probes ($(grep -c '^MISMATCH' <<<"$out") mismatch(es)) — the gate fires on the defect"
  else
    bad "$label: the comparison failed on the defective configuration but did not name:$missing — the control has no subject there, so the green rows above prove less than they claim"$'\n'"$out"
  fi
}

# assert_source_fidelity <repo-root> <workdir> <nupkg>
assert_source_fidelity() {
  local root="$1" workdir="$2" nupkg="$3"
  local scratch="$workdir/source-fidelity" t missing=''
  for t in "${SOURCE_FIDELITY_TOOLS[@]}"; do command -v "$t" >/dev/null 2>&1 || missing+="$t "; done
  if [[ -n "$missing" ]]; then
    bad "source-fidelity: needs [${SOURCE_FIDELITY_TOOLS[*]}] and cannot run '${missing% }'; REFUSING rather than reporting the clean scan a missing tool produces (.github#266)"
    return
  fi
  [[ -f "$nupkg" ]] || { bad "source-fidelity: archive under test does not exist: $nupkg"; return; }

  rm -rf "$scratch"; mkdir -p "$scratch/seeded" "$scratch/control" "$scratch/packaged"
  local base seeded control
  base="$(basename "$nupkg")"
  seeded="$scratch/seeded/$base"; control="$scratch/control/$base"
  if ! python3 -I "$COMPOSITION_DIR/lib/source-fidelity.py" seed --in "$nupkg" --out "$seeded" >"$scratch/seed.log" 2>&1; then
    bad "source-fidelity: could not derive the probe-seeded archive (see $scratch/seed.log)"; return
  fi
  if ! python3 -I "$COMPOSITION_DIR/lib/source-fidelity.py" strip --in "$seeded" --out "$control" >"$scratch/strip.log" 2>&1; then
    bad "source-fidelity: could not derive the causal-control archive (see $scratch/strip.log)"; return
  fi
  # The packaged baseline is the SEEDED archive, so the probes are graded alongside the real files.
  if ! unzip -q -o "$seeded" -d "$scratch/packaged" 2>"$scratch/unzip.err"; then
    bad "source-fidelity: could not read the archive (see $scratch/unzip.err)"; return
  fi
  local hive_fixed="$scratch/hive-fixed" hive_control="$scratch/hive-control"
  mkdir -p "$hive_fixed" "$hive_control"
  if ! DOTNET_CLI_HOME="$hive_fixed" dotnet new install "$seeded" >"$scratch/install-fixed.log" 2>&1; then
    bad "source-fidelity: the seeded archive did not install (see $scratch/install-fixed.log)"; return
  fi
  if ! DOTNET_CLI_HOME="$hive_control" dotnet new install "$control" >"$scratch/install-control.log" 2>&1; then
    bad "source-fidelity: the control archive did not install (see $scratch/install-control.log)"; return
  fi

  local row label tdir args required
  for row in "${SOURCE_FIDELITY_MATRIX[@]}"; do
    IFS='|' read -r label tdir args required <<<"$row"
    if [[ ! -d "$scratch/packaged/content/templates/$tdir" ]]; then
      bad "source-fidelity $label: the archive carries no content/templates/$tdir, so there is nothing to compare"; continue
    fi
    local out="$scratch/scaffold/${label// /_}"
    rm -rf "$out"
    # shellcheck disable=SC2086 # args is intentionally word-split
    if ! sf_scaffold "$hive_fixed" "$out" $args >"$scratch/new-${label// /_}.log" 2>&1; then
      bad "source-fidelity $label: the scaffold failed, so nothing was compared (see $scratch/new-${label// /_}.log)"; continue
    fi
    sf_grade_combo "$label" "$scratch/packaged/content/templates/$tdir" "$out" "$required"
  done

  # Causal control — the configuration without the C-family entries must FAIL the same comparison.
  local cout="$scratch/scaffold/control-complete" cres crc
  rm -rf "$cout"
  if sf_scaffold "$hive_control" "$cout" --bundle complete >"$scratch/new-control.log" 2>&1; then
    cres="$(sf_compare "$scratch/packaged/content/templates/fs-gg-fable-game" "$cout" "$SOURCE_FIDELITY_POLICY_C" "${SOURCE_FIDELITY_SEEDS[@]}")"; crc=$?
    # NO-SUBJECT lines (the files were not delivered at all) are not the defect; only mismatches are.
    sf_grade_control "source-fidelity control" "$cres" "$crc"
  else
    bad "source-fidelity control: the control archive did not scaffold, so the causal control measured nothing (see $scratch/new-control.log)"
  fi
}
