# BindingsProduct Fable bindings workspace

The initial qualified forcing corpus is `@babylonjs/core@9.19.0` plus `@babylonjs/loaders@9.19.0`: a narrow, modular scene path (NullEngine, Scene, maths, camera/light, box, and explicit glTF side effect). Run locked restores, curate `src/`, then run compile, emitted-import, Node and real-browser runtime, drift, and clean-consumer evidence before release.

`npm run generate:candidate` writes only tracked `generated-candidates/`; it never overwrites maintained source or advances the declaration lock. `npm run check:drift` follows every selected relative declaration import/export and fails on changed transitive hashes. Unsupported TypeScript constructs must be recorded in `coverage-and-drift.json`, never silently exposed as `obj`. Product skills are supplied by the Templates-owned `fable-bindings` skill manifest rather than copied into this provider template. Local proof precedes publication and any registry/wizard activation.

## Package locking

`./build.sh` (also `npm run build`) is this workspace's .NET entrypoint: it asserts the lockfiles, restores in locked mode, builds, then runs the pinned npm install, doctor, drift and Node runtime lanes.

This workspace restores in **locked mode** (`RestoreLockedMode` in `Directory.Build.props`), so every `packages.lock.json` beside a project is enforced: a package whose content hash differs from the committed one fails the restore rather than being silently substituted.

Locked mode is only meaningful if the lock can be regenerated, so here is the path. After changing any `PackageVersion` in `Directory.Packages.props` or any `PackageReference`, regenerate and commit the affected locks:

```bash
dotnet restore BindingsProduct.slnx --force-evaluate
```

Never hand-edit a lock file; a hash typed by a human is a hash no restore can reproduce.

Three settings keep those hashes reproducible, and all are load-bearing (see `FS.GG.Templates#384`, whose root cause was established by `#380`):

- **`NuGet.config` pins the source.** Its `<clear />` drops every source inherited from the machine, so a package is never served by whatever local feed the host happens to configure. To use a private or mirrored feed, add it there and then regenerate the locks with the command above.
- **`DisableImplicitLibraryPacksFolder` in `Directory.Build.props`** stops the F# SDK appending its own bundled `library-packs` folder to the restore sources. That folder ships an `FSharp.Core` archive with the same version as nuget.org's but different bytes, so leaving it enabled lets one restore record one content hash and the next restore reject it with `NU1403: Package content hash validation failed`. These projects target `netstandard2.1` and resolve FSharp.Core 4.7.2 transitively, which the SDK folder does not ship, so today this is a forward guardrail rather than a live repair — it stops the collision arriving unobserved when a floor or a target framework moves.
- **`RestorePackagesPath` in `Directory.Build.props`** gives this workspace its own `.nuget/packages` folder instead of the machine-wide one. Source pinning alone is not enough: NuGet's shared package folder is keyed by id and version only, so whichever build reached it first decides which archive lives there, and a later restore validates the committed hash against *that* entry. A private folder is what makes the committed hash enforceable on any machine rather than only on machines that happen to agree. Two consequences worth knowing: packages are not shared with your other checkouts, so a cold build downloads its own copies; and `.nuget/` belongs in your ignore file — this workspace ships without one, in common with `bin/`, `obj/` and `node_modules/`.

`build.sh` refuses to restore at all if the lock files are missing, and `npm run doctor` fails on the same condition, because a locked-mode restore with no lock on disk does not fail — it quietly writes a new lock from whatever the machine resolves, which defeats the entire mechanism.

`node scripts/lifecycle-evidence.mjs --expect clean --junit reports/bindings.junit.xml --handoff readiness/002-bindings-upstream-review/governance-handoff.json` turns the executable closure check into runner evidence and a narrow upstream-review verdict. `npm run test:lifecycle` first records the Governance F# public-surface receipt, then imports the report into the supported SDD lifecycle and requires observed verification, ship readiness, and a coherent doctor result. The composition acceptance routes both the SDD-emitted handoff and the upstream-review verdict through Governance: unchanged pins pass, while upstream declaration drift is a blocking review state. These commands are local acceptance only; they do not publish or activate the provider.
