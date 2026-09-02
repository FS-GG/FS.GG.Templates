---
name: fable-bindings
description: Maintain a versioned Fable binding over an exact npm declaration closure, with review-only generation, curated interop, runtime proof, drift reporting, and release evidence.
---

# Fable bindings capability

Use this skill for a library that wraps a JS/TS package. Treat the JavaScript runtime, its TypeScript
declarations, the emitted ESM graph, and the public F# API as four related but distinct contracts.
Pin the npm package/version and lockfile, selected declaration entry points and transitive `.d.ts`
hashes, .NET SDK, Fable/Fable.Core, generator, Node, and package manager. An upstream update must red
until the declaration lock, mapping decisions, maintained source, coverage, runtime evidence, and
release notes are reviewed together.

## Design a slice before writing bindings

Start from one executable consumer journey, not a namespace or the whole declaration corpus. Record
its entry points, runtime target, package export paths, side-effect modules, owned object lifecycle,
and the types crossing its public boundary. Expand only after that slice compiles and runs.

Build a mapping ledger for the slice. For every selected symbol record its declaration source and
runtime import, F# representation, coverage class (`typed`, `typed-pass-through`, `dynamic`, or
`unsupported`), and verification call. Keep dynamic and unsupported rows out of typed-coverage
counts. Distinguish deliberate opaque pass-through values from accidental `obj` leakage.

Before choosing F# file order, derive a type dependency graph and inspect its strongly connected
components. Group mutually recursive or declaration-merged types into a maintained subsystem file;
topologically order the remaining files. Do not reproduce one F# file per `.d.ts`, alphabetize the
result, or accumulate forward-declaration stubs: those strategies conceal TypeScript declaration
merging and become brittle at large scale. Put browser/WebGL/WebAudio/WebXR types behind an explicit
shim or package boundary rather than inventing lookalike domain types throughout the binding.

## Map TypeScript deliberately

- Bind JavaScript classes as an instance interface plus an imported static/constructor companion
  when that keeps construction and inheritance honest. Use `[<ParamObject>]` for option bags.
- Preserve overload meaning. Prefer distinct F# members or a small erased union when call shapes are
  materially different; do not collapse overloads into `obj` merely to make generation compile.
- Model `undefined`, `null`, and omission according to runtime behavior. Optional parameters,
  optional properties, and nullable results are not automatically the same F# type.
- Use erased string/number unions for closed literal sets; retain an escape case only when upstream
  explicitly accepts future values. Treat conditional, mapped, template-literal, variadic tuple,
  and higher-kinded generic types as manual design decisions.
- Model callbacks, `this` binding, mutation, promises, iterables, typed arrays, and disposal in the
  shape the JavaScript caller observes. Test identity-sensitive values and setters at runtime.
- Represent module augmentation and registration imports explicitly. A side-effect import is part
  of the feature contract and needs a smoke that fails when it is absent.
- Use exact package export paths that the pinned artifact actually serves. Validate extension and
  case sensitivity on the target host and through the consumer's bundler/module resolver.

Assisted generation (Glutinum when qualified; `ts2fable` only as comparison input) writes a tracked
candidate and analysis, never maintained source, the mapping ledger, or declaration lock. Review
generator diagnostics as coverage information. Parser-aware transforms are acceptable; broad regex
rewrites of nested type syntax are not. Curated `[<Import>]`/`jsNative` code remains the public API.

```sh
npm ci
node scripts/lock-declarations.mjs        # deterministic transitive closure
node scripts/generate-candidate.mjs       # proposal and hazard inventory only
dotnet restore --locked-mode
dotnet tool restore
dotnet fable tests/BindingsProduct.CompileTests/BindingsProduct.CompileTests.fsproj --outDir runtime/fable-dist --noCache
node runtime/fable-dist/Program.js
dotnet pack --no-restore
```

Inspect the emitted imports as an API artifact; compile success does not prove that names, default vs
named exports, augmentation, or tree-shaken side effects are correct. Release only after a clean
consumer installs the packed NuGet library, separately installs the exact npm runtime dependency,
Fable-compiles, bundles/resolves the emitted imports, and runs the same typed journey in applicable
Node and real-browser targets. Add negative controls for a missing side-effect import and a changed
transitive declaration. Publish and verify the package artifact before registry/wizard activation.
The currently qualified reference is Fable 5.13.0/Fable.Core 5.2.0 with exact locks; requalify any
tool upgrade rather than floating it.

## Sources

- [Fable JavaScript interop](https://fable.io/docs/javascript/)
- [npm package-lock documentation](https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json)
- [NuGet lock files](https://learn.microsoft.com/nuget/consume-packages/package-references-in-project-files#locking-dependencies)
