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
