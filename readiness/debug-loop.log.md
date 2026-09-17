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
