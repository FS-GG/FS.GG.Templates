# TypeScript todo language route

This isolated qualification fixture ports the delivered enrollment todo behavior to strict TypeScript without changing the delivered app. The browser executes JavaScript emitted by the exact TypeScript 5.9.2 compiler and exercises add, edit, complete, filter, delete, reload retention, and malformed retained-state recovery through the served entry point.

```console
npm ci
npm run verify
```

`toolchain-lock.json` selects Node 24.8.0 and TypeScript 5.9.2 for the future V2-LANG-01.2 qualification candidate. `scripts/check-toolchain.mjs` prints the actual host version and marks any other Node runtime as `preparatory-host-version-mismatch`. Such a run verifies source and behavior but does not qualify the selected runtime or an execution image. No image is selected by this fixture.

This is source and native fixture preparation for V2-LANG-01.5. Portable installed adoption remains dependent on the published and enforced V2-LANG-01.2 integration route.
