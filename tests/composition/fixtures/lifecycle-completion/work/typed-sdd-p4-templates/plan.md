---
schemaVersion: 1
workId: typed-sdd-p4-templates
title: P4 Typed SDD templates adoption
stage: plan
changeTier: tier1
status: planned
sourceSpec: work/typed-sdd-p4-templates/spec.md
sourceClarifications: work/typed-sdd-p4-templates/clarifications.md
sourceChecklist: work/typed-sdd-p4-templates/checklist.md
publicOrToolFacingImpact: true
---

# P4 Typed SDD templates adoption Plan

Prose status: planned

## Source Snapshot
- spec: work/typed-sdd-p4-templates/spec.md sha256:31f5a7e099aae95427edf8ad938c9a89264a7ab69ee3a1fcdcc7a9542d66080a schemaVersion:1
- clarifications: work/typed-sdd-p4-templates/clarifications.md sha256:28f767efc02e0e959be14f09dde01a81ebb0d865ff039622e183d913a48301ca schemaVersion:1
- checklist: work/typed-sdd-p4-templates/checklist.md sha256:81f43f88f0caa7b28c8a78c796cd55eb78e3eec91e8f1c42a4e09b65a1ca6276 schemaVersion:1

## Plan Scope
- Work item typed-sdd-p4-templates is planned from the current specification, clarification, and checklist facts.
- Requirement count: 10.
- Clarification decision count: 3.
- Checklist result count: 10.

## Plan Decisions
- PD-001 [AC-001] [FR-001] [DEC-001] complete: Add `lifecycle` choice symbols (`none`, `sdd`, `typed-sdd`, default `sdd`) to console, web, fable-game, and fable-bindings; declare the same optional parameter in all provider descriptors.
- PD-002 [AC-001] [FR-002] complete: Treat lifecycle as an opaque value at the provider boundary and assert the exact effective value in scaffold provenance.
- PD-003 [AC-002] [FR-003] complete: Compare canonical lifecycle path sets and provenance for omitted and explicit `sdd` in every provider/profile cell.
- PD-004 [AC-003] [FR-004] complete: Advance the minimum orchestrator floor to `1.4.0-preview.1`, Rendering to `0.28.0`, and all self-package sources to the release version selected by PD-010.
- PD-005 [AC-003] [FR-005] complete: Exercise the published Typed SDD author/inspect compiler loop in installed-package products without duplicating compiler implementation in Templates.
- PD-006 [AC-003] [FR-006] complete: Assert typed model/projection/provenance stability before and after refresh and upgrade; compare generated agent behavior digests.
- PD-007 [AC-004] [FR-007] complete: Implement mutation fixtures for each required failure class and require both non-zero exit and its expected diagnostic identifier.
- PD-008 [AC-005] [FR-008] [DEC-003] complete: Generate the provider/profile/lifecycle matrix from descriptors and template profiles, while retaining one full restore/build/test/publish path per identity.
- PD-009 [AC-002] [FR-009] complete: Retain direct-template lane coverage and product-skill manifest exactness; add explicit Standard SDD and Freeform compatibility assertions.
- PD-010 [AC-005] [FR-010] [DEC-002] complete: Set package version `0.9.0`, pack once, verify the checksum-bound dual-feed mechanism, and declare the exact-head post-merge publication obligation; after merge, dual-publish byte-identical bytes, prove public-only install, then accept the hub registry feed automation.

## Contract Impact
- PC-001 [PD-001] provider descriptors: `parameters.lifecycle` becomes uniformly available with default `sdd` across all five providers.
- PC-002 [PD-001] dotnet template CLI: four owned workspace templates accept `--lifecycle none|sdd|typed-sdd`; the value is orchestration metadata and emits no template-owned lifecycle tree.
- PC-003 [PD-004] coherent dependency contract: `minimumFsggSdd.version` becomes `1.4.0-preview.1`, rendering source becomes `FS.GG.UI.Template::0.28.0`, and workspace sources become `FS.GG.Workspace.Template::0.9.0`.
- PC-004 [PD-008] test contract: composition discovers every supported provider/profile/lifecycle cell and fails if a descriptor, template symbol, or executable lane is missing.

## Verification Obligations
- VO-001 [PD-001] [PD-002] [PC-001] [PC-002] semanticTest: Validate descriptor defaults, template choice symbols, exact forwarding, and lane-specific path sets for every matrix cell.
- VO-002 [PD-003] [PD-006] semanticTest: Validate omitted/explicit-SDD equivalence plus refresh, upgrade, provenance, projection, and generated-guidance stability.
- VO-003 [PD-005] semanticTest: Run Typed SDD author/inspect over a scaffolded installed-package product and assert compiler/model/projection/evidence surfaces.
- VO-004 [PD-007] negativeControl: Mutate each compiler/lifecycle/projection/extension/edit/agent condition and assert its distinct failing diagnostic.
- VO-005 [PD-008] [PD-009] compatibilityTest: Run full composition and all identity lanes, including direct `dotnet new`, Standard SDD, Freeform, and skill-manifest checks.
- VO-006 [PD-010] releasePreflight: Verify candidate contents/version and the checksum-bound dual-feed mechanism before merge; the declared post-merge obligation separately requires feed reads, byte identity, public-only installation, and downstream registry provenance before completion.

## Performance Intent
No performance intent is declared for this work item.

## Migration Posture
- PM-001 [PC-001] additiveDefault: Existing descriptors gain a default matching current behavior, so omitted invocations remain Standard SDD.
- PM-002 [PC-002] additiveChoice: Direct template consumers may ignore the new parameter; orchestrated consumers can select it explicitly.

## Generated View Impact
- GV-001 [PD-001] [PD-006] workModelAndAgentGuidance: Lifecycle sources regenerate the normalized work model and both configured agent guidance targets; acceptance compares their source and behavior digests and rejects stale or directly edited projections.

## Accepted Deferrals
No accepted plan deferrals recorded.

## Planning Findings
No blocking planning findings recorded.

## Advisory Notes
- Optional Governance pointers remain compatibility facts only.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd tasks --work typed-sdd-p4-templates`.
