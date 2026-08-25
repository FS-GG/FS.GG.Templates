---
schemaVersion: 1
workId: typed-sdd-p4-templates
title: P4 Typed SDD templates adoption
stage: charter
changeTier: tier1
status: chartered
policyPointers:
  - .fsgg/sdd.yml
  - .fsgg/agents.yml
  - .fsgg/policy.yml
  - .fsgg/capabilities.yml
  - .fsgg/tooling.yml
---

# P4 Typed SDD templates adoption Charter

## Identity
- Work id: `typed-sdd-p4-templates`
- Lifecycle stage: charter
- Status: chartered

## Principles
- Lifecycle selection is one public contract across every supported provider and profile.
- FS.GG.SDD owns lifecycle artifacts; product templates only accept and preserve the selected lane.
- Published packages, not sibling-source shortcuts, are the acceptance authority.
- Negative controls must prove that each guard can fire with a distinct diagnostic.

## Scope Boundaries
- Keep SDD lifecycle ownership separate from optional Governance enforcement.
- Consume the already-published SDD, Rendering, and workspace-registry contracts; do not alter their implementations here.
- Preserve direct `dotnet new`, Standard SDD, and Freeform behavior while adding Typed SDD.

## Policy Pointers
- SDD policy comes from `.fsgg/sdd.yml` and `.fsgg/agents.yml`.
- Governance files are optional compatibility pointers and are not evaluated by this command.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd specify --work typed-sdd-p4-templates`.
