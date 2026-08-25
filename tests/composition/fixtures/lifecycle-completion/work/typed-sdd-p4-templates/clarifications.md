---
schemaVersion: 1
workId: typed-sdd-p4-templates
title: P4 Typed SDD templates adoption
stage: clarify
changeTier: tier1
status: clarified
sourceSpec: work/typed-sdd-p4-templates/spec.md
publicOrToolFacingImpact: true
---

# P4 Typed SDD templates adoption Clarifications

## Source Specification
- work/typed-sdd-p4-templates/spec.md

## Clarification Questions
- CQ-001: Does lifecycle belong to each product template or to the SDD orchestrator?
- CQ-002: What versioning level reflects the public provider and template parameter addition?
- CQ-003: Must the complete build/test lifecycle run for every matrix cell?

## Answers
- CQ-001: SDD owns all lifecycle files; owned templates accept lifecycle only so the provider can forward the exact selected lane.
- CQ-002: Use package version 0.9.0 because this is an additive public contract over 0.8.4.
- CQ-003: Every cell must prove installed-package scaffold semantics; expensive restore/build/test/publish remains once per provider identity, with lifecycle-specific semantic checks applied to every cell.

## Decisions
- **DEC-001** [CQ-001] [FR-001] [FR-002]: Add a choice-valued lifecycle symbol to the four owned workspace templates and an optional defaulted lifecycle parameter to all five providers; only FS.GG.SDD writes lifecycle artifacts.
- **DEC-002** [CQ-002] [FR-010]: Release FS.GG.Workspace.Template 0.9.0 and dual-publish the same packed artifact.
- **DEC-003** [CQ-003] [FR-007] [FR-008] [FR-009]: Split acceptance into a complete installed-package lifecycle per provider identity and a deterministic lifecycle semantic matrix for every provider/profile/lane, including can-fire controls.

## Accepted Deferrals
No accepted deferrals recorded.

## Remaining Ambiguity
No blocking ambiguity remains.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd checklist --work typed-sdd-p4-templates`.
