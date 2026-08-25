---
schemaVersion: 1
workId: 436-workspace-template-0-10-0-release
title: Workspace Template 0 10 0 Release
stage: clarify
changeTier: tier1
status: needsAnswers
sourceSpec: work/436-workspace-template-0-10-0-release/spec.md
publicOrToolFacingImpact: true
---

# Workspace Template 0 10 0 Release Clarifications

## Source Specification
- work/436-workspace-template-0-10-0-release/spec.md

## Clarification Questions
- CQ-001 [AMB:AMB-001]: Must the Templates 0.10.0 cut consume the independently planned Game 0.14.0 release?
- CQ-002 [AMB:AMB-002]: Does the existing release workflow already implement the required pack-once, tag-bound, dual-feed route?
- CQ-003 [AMB:AMB-003]: Where is the boundary between preparation evidence and post-merge publication evidence?

## Answers
- CQ-001 → No. The generated fable-game workspace retains its exact Game 0.13.0 pin; that published version remains valid and Templates has no contractual dependency on Game 0.14.0. The four provider descriptors do advance their self-package source to 0.10.0 so orchestration selects this release.
- CQ-002 → Yes. The current workflow resolves the tag/head, packs one archive, uploads it once, gates the downloaded artifact through all four workspace lanes, publishes GitHub-first then nuget.org, and supports checksum-bound failed-run replay.
- CQ-003 → The preparation PR owns the 0.10.0 source declaration, release notes, SDD package, exact candidate archive, and preflight gates. The tag, both feed pushes, downloaded-byte comparison, public-only clean install, registry continuation, and downstream dispatch are post-merge obligations.

## Decisions
- **DEC-001** [CQ-001] [AMB:AMB-001] [FR-002]: Keep external generated dependency pins unchanged while advancing the four self-package provider sources to 0.10.0; the release version advances because merged template behavior becomes installable, not because its external dependency graph changes.
- **DEC-002** [CQ-002] [AMB:AMB-002] [FR-003] [FR-004] [FR-005]: Reuse the existing producer workflow unchanged unless executable preflight proves a distinct defect; no speculative workflow churn is part of the cut.
- **DEC-003** [CQ-003] [AMB:AMB-003] [FR-006] [FR-007]: Declare publication and registry work as exact-head post-merge delivery obligations and do not represent them as preparation-PR evidence.

## Accepted Deferrals
- None.

## Remaining Ambiguity
- None.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd checklist --work 436-workspace-template-0-10-0-release`.
