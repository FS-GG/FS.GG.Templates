---
name: fable-project
description: Build or maintain a generated Fable workspace with a locked .NET/npm toolchain, explicit shared-code boundary, Vite development loop, and reproducible production build.
---

# Fable project capability

Use this skill for a Fable client or Fable library workspace. Keep server-only ASP.NET Core,
filesystem, reflection, clocks, and secrets out of Fable-compiled source; keep DOM and JavaScript
interop out of server-only source. A shared project is eligible only when it Fable-compiles and its
semantics are explicitly tested on both runtimes.

## Pinned toolchain and layout

Commit `global.json`, NuGet lock files, `package.json`, and `package-lock.json`; use `dotnet restore
--locked-mode` and `npm ci`, never an unconstrained latest restore. The currently qualified local
reference is Fable CLI 5.13.0 with Fable.Core 5.2.0; treat that as an exact compatibility input, not
a promise that arbitrary Fable packages work with it. Pin Node, npm, Vite, browser, and every Fable
package in the generated workspace and record their observed versions in evidence.

Use separate `Server`, `Client`, `Shared`, and test lanes. `Shared` contains DTOs and pure rules only;
the server remains authoritative. Put Fable output under the client package directory and let Vite
own development serving, hot reload, bundling, and production assets. ASP.NET Core owns production
static-file serving after Vite has built the assets.

```sh
dotnet restore --locked-mode
npm ci --prefix Client
dotnet fable Client/Client.fsproj --outDir Client/src/generated --noCache
npm run --prefix Client dev
npm run --prefix Client build
dotnet test --no-restore --logger "trx"
```

Make the Vite development proxy explicit (for example `/api` to the local ASP.NET Core port); never
hide it in a developer-specific browser setting. Production testing must serve `Client/dist` through
the server and exercise the same JSON route as the browser.

## Watch and release evidence

The watch loop is Fable compilation plus Vite, with a separately started server when the product has
one. Production evidence is a clean locked restore, Fable compilation, Vite build, server publish,
and browser smoke against the published static assets. Record TRX/JUnit paths and actual Node/browser
versions; Node success does not establish browser support.

## Sources

- [Fable compiler documentation](https://fable.io/docs/)
- [Vite guide](https://vite.dev/guide/)
- [ASP.NET Core static files](https://learn.microsoft.com/aspnet/core/fundamentals/static-files)
