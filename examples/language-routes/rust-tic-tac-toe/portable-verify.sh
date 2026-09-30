#!/bin/sh
set -eu
test "$(rustc --version)" = "rustc 1.98.1 (48a229cea 2026-09-01)"
test "$(cargo --version)" = "cargo 1.98.1 (797e8a9bc 2026-08-05)"
export HOME=/output/home
export CARGO_HOME=/output/cargo
export CARGO_TARGET_DIR=/output/target
mkdir -p "$HOME" "$CARGO_HOME" "$CARGO_TARGET_DIR"
cargo test --locked --offline
printf '%s\n' '{"journey":"rust-tic-tac-toe","schema":"fsgg.language-route.rust-tic-tac-toe/1","toolchain":"1.98.1"}' > /output/rust-tic-tac-toe-verification.json
