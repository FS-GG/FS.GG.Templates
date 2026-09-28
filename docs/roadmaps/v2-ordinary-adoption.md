# C3-TEMPLATES-01 — Ordinary V2 receiver adoption

Status: disabled source prepared. The main-only `ordinary-v2` environment exists; dedicated
credential enrollment, Coordination CLI 0.1.6 publication, installation, and activation remain
pending.

FS.GG.Templates is the fixed source repository (`FS-GG/FS.GG.Templates`, repository ID
`1281961814`) under the code-owned `templates-v1` profile. The repository-owned receiver source
changes no branch protection, required check, package, generated workspace, or protected effect.
Section 9.9 workspace impact is **none**: no template or wizard creation path changes, enabled
runtime behavior stays disabled, and no existing workspace upgrade is implied. A later activation
would affect coordination only; it must not change product template defaults.

## Prepared source and native boundaries

- The protected-main push workflow has an unconditional false job guard. It has read-only GitHub
  permissions, no persisted checkout credential, credential job, environment binding, secret
  reference, package download, or settlement command. It invokes no .NET setup while disabled;
  this repository has no root `global.json`. A later credential job must use the CLI-supported
  SDK explicitly in the workflow without changing template SDK pins or adding a root SDK pin.
- The secret-free observer and qualifier derive from Net's disabled receiver at
  `dfc04d994e955842a7e16597f7093ed14f1b5251`, adapted only for the code-owned Templates
  source profile. The policy records their exact SHA-256 digests.
- The selected settlement checks are `composition` and `kit / coordination-kit`. The three
  separate native required checks are those two plus `materialize / receiver-validate`. All three
  require GitHub Actions App `15368`; the producer workflows are composition `303314945`,
  coordination coherence `307166384`, and kit materialization `316874197`. The qualifier binds
  each selected check to its exact PR head, workflow, run, job, suite, and attempt. Templates
  does not require or add `routine-eligibility`.
- The shared policy ID is `v2-ci-i1-ordinary-settlement-v1`. The shared Authority anchor retains
  App `5064713`, installation `164553252`, Authority repository `1351660651`, and the existing
  writer and integrity ruleset pins. No V1 admission or receiver state is imported.
- Read-only API observation on 2026-09-28 found protected main
  `f3a7cd6ab6f035d4ba335d03fdc367db6164793f` and the new `ordinary-v2` environment ID
  `22939062322`, restricted to its sole `main` branch policy ID `61312282`, with no reviewers.
  Environment protection rule ID is `66982112`. Its current secret count is zero. Dedicated
  custody will be enrolled through the separate sealed bridge and independently read back.
- No immutable published CLI release with `templates-v1` support is selected. Version and
  package SHA-256 remain null; the disabled source cannot settle work. Activation requires a
  verified public 0.1.6 package and custody evidence.

## Installation boundary

One later reviewed source change must bind the immutable published CLI 0.1.6 asset digest and
`templates-v1` capability, current Templates identity and check producers, dedicated secret names,
and shared Authority binding. It must change policy status, installed state, package evidence,
observer guard, and a bounded credential job together. Preserve the three native required checks,
merge only an exact green PR head, and verify the protected Authority result and normal
`SettlementAlreadyComplete` whole-workflow rerun after activation.
