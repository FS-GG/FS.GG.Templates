# C3-TEMPLATES-01 — Ordinary V2 receiver adoption

Status: ordinary V2 activation source. The main-only `ordinary-v2` environment has dedicated
custody, and the protected-main workflow pins the verified public Coordination CLI 0.1.6 archive.

FS.GG.Templates is the fixed source repository (`FS-GG/FS.GG.Templates`, repository ID
`1281961814`) under the code-owned `templates-v1` profile. The repository-owned receiver source
changes no branch protection, required check, package, generated workspace, or protected effect.
Section 9.9 workspace impact is **none**: no template or wizard creation path changes, enabled
runtime behavior stays disabled, and no existing workspace upgrade is implied. A later activation
would affect coordination only; it must not change product template defaults.

## Prepared source and native boundaries

- The protected-main push workflow runs a secret-free preflight. Only its exact-run receipt can
  admit the bounded credential job in the dedicated environment. Both jobs use read-only GitHub
  permissions and exact-source checkout without persisted credentials. The credential job pins
  .NET SDK `10.0.400` explicitly in the workflow. This repository has no root `global.json`;
  template SDK pins stay unchanged.
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
  `bc0e89012804736268eb955077b6c03ab5793a50` and the `ordinary-v2` environment ID
  `22939062322`, restricted to its sole `main` branch policy ID `61312282`, with no reviewers.
  Environment protection rule ID is `66982112`. Its three dedicated secret names were enrolled
  through the signed sealed bridge at `.github` commit `3ed9b4f8316a14c5e15bfb4c1e11554730b9ae3f`
  (run `36450830306`, attempt 1) and independently read back. No secret values are in source.
- The immutable `v0.1.6` tag resolves to source
  `275cccb30a5c9ade4b3bba344ede13d7df446d13`. Publisher run `36457989575` succeeded after
  both served feeds and an anonymous install were read back. The public release archive SHA-256
  is `0f5d92799af84acb8663df0f524dc2ccfe54cfcc0bc6ad2183e867c8cdd47730`; the workflow
  verifies it before installing from a temporary local-only source. Nuget.org adds a signature
  to its served archive but preserves the package payload.

## Installation boundary

Admit this source only through a reviewed PR with the three native required checks, then merge its
exact green head. The protected-main run must produce a secret-free receipt, execute one installed
settlement attempt, and write one Authority effect. Read that Authority result independently and
normally rerun the whole workflow to verify `SettlementAlreadyComplete` with an unchanged shard.
