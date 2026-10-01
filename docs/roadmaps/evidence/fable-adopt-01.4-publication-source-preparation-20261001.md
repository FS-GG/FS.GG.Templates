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
