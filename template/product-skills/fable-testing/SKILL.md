---
name: fable-testing
description: Test a Fable product across .NET, emitted JavaScript, Node, and real browsers, with runtime-specific fixtures and imported TRX/JUnit evidence.
---

# Fable testing capability

Test each boundary in the runtime that owns it. .NET tests cover server authority and pure shared
rules; Fable compilation proves only that the client emits JavaScript; Node proves module loading and
Node-target behavior; browser tests prove DOM, bundler, and browser-only APIs. Do not call one lane a
substitute for another.

```sh
dotnet test --no-restore --logger "trx;LogFileName=server.trx"
dotnet fable Client/Client.fsproj --outDir Client/src/generated --noCache
npm run --prefix Client test -- --reporter=junit
npm run --prefix Client test:browser -- --reporter=junit
```

Keep cross-runtime fixtures as explicit serialized inputs/expected outputs rather than assuming F#
runtime identity. For a shared contract, execute the same fixture in .NET and emitted JavaScript and
compare canonical observable values. Record target, compiler, Node, browser, npm lock hash, and the
TRX/JUnit artifact paths with the evidence.

Run clean locked restores in a directory outside the producer checkout. A passing local project
reference, warm npm cache, or test that never loads emitted output is not package/runtime evidence.

## Sources

- [Fable testing documentation](https://fable.io/docs/testing/)
- [Vite testing guide](https://vite.dev/guide/features.html)
- [Playwright test reporters](https://playwright.dev/docs/test-reporters)
