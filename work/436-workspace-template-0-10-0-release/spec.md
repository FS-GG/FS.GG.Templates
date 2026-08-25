---
schemaVersion: 1
workId: 436-workspace-template-0-10-0-release
title: Workspace Template 0 10 0 Release
stage: specify
changeTier: tier1
status: specified
publicOrToolFacingImpact: true
---

# Workspace Template 0 10 0 Release Specification

Prose status: specified

## User Value
Consumers can install the accessible fable-game browser baseline merged by
Templates #417 as a stable, source-verifiable `FS.GG.Workspace.Template` 0.10.0
package from either supported feed.

## Scope
- SB-001: Advance the single `FS.GG.Workspace.Template` coherent package from 0.9.0 to 0.10.0 as a SemVer MINOR release.
- SB-002: Preserve the five identities carried by the package: governance, console, web, fable-bindings, and fable-game.
- SB-003: Prepare one source-bound archive, run the existing release and generated-product gates over that archive, and declare the post-merge publish/verification obligations.
- SB-004: Publish only after the release preparation PR is reviewed, accepted, merged, and identified by its immutable release tag.

## Non-Goals
- SB-005: Do not add or alter accessible-browser behavior; this cut distributes the implementation already merged by #417.
- SB-006: Do not advance Game, Rendering, SDD, npm, or other external dependency pins solely because this package version advances; the four provider descriptors' self-package sources advance coherently to 0.10.0.
- SB-007: Do not edit the Coordination registry before both package feeds report the released bytes.
- SB-008: Do not rename a template or package identity, repack between feeds, move a tag, or publish from an unmerged feature head.

## User Stories
- US-001 (P1): As a workspace consumer, I can install version 0.10.0 and generate a fable-game workspace whose browser baseline is keyboard accessible and behaviorally tested.
- US-002 (P1): As a release operator, I can prove the two feeds expose the same prepared package from the tagged merged source without recreating its bytes.
- US-003 (P2): As a fleet maintainer, I receive a registry update only after publication is observable, so compatibility projections never advertise a package that consumers cannot restore.

## Acceptance Scenarios
- AC-001 [US-001] [FR-001] [FR-002]: Given the release candidate is packed, when its template inventory is inspected and instantiated, then it reports version 0.10.0 and retains all five identities with the #417 fable-game browser files present.
- AC-002 [US-001] [FR-003]: Given the one prepared candidate archive, when the full composition and fable-game browser lanes run, then generated products restore, build, test, publish, and pass the accessible two-client browser scenarios against those exact bytes.
- AC-003 [US-002] [FR-004] [FR-005]: Given the accepted preparation PR is merged, when `fs-gg-templates/v0.10.0` is created at that merge and the producer workflow runs, then the tag/version/source bindings hold and GitHub Packages receives the prepared archive before nuget.org receives byte-identical content.
- AC-004 [US-002] [US-003] [FR-006] [FR-007]: Given publication succeeds, when both feeds and a clean public-only install are inspected, then package metadata names the tagged source commit, payloads agree excluding only feed-added signatures, and the feed-derived registry continuation is dispatched.

## Functional Requirements
- FR-001: The project MUST declare package id `FS.GG.Workspace.Template` at version 0.10.0 with release documentation explaining that the MINOR cut exposes the merged accessible-browser baseline. (Stories: US-001; Acceptance: AC-001)
- FR-002: The packed archive MUST retain exactly the five existing identities, advance the four workspace provider self-package sources to `FS.GG.Workspace.Template::0.10.0`, and include the merged #417 fable-game browser sources without changing their behavior in this release preparation. (Stories: US-001; Acceptance: AC-001)
- FR-003: The release preflight MUST pack exactly once from the candidate source, run the full composition suite and every configured identity lane including the fable-game Playwright route against that exact archive, and preserve command-produced test evidence. (Stories: US-001; Acceptance: AC-002)
- FR-004: Publication MUST remain a declared post-merge obligation; the immutable `fs-gg-templates/v0.10.0` tag MUST resolve to the accepted merged source and match the package version before any feed push. (Stories: US-002; Acceptance: AC-003)
- FR-005: The producer workflow MUST push the same prepared archive to GitHub Packages first and then nuget.org, never repacking between destinations. (Stories: US-002; Acceptance: AC-003)
- FR-006: Release verification MUST compare package payloads from both feeds excluding only feed-added signatures, verify the nuspec repository commit and tag anchor, and prove a clean install using nuget.org without a private-feed dependency. (Stories: US-002; Acceptance: AC-004)
- FR-007: The Coordination registry and downstream update fabric MUST advance only through a post-publication, feed-derived continuation after 0.10.0 is observable on both feeds. (Stories: US-003; Acceptance: AC-004)

## Ambiguities
- AMB-001: Does this cut also advance the embedded Game 0.13.0 pin because a separate Game 0.14.0 release is planned?
- AMB-002: Is a newly authored release workflow required, or is the current pack-once/tag/replay pipeline already sufficient for 0.10.0?
- AMB-003: Which facts may be completed in the preparation PR and which must remain post-merge release obligations?

## Public Or Tool-Facing Impact
- The public NuGet package version advances from 0.9.0 to 0.10.0; the package id and five template identities are unchanged.
- The fable-game identity now becomes publicly installable with the already-merged #417 browser accessibility baseline.
- No generated workspace external dependency pin or command-line option changes in this cut; provider self-package sources advance to the released 0.10.0 archive.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd clarify --work 436-workspace-template-0-10-0-release`.
