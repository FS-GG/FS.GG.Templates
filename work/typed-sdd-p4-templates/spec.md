---
schemaVersion: 1
workId: typed-sdd-p4-templates
title: P4 Typed SDD templates adoption
stage: specify
changeTier: tier1
status: specified
publicOrToolFacingImpact: true
---

# P4 Typed SDD templates adoption Specification

Prose status: specified

## User Value
Authors can select none, Standard SDD, or Typed SDD explicitly for every supported workspace provider and profile, while omitted lifecycle selection remains Standard SDD.

## Scope
- SB-001: Five provider descriptors; rendering game and app profiles; four workspace template lifecycle symbols; exact SDD and Rendering pins; published-package matrix, provenance, refresh, upgrade, doctor-control, guidance, compatibility, documentation, packaging, and registry-delivery proof. Governance policy, new providers, and upstream implementations are excluded.

## Non-Goals
- SB-002: Do not change Governance policy or enforcement.
- SB-003: Do not add provider identities or profiles.
- SB-004: Do not repair FS.GG.SDD, FS.GG.Rendering, or new-sdd-workspace upstream behavior in this repository.

## User Stories
- US-001 (P1): As a workspace author, I can select `none`, `sdd`, or `typed-sdd` explicitly for every supported provider and profile.
- US-002 (P1): As an existing workspace author, I get Standard SDD when I omit lifecycle selection and retain existing Standard SDD and Freeform behavior.
- US-003 (P1): As a maintainer, I can prove from published packages that the selected lifecycle is preserved through template invocation, provenance, refresh, upgrade, and generated guidance.
- US-004 (P1): As a maintainer, I receive distinct failures for broken compiler, lifecycle, projection, extension, edit, or agent-availability conditions.

## Acceptance Scenarios
- AC-001 [US-001] [FR-001] [FR-002]: Given any supported provider/profile, when it is scaffolded from installed packages with each explicit lifecycle value, then the provider accepts and forwards the exact value and the expected lifecycle tree is produced.
- AC-002 [US-002] [FR-003] [FR-009]: Given lifecycle is omitted, when any supported provider/profile is scaffolded, then its observable lifecycle result equals explicit `sdd`, and existing Standard SDD, Freeform, and direct-template paths still pass.
- AC-003 [US-003] [FR-004] [FR-005] [FR-006]: Given a Typed SDD scaffold, when provenance, refresh, upgrade, and generated guidance are exercised, then all projections remain current, lifecycle identity is preserved, and the Typed Protocol Kernel is available.
- AC-004 [US-004] [FR-007]: Given each prescribed negative-control mutation, when the matching check runs, then it fails closed with the expected distinct diagnostic class.
- AC-005 [US-003] [FR-008] [FR-010]: Given release candidates from the package, when acceptance uses public feeds only, then every matrix cell passes and the package and hub registry advance only after publication proof.

## Functional Requirements
- FR-001: Every supported provider descriptor MUST declare optional `lifecycle` with default `sdd`, and every owned workspace template MUST accept `none`, `sdd`, and `typed-sdd` without owning lifecycle files. (Stories: US-001; Acceptance: AC-001)
- FR-002: The scaffold path MUST preserve the exact explicit lifecycle value without rejection, dropping, aliasing, reinterpretation, or downgrade. (Stories: US-001; Acceptance: AC-001)
- FR-003: An omitted lifecycle MUST have the same lifecycle tree and provenance lane as explicit `sdd`. (Stories: US-002; Acceptance: AC-002)
- FR-004: Provider descriptors MUST pin FS.GG.SDD.Cli `1.4.0-preview.1`; the rendering provider MUST pin FS.GG.UI.Template `0.28.0`; all package sources MUST be exact published versions. (Stories: US-003; Acceptance: AC-003)
- FR-005: Typed SDD scaffolds MUST expose the compiler, inspectable typed model, Markdown and JSON projections, evidence binding, semantic diff, migration, and extension-contract surfaces delivered by FS.GG.SDD. (Stories: US-003; Acceptance: AC-003)
- FR-006: Refresh and upgrade MUST preserve lifecycle identity and provenance, regenerate stale projections deterministically, and generate equivalent agent guidance from the current normalized work model. (Stories: US-003; Acceptance: AC-003)
- FR-007: Acceptance MUST demonstrate distinct failing controls for missing compiler, wrong lifecycle, stale projection, unsupported extension, direct projection edit, and unavailable agent guidance. (Stories: US-004; Acceptance: AC-004)
- FR-008: The matrix MUST cover console, web, fable-game, fable-bindings, and rendering game/app against explicit `none`, `sdd`, `typed-sdd`, plus omitted lifecycle, using installed package artifacts. (Stories: US-003; Acceptance: AC-005)
- FR-009: Existing Standard SDD, Freeform, product-skill manifests, and direct `dotnet new` workflows MUST remain compatible. (Stories: US-002; Acceptance: AC-002)
- FR-010: Release MUST dual-publish byte-identical package content, verify public-only installation, then update the hub registry with publication provenance. (Stories: US-003; Acceptance: AC-005)

## Ambiguities
No material ambiguities recorded.

## Public Or Tool-Facing Impact
- Provider descriptors gain a uniform lifecycle parameter and newer exact dependency floors.
- Four workspace template command surfaces gain the lifecycle choice parameter as an orchestration pass-through.
- The package advances by a minor version because this is an additive public authoring contract.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd clarify --work typed-sdd-p4-templates`.
