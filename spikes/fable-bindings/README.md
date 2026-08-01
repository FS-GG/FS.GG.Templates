# Fable bindings qualification spike

This forcing corpus pins a narrow Babylon ESM slice, records its declaration
closure, keeps maintained Fable interop separate from candidates, and proves the
JavaScript runtime slice in Node. Run `npm ci`, `npm run check:drift`, and
`npm run test:runtime`. A candidate rerun only writes `generated-candidates/`.
