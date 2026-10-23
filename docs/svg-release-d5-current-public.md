# Current public D.5 receiver

The successor qualifier targets the remaining contract in
[organization issue #4849](https://github.com/FS-GG/.github/issues/4849), under
[the SVG release outcome](https://github.com/FS-GG/.github/issues/4644).
It selects exactly public Workspace.Template 0.19.3, SDD 2.4.0 and Wizard 0.22.0.
The historical [D.5 public-default route](svg-release-d5-public-default.md) keeps its
original versions, source and acceptance. The current
[run 39988246429](https://github.com/FS-GG/FS.GG.Templates/actions/runs/39988246429)
retains its accepted clean-creation, four-build and dedicated-browser scope; this
qualifier does not repeat those product builds or browser runs.

The current entry point is
`tests/composition/fable-game/verify-svg-release-d5-current-public.sh`.
Its closed pin input binds each package's public archive SHA256 and NuSpec source
commit, the immutable provider descriptor, and the independently published 0.18.2
initial knowledge overlay. Package checks reuse the maintained D.5 archive checker
and ProviderTool's publication and installed-tool commands. No producer is packed
and no provider descriptor is rewritten.

Run the pure controls locally:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/composition/fable-game/test-d5-current-public.py
```

They invoke the actual shell preflight with workload sentinels, reject historical,
mixed and malformed identities, exercise the shared package parser, and detect
authority publication or owner-file mutation on refusal. These tests require no
CLR, network, package acquisition, npm or browser.

Emit the exact pin document and validate it without creating an evidence directory:

```bash
python3 tests/composition/fable-game/d5-current-public.py pins > /absolute/current-pins.json
bash tests/composition/fable-game/verify-svg-release-d5-current-public.sh \
  /absolute/current-pins.json /absolute/unused-evidence --preflight-only
```

Runtime requires separate root admission of the reviewed source, public identities,
resource profile, original operation and finite window. The manual
`svg-release-d5-current-public.yml` workflow and direct script default to `rehearsal`;
full script execution requires the explicit `--full` flag. Its preflight
must pass before SDK/profile-tool setup or product acquisition. The proposed hosted
profile is Linux x64, .NET SDK 10.0.401, Go 1.24.1, exact profile-2 Quint 0.32.0/lmt
bytes and the existing Linux user/network namespace sandbox. The job has a
45-minute ceiling; actual resource, cleanup and evidence acceptance remain root-owned.
No runtime result follows from delivering this source.

Rehearsal creates three fresh receivers: raw SDK omission, provider omission and
Wizard omission. It checks Player files, the two orchestrated root `typed-sdd`
lifecycles, then authors and inspects each default with the backend flag omitted.
It verifies current producer/profile/artifact identities and refuses wrong-profile
bindings while comparing hashes of existing authority and owner files. Before each
Wizard creation, a new isolated hive contains only the exact initial overlay when
the current Wizard's typed/omitted preflight requires it; the final hive must contain
only the selected public 0.19.3 workspace registration. No global installation changes.

Full mode additionally materializes the four declared lifecycle tokens (`none`,
`sdd`, `typed-sdd`, `spec-kit`) with all five named SVG bundles (`player`, `studio`,
`tactical`, `arcade`, `complete`) through both provider and Wizard routes. These
choices come from the pinned current package's template symbols and Wizard 0.22.0
option contract. The package checker refuses a changed choice/default declaration;
each actual cell must succeed with its expected lifecycle and contents. A refusal
is a gap to resolve, not permission to omit a cell. Complete-only FourD, external
authority, soldier and WASM reference files are checked as contents; no native,
WASM or browser execution is claimed by those checks.

Receipts bind actual completed cases, source and archive identities, provenance,
authored authority and before/after owner hashes. Rehearsal explicitly reports the
full matrix pending. Both modes leave retained upgrades, product-native adoption,
public hosting, exhaustive model verification and the whole outcome's remaining
assertions separate. All historical failures and Unknown effects remain retained.

Preflight choice: focused static and actual-caller refusal controls precede the
costly receiver. The workflow has one ordered qualification job, no shared cache,
retry coordinator, publication or evidence-reuse state machine; a custom model
would add little to this boundary. The first six pure controls ran in 0.271 seconds
on the source host. This is local validation cost, not measured runner savings.
