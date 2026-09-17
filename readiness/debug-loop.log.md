## Iteration 1 — 2026-09-17T15:18:26Z

**Verify command:** `GitHub required checks for FS-GG/FS.GG.Templates#495, with local manifest restore/version checks`
**Exit code:** 1

**Primary failure:** test-failure
- Signal: `FS-GG/FS.GG.Templates#495: composition, Installed typed SDD package receivers, and Release C public producer source qualification failed on the pre-main-sync candidate`
- Hypothesis: The branch was stale relative to `main`, and the emitted F# template manifests were outside the original formatter pin despite being part of issue #494's acceptance criteria.

**Fix applied:**
- `templates/fs-gg-fable-bindings/.config/dotnet-tools.json` — pin Fantomas 8.0.0 in the emitted bindings workspace.
- `templates/fs-gg-fable-game/.config/dotnet-tools.json` — pin Fantomas 8.0.0 in the emitted game workspace.
- branch history — merge current `main` so qualifications run against the current repository contract.

**Narrow re-run result:** pass — all three manifests restore Fantomas 8.0.0; `dotnet fantomas --check .` exits 0
**Full verify result:** deferred

## Iteration 4 — 2026-09-17T15:38:54Z

**Verify command:** `GitHub required checks for FS-GG/FS.GG.Templates#495`
**Exit code:** 1

**Primary failure:** test-failure
- Signal: `verify-svg-preview-c-public.sh: legacy preview adopter root build lock check is not the expected shape`
- Hypothesis: The compatibility transaction selected every no-SVG legacy workspace, including older root entry points that never contained the newer unconditional SVG lock check and therefore need no patch.

**Fix applied:**
- `scripts/apply-svg-foundation-preview.sh` — include the root entry point only when the exact newer unconditional SVG-lock loop is present; older entry points remain byte-identical.

**Narrow re-run result:** pass — exact SDK reproduction covers both public 0.10.0’s older root entry point (unchanged) and wizard 0.11.1’s newer lock loop (patched and rollback-restored)
**Full verify result:** deferred

## Iteration 3 — 2026-09-17T15:31:29Z

**Verify command:** `GitHub required checks for FS-GG/FS.GG.Templates#495`
**Exit code:** 1

**Primary failure:** test-failure
- Signal: `verify-svg-typed-receivers.sh: wizard still missing SvgFoundation/packages.lock.json after the source-copy repair`
- Hypothesis: The exact public Preview-A source also predates the root lock, while `FS.GG.NewSddWorkspace` 0.11.1 emits a newer root build entry point that requires it unconditionally.

**Fix applied:**
- `scripts/apply-svg-foundation-preview.sh` — include the root build entry point in the atomic transaction only for a new legacy SVG retrofit, and gate its root-lock requirement on the newer `PlayerInput.fs` generation marker; retained SVG workspaces and newer payloads are unchanged.

**Narrow re-run result:** pass — exact SDK 10.0.400 reproduction with public template 0.11.0 and wizard 0.11.1 applies the Preview-A retrofit without inventing a lock, patches the expected root guard, and restores the original root script with no managed SVG files left on rollback
**Full verify result:** deferred

## Iteration 2 — 2026-09-17T15:23:46Z

**Verify command:** `GitHub required checks for FS-GG/FS.GG.Templates#495`
**Exit code:** 1

**Primary failure:** test-failure
- Signal: `verify-svg-typed-receivers.sh: wizard root build/test/browser entry failed: missing SvgFoundation/packages.lock.json`
- Hypothesis: The retrofit adds `SvgFoundation` to a published workspace whose root build requires its lock, but commit `d36171f` removed the conditional that copies that reviewed lock into a workspace with no existing SVG foundation.

**Fix applied:**
- `scripts/apply-svg-foundation-preview.sh` — restore conditional copying of the root SVG lock only for a new SVG adoption; retain an existing workspace lock unchanged.
- `scripts/svg-foundation-preview-baseline.manifest` — assert that the pre-adoption wizard baseline has no root SVG lock.

**Narrow re-run result:** pass — adoption script syntax and diff checks pass; the guarded copy now covers a source lock plus an absent destination lock while excluding retained destinations
**Full verify result:** deferred
