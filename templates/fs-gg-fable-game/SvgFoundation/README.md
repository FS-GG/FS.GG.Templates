# Retained SVG foundation fixture

This opt-in fixture is emitted only by `dotnet new fs-gg-fable-game --svgFoundation`.
It consumes the candidate `FS.GG.UI.Scene` and `FS.GG.UI.Scene.SvgBrowser` packages and mounts two
neutral retained scenes: an integer grid and a fractional continuous-coordinate route. Neither
scene depends on S.I.R. types or on a sibling Rendering checkout.

Until these packages are published, restore this project with a NuGet source containing the
locally packed `0.4.0-preview.1` candidate artifacts. The default template remains the supported
arena sample.
