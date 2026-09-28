# Release D.5 public default qualification

This receiver qualifies public Templates 0.15.0 with SDD 2.0.2, and public wizard
0.12.0 when available. It is separate from the historical 0.14.0/0.11.2 public
workflow. It never packs a producer, consumes a sibling build, publishes a package,
or changes the effective registry/default.

After the release workflows finish, collect each public archive SHA-256 and
NuSpec repository commit. Collect the SHA-256 of the Templates provider descriptor
at that source commit. Supply those identities in a local JSON file:

```json
{
  "schema": "fsgg.svg-release-d5.public-pins/1",
  "mode": "templates",
  "templates": {
    "version": "0.15.0",
    "sha256": "REQUIRED_PUBLIC_ARCHIVE_SHA256",
    "sourceCommit": "REQUIRED_MERGED_SOURCE_COMMIT",
    "providerSha256": "REQUIRED_IMMUTABLE_PROVIDER_SHA256"
  },
  "sdd": {
    "version": "2.0.2",
    "sha256": "REQUIRED_PUBLIC_ARCHIVE_SHA256",
    "sourceCommit": "REQUIRED_PACKAGE_SOURCE_COMMIT"
  }
}
```

The placeholders intentionally fail preflight. Do not substitute a local pack hash
for a public archive hash. For the full proof, set `mode` to `full` and add `wizard`
with `version: "0.12.0"`, its public `sha256` and `sourceCommit`. Templates-only
mode rejects a wizard entry and reports the wizard as pending.

Run locally with the qualified Quint/lmt binaries and exact .NET SDKs from the
workflow:

```bash
bash tests/composition/fable-game/verify-svg-release-d5-public-default.sh \
  /absolute/public-pins.json /absolute/new-evidence --preflight-only
QUINT_BIN=/absolute/quint LMT_BIN=/absolute/lmt \
  bash tests/composition/fable-game/verify-svg-release-d5-public-default.sh \
  /absolute/public-pins.json /absolute/new-evidence
```

Once this workflow is on protected main, dispatch
`svg-release-d5-public-default.yml` with the complete JSON as its `public_pins`
input. The preflight runs before qualification; pull requests run only static and
identity refusal tests. The evidence artifact is
`svg-release-d5-public-default-<run-id>-<attempt>`.

Each invocation uses a previously nonexistent output directory, fresh .NET home,
NuGet package/HTTP caches and isolated tool paths. It downloads exact packages from
nuget.org, verifies their hashes and NuSpec identities, then checks installed tool
archive identity and the template package's lifecycle defaults/choices. The
immutable tag must resolve to the package source commit, and tag/source provider
descriptors must match. The package-backed provider remains unmodified.

The receipt covers raw Player product omission; installed-provider root lifecycle
omission; all four explicit tokens; complete bundle content; and fresh
`svgFoundation=false` omission/explicit-sdd behavior. Full mode also covers wizard
omission and explicit tokens using the immutable provider tag. Both omitted roots
author with the backend omitted, inspect Quint profile-2 authority and artifact
hashes, run six named invariants for 32 traces of at most 12 steps with a fixed seed,
and refuse wrong-profile bindings without publishing authority. All raw/provider
lanes and, in full mode, all wizard lanes perform locked restore/build.

This is compiled-authority and sampled-model verification, not exhaustive model
checking or a full SDD `verificationReady` lifecycle. No installed-public pass is
claimed until the real public run completes. A Templates-only pass leaves the
wizard join pending. After full candidate qualification and the separately owned
registry/default update, repeat with another empty output directory using the
effective pins and independently read back the selected default. The receipt
deliberately leaves that activation/readback pending for its owner.

Preflight choice: static checks and focused identity/refusal tests, with a small
local investment, catch historical versions, missing hashes, wrong package source,
and incomplete wizard joins before tool bootstrap and the bounded 70-minute job.
This linear workflow has no shared cache, publication, retry coordinator or custom
model. No runner savings are claimed without measurement.
