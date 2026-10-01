# FABLE-ADOPT-01.4 publication source preparation — 2026-10-01

This source window prepares `FS.GG.Workspace.Template` 0.17.0 and a public-only installed-reference qualification. It preserves Game 0.16.0, Rendering 0.31.0, the typed-sdd lifecycle default, the canonical Python projection, and every existing template identity.

The provider descriptor selects `FS.GG.Workspace.Template::0.17.0`. Release jobs use SDK 10.0.401 at the two formerly floating setup points. Existing pack-once, dual-feed push, payload readback, and release ordering remain unchanged.

`ProviderTool reference-publication-check` owns the stateless archive contract: exact archive SHA-256, package ID/version, source revision, descriptor source/default, safe unique bounded ZIP census, and required complete-bundle FourD reference members. The manual public workflow downloads only from nuget.org and the exact protected source revision. It creates direct, provider, and pinned-wizard complete receivers, then executes the real FourD browser test with one worker and refuses skips.

Publication, feed readback, tag creation, installed qualification, retained upgrades, product adoption, and native acceptance remain pending root-owned operations. Before any tag, verify 0.17.0 is unoccupied on both feeds and in tags/releases. A GitHub Packages 403 remains unknown and blocks publication admission.

## Bounded feed occupancy source window

The routine successor based on `907242cbce167d88cc7155a28268367bb5538438` adds `operation=feed-occupancy` to the existing release workflow. Its isolated job has only `contents: read` and `packages: read`, checks out the dispatched commit without persisted credentials, binds the actual commit/tree through step-written environment values, and invokes the existing ProviderTool with `feed-occupancy --version <canonical-stable-version>`. Replay remains the dispatch default and still requires its tag and failed source run. Occupancy refuses replay inputs; replay refuses a candidate version. Route, pack, gate, and publish explicitly exclude the read-only operation.

The stateless F# implementation fixes the package, owner, repository, and endpoint identities; disables redirects and retries; sends the workflow token only to `api.github.com`; brackets an active/deleted GitHub version census with exact metadata reads; resolves the public NuGet PackageBaseAddress and reads its complete version index; and returns independent `ABSENT`, `OCCUPIED`, or `UNKNOWN` verdicts. Only two authoritative absences exit successfully. Receipts contain status/count/completion data and response hashes, without headers or raw feed censuses.

Local source qualification on 2026-10-01:

- `dotnet run --project tests/ProviderComposition.Tests/ProviderComposition.Tests.fsproj -c Release`: 92 checks passed, measured final warm duration 3.59 seconds. Cases include both absent, active/deleted/public occupancy, later pages, redirect/401/403/404 refusal, wrong binding, changed metadata, malformed/duplicate evidence, pagination, time/size/page bounds, stable aliases, prerelease distinction, GET-only transport, public-token isolation, and sanitized receipts.
- `dotnet restore FS.GG.Templates.csproj --locked-mode`: passed in 0.54 seconds.
- exact canonical-fixture `dotnet pack` of 0.17.0: passed in 1.66 seconds after restore.
- existing `release-preflight.py --self-test` plus the packed 0.17.0 archive and changed workflow: passed.
- changed workflow shell blocks parsed with `bash -n`; the workflow parsed as one YAML document with the already-cached YamlDotNet 18.1.0 parser; explicit operation/effect guard and preflight-order assertions passed.
- `actionlint` was not installed in the workspace and no repository-provided invocation was present, so no actionlint result is claimed and no convenience install was introduced.

No live feed request, credential read, tag, publication, installation, browser run, push, PR mutation, or registry/progress flip occurred in this source window. Root still owns native dispatch/readback and the time-bounded pre-tag decision.

## Canonical candidate and deadline repair

Independent review of frozen head `23b27026097cac16786274ef5f78dfca206f7f09` identified two bounded defects, recorded in `/tmp/fable-feed-occupancy-source-review-20261001-2100.md` at SHA256 `1104a0b0a58107d0713be4d720c69158520dc005e60bbbe8d8593acf77ff2971`. That reviewed head remains historical and unchanged.

The successor uses absolute `\A`/`\z` ASCII version patterns, so terminal LF/CRLF and other trailing material are refused rather than normalized. The transport now carries the effective cancellation token through asynchronous header, stream, and body reads. Each injected request is timed, the shared acquisition deadline is checked after transport/body completion, and both feed classifiers recheck it immediately before producing a complete verdict. A late final response therefore remains `UNKNOWN` and cannot create false absence.

Focused qualification passed all 92 prior checks plus ten repair controls in 4.20 seconds on the first repair run and 1.51 seconds on the final warm run. The added controls reproduce and close newline candidate false absence, malformed served newline identity, a final response returning after both request and aggregate deadlines, and a body stalled after headers. The stalled-body control uses the production HTTP transport with an injected handler and confirms cancellation reaches the content stream within the bounded control window. The unchanged workflow effect-isolation/preflight assertions passed. Cached actionlint 1.7.12 (`c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4`) validated the actual workflow with `-shellcheck= -pyflakes=` and no diagnostics.

This repair made no workflow, CLI, project, publication, credential, live-feed, tag, installation, browser, registry, or remote change. Native occupancy and every later release/installed effect remain root-owned and pending.

## Deleted-census capability diagnostic source

Protected source `40a1bfd992a4d040181af3e196a26afa07be6d62`, tree `599b5b0e60ac05e57c050b986980dbf0232599c8`, produced read-only run `36934881826`. Its retained receipt SHA256 is `1846861aa0930165cc33f46c35b3942cc58630be97a4f0fc318cb2d1269aa17c`: GitHub metadata returned 200, the active census returned 200 with 12 records, the deleted census returned 403, and NuGet independently returned `ABSENT`. GitHub and overall remained `UNKNOWN`; route, pack, release-route and publish were skipped. That result is correct and does not admit publication.

The bounded successor adds an optional `githubPackages.failureDiagnostic` only for non-200 GitHub responses. It records a closed phase/page/status/error class, bounded accepted-permissions parsing with preserved AND terms and OR alternatives, and only enumerated package scope tokens from narrowly recognized messages. Missing, malformed, unrecognized and oversized headers remain explicit. Raw headers, bodies, messages, URLs, credentials, cookies, held scopes and organization data are never emitted. The original status and response hash remain in the receipt, while feed classification, complete active-plus-deleted census, read-only permissions, fixed-host authorization, retry policy and acquisition limits are unchanged.

Local qualification on 2026-10-02 passed 142 checks in 4.13 seconds, retaining all 102 earlier checks. Controls cover the observed 200/200/403 sequence, successful empty and occupied deleted censuses, missing/valid/alternative/malformed/duplicate/conflicting/over-limit permission headers, closed serialized fields, body/header redaction, diagnostic body limits, original status/hash custody, non-GET and authenticated off-host refusal, and absence of Authorization on NuGet. Cached actionlint 1.7.12 passed against unchanged `release.yml`; the unchanged effect-isolation and read-only permission assertions passed; the existing release preflight passed against the retained 0.17.0 archive (`4651704ec70b2e230e7f3260488c3ce51701fbe80abb66b607a6250de797ad44`).

No permission increase is selected. Live occupancy is still `UNKNOWN` and publication is pending. Root owns protected integration and one fresh read-only diagnostic run; its actual sanitized diagnostic determines whether any separate permission experiment is justified. No live request, workflow dispatch, credential access, push, PR mutation, tag, publication, package permission change, installation, browser run or registry flip occurred in this source window.

## Accepted-permission alternative classification repair

Review of frozen diagnostic head `ae90cac65e4ed475bac752f3a82a612e4426a439` found that the closed error classifier treated a `packages=admin` term in any accepted-permission alternative as proof that package administration was mandatory. GitHub's header separates alternatives with `;`, so `packages=admin;packages=read` permits either alternative and does not prove an administration requirement.

The successor emits `package-admin-required` for the narrowly recognized administration message or when every valid alternative contains `packages=admin`. Other valid alternatives containing a recognized package permission retain their structured AND/OR sets and use `integration-permission-denied`. Classification remains diagnostic only: non-200 responses, including the observed deleted-census 403, still produce GitHub and overall `UNKNOWN`, preserve the response status and body hash, and cannot admit publication.

Focused qualification adds actual `inspectWith` and serialized-receipt cases for admin OR read, admin OR write, and two distinct AND alternatives that both require package admin. The cases bind the original 403 hash, preserve the parsed alternatives, and confirm that unrecognized upstream messages do not enter the receipt. The workflow and its read-only permissions are unchanged. Live occupancy remains `UNKNOWN`, and publication remains pending the root-owned protected integration and fresh read-only diagnostic run.

The complete ProviderComposition harness passed 148 checks, including all 142 checks from the frozen diagnostic source, in 4.369 seconds. Cached actionlint 1.7.12 passed against unchanged `release.yml`; the release preflight passed against the retained checksum-bound 0.17.0 archive; and the workflow effect-isolation assertions confirmed that occupancy remains read-only while route, pack, gate and publish exclude it and unknown operations fail closed. No live request, credential access, workflow dispatch, push, PR mutation, tag, publication, package permission change, installation, browser run or registry flip occurred in this repair.
