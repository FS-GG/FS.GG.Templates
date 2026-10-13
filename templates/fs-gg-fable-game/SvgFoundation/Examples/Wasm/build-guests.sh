#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode=build
if [[ "${1:-}" == --generate-lock ]]; then mode=generate-lock; shift; fi
archive="${1:?usage: build-guests.sh [--generate-lock] <authenticated-sdk-0.3.0.tar.gz> <wasi-sdk-34-root>}"
wasi="$(realpath -e "${2:?missing WASI SDK root}")"
# Acquisition and runtime admission belong to the caller's maintained build route.
printf '%s  %s\n' 8091df6824981c0c37131524ffbcbae9bb8b36f672a20edc2efaddd35664f8c8 "$archive" | sha256sum --check --status
[[ "$(rustc --version)" == 'rustc 1.90.0 (1159e78c4 2025-09-14)' ]]
[[ "$(cargo --version)" == 'cargo 1.90.0 (840b83a10 2025-07-30)' ]]
[[ "$("$wasi/bin/clang" --version | head -n1)" == 'clang version 23.1.0-wasi-sdk (https://github.com/llvm/llvm-project 895aa2c896ada719451be2e3673c83da8ddf1141)' ]]
[[ "$mode" == generate-lock || -f "$source_dir/guest/rust/Cargo.lock" ]] || { echo 'Generate and qualify the independent Rust Cargo.lock before guest compilation' >&2; exit 2; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-template-policy.XXXXXX")"
trap 'rm -rf "$work"' EXIT
python3 - "$archive" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    members = archive.getmembers()
    if len(members) > 128 or sum(member.size for member in members) > 2 * 1024 * 1024:
        raise SystemExit('SDK archive exceeds the selected source bounds')
    for member in members:
        if (member.issym() or member.islnk() or not (member.isdir() or member.isfile())
                or member.name.startswith('/') or '..' in member.name.split('/')):
            raise SystemExit('Unsafe SDK archive member')
PY
tar -xzf "$archive" -C "$work"
sdk="$work/fsgg-wasm-sdk-0.3.0"
[[ -d "$sdk" ]]
(cd "$sdk" && sha256sum --check --strict SHA256SUMS >/dev/null)
rust="$sdk/examples/wasm/rust/template-policy"
mkdir -p "$rust"
cp -a "$source_dir/guest/rust/." "$rust/"
if [[ "$mode" == generate-lock ]]; then
  # Resolve only the independently authored crate in its actual verified SDK layout.
  cargo generate-lockfile --offline --manifest-path "$rust/Cargo.toml"
  [[ -f "$rust/Cargo.lock" ]] || { echo 'Cargo did not generate its actual lock' >&2; exit 2; }
  cp "$rust/Cargo.lock" "$source_dir/guest/rust/Cargo.lock"
  exit 0
fi
out="$source_dir/../../obj/wasm-policy-guests"
mkdir -p "$out"
for variant in normal malformed trap loop; do
  define=(); [[ "$variant" == normal ]] || define=("-DPOLICY_${variant^^}")
  "$wasi/bin/clang" --target=wasm32 -std=c17 -Oz -nostdlib -mno-bulk-memory -mno-reference-types -mno-multivalue "${define[@]}" \
    -I "$sdk/sdk/wasm" "$sdk/sdk/wasm/fsgg-wasm-guest.c" "$source_dir/guest/policy.c" \
    -Wl,--no-entry -Wl,--export-memory -Wl,--initial-memory=2097152 -Wl,--max-memory=8388608 \
    -Wl,--export=sc2c_abi_version -Wl,--export=sc2c_alloc -Wl,--export=sc2c_free \
    -Wl,--export=sc2c_initialize -Wl,--export=sc2c_process -Wl,--export=sc2c_shutdown \
    -o "$out/c-$variant.wasm"
done
export CARGO_TARGET_DIR="$work/target"
export RUSTFLAGS='-Copt-level=z -Cpanic=abort -Ctarget-feature=-bulk-memory,-multivalue,-reference-types,-relaxed-simd,-sign-ext,-simd128,-tail-call -Clink-arg=--no-entry -Clink-arg=--export-memory -Clink-arg=--initial-memory=2097152 -Clink-arg=--max-memory=8388608 -Clink-arg=--table-base=0'
cargo build --locked --offline --release --target wasm32-unknown-unknown --manifest-path "$rust/Cargo.toml"
# Some independently authored crates emit no table. Inspect framing only;
# table removal, when needed, still belongs to the selected SDK normalizer.
raw="$work/target/wasm32-unknown-unknown/release/fsgg_template_policy.wasm"
table="$(python3 - "$raw" <<'PYMODULE'
import pathlib, sys
module = pathlib.Path(sys.argv[1]).read_bytes()
if module[:8] != b"\x00asm\x01\x00\x00\x00":
    raise SystemExit("Compiler output is not a WASM v1 module")
offset, table = 8, False
while offset < len(module):
    section = module[offset]
    offset += 1
    length = 0
    for shift in range(0, 35, 7):
        if offset >= len(module):
            raise SystemExit("Truncated module section length")
        value = module[offset]
        offset += 1
        length |= (value & 127) << shift
        if value < 128:
            break
    else:
        raise SystemExit("Oversized module section length")
    if offset + length > len(module):
        raise SystemExit("Module section exceeds compiler output")
    table = table or section == 4
    offset += length
print("present" if table else "absent")
PYMODULE
)"
if [[ "$table" == present ]]; then
  node "$sdk/sdk/wasm/tools/strip-unused-table.mjs" "$raw" "$out/rust-normal.wasm"
else
  cp "$raw" "$out/rust-normal.wasm"
fi
python3 - "$out" "$source_dir" <<'PY'
import hashlib, json, pathlib, sys
out, source = map(pathlib.Path, sys.argv[1:])
modules = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.glob('*.wasm'))}
if set(modules) != {'c-normal.wasm', 'c-malformed.wasm', 'c-trap.wasm', 'c-loop.wasm', 'rust-normal.wasm'}:
    raise SystemExit('Unexpected guest output population')
(out / 'modules.json').write_text(json.dumps({
    'sdkSha256': '8091df6824981c0c37131524ffbcbae9bb8b36f672a20edc2efaddd35664f8c8',
    'cSourceSha256': hashlib.sha256((source / 'guest/policy.c').read_bytes()).hexdigest(),
    'rustSourceSha256': hashlib.sha256((source / 'guest/rust/src/lib.rs').read_bytes()).hexdigest(),
    'modules': modules,
}, sort_keys=True))
PY
