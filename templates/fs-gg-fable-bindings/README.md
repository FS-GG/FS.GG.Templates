# BindingsProduct Fable bindings workspace

Required inputs are a binding name, exact npm package/version, and `browser`, `node`, or `universal` target. Run locked restores, complete `declaration-lock.json`, curate `src/`, then run compile, emitted-import, applicable runtime, drift, and clean-consumer evidence before release.

`npm run generate:candidate` writes only `generated-candidates/`; it never overwrites maintained source or advances the declaration lock. Unsupported TypeScript constructs must be recorded in `coverage-and-drift.json`, never silently exposed as `obj`. Product skills are supplied by the Templates-owned `fable-bindings` skill manifest rather than copied into this provider template.
