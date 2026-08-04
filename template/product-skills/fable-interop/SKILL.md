---
name: fable-interop
description: Design narrow, maintained Fable bindings for JavaScript or TypeScript modules, with imports, side effects, and generated candidates reviewed as source rather than accepted as API.
---

# Fable interop capability

Use this skill when F# calls JavaScript. Bind the smallest useful module surface with
`Fable.Core.JsInterop` imports and `jsNative`; keep the public F# shape curated and runtime-oriented.
Use direct ESM imports for stable module paths, and model side-effect-only imports explicitly.

```fsharp
open Fable.Core
open Fable.Core.JsInterop

[<Import("Engine", "@babylonjs/core/Engines/engine")>]
type Engine(canvas: obj, antialias: bool) = class end

[<ImportSideEffects("@babylonjs/loaders")>]
let loadLoaders : unit = jsNative
```

Do not expose an entire `.d.ts` file as the maintained API merely because a generator parsed it.
Glutinum or `ts2fable` can create a candidate, but a human must review import paths, erased unions,
optional arguments, parameter objects, overloads, static companions, side effects, and unsupported
constructs. `obj` is an escape hatch with a documented boundary; it is not typed-coverage evidence.

## Verification

Compile the curated F# surface through Fable, inspect emitted imports, run the bundler, then execute
one real Node and/or browser call against the exact npm artifact. Lock npm and .NET restores. The
currently qualified reference uses Fable 5.13.0/Fable.Core 5.2.0; pin rather than float replacements.

## Sources

- [Fable JavaScript interop](https://fable.io/docs/javascript/)
- [Fable.Core API](https://fable.io/repl/)
- [TypeScript declaration files handbook](https://www.typescriptlang.org/docs/handbook/declaration-files/introduction.html)
