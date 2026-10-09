# Opt-in managed portal example

Generate the current Fable Game template with `--portalExample true`, independently
of its bundle and lifecycle. Omission or false excludes this directory; the legacy
`--svgFoundation` selector does not support it. This is a separately invoked .NET 10
headless game/server example. The browser player, ASP.NET authority, protocol and
ordinary workspace solution do not reference it.

```console
dotnet restore PortalExample/Consumer.fsproj --locked-mode
dotnet run --project PortalExample/Consumer.fsproj --no-restore -- --presentation
```

No argument runs the canonical traversal/replay checks. `--presentation` runs five
simulation ticks and twelve interpolated frames with stable entity ownership,
traveller reset and ordinary interpolation, yielding twenty-four area nodes and
points. An invalid argument prints usage and exits 2. Managed scene nodes do not
establish browser/raster output or cross-boundary collision support.

The independent project uses exact public package pins: Game Core/Physics.Box2D/Render
0.17.0, UI Scene/KeyboardInput 0.31.0, Box2D.NET 3.1.654, FSharp.Core 10.1.302. It has
no sibling projects or linked source; its committed lock is genuinely generated.
Workspace-local package caches may contain other versions for independent projects.
Run `python3 verify-package-boundary.py --presentation --preflight` from this directory
before restore, and omit `--preflight` afterwards to check actual assets and nuspecs.

`source-provenance.json` binds the vendored Game example/tool/project bytes to their
canonical producer revision. Do not locally edit them as a parallel physics model.
Template source preparation is separate from candidate generation, publication and
public installed acceptance. Retained adoption/removal commands are not shipped yet;
do not rerun scaffolding over an existing product or remove user files manually.
