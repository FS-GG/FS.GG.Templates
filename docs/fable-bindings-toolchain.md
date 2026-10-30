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
| npm corpus | `@babylonjs/core@9.33.1`, `@babylonjs/loaders@9.33.1`; `pixi.js@8.22.0` |
| core artifact integrity | `sha512-NoIfREw4QeoXzRPpXnbUpmxxPIjuRi9iS4xFDbPgXHiLwCeHSI13DJHF8YB2gKHp6rA6T5R7BAevPvWHklvXWQ==` |

The selected corpus is declared once in `corpus.json` (spike and template): the exact npm
artifacts, the `.d.ts` entry points and the candidate file stem. The selected closure is recorded
in `spikes/fable-bindings/declaration-lock.json`.
It covers deep ESM engine (null, WebGL and WebGPU), scene, maths, camera, light,
mesh-builder, material, scene-loader and glTF loader entry points, then
deterministically follows every declaration edge (see "Closure scanner" below).
Every transitive declaration file is individually SHA-256 hashed. A changed npm artifact causes drift until the lock, curated
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
F# public surface. For the qualified Babylon `9.33.1` slice that reports 2,976 transitive
declaration files, including 43- and 44-file merge candidates around `AbstractEngine`
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
| .NET SDK | 10.0.401 | 10.0.401 (unchanged) | Newest feature band and patch used across FS-GG (`global.json` in Game, Rendering, SDD, Governance, Audio, Net and the other Templates workspaces). 10.0.402 and 10.0.403 (October 2026 servicing, including security fixes) are published, and `rollForward: latestPatch` admits them. Moving the exact pin is an FS-GG-wide SDK change that is outside Templates#807; it is tracked by FS-GG/.github#4935. |
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

The closure scanner was replaced in Templates#809; see "Closure scanner" below.

## Closure scanner and Babylon 9.33.1 re-lock (2026-10-30, Templates#809)

`scripts/lock-declarations.mjs` (identical in the spike and the template) no longer uses a
regular expression. It reads every declaration file in the closure with the pinned TypeScript
6.0.3, in two passes. Comments and JSDoc are never edges in either pass.

- A syntax-tree pass (`ts.createSourceFile`) collects module specifiers from `import` and `export`
  declarations, including `export * as ns from` and `export type * as ns from`; from
  `import x = require()`; from `import()` types; and from `declare module "m"` targets.
- `ts.preProcessFile` supplies the `/// <reference path>` and `/// <reference types>`
  directives (for example, global mixins). It does not report `export * as` edges, which is why
  the specifiers come from the syntax tree. Its own module list is a cross-check: a specifier it
  reports that the syntax-tree pass missed is an error.

The scanner fails loudly instead of omitting a reference. It throws on an `import()` whose
argument is not a string literal, on a `require()` or dynamic `import()` call, and on any other
module-specifier node whose specifier is not a string literal.

Specifiers resolve like this:

- `x.js`, `x.mjs` and `x.cjs` resolve to their `.d.ts`/`.d.mts`/`.d.cts` twins.
- An explicit `.d.ts` resolves to itself.
- An extensionless specifier resolves to `x.d.ts`, then `x/index.d.ts`. This also covers `.` and `..`.
- A bare specifier is followed only into the corpus's pinned artifacts. For a package root, the
  package's `types` field is used. Modules outside the pinned artifacts are listed in the lock's
  `externalModules` and are not followed. For Babylon that list is `babylonjs-gltf2interface`,
  the loaders' peer types package.
- A specifier with no declaration whose extension is on an explicit asset allowlist is a bundler
  asset. It is listed in `nonDeclarationAssets` and is never read, so a missing asset file is not
  an error. The allowlist is `.frag`, `.vert`, `.wgsl`, `.glsl`, `.fx`, `.css`, `.scss`, `.sass`,
  `.less`, `.json`, `.svg`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.ktx`, `.ktx2`, `.dds`,
  `.env`, `.hdr`, `.glb`, `.gltf`, `.bin`, `.wasm`, `.txt` and `.html`.
- Any other unresolved reference, including a dotted name with an extension not on the allowlist,
  still fails the lock.

The two new lock fields appear only when non-empty. The lock stays schema 2, and hashing and
drift detection are unchanged. `tests/toolchain/fable-bindings/closure-scanner-fixture.sh` pins
each rule: reference paths and types, folder imports, bare imports into the artifact, files
reachable only through `export * as` and `export type * as` (and drift in them), a JSDoc
`import()` example, a `.frag` asset, external modules, drift through a referenced mixin, an
unresolved dotted name that is not an allowlisted asset, an unsupported specifier form, and the
failure on a real missing import. The `export * as` case fails against the earlier
`preProcessFile`-only scanner, which omitted those files without any error. The toolchain gate
and the composition lane both run the fixture.

Closure counts:

| Corpus | Regex tracer | Current scanner |
| --- | --- | --- |
| Babylon `9.19.0`, original 7 entry points | 2,898 | 2,893. The regex followed two JSDoc import examples in `rawTexture2DArray.functions.d.ts` into five `texture2DArrayImageSource` files. |
| Babylon `9.33.1`, original 7 entry points | 2,976 | 2,976 |
| Babylon `9.33.1`, current 19 entry points (locked) | 2,976 | 2,976 |

Babylon moved from `9.19.0` to `9.33.1`, the current `latest` for both `@babylonjs/core` and
`@babylonjs/loaders`. No declaration file was removed between the two releases. The added entry
points (WebGL and WebGPU engines, `math.color`, arc-rotate camera, directional and point lights,
box/sphere/ground builders, standard and PBR materials, `Loading/sceneLoader`) were already
inside the closure, so they add no files. They make the curated surface's import modules
explicit lock roots.

The template's curated surface is now a 3D renderer slice:

- engines: null, WebGL `Engine` on an opaque canvas shim, and WebGPU (support probe plus async
  initialisation);
- the render loop: `runRenderLoop`, `stopRenderLoop`, `resize`, `render` and dispose;
- `Scene` and its clear colour; `Vector3` and `Color3`;
- free and arc-rotate cameras; hemispheric, directional and point lights;
- the tree-shakeable `CreateBox`/`CreateSphere`/`CreateGround` builders, and mesh transforms;
- `StandardMaterial` and `PBRMaterial`;
- the glTF side-effect registration, and the module-level `ImportMeshAsync`. The deprecated
  `SceneLoader` class is used only for the registration query.

Every call is an `Import`/`Emit` native declaration over opaque interface types, as binding mode
requires. The evidence covers each binding:

- The Fable-emitted compile test runs the whole journey on a `NullEngine` in Node and Chromium.
  It imports a one-triangle glTF from a data URL and runs the render loop.
- Chromium also renders the scene on a WebGL `Engine`. Locally, Chrome 156 headless used the
  SwiftShader WebGL2 fallback.
- A WebGPU engine initialises only when the browser reports support.
- `npm run test:imports` imports every `binding-plan.json` entry point in Node.
- The packed clean consumer exercises cameras, lights, a PBR material, rendering and glTF
  registration.

The spike's library-mode `src/BabylonBindings.fs` keeps its narrow qualification slice. It runs
unchanged against `9.33.1`.

A probe lock of `pixi.js@8.22.0` (`lib/index.d.ts`, not committed) now succeeds with 687
declaration files. It follows the `/// <reference path>` mixins and folder imports. It records
23 shader assets (8 `.frag`, 5 `.vert`, 10 `.wgsl`) and the external modules `@pixi/colord`,
`earcut`, `eventemitter3` and `tiny-lru`. The Pixi corpus is delivered by Templates#808; see "PixiJS 8.22.0 corpus" below.

## PixiJS 8.22.0 corpus (2026-10-30, Templates#808)

### Package home

The PixiJS bindings live in the same template as the Babylon bindings: FS-GG/FS.GG.Templates,
template `fs-gg-fable-bindings`, selected with `--npmPackage=pixi.js --npmVersion 8.22.0`. The
default stays Babylon (`@babylonjs/core 9.33.1`). Babylon is the template root; the Pixi files are
`templates/fs-gg-fable-bindings/corpora/pixi/`, the same layout, delivered over the root by a second
`sources` entry when `npmPackage` is `pixi.js`. The first source withdraws exactly the root files the
overlay supplies, so no target is written twice, and `corpora/` itself never reaches a product. The
shared scripts (`corpus.mjs`, `lock-declarations.mjs`, `generate-candidate.mjs`, `doctor.mjs`) are
not copied: they read `corpus.json`.

The packaged artifact is what a product generates and packs, as for Babylon. `dotnet new
fs-gg-fable-bindings --name <Name> --npmPackage=pixi.js --npmVersion 8.22.0` produces a workspace
whose `src/<Name>/<Name>.fsproj` is a Fable `binding` package (module `Qualification.Pixi`, Femto
`<NpmDependencies>` naming `pixi.js@8.22.0`). FS.GG.Game consumes it as the packed `.nupkg` (the clean
consumer route below) or with a `ProjectReference` to that project, plus `pixi.js@8.22.0` in its own
`package.json`. Nothing is published; publication stays a separate, explicit Delivery.

The template's `npmPackage` and `npmVersion` choices are now the primary artifacts of the corpora it
delivers. The pair is not validated by the template engine, so the requested values are written into
`scaffold-provenance.json` (`requestedCorpus`) and `npm run doctor` fails when they are not the
delivered corpus's primary artifact. A mismatched pair such as `pixi.js` with `9.33.1` therefore reds
the first doctor run.

### Locked inputs

| Item | Value |
| --- | --- |
| npm artifact | `pixi.js@8.22.0`, the npm `latest` (major 8) |
| integrity | `sha512-QbTANHMZ751MIjLiLSUSM8a7LNMWwMIf0KbRCqlW+SPS9hNLfSVS+cl1O2SEp9g1K/wyLzj/OJHv+1TUfiPr/w==` |
| entry points | `pixi.js/lib/index.d.ts`, `pixi.js/lib/events/init.d.ts` |
| hashed declaration files | 688 (687 reached from `index.d.ts`; `events/init.d.ts` is the one more) |
| `nonDeclarationAssets` | 23 shader files (8 `.frag`, 5 `.vert`, 10 `.wgsl`); none is in the package |
| `externalModules` | `*.frag`, `*.vert`, `*.wgsl` (ambient wildcard declarations in `Shaders.d.ts`), `@pixi/colord`, `earcut`, `eventemitter3`, `tiny-lru` |

The scanner needed no change. It follows the 22 `/// <reference path>` mixins and ambient files, the folder
`index.d.ts` imports and `export * from` edges, and ignores the JSDoc `import('./gl/init')` example.

### External-module curation

An external module is followed only if the curated binding exposes or depends on its types. None
does: the F# surface uses opaque interfaces, integers for colours and plain functions for listeners.
All four packages are therefore recorded and not followed, and the decision is executable instead of
prose:

- `coverage-and-drift.json` has an `externalModules` row per entry in the lock (a decision, a reason,
  and for a package its exact version and integrity).
- `npm run doctor` fails when the rows and the lock's `externalModules` differ, when a row has no
  reason, or when a package row differs from what `package-lock.json` locks. A moved external
  dependency is a reviewed change. The Babylon corpus gained the same row for
  `babylonjs-gltf2interface`.

| Module | Locked | Why not followed |
| --- | --- | --- |
| `eventemitter3` | 5.0.4 | `Container.on/once/off/emit/listenerCount/removeAllListeners` are emitted native calls, and no `eventemitter3` type appears in the binding. This is the closest call: events are in scope, so the runtime journeys call each of those methods, and a changed version moves `package-lock.json` and the doctor row. |
| `@pixi/colord` | 2.9.6 | Colour parsing internal to `Color`; colours cross the binding as `0xRRGGBB` integers. |
| `earcut` | 3.2.4 | Triangulation internal to `Graphics`. |
| `tiny-lru` | 11.4.7 | Cache internal to the text and texture systems. |

Following `eventemitter3` would mean pinning a transitive dependency as a direct one in every
consumer's `package.json` and `<NpmDependencies>`. That is the cost of a stronger event-type contract;
revisit it if the binding ever exposes an emitter type.

### Curated 2D surface

Every call is an `Import`/`Emit` native declaration over opaque interface types. The package root
`pixi.js` is the only runtime import (plus the `pixi.js/events` side effect), so a bundler or import
map chooses the build. The module is `Qualification.Pixi`.

- `Application`: construct, asynchronous `init` on a canvas with width, height, background,
  antialiasing and a `"webgl"`/`"webgpu"` preference, `stage`, `canvas`, `screen`, renderer name,
  resize, background colour, render, destroy, and `readPixel` for render verification.
- `Container`: add, remove and index children, position, scale, pivot, rotation, alpha, visibility,
  `zIndex`, sorting, label, bounds and destroy. `Sprite`, `Graphics` and `Text` inherit it.
- `Sprite`, `Texture` and `Assets`: anchor, tint, size and texture; `Texture.WHITE`/`EMPTY`, a
  canvas-backed texture and a sub-texture frame; `Assets.load/add/get/unload` and a cache query.
- `Graphics`: rect, rounded rect, circle, ellipse, polygon, move/line/close, fill with alpha, stroke
  and clear.
- `Text`: construct from content, fill, size and family; read and set content, fill and size; layout
  width and height (browser only).
- `Ticker`: a new or the shared ticker; add, add-once and remove listeners; start, stop, manual
  `update`; `deltaMS`, `deltaTime`, `elapsedMS`, `FPS`, `speed`, `minFPS`, `maxFPS`; the listener
  count.
- Events: the `pixi.js/events` side-effect registration and a query for it; `eventMode`, cursor and
  `hitArea`; `on/once/off/emit/listenerCount`; the event's global position, local position, button and
  `stopPropagation`.
- `Rectangle` and `Point`.

Listener removal is by subscription, not by function name. Fable turns a module-level F# function
passed as an argument into a new JavaScript closure at every call site, so `remove(step)` after
`add(step)` removes nothing. `addTicker`, `onEvent` and the once variants return an opaque
`Subscription`, the exact function Pixi holds, and `removeTicker`/`offEvent` take it. The packed
consumer registers and removes module-level functions to hold this in place.

Out of scope for this slice, and named as `unsupportedConstructs` in `coverage-and-drift.json`: the
`math-extras`, `gif`, `html-source` and compressed-texture add-ons, filters, meshes, bitmap and HTML
text, particle containers, tiling and nine-slice sprites, masks and render textures beyond what the
slice touches.

### Build boundary: `lib` or `dist`

Node resolves `pixi.js` to `lib/index.mjs`, whose graph covers the hashed declarations. A browser
cannot load that graph from an import map: `eventemitter3` and `@xmldom/xmldom` are CommonJS-only. The
Chromium page therefore maps both `pixi.js` and `pixi.js/events` to the package's self-contained
`dist/pixi.mjs`, which is the same locked artifact with those dependencies bundled and the event
system included. A consumer using a bundler gets `lib`.

Two PixiJS behaviours shape the side effect. `import 'pixi.js'` does not register the event mixin: it
is added by `pixi.js/events` or lazily by `Application.init` in a browser. The negative control is a
fresh Node process that finds no `eventMode` on `Container.prototype`; the positive journey registers
it with `enableEvents ()`. Pointer events also hit-test the last rendered frame, and pixel extraction
renders its own copy, so a test renders once more before dispatching.

### Performance-first

There is no producer-owned typed performance intent for this bindings product, and no timing target is
invented. What applies to a binding is its cost shape, and the representative workload is declared in
the compile test that traverses the real binding route:

- Workload: one container holding 1,000 sprites (a small 2D game scene) positioned, sized and tinted
  through the binding, 60 manual ticker frames, and 40 columns by 25 rows of bounds that must equal
  398 x 248.
- Structural counters, asserted rather than timed: 1,000 children, a ticker listener count that
  returns to zero after removal, a listener that runs once per `update`, and 3 stage children plus
  more than zero application ticks in Chromium.
- Cost shape: each call is emitted as the native member call itself. The composition lane asserts
  that the hot loop is emitted as `world.addChild(s);`, `s.position.set(...)` and `s.tint = ...`, and
  that the binding emits no JavaScript module of its own, so it adds no wrapper, closure or
  allocation per call.
- The headless Chromium run uses SwiftShader WebGL. It is bounded headless evidence and is labelled so.
  It does not substitute for live-compositor or swapchain evidence, which belongs to the Game adapter
  (FS-GG/FS.GG.Game#730).

### Evidence

All of it runs in `tests/composition/fable-bindings/pixi-corpus.sh`, called from the `fable-bindings`
composition lane against the packed template archive:

- the delivered product has the Pixi files and neither `corpora/` nor any Babylon candidate;
- locked NuGet and npm restore, the doctor, drift, and the closure scanner fixture on the product's
  script;
- `test:side-effect-control` (no event mixin without the import) and `test:imports` (Node imports both
  plan entry points and runs a JavaScript journey);
- the Fable 5.26.0 emitted journey in Node, then in headless Chromium, where it renders on a WebGL
  `Application`: a filled rectangle, a canvas-backed sprite and a decoded PNG asset are read back pixel
  for pixel, a real DOM pointer event reaches the stage listener with the right local position, the
  application ticker runs, and a WebGPU preference yields WebGPU where supported and WebGL otherwise;
- drift negatives: a changed direct declaration (`Ticker.d.ts`) and a changed reference-only mixin
  (`GraphicsMixins.d.ts`) red `check:drift`, and `npm ci` restores it;
- doctor negatives for a missing curation row, a curated external module at another version or
  integrity, a row with no reason, a corpus pin that disagrees with `package.json`, a requested pair that
  is not the delivered corpus, and Femto `<NpmDependencies>` at another version;
- candidate stability: regenerating candidates changes neither `Bindings.fs` nor the lock, and leaves no
  diff;
- a packed clean consumer: the `.nupkg` is inspected (compiled binding, no source, no bundled npm
  payload, no `Fable.Package.SDK` dependency, the binding tags; both defect shapes are mutated and
  rejected), restored from a local feed with an empty NuGet cache, compiled by Fable with the exact
  `pixi.js@8.22.0` integrity installed, and run in Node.

The default Chromium run is software WebGL (SwiftShader) and is what CI runs. A host with a GPU adds a
hardware run of the same emitted program: set `FSGG_BROWSER_GPU_ARGS` (for example `--headless=new
--use-angle=vulkan --enable-features=Vulkan --ignore-gpu-blocklist`), which `browser-smoke.mjs` receives
as `BROWSER_SMOKE_ARGS`, and the lane requires that the recorded WebGL device is not SwiftShader. The
page records the unmasked renderer string of every run. On the development host (AMD Ryzen 9 7900
integrated GPU) the two runs reported
`ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) ...), SwiftShader driver)` and
`ANGLE (AMD, Vulkan 1.4.354 (AMD Ryzen 9 7900 12-Core Processor (RADV RAPHAEL_MENDOCINO) ...), radv)`,
and both passed every pixel, pointer, ticker and asset check.

The Chromium run needs real time: `chromium --dump-dom` reports a page before an image decode finishes
under its virtual-time budget, so `scripts/browser-smoke.mjs` serves the workspace, drives headless
Chromium over the DevTools protocol and waits for the page's result. Text is verified by layout height.
A host with no fonts measures every width as 0 (this development host has none), so the width
comparison runs only when a width can be measured.

### Not covered

- WebGPU is not a dependency of the evidence. With the hardware flags above, the development host's
  headless Chromium reported WebGPU as supported and the `"webgpu"` preference then yielded a WebGPU
  renderer in the same program (observed on repeated local runs); the default software run reports it
  unsupported and exercises the fallback to WebGL. Whether headless WebGPU is reliable elsewhere,
  including CI, is Unknown, and nothing here asserts it.
- Glyph pixels were not rendered, because of the missing fonts above on this host.
- Installed or published consumption: nothing is published, so FS.GG.Game's adapter (Game#730) is the
  first consumer of the packed artifact.

