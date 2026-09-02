# Fable bindings toolchain qualification

## Result

The narrow workflow was qualified as the v1 foundation for the
`fs-gg-fable-bindings` template: lock an exact npm artifact and selected `.d.ts`
closure, use assisted generation only to propose a candidate, curate the public
Fable surface, and require compile/import-resolution/runtime/drift/consumer
evidence before release. The spike itself does not publish the template; its
findings are now enforced by the generated workspace and composition gate.

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
loader entry points, then deterministically follows every relative declaration
`import`/`export` edge. Every transitive declaration file is individually
SHA-256 hashed. A changed npm artifact causes drift until the lock, curated
surface, runtime evidence, coverage statement, and release notes are reviewed
together.

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
the tracked `generated-candidates/BabylonBindings.generated.fs` and its tracked
proposal note. The declaration-lock digest makes an upstream rerun a visible,
reviewable Git diff. It can never overwrite maintained bindings or advance the
declaration lock. The test asserts the two protected files retain their hashes
after a rerun.

## Curated surface and evidence

`src/BabylonBindings.fs` exposes a small runnable slice with deep ESM imports,
typed opaque F# companions around JavaScript instances, `jsNative` import
bindings, and an explicit glTF side-effect import. Dynamic APIs are escape
hatches outside typed coverage; `obj` stays internal to the interop boundary.
`runtime/runtime-smoke.mjs` constructs a null engine, scene, camera, light, and
box, then loads glTF registration; it proves module paths resolve against the
pinned npm artifact in Node.

The gate packs the Fable library, restores that `.nupkg` through a clean local
NuGet source, independently installs the exact npm dependencies, compiles the
consumer through Fable, and executes the emitted JavaScript in Node. The library
uses `Fable.Package.SDK` as a Fable library so its curated source is available to
the consumer compiler. Browser-targeted packages additionally need a real-browser
smoke test. The template never republishes the JavaScript package and
consumers install the npm runtime dependency.

## Babylon prototype feedback incorporated

The template and product skill were re-evaluated against the complete
`EHotwagner/babylonjsBindings` prototype at commit
`474573cc5695012c8c266f38cd6ebf0d970dacaf`, not only its HelloCube surface. Its
first generation attempt began from all 2,213 Babylon declaration files:
Glutinum produced 1,420 F# files, rejected 53 complex inputs, and still left the
compiler's 100-error cap concentrated in about 20 engine/culling files. The
dominant failures were cross-file ordering, declaration merging and module
augmentation, generic arity, browser API gaps, cyclic inheritance, and missing
runtime import paths. Hundreds of forward declarations and alphabetical file
ordering reduced individual errors but did not provide a maintainable type
architecture. Broad text rewriting also corrupted nested nullable function
types, demonstrating why declaration transforms need parser-shaped controls.

The successful second pass was narrow and curated: about 35 types across ten
subsystems, deep ESM paths, interface/static-companion constructors,
`[<ParamObject>]` option bags, explicit side-effect imports, browser/TypeScript
shims, subsystem-oriented F# files, a runnable sample, and documented dynamic
escape hatches. That result is much more usable, but it also retained floating
NuGet/npm ranges and had no automated locked compile, runtime, drift, or clean
consumer evidence. Both halves matter: the failed broad attempt explains the
mapping process; the curated attempt identifies the interop techniques worth
preserving.

The generated workspace now makes those lessons executable. `binding-plan.json`
records the consumer journey, runtime imports, subsystem/file strategy, browser
type ownership and mapping ledger. Candidate generation parses the entire locked
closure and records conditional/mapped types, index signatures, bare module
references, and cross-file declaration-merging candidates without guessing an
F# public surface. For the qualified Babylon slice that reports 2,898 transitive
declaration files, including 43-file merge candidates around `AbstractEngine`
and loader extension options. The normal workspace build restores the exact
Fable tool and executes the curated F# slice after emission; Node and Chromium
run that same emitted program. A separate fresh Node process proves glTF is not
registered without the side-effect import before the positive binding journey
observes that registration.
