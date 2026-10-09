# BindingsProduct

This NuGet package contains compiled Fable bindings for `@babylonjs/core@9.19.0` and
`@babylonjs/loaders@9.19.0`, targeting JavaScript. Consumers must separately install both supported
npm artifacts; this package never bundles or republishes their implementation.

The project declares the native npm requirements through Femto's `NpmDependencies` metadata.
Retain the exact repository npm and declaration locks. This metadata does not prove automatic
Femto discovery from a compiled-only package; a consumer must separately install the npm artifacts.

Before publication, inspect the `.nupkg` for the binding DLL, no library source payload, no
`Fable.Package.SDK` dependency, and the `fable`, `fable-binding` and `fable-javascript` tags.
The curated calls use native import/emission metadata and opaque interface types so the consumer
uses the compiled binding rather than an F# wrapper implementation.
Then restore the inspected archive in a clean consumer with an isolated NuGet cache, install the
locked npm dependencies, Fable-compile, inspect the emitted imports and run the typed journey.

Publish the binding archive to NuGet.org or an explicitly selected private NuGet feed and verify
its published identity and installation. The JavaScript implementation remains on npm.
[Fable Packages](https://fable.io/docs/your-fable-project/use-a-fable-library.html) indexes eligible
NuGet publications after indexing; there is no second upload to a Fable registry. Local package
qualification does not establish publication.
