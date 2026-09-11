# Retained SVG foundation fixture

This opt-in fixture is emitted only by `dotnet new fs-gg-fable-game --svgFoundation`.
It consumes the candidate `FS.GG.UI.Scene` and `FS.GG.UI.Scene.SvgBrowser` packages and mounts two
neutral retained scenes: an integer grid and a fractional continuous-coordinate route. Neither
scene depends on S.I.R. types or on a sibling Rendering checkout.

`TacticalCompatibility.fs` is a contract fixture and clean-room reimplementation of the disclosed
`SharedSceneProjection` characteristics audited at S.I.R. revision
`80e1ac9328865ec8d1ee3eeea130560ef22b1b01`. The SVG-FOUND-01.1 audit records the copyright
owner's 2026-09-11 authorization context and separately excludes third-party material. This fixture
copies no S.I.R. source, type, asset, package, or dependency. It accepts disclosed presentation
values only, retains ordered layer visibility and product-owned lock characterization, and projects
camera and relevant selection/focus state into the Rendering contract.

Until these packages are published, restore this project with a NuGet source containing the
locally packed `0.4.0-preview.1` candidate artifacts. The default template remains the supported
arena sample.
