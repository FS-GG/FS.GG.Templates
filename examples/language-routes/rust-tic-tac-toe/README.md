# Rust tic-tac-toe route fixture

This dependency-free native fixture preserves the delivered two-player behavior in
`examples/enrollment-apps/tic-tac-toe`: X starts, legal moves alternate, wins are evaluated before a
full-board draw, terminal games refuse moves, and restart returns a fresh game.

The crate pins Rust 1.98.1 with `rust-toolchain.toml`. That version is listed in the official
[Rust release announcements](https://blog.rust-lang.org/releases/) and was published as the
[Rust 1.98.1 point release](https://blog.rust-lang.org/2026/09/03/Rust-1.98.1/). It fixes the 1.98.0
vtable-generation miscompilation. The crate uses only the standard library and has no registry dependencies.

## Build and test

From this directory:

```console
rustc --version --verbose
cargo test --locked
cargo clippy --all-targets -- -D warnings
cargo fmt --check
```

The tests cover legal play, occupied and out-of-range refusal, both players on all eight winning lines,
a draw, ninth-move win precedence, terminal refusal, restart from every phase, protocol errors, and a
subprocess journey through the actual Cargo-built entry point from its initial state through a completed
game and restart.

Preparation evidence on 2026-09-30 is bound to protected Templates base
`ba760d7725fe64b9311c20b57a05ef8630533804`. An isolated rustup home reported:

```text
rustc 1.98.1 (48a229cea 2026-09-01)
cargo 1.98.1 (797e8a9bc 2026-08-05)
```

With that toolchain, `cargo test --locked` passed six library tests and one built-entrypoint integration
test; `cargo clippy --all-targets --locked -- -D warnings` and `cargo fmt --check` also passed. The host's
pre-existing Rust/Cargo 1.90.0 was observed but is not qualification evidence for this 1.98.1-pinned fixture.

Run the player protocol with:

```console
cargo run --locked
```

Commands are `move INDEX` for zero-based indices 0 through 8, `restart`, and `quit`. Every non-quit command
emits an `ACCEPT` or `REFUSE` line followed by the complete state:

```text
STATE phase=playing turn=X winner=- board=---------
```

## Acceptance boundary

This directory is source and native fixture preparation only. A local build does not establish a qualified
portable image, a published producer artifact, an installed receiver, generated-workspace availability or
route adoption. V2-LANG-01.5 acceptance waits for the enforced portable executor P2 boundary, P3 publication
from the protected producer, and P4 receiver qualification against those exact bytes. Until those steps complete,
Rust 1.98.1 is a pinned source requirement rather than an installed FS.GG language-route capability.

Telemetry attempt `rust-tictactoe-source-prep-20260930` is not configured; no usage or economic claim is made.
