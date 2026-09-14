# Complete SVG workspace adoption

The complete adopter upgrades the generated product surface from public Templates 0.10–0.13 to the current complete SVG workspace. It extends the earlier preview-only transaction without changing that command's contract.

Run inventory first and review its diff before applying:

```bash
scripts/apply-svg-foundation-preview.sh complete-inventory \
  /path/to/materialized-complete-candidate \
  /path/to/retained-workspace \
  scripts/svg-complete-workspace-baselines.json \
  /outside/workspace/inventory.json \
  /outside/workspace/review.diff

scripts/apply-svg-foundation-preview.sh complete-apply \
  /path/to/materialized-complete-candidate \
  /path/to/retained-workspace \
  scripts/svg-complete-workspace-baselines.json \
  /outside/workspace/inventory.json \
  /outside/workspace/rollback-journal
```

The inventory binds candidate and receiver bytes and executable modes, the public baseline archives, manifest, and complete textual/binary diff. Added files appear against `/dev/null`, and mode changes appear in the review. Apply refuses a stale inventory or changed diff.

The manifest owns generated product source, projects, dependency locks, conformance tests, player and Studio files, examples, formal models, product scripts, the product CI workflow, and the package-owned Fable skill set. The candidate must be an actually materialized complete receiver: its scaffold provenance identifies the Fable bodies the package produced, and each materialized body must match its declarative manifest row. The raw template source directory is insufficient. An existing managed file is replaceable only when its normalized bytes match the same logical path from a named public baseline, or already match the candidate. A customized `Domain`, `Protocol`, `Server`, build, scene, model, or package-owned skill path is a collision and refuses the whole transaction before a backup or workspace write. Symlinks in any managed path chain are also refused.

Lifecycle trees (`.fsgg`, `.specify`), owner guidance, lifecycle-aware `.gitignore` entries, root documentation, and files outside the explicit managed list are inventoried and preserved. The package's current Fable declarations are merged into the existing skill manifest: old package rows are admitted by their per-row public hashes, while Game, Rendering, Audio, driver, lifecycle, and local rows survive byte-for-byte. Editing package row metadata refuses before writes. The neutral `.agents` bodies and an already-configured `.claude` mirror follow SDD 1.8's declared skill-root set and receive identical package-owned bytes and merged manifests; no undeclared mirror root is invented and no lifecycle body or provenance record is copied or reattested. The obsolete `fable-remoting` skill is deleted only when its bytes match the same path from an admitted public baseline; an edited copy is preserved by refusing before writes. Refreshing SDD owner guidance remains an SDD-owned operation. Arbitrary gameplay AST, profile, evidence, save, replay, and keymap conversion is outside this byte-bounded adopter. Their existing readers or explicit compatibility refusals remain authoritative.

Every journal stores the before and candidate hashes and executable modes for all managed paths before replacement begins. An injected failure rolls back through that journal. Manual recovery is explicit:

```bash
scripts/apply-svg-foundation-preview.sh complete-recover \
  /path/to/retained-workspace \
  /outside/workspace/rollback-journal
```

Recovery validates every backup object and every current managed path before its first write. It accepts a partially applied journal only when each path still equals its recorded before or candidate state. Explicit rollback first records and flushes a `rolling-back` phase; recovery can resume its recorded before/candidate mixture after interruption. After a completed adoption, any newer managed edit makes rollback refuse before writes, so rollback cannot downgrade newer authored code or content. A completed recovery is byte- and mode-identical for managed files and leaves all preserved paths untouched.

`tests/composition/fable-game/verify-svg-complete-adoption.sh` materializes each exact public 0.10–0.13 archive, retains authored level/keymap/replay and local-skill sentinels, reviews and applies the transition, builds the adopted solution, and exercises union-manifest preservation, package-row and body collisions, configured mirror equality, retirement, symlink, post-inventory mode changes, apply and rollback interruption, corrupt-backup, newer-edit, and explicit-recovery controls.
