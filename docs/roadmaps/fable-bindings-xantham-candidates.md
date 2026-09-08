# Fable bindings candidate generation and upstream integration assessment

Feature identity: `FB-XANTHAM-01`  
Owner: FS.GG.Templates  
Status: source implementation complete; package publication pending  
Route: routine, one accountable Sol-medium worker  
Unified part: **Fable bindings candidate generation and upstream integration assessment**  
Stage: independently executable producer work from section 15; not a v2 prerequisite

[Unified feature index](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index) ·
[Accepted evaluation](https://github.com/FS-GG/.github/blob/docs/xantham-evaluation-and-integration/docs/reports/2026-09-08-105454-xantham-fable-bindings-evaluation.md)

## Outcome and completion boundary

The existing Fable bindings workflow gains an explicitly selected Xantham candidate backend.
Its first qualified example generates a small useful binding, compiles it, and executes a real
Fable/Node consumer. Generation writes review material under `generated-candidates`; maintained
bindings, declaration locks, mapping decisions and accepted coverage remain owner-controlled.

Whenever an agent loads the Templates-owned `fable-bindings` skill, its opening instructions require
a live Xantham update assessment. The assessment compares published packages and upstream source
against the workspace's exact qualified baseline, explains relevant changes and compatibility gaps,
and proposes concrete integration steps. Loading the skill does not install tools, execute fetched
code, change pins, regenerate bindings, publish artifacts, or contact upstream maintainers.

Completion here means a usable optional backend, an executable small-package qualification,
automated diagnostics/provenance, updated delivered skill guidance, and local packed-product
qualification. Producer publication and installed receiver adoption remain separately reported.
It does not mean complete Babylon, Zod, XState or arbitrary-package synthesis.

## Evidence to reuse

The inspected Templates baseline is `1cffa0603e8e5d0991ba5ec7b650fed75f748f7b`.

| Capability | Actual status |
|---|---|
| Declaration locking, mapping ledger, maintained F# source, drift, emitted imports, Node/browser and clean NuGet-consumer checks | Implemented in the existing bindings template and composition tests |
| `scripts/generate-candidate.mjs` | Implemented inventory of TypeScript declaration hazards and an empty candidate shell; no translator |
| Owner-supplied bindings skill and digest manifest | Implemented under `template/product-skills/fable-bindings/SKILL.md`; projected into the packed template |
| Xantham candidate integration and update assessment | Missing |
| Mapped `ansi-regex@6.2.2` generation, F# compilation and real Fable/Node execution | Independently demonstrated by the accepted evaluation; not yet a repository-delivered test |
| Anime.js | Generation and F# compilation demonstrated; runtime compatibility unproved |
| Babylon, Zod and XState | Known compilation failures; Babylon output also exceeds a practical reviewable size |
| Catalog ownership and cross-platform determinism | Unqualified; upstream test exclusions remain relevant |

Use these exact starting identities, preserving their different meanings:

- Published CLI: `xantham` `0.1.0-alpha.2`, reporting source
  `ce841e91500f8b4a668c6d64def61936eccda50f`.
- Inspected upstream source: `0d785c68bbc539bb2f07ff2bc3e8750a153c8d55`.
- Wire baseline: `Xantham.TypeScript.Wire` `0.2.0`.
- Support baseline: `Xantham.Fable.Core` `0.1.0-alpha.1`.
- Native compiler: TypeScript `7.1.0-dev.20260902.1`; evaluated Linux executable SHA-256
  `aee0bac365d2477e73c06a36909b1c8f2bc7bea3839874215120e4b9da173b46`.
- Existing template parser: TypeScript `5.9.3`; Fable `5.13.0`, Fable.Core `5.2.0`,
  library target `netstandard2.1`.

The evaluation used SDK `10.0.400`, Node `26.8.1` and npm `12.0.2`; the template and older
toolchain lane carry their own pins. Qualify the new path against its declared environment rather
than silently changing workspace-wide tool versions.

Local evaluation inputs are in `/tmp/fsgg-xantham-spike-20260908` and source in
`/tmp/fsgg-xantham-eval-20260908`. Reuse useful fixtures and exact commands, but commit the necessary
reproducible inputs and concise results: temporary paths are not durable acceptance evidence.

## Scope and contract

This is an additive Tier 1 command, artifact and skill-contract change. This document carries the
bounded specification, decisions, tasks and migration intent; focused executable fixtures provide
its behavioral evidence. The user's routine-process instruction takes precedence over inherited
requirements for separate SDD artifact families.

Keep the current provider identity, Babylon scaffold corpus, lifecycle selection and inventory default.
Do not replace the JavaScript TypeScript 5.9 parser with the separate native TS7 compiler.
The optional pilot can have its own locked npm root and config without changing the maintained
Babylon application's package dependencies or declaration lock.

Use ordinary template files for executable helpers, schemas and pinned configuration. The current
product-skill packer projects `SKILL.md`, not arbitrary adjacent resources; all skill references must
resolve in a packed product. Templates#446 owns separate publication-contract guidance work; this
feature does not absorb a packaging migration.

Public command shape:

- Existing `npm run generate:candidate` retains inventory behavior.
- `npm run generate:candidate -- --backend xantham --config <workspace-relative-config>` selects
  Xantham explicitly. An unknown backend or invalid config fails with an actionable diagnostic.
- A separate explicit preparation command installs only the exact reviewed generator/compiler
  dependencies into an isolated tool directory. Normal build and skill loading do not invoke it.
- `npm run xantham:assess` performs read-only upstream network requests and emits the update
  assessment. Its optional retained report belongs under `generated-candidates`.

Keep the implementation small: pure config parsing, identity comparison, loss classification and
assessment decisions; an edge interpreter performs fetch, filesystem and subprocess operations.
Represent requested effects and outcomes explicitly enough to test failure and retry behavior.
No new controller, formal model or generic plugin framework is needed.

### Exact compiler and write boundaries

Use the published CLI through an isolated child-process home/cache boundary, supplied by the
process runner without changing the calling shell's HOME. Do not rely on `XANTHAM_TSGO_EXE` alone:
the CLI's cache lookup can override it. Verify the configured executable's fingerprint and actual
version, and test against an intentionally conflicting ambient user cache.

Keep tool preparation and process scratch outside maintained workspace files and excluded from
packaged template payloads. Each Xantham run writes to a fresh directory under
`generated-candidates/xantham/`; validate configured paths and reject escapes or symlink redirection
outside this root. A failed run retains diagnostics and cannot replace a successful proposal,
modify `src`, advance locks, or claim accepted coverage.

Initially qualify the available Linux host only. Bound wall time, subprocess memory, output size and
captured logs; terminate the subprocess group and record the triggering limit. Use conservative
defaults appropriate to the small pilot, including a 90-second generation timeout and a bounded
output size that rejects the observed approximately 15 MB Babylon expansion. Unsupported hosts or
unavailable enforcement fail explicitly for Xantham execution, while curated maintenance remains usable.

### Versioned machine-readable outputs

Author one exact qualified-baseline config and versioned schemas for the new artifacts. Do not fabricate
unknown package or executable hashes: capture and verify them during qualification before accepting
the baseline. Vendor a matching upstream config schema if required; the evaluated `schema -o` command fails.

The run report, schema version 1, records:

- Run identity, UTC start/end, phase durations, platform/architecture and environment versions.
- Requested package/version, npm integrity and lock hash, declaration root/entry and closure hash,
  runtime import, F# module, selected signatures and config hash.
- CLI package/version/source/hash, inspected upstream revision separately, native compiler
  version/executable hash, and any support dependencies actually used.
- Commands as argument arrays, process exits/signals, enforced limits and captured-log locations.
- Raw artifact paths/hashes, findings counts by Xantham grade, selected-symbol losses and their
  reviewed dispositions, and generated signature changes against a named baseline when available.
- References/hashes for maintained mapping and coverage evidence; no generated grade is typed coverage.
- Verification outcomes for reports/schema, limits, imports, F# compilation and any Fable/runtime
  tests performed, with `not-run` represented explicitly.
- Overall status `rejected` or `proposal-ready`, and actionable diagnostics.

A proposal is ready for review only after successful generation, complete valid reports, bounded
output, resolved configured imports, successful compilation and accounted-for selected-signature
losses. `proposal-ready` never means API acceptance or runtime qualification. Preserve untouched
upstream reports alongside the adapted report.

The update assessment, schema version 1, records:

- Check timestamp, exact qualified baseline and its hash.
- Each primary source URL, observed identity and retrieval status, distinguishing published package
  versions from repository head and source-only changes.
- Overall status `current`, `updates-found`, `unavailable` or `partial`.
- Relevant changes with source links, affected compiler/config/output/support contracts, known
  blockers and an explicit `unqualified` compatibility result where evidence is absent.
- Recommended disposition `retain`, `investigate` or `qualify-update`, with concrete affected files,
  qualification checks and integration steps; recommendations never enact those steps.

Compare NuGet versions with prerelease-aware semantics and commits by identity; do not equate a newer
source head with an installable release. Availability of the current exact pin is distinct from
availability of updates. Failure to retrieve updates is visible and does not block unrelated
curated maintenance. An unavailable required pinned dependency blocks its own preparation/run.

## Ready milestones

- [x] FBX-01 — Exact configuration and isolated execution work — route: routine  
  Depends on: none.  
  Scope: template configuration/schemas, pure decision helpers, explicit preparation and subprocess
  runner, focused fixtures under `tests/toolchain/fable-bindings/`.  
  Acceptance: prepare the exact published CLI/native compiler pair; validate fingerprints; execute
  the mapped ANSI input through the controlled process boundary. A conflicting ambient cache cannot
  select another compiler. Wrong hashes, invalid paths, unsupported enforcement, timeout and excessive
  output produce rejected run reports without modifying maintained files. Synthetic failure fixtures
  are labelled; actual CLI execution supplies the positive evidence.

- [x] FBX-02 — Useful candidates carry losses and real runtime proof — route: routine  
  Depends on: FBX-01.  
  Scope: optional backend in `generate-candidate.mjs`, report adapter, shipped ANSI pilot config and
  locked inputs, focused F#/Fable/Node qualification.  
  Acceptance: the default inventory remains compatible; opt-in mapped `ansi-regex@6.2.2` generates
  a reviewable candidate, compiles for `netstandard2.1`, Fable-compiles with the declared pins, and
  runs against the actual package in Node. Verify ANSI and plain-text controls, omitted options,
  the generated option constructor, `onlyFirst`, and the default emitted import. Do not generalize
  the RegExp mapping beyond proven operations. Two equivalent runs have identical candidate,
  manifest and symbol bytes; timestamps remain outside deterministic comparisons. Missing reports,
  selected unaccounted widening/escape, unresolved imports and compilation failure reject a
  proposal even when the generator exits zero. Before/after hashes prove maintained bindings,
  declaration locks, mapping ledger and accepted coverage are unchanged on both success and failure.

- [x] FBX-03 — Every skill load assesses current upstream changes — route: routine  
  Depends on: FBX-01; finalize baseline references after FBX-02.  
  Scope: update-assessment helper, exact baseline, owner-authored `fable-bindings/SKILL.md`,
  README and generated skill manifest.  
  Acceptance: the skill's opening action invokes a fresh assessment for each load and reports how
  relevant updates could be integrated. Check current NuGet CLI/Wire/support versions and upstream
  source/release information through bounded read-only requests. Fixture cases cover unchanged pins,
  newer prereleases, source-only fixes, incompatible compiler/config changes, partial retrieval and
  total outage; run one real network smoke with its observation timestamp. Update assessment cannot
  mutate pins or execute downloaded code. Guidance explicitly distinguishes a recommendation from
  completed qualification. A workspace missing the helper reports that upgrade prerequisite
  instead of falsely claiming a successful check.

- [x] FBX-04 — Packed workspaces receive and can use the feature — route: routine  
  Depends on: FBX-02 and FBX-03.  
  Scope: existing bindings composition lane, manifest validation, producer documentation and concise
  delivery evidence in this roadmap.  
  Acceptance: pack the candidate Templates artifact, instantiate a clean bindings product and verify
  all referenced helpers/config/schemas and the updated owner skill are delivered with matching
  manifest digests. Run the pilot through that product's delivered command; prove the default
  Babylon curated journey remains green through the existing composition checks, including emitted
  Fable code, Node/browser execution, side-effect control and clean NuGet-consumer proof. Confirm
  lifecycle selection and unsupported scaffold-corpus rejection retain their existing behavior.
  Document a selective existing-workspace upgrade with conflict handling and no automatic overwrite
  of owner-edited skills, maintained bindings or locks. Record exact local package/source identities
  and identify publication/adoption as pending unless independently completed.

Use one accountable worker and a coherent routine implementation branch/PR for this bounded window.
Run focused checks as slices become ready, then the affected native delivery checks. Current required
contexts include `kit / coordination-kit`, `composition`, and `materialize / receiver-validate`.
The absence of a Templates routine-pilot policy does not create a new heavy process or authorize
unrelated policy changes.

### Delivery evidence

The source window delivers an isolated exact-pinned Xantham alpha.2/TypeScript 7 pilot, the mapped
`ansi-regex@6.2.2` proposal, versioned run/update schemas, bounded rejection reports, and per-load
update guidance. The focused qualification executes the real generator twice, proves deterministic
candidate/manifest/symbol bytes and unchanged maintained Babylon evidence, compiles for
`netstandard2.1`, Fable-compiles with 5.13.0/Fable.Core 5.2.0, and runs the generated default import,
omitted options, `Options.Create`, `onlyFirst`, ANSI/plain controls in Node. Synthetic fixtures cover
wrong fingerprints, path escape/symlink refusal, timeout, sampled process-group RSS, output limits,
compile failure, source-only updates, package updates, missing pins, partial retrieval and outage.
The live update observation at `2026-09-08T09:51:04.822Z` found all three exact NuGet pins available,
the inspected source revision unchanged, and no GitHub Release; the recommended disposition was
`retain`. The generated skill manifest and packed clean-workspace composition prove the helper,
schemas, configs and updated skill entrypoint reach the product. Package publication remains pending.

## Generated-workspace effect and adoption

Affected family: `fs-gg-fable-bindings` and its Templates-owned product skill, across existing lifecycle
choices. Other product providers and shared driver skills have no intended behavior change.

Before: generation inventories declarations; the skill has no Xantham assessment.
After: inventory remains the default, the explicit Xantham backend can produce qualified small-package
review candidates, and skill loading checks current upstream information.

FBX-02 first changes local opt-in execution. FBX-03 first changes local skill behavior. FBX-04 proves
fresh creation from a locally packed producer artifact. Installed users receive those changes only
after publication of an exact FS.GG.Templates release and selection/adoption through their actual
template/provider path. No release number is reserved by this plan; record the published identity and
receiver selection when known. Inspect the scaffold consumer's actual pin before claiming adoption.

Publication does not rewrite existing workspaces. Their upgrade must deliberately reconcile the
new scripts/config, package commands and owner skill/manifest with local edits. Existing-workspace
skill preservation means a new scaffold release alone cannot establish the every-load behavior there.
Neither delivery nor adoption changes omitted lifecycle from `sdd`, opens v2 or activates a registry.

## Later outcome outline

Expand only when the preceding evidence makes a useful next window concrete:

- A second real package and reusable mapping policy: require a selected executable journey, runtime
  proof, classified losses and measured review/curation effort before widening qualification.
- Wire-backed declaration closure: compare resolved closure with existing locks and target-host
  conditions before replacing the current traversal.
- Catalog/shared-type reuse: restore relevant upstream tests; prove a producer/consumer shared type,
  stale-catalog refusal and Fable/runtime identity before adoption.
- Babylon: require bounded reachability or a justified small facade, reviewable output and clean
  F#/Fable/runtime results; current entry selection and numeric fixes alone do not establish feasibility.
- Other platforms: add exact compiler identities, enforceable limits and repeat/runtime evidence
  before making cross-platform claims.

These remain outcomes rather than executable checkboxes. Upstream changes that invalidate compiler
isolation, output contracts or the pilot's semantics require a bounded replan preserving delivered work.

## Observation and accounting

The runner automatically records generation, validation and test phases, findings and limits.
Native git/PR/check records remain delivery evidence; use available observer/runtime records for
administrative effort, model usage and critical-path delay. Missing attribution remains unknown,
not zero. Do not build a new manual ledger or reporting service. The inspected shared observer
reports a broad 20% measure and does not supply this session's narrow whole-item attribution;
that wiring gap cannot certify the 10% ceiling.

Apply Unified Roadmap section 7.4: useful test execution is excluded from narrow bureaucracy;
target 5%, ceiling 10%. Count distinct original items cumulatively. Fifteen items above 10% or any
item above 25% trigger one aggressive intervention. Good items and worker changes do not reset
the count; only a deployed, verified intervention does. Keep broad overhead and avoidable repeated
test costs separately visible.
