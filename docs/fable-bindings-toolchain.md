# Fable bindings toolchain qualification

## Result

The narrow workflow is qualified as the v1 shape for a future
`fs-gg-fable-bindings` template: lock an exact npm artifact and selected `.d.ts`
closure, use assisted generation only to propose a candidate, curate the public
Fable surface, and require compile/import-resolution/runtime/drift/consumer
evidence before release. This spike does not publish a template.

## Exact inputs

| Input | Pin |
| --- | --- |
| .NET SDK | 10.0.302 |
| Node / npm | 26.5.0 / 12.0.1 |
| Fable tool / Fable.Core | 5.13.0 / 5.2.0 |
| Glutinum template | `Glutinum.Template@1.1.1` |
| npm corpus | `@babylonjs/core@9.19.0`, `@babylonjs/loaders@9.19.0` |
| core artifact integrity | `sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==` |

The selected closure is recorded in `spikes/fable-bindings/declaration-lock.json`.
It covers deep ESM engine, scene, maths, camera, light, mesh-builder, and glTF
loader entry points; every file is individually SHA-256 hashed. A changed npm
artifact causes drift until the lock, curated surface, runtime evidence, coverage
statement, and release notes are reviewed together.

## Generator evaluation

`Glutinum.Template@1.1.1` installed and created a Fable binding project, but its
scaffold is project-wide and includes an interactive `git init` post-action. It
does not provide a non-interactive, closure-scoped generator or a policy that
protects maintained source and declaration locks. For the Babylon slice it is a
useful assisted-generation comparison, not an API authority. It must report,
not erase, overloaded constructors, structural/conditional types, mapped types,
template-literal types, index signatures, and dynamic module augmentation.
`ts2fable is legacy comparison input only`; it is not the default generator.

`npm run generate:candidate` demonstrates the required safe behavior: it writes
only `generated-candidates/BabylonBindings.generated.fs`. It can never overwrite
maintained bindings or advance the declaration lock. The test asserts the two
protected files retain their hashes after a rerun.

## Curated surface and evidence

`src/BabylonBindings.fs` exposes a small runnable slice with deep ESM imports,
typed opaque F# companions around JavaScript instances, `jsNative` import
bindings, and an explicit glTF side-effect import. Dynamic APIs are escape
hatches outside typed coverage; `obj` stays internal to the interop boundary.
`runtime/runtime-smoke.mjs` constructs a null engine, scene, camera, light, and
box, then loads glTF registration; it proves module paths resolve against the
pinned npm artifact in Node.

Before template freeze, the same files must also compile through Fable and pack
as a NuGet library; a clean Fable consumer installs that NuGet package and the
pinned npm package independently. Browser-targeted packages additionally need a
real-browser smoke test. The future template documents that it never republishes
the JavaScript package and consumers install the npm runtime dependency.
