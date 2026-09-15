# Complete SVG workspace adoption

The complete adopter upgrades the generated product surface from public Templates 0.10–0.13 to the current complete SVG workspace. It extends the earlier preview-only transaction without changing that command's contract.

Native development qualification uses fresh public synthetic clean and retained receivers generated only from
audited public template sources and package archives. Earlier private receivers remain private access-negative
fixtures; none of their history, artifacts, or local evidence is an input to the public receivers.

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

The inventory binds candidate and receiver bytes and executable modes, the public baseline archives, the previously selected 0.14 candidate identity, manifest, and complete textual/binary diff. This lets a retained receiver move from that selected candidate to a repaired candidate without treating previously adopted bytes as authored collisions. Added files appear against `/dev/null`, and mode changes appear in the review. Apply refuses a stale inventory or changed diff.

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

## Qualification record

The final functional candidate was scaffolded from Templates source
`7e708efeb5f5e645bcfc49421c8d80a05d712430` with the exact native
`FS.GG.Workspace.Template` 0.14.0 archive
`be3f5bade3e66e82b99cf6edc8b52329338939b0715eea7e9a10781e76d31965`, wizard 0.11.2 and
SDD 1.8.0. The archive installed in the isolated template-engine home was byte-identical to native
custody. Its complete/typed receiver reported 122 generated product paths and a coherent doctor result. The
final four-baseline transaction report is `fsgg.svg-complete-adoption-qualification/v1`, digest
`f819920c2ad22da0d1e416815d672d3508248f281db53c542988d95944be6e74`; every adopted solution
built with SDK 10.0.400. The later exact-head archive at Templates
`0f7f022f487f9fbc6d800a6193f8f6bc89f19526` has digest
`0e2c1b23f18ba53fc708297758cf473e875991fa4250f30684859a1436022fb6`; all template payload
entries are byte-identical, and only the NuGet repository-commit metadata advanced. ADR-0084 therefore permits
reuse of the functional matrix while the exact-head native checks bind the final source and archive metadata.

Four native receiver PRs exercised development after creation and after retained adoption:

| Receiver | Routine repair | Semantic change |
|---|---|---|
| clean | [queued relative movement](https://github.com/FS-GG/svg-workspace-public-clean-20260914/pull/2), head `c7e2fe231d7e078e12981670ec9291ac5fa9b90e`, merge `88b79909440f35d7db9c16c8cf2e8d02e7888889` | [Arcade reward 125](https://github.com/FS-GG/svg-workspace-public-clean-20260914/pull/3), head `cec3ba1ffedf761445393b55f176e111bb0723da`, merge `f205975da486ac2c0e236a09e40ce73b6e529501` |
| retained 0.13 | [snapshot compatibility validation](https://github.com/FS-GG/svg-workspace-public-retained-20260914/pull/2), head `9b2fbbe97190e65980e3ca42786eac48fb319e45`, merge `7b4104b769363a614c04c0b5138030ea19feda01` | [retained Arcade reward 125](https://github.com/FS-GG/svg-workspace-public-retained-20260914/pull/3), head `a59e8be3931c415c0cbec35ce69fa862178e905d`, merge `f9d4ffb92c7cfac6b16034339ed030f95eba7d67` |

Each exact head passed the protected `build` and `routine-eligibility` checks and was delivered by the
native routine helper. Actual merge requests refused while `build` was pending. Later useful corrections
advanced both repair heads; merge requests naming the obsolete head returned `409`, after which current checks
and markers were rebound. Helper readback reports `telemetryHealth: not-configured`; that is the observed
unavailable-usage disposition, not a fabricated usage receipt. Delayed derived-view handling was qualified
separately through the helper's installed read-only `NativeApi` adapter: an authentic earlier captured PR response
at head `096735a4c7071c75eb1b46ef029388d0a6616efc` was refused for expected head
`c7e2fe231d7e078e12981670ec9291ac5fa9b90e` without a write, then a live GitHub response reported the
current head delivered at merge `88b79909440f35d7db9c16c8cf2e8d02e7888889`. The retained result is
`/tmp/svg-workspace-015-delayed-view-readback.json`, digest
`763408e63dfc12a1c3deb46c0219c085ac6e82ca596a734a74f306d8e1dfb2dc`.

Both semantic PRs changed the visible Arcade collectible reward from 100 to 125. Their literate Arcade model,
bindings, content identity, .NET/Fable reducer projections, old-content restore/replay refusal and browser journey
changed together. Published SDD 1.8 author/inspect accepted the resulting profile-2 authority in each receiver.
The repair PRs kept rule semantics fixed: the clean case preserved the authority's highest-sequence-per-tick
contract while serializing relative keyboard intent against accepted snapshots; the retained case made direct
continuous-session restore accept an exact round trip and refuse foreign session and compatibility identities.

The wider authority matrix used the published SDD 1.8 CLI. Exact profile-2 tools worked with no network after
provision; stale generation, missing source/verifier, changed bindings, wrong profile/authority and wrong cached
tool identity refused without workspace writes. Manifest-v1 preview/accept/recovery retained all original files,
including interruptions in migration and rollback; its retained Quint profile-1 remained inspectable and refused
a forged profile-2 reinterpretation. The `none`, `sdd`, and `spec-kit` lifecycle tokens remained distinct, and
supported Markdown migration preserved originals while ambiguous or unsupported input produced a no-change
refusal. These bounded producer migrations do not claim arbitrary gameplay AST or profile conversion. Exact
retained readbacks are `/tmp/svg-workspace-015-offline-root/readback.json` digest
`5b7da0e985baccdd8be066200e1ded794a6a8d3a81b248ae2da7b6b35f0514a2`,
`/tmp/svg-workspace-015-manifest-v1-root/readback.json` digest
`789fd33695ca8f40d8fb6eabb0ffbf00d3dfec253488fab2a9c0c88b08767c61`, and
`/tmp/svg-workspace-015-lifecycle-root/readback.json` digest
`97fe0922d5e344a13a6d73e0f45603ad37207f80c7cda7591a4a5735a850e4d6`.

Authored level, replay and keymap fixture bytes remained exact across every complete transaction. That sentinel
result establishes preservation only. Actual old preview save/reload and replay reading remain covered by the
published 0.13 installed runner and its frozen Release-C observer. Keymap compatibility is owned by the unchanged
public `FS.GG.UI.KeyboardInput` 0.31.0 and `FS.GG.Game.Core` 0.16.0 reader contracts: an actual package probe decoded
the version-1 `fsgg.keymap` envelope, resolved `move.north`, retained an opaque unknown command token, reported that
token unavailable through `Command.ofId`, and explicitly refused envelope version 2. This workspace exposes no
separate importer for arbitrary external keymap files, so byte preservation does not imply that unsupported path.
The package probe source is `/tmp/svg-workspace-015-keymap-reader/Program.fs` digest
`b520f2ed4ce2f04f6c88448d8bc52b636803571df148b612c3ab1b907afdaff6`; its successful output digest is
`3b6c92e5154be8bc68604dd4059778c734443ee142a5b1091ef653dd1cfb5805`.
