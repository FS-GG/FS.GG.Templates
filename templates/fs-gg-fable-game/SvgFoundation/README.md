# Retained SVG foundation fixture

This is the selected SVG product payload. The default `player` bundle emits the runtime;
`studio`, `tactical`, `arcade`, and `complete` add separate tools and examples.
It consumes the coherent public `FS.GG.UI.Scene`, transitive `FS.GG.UI.KeyboardInput`, and
`FS.GG.UI.Scene.SvgBrowser` packages and mounts two
neutral retained scenes plus the identified Preview-A document. The document combines integer-grid and
fractional coordinates with gradients, affine transforms, nested clipping, alpha/luminance masks, text,
symbols, semantic selection and standalone export. No scene depends on S.I.R. types or on a sibling
Rendering checkout.

`TacticalCompatibility.fs` is a contract fixture and clean-room reimplementation of the disclosed
`SharedSceneProjection` characteristics audited at S.I.R. revision
`80e1ac9328865ec8d1ee3eeea130560ef22b1b01`. The SVG-FOUND-01.1 audit records the copyright
owner's 2026-09-11 authorization context and separately excludes third-party material. This fixture
copies no S.I.R. source, type, asset, package, or dependency. It accepts disclosed presentation
values only, retains ordered layer visibility and product-owned lock characterization, and projects
camera and relevant selection/focus state into the Rendering contract.

The embedded Noto Sans Latin 400 object is sourced from `@fontsource/noto-sans` 5.3.0 and remains under
OFL-1.1; its exact identity and license are recorded in `THIRD-PARTY-NOTICES.md`.

Restore this project from NuGet.org using the exact public Rendering `0.31.0`, Game `0.16.0`, and
Audio `0.6.0` packages. The SVG player is the default Templates 0.14.0 composition.

## Authoring

`Studio/` is a separately compiled and served authoring entry. It consumes the generic Rendering
scene descriptors and mounts `SvgStudio`; the player `Program.fs` does not import studio or geometry
modules. The public template pins the Rendering archive version. Maintainers can still override the
internal `FsGgSvgAuthoringVersion` seam when qualifying a future isolated producer packet:

```bash
bash SvgFoundation/Studio/build.sh
./Client/node_modules/.bin/vite --config SvgFoundation/Studio/vite.config.js
```

The build adapter extracts the geometry worker, npm lock, verified Noto bytes and manifest from the
restored `FS.GG.UI.Scene.SvgBrowser` archive into ignored output. There is no checked-in worker,
font, or polygon-clipping implementation. The generated controls use neutral sample descriptors;
terrain rules, traversal, collision and gameplay meaning remain product-owned.

Scene-file migration is separate from workspace adoption. `fsgg.svg-document/1` and asset-catalog
v1 values can be wrapped through `SvgScene.migrateLegacy`; preserve the originals and exports.
Package rollback restores managed workspace files only. It never downgrades or deletes authored
`fsgg.svg-scene/1` content, and an older consumer must report that format as unsupported.

## Input

The selected composition enables `PlayerInput.fs` and `Studio/WorkspaceInput.fs` inside the SVG payload.
`SvgFoundation/build.sh` produces the small player entry; its commands adapt to retained focus
and activation and its output excludes Studio, workspace and geometry-worker modules. The Studio entry
uses one effective product profile for mode shortcuts, Ctrl/Command palette access, sequence help,
displacement-aware rebinding, pointer/touch actions and Gamepad API polling. Its accessible controls use
the same semantic commands and keep focus restoration explicit.

Release evidence records exact Rendering archive and curated Fable-interface hashes plus the Templates payload
identity. Qualification covers direct generation, SDD routes, the pinned wizard adopter,
retained 0.10/0.11 upgrades, collision refusal, interrupted apply, byte-identical rollback, all three
browser engines and Orca/AT-SPI.

## Presentation

`PresentationPlayer.fs` keeps animation and save codecs at the generated product boundary. The player
uses the portable Game save/migration reducer, Rendering's disposable animation and IndexedDB hosts, and
Audio's gesture-gated Web Audio host. Authority snapshots remain distinct from animation frames, audio
voices, and browser storage operations.

Movement and outcome clips apply to the retained player object. Live cue batches dispatch a product-owned
sound, while timeline seek and reduced-motion settling remain silent. Four storage families use independent
keys; the sample save uses `save:primary`. The archive control exports the host's complete, hash-bound
archive and imports it only after all declared paths, contents, and SHA-256 identities validate.

The browser journey demonstrates gesture unlock, asset readiness, one-shot dispatch, cue suppression on
seek, reduced-motion settling, successful autosave and reload, quota failure with the prior save preserved,
recovery through a later valid edit, and archive replacement. Closing the page disposes the frame clock,
audio graph, IndexedDB connection, input host, session host, and retained SVG hosts.

## Deterministic external authority reference

The `complete` bundle adds [ExternalAuthorityReference.fs](ExternalAuthorityReference.fs) and its
[fixture marker](Examples/ExternalAuthority/reference.json). This source-only window keeps
`FsGgExternalReferenceCandidate=false` while the published Rendering pin remains `0.31.0`, which
lacks the external API. The candidate runner explicitly enables the property with actual packed
`0.32.0` producer archives. The .4 publication/pin join must select the delivered successor and
enable this default before public installed complete bundles acquire the reference. In that
qualified composition, click **Mount external authority
reference**, then **Connect sample authority**. The sample gateway supplies epoch `epoch-A`, revision
1 and a small counter projection. Increment commands advance its revision; rejected commands leave
that revision unchanged. An explicit authority replacement creates a different epoch that may start
at revision 1. Disconnecting and reconnecting preserves the same authority epoch and accepted revision.

The gateway captures each snapshot's epoch, revision and value when `SvgExternalSessionHost` requests
it. Completion controls can return that captured envelope later; they never generate revisions or
substitute the mount generation for an epoch. The retained SVG host presents accepted projections.
`SvgInputHost` resolves keyboard input; retained SVG hit testing and ordinary invoke buttons submit
semantic commands to the same gateway. Normal editing and IME keep their native input behavior.

Commands receive increasing `sample:N` correlations. Each command settles one accepted or rejected
receipt in admission order, before presentation demand. `data-command-order` and `data-receipt-order`
expose this gateway ledger independently of rendered state. Snapshot acquisition permits one pending
request and one replaceable presentation demand. Coalescing, cancellation, old replies and authority
replacement affect presentation only. The sample contains no transport, engine identity verification,
authentication, authority clock, pause or reset operation.

The loss, cancellation and callback failure controls exercise recovery. Disposal releases input,
external host, retained SVG, button listeners and sample acquisition ownership. The visible terminal
section reports ownership and `CancellationSettlementUnknown`; an unknown cancellation is not
reported as successful zero-resource settlement. The `player` bundle omits the marker, so it neither
compiles nor mounts this module. The existing FourD reference stays available in `complete`.

Source qualification uses `tests/composition/fable-game/verify-external-reference-candidate.sh` from
the Templates repository with an exact Rendering checkout and its packed candidate feed. It compares
the packaged external-host and input files to that source, compiles delivered Fable files through an
isolated package cache, and runs the generated complete receiver in Chromium, Firefox and WebKit.
The external API requires the qualified successor Rendering package; public `0.31.0` cannot supply
it. Candidate qualification does not establish public installed acceptance, actual screen-reader
behavior, FourD engine adoption or BAR/SC2 adoption.
