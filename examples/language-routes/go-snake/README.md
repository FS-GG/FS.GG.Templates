# Go snake route fixture

This standalone native fixture preserves the deterministic game behavior delivered in
`examples/enrollment-apps/snake`. It starts on a 32 by 18 board with the same body, direction, seed, food,
score and 180 ms step. Food grows the snake, adds 10 points and reduces the step toward the same 60 ms floor.
The turn queue, reversal refusal, pause/resume, wall and body collision, vacating-tail rule, full-board win and
restart behavior match the delivered browser reducer.

The executable reads one JSON player command per line from standard input and emits one JSON response containing
the acceptance disposition and complete state. Supported public commands are `state`, `start`, `direction`,
`advance`, `pause`, `resume` and `restart`. `advance` accepts 1 through 60,000 deterministic milliseconds; this
keeps the native journey independent from wall-clock scheduling.

## Exact toolchain and verification

The module requires Go 1.27.1 and uses only the standard library. The official
[Go download index](https://go.dev/dl/) identifies `go1.27.1.linux-amd64.tar.gz` with SHA-256:

```text
63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445
```

Provision that archive into an isolated directory, then run all checks without automatic toolchain or module
downloads:

```console
./scripts/provision-go.sh /tmp/fsgg-go-1.27.1
FSGG_GO_BIN=/tmp/fsgg-go-1.27.1/bin/go ./scripts/verify.sh
```

`verify.sh` requires exactly `go version go1.27.1 linux/amd64`, sets `GOTOOLCHAIN=local`, disables workspace,
proxy and checksum-network discovery, uses temporary build/module caches, checks formatting, and runs `go test`,
`go vet` and a trimmed native build. No .NET tool or runtime participates.

Preparation on 2026-09-30 started from protected Templates main
`ba760d7725fe64b9311c20b57a05ef8630533804`, verified the official archive checksum above and used the isolated
toolchain. All five tests passed, including the actual built-entrypoint journey; formatting, vet and native build
checks also passed. The journey starts by requesting the public initial state, then uses only public JSON commands
to exercise reversal refusal, growth and score, pause/resume, wall collision, terminal refusal and deterministic
restart. Focused domain tests separately cover body collision, legal entry into a vacating tail cell and eating the
final free cell.

For a manual native session after building, send newline-delimited commands such as:

```json
{"type":"state"}
{"type":"start"}
{"type":"direction","direction":"down"}
{"type":"advance","milliseconds":180}
{"type":"restart"}
```

## Acceptance boundary

This directory is source and native fixture preparation only. A local build does not establish a qualified
portable image, published producer artifact, installed receiver, generated-workspace availability or route
adoption. V2-LANG-01.5 acceptance waits for the enforced portable executor P2 boundary, P3 publication from the
protected producer and P4 receiver qualification against those exact bytes.

Telemetry attempt `go-snake-source-complete-20260930` is not configured; no usage or economic claim is made.
