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

Until these packages are published, restore this project with a NuGet source containing the
locally packed `0.29.0-preview.1` candidate artifacts. The default template remains the supported
arena sample. Public publication, installed receiver qualification and default activation belong to
SVG-PREVIEW-A rather than this local candidate.
