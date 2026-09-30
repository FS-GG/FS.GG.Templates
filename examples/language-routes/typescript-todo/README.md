# TypeScript todo language route

This isolated qualification fixture ports the delivered enrollment todo behavior to strict TypeScript without changing the delivered app. The browser executes JavaScript emitted by the exact TypeScript 5.9.2 compiler and exercises add, edit, complete, filter, delete, reload retention, and malformed retained-state recovery through the served entry point.

```console
npm ci
npm run verify
```

`toolchain-lock.json` selects Node 24.8.0, TypeScript 5.9.2, Playwright 1.63.0 and the Linux amd64 browser-image recipe. `scripts/check-toolchain.mjs` prints the actual host version and marks any other Node runtime as `preparatory-host-version-mismatch`. Such a run verifies source and behavior but does not qualify the selected runtime or image.

An isolated exact Node 24.8.0 installation can run the bounded native fixture qualification after its official archive is independently verified:

```console
TYPESCRIPT_TODO_NODE_ARCHIVE=/absolute/node-v24.8.0-linux-x64.tar.gz \
  /absolute/node-v24.8.0-linux-x64/bin/node scripts/qualify-selected-node.mjs
```

The fixture qualifier refuses another Node version or a mismatched archive, binds TypeScript compilation, unit tests, the static server and Playwright to `process.execPath`, and reports native fixture scope. The dedicated image qualifier in `eng/typescript-todo-image` additionally compiles from a read-only source mount and redirects `dist`, reports, caches and retained browser state below `/output`.

This is source and native fixture preparation for V2-LANG-01.5. Portable installed adoption remains dependent on the published and enforced V2-LANG-01.2 integration route.
