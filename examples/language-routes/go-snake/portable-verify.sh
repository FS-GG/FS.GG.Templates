#!/bin/sh
set -eu
test "$(go version)" = "go version go1.27.1 linux/amd64"
export HOME=/output/home
export TMPDIR=/output/tmp
export GOCACHE=/output/go-cache
export GOPATH=/output/go-path
export GOTOOLCHAIN=local
export GOWORK=off
export GOPROXY=off
export GOSUMDB=off
mkdir -p "$HOME" "$TMPDIR" "$GOCACHE" "$GOPATH"
go test -count=1 ./...
printf '%s\n' '{"journey":"go-snake","schema":"fsgg.language-route.go-snake/1","toolchain":"1.27.1"}' > /output/go-snake-verification.json
