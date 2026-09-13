# Retained SVG foundation fixture

This opt-in fixture is emitted only by `dotnet new fs-gg-fable-game --svgFoundation`.
It consumes the coherent candidate `FS.GG.UI.Scene`, transitive `FS.GG.UI.KeyboardInput`, and
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

Restore this project from NuGet.org using the exact public `0.29.0` packages. The default template
remains the supported arena sample. Templates publication, installed receiver qualification, and
default activation remain later SVG-PREVIEW-A operations.

## Authoring candidate

`Studio/` is a separately compiled and served authoring entry. It consumes the generic Rendering
scene descriptors and mounts `SvgStudio`; the player `Program.fs` does not import studio or geometry
modules. An exact candidate packet supplies the Rendering archives and replaces only the internal
`FsGgSvgAuthoringVersion` seam. After restoring from that packet's isolated feed:

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

## Input candidate

The SVG-INPUT candidate enables `PlayerInput.fs` and `Studio/WorkspaceInput.fs` only inside the staged
package. `SvgFoundation/build.sh` produces the small player entry; its commands adapt to retained focus
and activation and its output excludes Studio, workspace and geometry-worker modules. The Studio entry
uses one effective product profile for mode shortcuts, Ctrl/Command palette access, sequence help,
displacement-aware rebinding, pointer/touch actions and Gamepad API polling. Its accessible controls use
the same semantic commands and keep focus restoration explicit.

The packet records exact Rendering archive and curated Fable-interface hashes plus the Templates payload
identity. Candidate qualification covers direct generation, SDD routes, the pinned wizard adopter,
retained 0.10/0.11 upgrades, collision refusal, interrupted apply, byte-identical rollback, all three
browser engines and Orca/AT-SPI. These candidate seams do not change the public package pins.

## Presentation candidate

`PresentationPlayer.fs` keeps animation and save codecs at the generated product boundary. The player
uses the portable Game save/migration reducer, Rendering's disposable animation and IndexedDB hosts, and
Audio's gesture-gated Web Audio host. Authority snapshots remain distinct from animation frames, audio
voices, and browser storage operations.

Movement and outcome clips apply to the retained player object. Live cue batches dispatch a product-owned
sound, while timeline seek and reduced-motion settling remain silent. Four storage families use independent
keys; the sample save uses `save:primary`. The archive control exports the host's complete, hash-bound
archive and imports it only after all declared paths, contents, and SHA-256 identities validate.

The candidate journey demonstrates gesture unlock, asset readiness, one-shot dispatch, cue suppression on
seek, reduced-motion settling, successful autosave and reload, quota failure with the prior save preserved,
recovery through a later valid edit, and archive replacement. Closing the page disposes the frame clock,
audio graph, IndexedDB connection, input host, session host, and retained SVG hosts. Public package pins stay
unchanged until SVG-PREVIEW-B publishes and qualifies the coherent set.
