#!/usr/bin/env bash
set -euo pipefail

route_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
go_bin="${FSGG_GO_BIN:-go}"
actual="$($go_bin version)"

if [[ "$actual" != "go version go1.27.1 linux/amd64" ]]; then
  echo "expected exact Go 1.27.1 linux/amd64, observed: $actual" >&2
  exit 2
fi

gofmt_bin="$(dirname -- "$go_bin")/gofmt"
if [[ ! -x "$gofmt_bin" ]]; then
  echo "gofmt missing beside exact Go binary: $gofmt_bin" >&2
  exit 3
fi

scratch="$(mktemp -d "${TMPDIR:-/tmp}/fsgg-go-snake-check.XXXXXX")"
trap 'rm -rf -- "$scratch"' EXIT

export GOTOOLCHAIN=local
export GOWORK=off
export GOPROXY=off
export GOSUMDB=off
export CGO_ENABLED=0
export GOCACHE="$scratch/cache"
export GOMODCACHE="$scratch/modules"

cd "$route_root"

unformatted="$($gofmt_bin -l .)"
if [[ -n "$unformatted" ]]; then
  printf 'gofmt required:\n%s\n' "$unformatted" >&2
  exit 4
fi

"$go_bin" test -count=1 ./...
"$go_bin" vet ./...
"$go_bin" build -trimpath -o "$scratch/go-snake" .

printf '%s\n' "$actual"
printf 'stdlib-only locked module and native entrypoint checks passed\n'
