---
name: fable-bindings
description: Maintain a versioned Fable binding over an exact npm declaration closure, with review-only generation, curated interop, runtime proof, drift reporting, and release evidence.
---

# Fable bindings capability

Use this skill for a library that wraps a JS/TS package. Pin the npm package/version, lockfile,
declaration entry points and transitive `.d.ts` hashes, .NET SDK, Fable/Fable.Core, generator, Node,
and package manager. Generate a deterministic declaration-closure lock and machine-readable coverage
and drift report; an upstream update must red until those artifacts and maintained source are reviewed.

Assisted generation (Glutinum when qualified; `ts2fable` only as legacy comparison input) writes a
candidate/proposal, never the maintained public source or declaration lock. Review imports, optional
values, overloads, interfaces/static companions, side effects, and unsupported/lossy constructs.
Curated `[<Import>]`/`jsNative` code is the public API; dynamic escape hatches are documented but do
not count as typed coverage.

```sh
npm ci
node scripts/lock-declarations.mjs
node scripts/generate-candidate.mjs       # proposal only
dotnet restore --locked-mode
dotnet fable runtime/RuntimeSmoke.fsproj --outDir runtime/dist --noCache
node runtime/dist/Program.js
dotnet pack --no-restore
```

Release only after a clean consumer installs the packed NuGet library, separately installs the exact
npm runtime dependency, Fable-compiles, resolves emitted imports, and runs applicable Node and/or real
browser smoke tests. Publish and verify the package artifact before any registry/wizard activation.
The currently qualified reference is Fable 5.13.0/Fable.Core 5.2.0 with exact locks; requalify any
tool upgrade rather than floating it.

## Sources

- [Fable JavaScript interop](https://fable.io/docs/javascript/)
- [npm package-lock documentation](https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json)
- [NuGet lock files](https://learn.microsoft.com/nuget/consume-packages/package-references-in-project-files#locking-dependencies)
