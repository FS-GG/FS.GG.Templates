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
| .NET SDK | 10.0.401 |
| Node / npm | 26.13.0 / 12.2.1 |
| Fable tool / Fable.Core | 5.26.0 / 5.6.1 |
| Fable.Package.SDK | 1.4.1 |
| TypeScript declaration parser | 6.0.3 |
| Glutinum template | `Glutinum.Template@1.1.1` |
| npm corpus | `@babylonjs/core@9.19.0`, `@babylonjs/loaders@9.19.0` |
| core artifact integrity | `sha512-8bQfSnXnFVEUolPBl5Y3S1WDmQKpPKfguOQvGdCxjTIHlLku8Crc0DdvlFbmqeGpS/bQ3NzwtApB84GScm9v8w==` |

The selected corpus is declared once in `corpus.json` (spike and template): the exact npm
artifacts, the `.d.ts` entry points and the candidate file stem. The selected closure is recorded
in `spikes/fable-bindings/declaration-lock.json`.
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

## Current-toolchain re-qualification (2026-10-30, Templates#807)

The machinery was moved to current supported tools and re-qualified on the unchanged Babylon
`9.19.0` corpus. The Babylon version bump is separate (Templates#809).

| Input | Before | After | Basis |
| --- | --- | --- | --- |
| .NET SDK | 10.0.401 | 10.0.401 (unchanged) | Newest feature band and patch used across FS-GG (`global.json` in Game, Rendering, SDD, Governance, Audio, Net and the other Templates workspaces). 10.0.402 and 10.0.403 (October 2026 servicing, including security fixes) are published, and `rollForward: latestPatch` admits them. Moving the exact pin is an FS-GG-wide SDK change that is outside Templates#807 and has no owner yet. |
| Node / npm | 26.10.0 / 12.1.0 | 26.13.0 / 12.2.1 | 26.13.0 is the first Node 26 Active LTS release (`lts: Lithium`); npm 12.2.1 is the current `latest`. The `composition` and `release` gates install the same pair. |
| Fable tool / Fable.Core | 5.18.0 / 5.3.0 | 5.26.0 / 5.6.1 | Latest stable. Fable.Core 5.6.1 still floors FSharp.Core at 4.7.2, so the netstandard2.1 lock shape is unchanged. |
| Fable.Package.SDK | 1.4.1 | 1.4.1 | Already current. |
| TypeScript declaration parser | 5.9.3 | 6.0.3 | Latest JavaScript-API TypeScript. TypeScript 7 is the native compiler and remains only Xantham's pinned compiler. `declaration-analysis.json` and the candidate proposal are byte-identical under 5.9.3 and 6.0.3. |
| Glutinum | `Glutinum.Template@1.1.1` | `Glutinum.Template@1.1.1` | Still the latest template. It remains a comparison input, not a closure-scoped generator. |
| Xantham candidate | `0.1.0-alpha.2` | `0.1.0-alpha.2` (retained) | `Xantham.Fable.Core.TS` still publishes only `net8.0`, so 0.1.0 remains blocked (see `xantham/release-assessments.json`). Upstream source movement is tracked by the FBX-07 watch (#751, signal #805). |

The Xantham pilot's F#/Fable check now reads the workspace's Fable pin instead of a separate
5.13.0 install, so the candidate path compiles under the same Fable as the curated slice.

Evidence on the unchanged corpus:

- The declaration lock is byte-identical, still 2,898 hashed transitive declaration files.
  Generated candidates and `declaration-analysis.json` produce no diff.
- `tests/toolchain/fable-bindings/run.sh` passes under the new pins. It admits any SDK that the
  spike's `global.json` admits (10.0.4xx at or above 10.0.401). Its Xantham step packs
  `FS.GG.Templates.csproj`, so it needs `FSGG_PYTHON_COORDINATION_ROOT` to name the Coordination
  fixture checkout recorded in `eng/portable-workspace/python-fixture-source.json`. It covers drift, the transitive
  drift negative fixture, the Node runtime smoke and the Fable-emitted slice in Node. It also covers
  the protected-file hashes across a candidate rerun, and a clean consumer restoring the packed
  library with Fable 5.26.0 / Fable.Core 5.6.1 and the exact npm artifact. It finishes with the
  Xantham ANSI and strip-ansi qualification (deterministic bytes, rejection fixtures, Fable/Node
  witnesses, packed members).
- The `fable-bindings` composition lane runs the packed template on the new pins. It covers locked
  NuGet/npm restore, doctor, drift, the side-effect negative control, emitted imports, the Node and
  Chromium runtimes, the clean NuGet/npm consumer, the SDD lifecycle and the Governance drift block.
  It also covers a single-artifact `corpus.json` fixture and a doctor corpus-mismatch control.
- `Glutinum.Template@1.1.1` still installs and instantiates on SDK 10.0.401. Its `git init`
  post-action still requires explicit consent.

### Adding a corpus

A corpus is data plus curated source. Do not copy scripts. Write `corpus.json` with
`schemaVersion` 1, a slug `id`, exact `npmArtifacts`, `.d.ts` `declarationEntryPoints` inside
those artifacts, and a PascalCase `candidateStem`. Pin the same artifacts in `package.json`, then
run `npm ci` and `npm run lock:declarations`. The lock script refuses an installed artifact whose
version differs from the corpus, and the lock keeps schema 2.

Every other place that names the npm closure must agree with `corpus.json`:

| Place | Checked by |
| --- | --- |
| `package.json` dependencies | `npm run doctor` |
| `src/<Product>/<Product>.fsproj` `<NpmDependencies>` (Femto metadata in the packed NuGet package) | `npm run doctor` |
| `scaffold-provenance.json` `npmClosure` | `npm run doctor` |
| `declaration-lock.json` package identity and entry points | `npm run doctor`, `npm run check:drift` |
| `binding-plan.json` runtime entry points (inside the artifacts) | `npm run doctor` |
| `.template.config/template.json` `npmPackage`/`npmVersion` choices and defaults (primary artifact) | `fable-bindings` composition lane |
| `providers/fable-bindings.providers.yml` | Declares the `npmPackage`/`npmVersion`/`bindingTarget` keys only, with no values; nothing to update |

The composition lane reds the doctor on a mismatched `corpus.json` and on a binding project whose
`<NpmDependencies>` pin another version. It also requires the spike and template copies of
`scripts/corpus.mjs` and `scripts/lock-declarations.mjs` to stay identical. Curated bindings, the
mapping ledger, coverage and the runtime/browser smokes stay per corpus and are reviewed.

The closure scanner is unchanged. Its lexical rules fit Babylon, but a probe of `pixi.js@8.22.0`
(`lib/index.d.ts`) found four gaps for the next corpus (Templates#808):

- Global mixins arrive through `/// <reference path>` directives, which the scanner does not follow.
- Extensionless specifiers resolve to `dir/index.d.ts`, not only `x.d.ts`.
- JSDoc examples contain `import('./gl/init')` for files that do not exist.
- Declarations import shader assets that have no `.d.ts`: 8 distinct `.frag`, 5 `.vert` and 10
  `.wgsl` specifiers.

A comment-aware scanner (TypeScript `preProcessFile`) also follows `declare module` augmentation
targets. On the Babylon closure it yields 2,893 instead of 2,898 files. The regex follows two
import examples inside a JSDoc comment (`rawTexture2DArray.functions.d.ts`), which pull in five
`texture2DArrayImageSource` files. Changing the scanner therefore needs a reviewed re-lock of the Babylon
corpus as well. Do it as one deliberate change, with Templates#809's Babylon re-lock, not as a
silent rewrite.

