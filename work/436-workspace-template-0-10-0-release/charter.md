---
schemaVersion: 1
workId: 436-workspace-template-0-10-0-release
title: FS.GG.Workspace.Template 0.10.0 accessible-browser release
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

# FS.GG.Workspace.Template 0.10.0 accessible-browser release Charter

## Identity
Cut the public `FS.GG.Workspace.Template` 0.10.0 package so the accessible
fable-game browser baseline already merged on `main` is installable from both
supported feeds.

## Principles
- Prepare exactly one package archive from one merged source revision and reuse those bytes for every feed.
- Keep the five provider/template identities intact: governance, console, web, fable-bindings, and fable-game.
- Publish before the Coordination registry advertises 0.10.0; registry reconciliation is a separate feed-derived continuation.
- A version tag or local pack is not completion: generated-workspace behavior, dual-feed identity, package metadata, and a clean install are all release facts.

## Scope Boundaries
- In scope: a SemVer MINOR bump from 0.9.0 to 0.10.0, release notes/design documentation, package preflight, full composition and browser verification, and explicit post-merge publication obligations.
- In scope: the already-merged accessible-browser files from Templates #417 as the behavior being released.
- Out of scope: new browser behavior, changes to any template identity, upstream Game/Rendering/SDD releases, consumer pin changes, and pre-publication registry claims.
- Out of scope: repacking between feeds or moving an immutable release tag.

## Policy Pointers
- Constitution I and VI require specification before release edits and observed test evidence.
- The repository release workflow is the producer authority for tag, pack-once, composition, publish ordering, and dispatch.
- The FS-GG publishing-and-deployment contract requires GitHub Packages first, byte-identical nuget.org publication second, then feed-derived registry reconciliation.
- SDD policy comes from `.fsgg/sdd.yml` and `.fsgg/agents.yml`; optional Governance files remain compatibility pointers only.

## Lifecycle Notes
- The release candidate stops at an independently reviewable PR; no tag or publication is authorized before fresh critic and host acceptance.
- Next lifecycle action: `fsgg-sdd specify --work 436-workspace-template-0-10-0-release`.
