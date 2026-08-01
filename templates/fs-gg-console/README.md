# ConsoleProduct

This is a small F# console workspace. It deliberately uses `System.Console` only:
there is no browser, npm, generic host, command framework, or terminal UI dependency.

```sh
dotnet restore --locked-mode
dotnet fsi build.fsx build
dotnet fsi build.fsx test
dotnet run --project src/ConsoleProduct -- hello world
dotnet run --project src/ConsoleProduct -- --fail
```

`Ctrl+C` requests cancellation. `Program.run` accepts explicit output ports and a
`CancellationToken`, so command behavior and orderly shutdown stay deterministic in tests.
When generated through `fsgg-sdd scaffold`, the root `.fsgg/` lifecycle and
`scaffold-provenance.json` are owned by SDD; this template intentionally does not overwrite them.
