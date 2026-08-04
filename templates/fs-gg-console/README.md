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

## Package locking

This workspace restores in **locked mode** (`RestoreLockedMode` in `Directory.Build.props`), so every `packages.lock.json` beside a project is enforced: a package whose content hash differs from the committed one fails the restore rather than being silently substituted.

Locked mode is only meaningful if the lock can be regenerated, so here is the path. After changing any `PackageReference`, regenerate and commit the affected locks:

```bash
dotnet restore ConsoleProduct.slnx --force-evaluate
```

Never hand-edit a lock file; a hash typed by a human is a hash no restore can reproduce.

Two settings keep those hashes reproducible, and both are load-bearing (see `FS.GG.Templates#384`, whose root cause was established by `#380`):

- **`NuGet.config` pins the source.** Its `<clear />` drops every source inherited from the machine, so a package is never served by whatever local feed the host happens to configure. To use a private or mirrored feed, add it there and then regenerate the locks with the command above.
- **`DisableImplicitLibraryPacksFolder` in `Directory.Build.props`** stops the F# SDK appending its own bundled `library-packs` folder to the restore sources. That folder ships an `FSharp.Core` archive with the same version as nuget.org's but different bytes, so leaving it enabled lets one restore record one content hash and the next restore reject it with `NU1403: Package content hash validation failed`. This workspace takes FSharp.Core implicitly from the F# SDK, so it is exposed to that collision even though it declares no `PackageReference` to it.
- **`RestorePackagesPath` in `Directory.Build.props`** gives this workspace its own `.nuget/packages` folder instead of the machine-wide one. Source pinning alone is not enough: NuGet's shared package folder is keyed by id and version only, so whichever build reached it first decides which of the two `FSharp.Core` archives lives there, and a later restore validates the committed hash against *that* entry. A private folder is what makes the committed hash enforceable on any machine rather than only on machines that happen to agree. Two consequences worth knowing: packages are not shared with your other checkouts, so a cold build downloads its own copies; and `.nuget/` belongs in your ignore file — this workspace ships without one, in common with `bin/`, `obj/` and `artifacts/`.

`build.fsx build` refuses to restore at all if the lock files are missing, because a locked-mode restore with no lock on disk does not fail — it quietly writes a new lock from whatever the machine resolves, which defeats the entire mechanism.
