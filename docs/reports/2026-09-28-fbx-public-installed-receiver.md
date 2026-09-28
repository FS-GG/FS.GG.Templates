# FB-XANTHAM-01 public installed receiver evidence

Observed on 2026-09-28 from Templates main
`0acf320953934d02c635af97b5fefc276a21cdc0`. This window did not publish or alter delivered
template sources.

The qualification downloaded `FS.GG.Workspace.Template` 0.14.0 directly from NuGet.org. Its
SHA-256 was `a5f218d10bbac42b11afcfb401806c8f0f56261cf79876cc76710471d3666563`, and the archive contained
all 20 expected Xantham-named `fs-gg-fable-bindings` members. Installation used an isolated
`DOTNET_CLI_HOME`; the product was created with `--lifecycle none`; all generation, compilation and
runtime inputs came from the installed product.

The installed workspace prepared Xantham 0.1.0-alpha.2 and TypeScript 7.1.0-dev.20260902.1, emitted
a `proposal-ready` report with zero widened and escape findings, and reproduced byte-identical
candidate, manifest and symbol outputs across two runs:

| Artifact | SHA-256 |
|---|---|
| `AnsiRegex.fs` | `a3606e8d7de23a88dcab368d974b80bbc313d262b0347fed0e90512dad5552f6` |
| `manifest.json` | `06e66cfea5631e3535d8fad19d63df79d90e8c7b61f237f9c29389a7d97d5bbc` |
| `symbols.jsonl` | `903d8f5e99c87040bd7a457893c1851ab793bc5779012a2056889fd0009ac476` |

The generated source compiled for `netstandard2.1`, Fable 5.13.0 emitted the default `ansi-regex`
import, and Node passed default import, omitted options, `Options.Create`, ANSI/plain controls and
`onlyFirst`. Maintained binding source, declaration lock, mapping ledger and accepted coverage stayed
unchanged. Exact rejected reports covered a wrong prepared-tool fingerprint, path escape, 1 ms
timeout, unaccounted selected-signature loss and compile failure. A conflicting ambient Xantham cache
resolved when called directly but could not replace the runner's fingerprinted private-cache compiler.

A public 0.13.0 workspace, archive SHA-256
`ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c`, then received the bounded
20-file payload through a three-way inventory. An unrelated owner README edit remained byte-identical,
the adopted workspace passed the same generation and runtime harness, and an owner edit to
`scripts/run-xantham.mjs` caused refusal before any write.

The live assessment at `2026-09-28T10:36:49.916Z` returned `updates-found`, compatibility
`unqualified`, and disposition `investigate`. It observed published CLI/support 0.1.0 and source head
`0161084197bd4e1cba281cc06a3f4b7aa8d23067`. The reviewed 0.1.0 result remains blocked for this
baseline because its support package cannot satisfy the required `netstandard2.1` gate, so the
qualified alpha.2 execution pin remains correct.

Repeat with:

```console
FSGG_FABLE_BINDINGS_PUBLIC_INSTALLED=1 \
  FSGG_FABLE_BINDINGS_PUBLIC_OUT=/tmp/fbx-public-installed \
  tests/composition/fable-bindings/run.sh
```
