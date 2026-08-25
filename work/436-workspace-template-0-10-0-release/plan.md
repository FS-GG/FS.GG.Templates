---
schemaVersion: 1
workId: 436-workspace-template-0-10-0-release
title: Workspace Template 0 10 0 Release
stage: plan
changeTier: tier1
status: planned
sourceSpec: work/436-workspace-template-0-10-0-release/spec.md
sourceClarifications: work/436-workspace-template-0-10-0-release/clarifications.md
sourceChecklist: work/436-workspace-template-0-10-0-release/checklist.md
publicOrToolFacingImpact: true
---

# Workspace Template 0 10 0 Release Plan

Prose status: planned

## Source Snapshot
- spec: work/436-workspace-template-0-10-0-release/spec.md sha256:6135239f367c422c9628c95b972e812944ad558ec2280f31bb7e7a4e2c2d3ec9 schemaVersion:1
- clarifications: work/436-workspace-template-0-10-0-release/clarifications.md sha256:5a7cf8f502e79e2a07fc142c7486229cf8ea5da6af1871e0c1e238c33d6e6c95 schemaVersion:1
- checklist: work/436-workspace-template-0-10-0-release/checklist.md sha256:5b9911f4246619ffdd70a392ef7f4d985301839893e7c66e702bad62495f8b5b schemaVersion:1

## Plan Scope
- Change the package version, four self-package provider source pins, release-version preflight expectation, and release documentation only; the accessible-browser implementation remains the already-reviewed #417 tree.
- Treat `FS.GG.Templates.csproj` as the package manifest and `.github/workflows/release.yml` as a read-only release contract unless an executable gate demonstrates a defect.
- Produce the SDD sources/readiness views, candidate package, command-produced test report, and exact-head delivery-obligation declaration as the reviewable preparation unit.

## Plan Decisions
- PD-001 [AC-001] [FR-001] complete: Change `<Version>` from 0.9.0 to 0.10.0 and add a concise rationale tying the MINOR increment to the merged accessible-browser behavior; prepend a 0.10.0 release note to README and align design prose where the published baseline is named.
- PD-002 [AC-001] [FR-002] [DEC-001] complete: Do not edit the #417 browser sources or external dependency pins; advance the four workspace provider self-package sources to 0.10.0, regenerate/check their effective projection, and inspect the packed `.template.config/template.json` inventory for the five existing identities plus the accessible fable-game payload.
- PD-003 [AC-002] [FR-003] [DEC-002] complete: Restore locked inputs, pack once to an isolated artifact directory with repository commit metadata, bind the package path through `FSGG_TEMPLATES_NUPKG`, and run the full composition suite so all identity and browser lanes consume that archive.
- PD-004 [AC-003] [FR-004] [DEC-003] complete: Open a canonical `item/436-*` PR that closes #436 and declares exact-head obligations for tag creation/publication, dual-feed verification/clean install, and registry/downstream reconciliation; create no tag during preparation.
- PD-005 [AC-003] [FR-005] [DEC-002] complete: Retain the current producer workflow because it already binds tag/version/source, downloads the one uploaded archive into its gate and publish jobs, pushes GitHub Packages before nuget.org, and supports immutable-tag replay.
- PD-006 [AC-004] [FR-006] [DEC-003] complete: After merge, verify tag SHA, workflow source SHA, nuspec repository commit, both feed downloads, normalized payload identity, and a clean nuget.org-only install before completing the publication obligation.
- PD-007 [AC-004] [FR-007] [DEC-003] complete: Only after both feeds agree, route the feed-derived Coordination registry update and downstream dispatch as the final obligation; do not author registry state in this repository.

## Contract Impact
- PC-001 [PD-001] [PD-002] packageManifest: `FS.GG.Workspace.Template` and its four workspace provider self-sources advance to 0.10.0 while the package id, five dotnet-new identities, parameters, external dependency pins, and generated file layout remain compatible.
- PC-002 [PD-004] [PD-005] releaseContract: `fs-gg-templates/v0.10.0` identifies the accepted merged source; one archive crosses pack, gate, GitHub Packages, nuget.org, and GitHub Release without repacking.
- PC-003 [PD-007] continuationContract: registry/downstream state is derived from observable feed publication and cannot be completed by the preparation PR.

## Verification Obligations
- VO-001 [PD-001] [PD-002] [PC-001] packageInspection: Assert the nuspec id/version/repository commit, the exact template identity inventory, and representative #417 accessible-browser payload paths in the one prepared archive.
- VO-002 [PD-003] [PC-001] generatedProductTest: Run `tests/composition/run.sh` with every configured lane against `FSGG_TEMPLATES_NUPKG`; retain its command-produced JUnit and require the fable-game Playwright/two-client acceptance route to pass.
- VO-003 [PD-004] [PD-005] [PC-002] releasePreflight: Parse the current workflow to prove tag/version/source binding, one uploaded package artifact, gate use of that artifact, and GitHub-first/nuget-second publication; invert the candidate version/tag relation and require the existing release guard to fail.
- VO-004 [PD-006] [PD-007] [PC-002] [PC-003] postMergeVerification: After merge and publication, compare feed downloads excluding only signatures, run a clean public-only install, verify the tag/source metadata, and attach the registry/downstream receipts.

## Performance Intent
No performance intent is declared for this work item.

## Migration Posture
- PM-001 [PC-001] additiveMinor: Existing installations stay valid and can update within the same package id; generated command shapes and pins are unchanged, while new installs receive the #417 accessible-browser baseline.
- PM-002 [PC-002] immutableRelease: A failed tag run is resumed through the workflow's checksum-bound replay path; the tag is never moved and the package version is never overwritten.

## Generated View Impact
- GV-001 [PD-001] [PD-003] sddReadiness: `readiness/436-workspace-template-0-10-0-release/**` is regenerated from the authored work package and must reach `implementationReady` before source edits and `shipReady` before review handoff.
- GV-002 [PD-007] registryProjection: the Coordination compatibility projection changes only in the separately owned, feed-derived post-publication continuation.

## Accepted Deferrals
No accepted plan deferrals recorded.

## Planning Findings
No blocking planning findings recorded.

## Advisory Notes
- Optional Governance pointers remain compatibility facts only.

## Lifecycle Notes
- Next lifecycle action: `fsgg-sdd tasks --work 436-workspace-template-0-10-0-release`.
