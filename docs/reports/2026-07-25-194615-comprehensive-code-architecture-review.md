# Comprehensive code and architecture review

- Repository: `FS-GG/FS.GG.Templates`
- Reviewed revision: `7b0cc2c11b37118c8a9e7c1a36399fa1db800be3`
- Review completed: 2026-07-25 19:46:15 UTC (21:46:15 CEST)
- Scope: template package, provider descriptors, scripts, release/composition workflows, documentation, and downstream contract role

## Executive assessment

Templates is intentionally small and mostly declarative. The package builds successfully, and all current GitHub checks are green. The key architectural risk is in release provenance: the publish job independently re-packs instead of publishing the exact package artifact verified earlier. This is currently low-impact because the project has no package dependencies, but it is a latent supply-chain/reproducibility defect.

Overall risk: **low to medium**. Composition validation is strong; release byte identity should be tightened before the package gains more build inputs.

## Architecture

The repository packages workspace templates and provider metadata, while executable behavior is delegated to versioned SDD, Rendering, and Governance tools. This keeps the template repository thin and makes downstream composition checks the critical architectural gate. Provider descriptors serve as a machine-maintained dependency contract and should remain declarative.

## Evidence

| Check | Result |
|---|---|
| `dotnet pack FS.GG.Templates.csproj -c Release` | Succeeded; produced `FS.GG.Templates.0.6.0.nupkg` |
| Current-revision GitHub checks | 3 succeeded, 0 failed |
| Packaging warning | Package has no NuGet readme |

This review exercised packaging and inspected workflows/configuration. It did not install every template on every supported OS or publish a package.

## Findings

### 1. Medium — release publishes a newly packed artifact rather than the verified artifact

In `.github/workflows/release.yml`, the publish job runs a fresh bare `dotnet pack`. That means build inputs, restore resolution, or tooling can differ from the package exercised by preceding jobs.

The project currently has no package dependencies, so practical divergence is limited. The workflow nevertheless lacks a “verify once, publish exact bytes” guarantee.

Recommendation: pack once with locked inputs, upload the `.nupkg` as an immutable workflow artifact, run composition/package checks against that artifact, and publish the same checksum-verified file.

### 2. Low — the NuGet package lacks an embedded/readme declaration

`dotnet pack` warns that the generated package has no readme. For a template package, discoverability and compatibility expectations are part of the user contract.

Recommendation: set `PackageReadmeFile`, include a concise package readme, and validate its presence in the package-content check.

### 3. Low — provider metadata is a large, history-heavy generated contract

`providers/rendering.providers.yml` carries substantial machine-maintained history. This supports traceability, but produces high-churn diffs that can obscure the effective current selection.

Recommendation: keep generation deterministic, validate uniqueness/order, and provide a small generated “effective providers” summary for review. Do not hand-edit generated history.

### 4. Low — release tool bootstrapping partially tolerates installation failure

The release/composition setup includes a governance CLI installation guarded with `|| true`. Later composition normally exposes a missing tool, but the immediate failure loses specificity.

Recommendation: tolerate only an already-installed condition; otherwise fail with the tool version and installation diagnostic.

## Strengths

- The repository stays declarative and delegates behavior to versioned tools.
- Live composition checks are green.
- The package builds cleanly apart from the readme warning.
- Provider metadata makes cross-repository selection auditable.
- The small code surface limits direct runtime risk.

## Recommended order

1. Publish the exact package artifact validated by CI.
2. Add and verify a package readme.
3. Tighten tool-install error handling.
4. Add a concise generated effective-provider view.
