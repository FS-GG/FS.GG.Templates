#!/usr/bin/env bash
# Runs INSIDE the carrier. Exports the independently selected inputs, then invokes the fixed consumer.
set -euo pipefail
. /opt/q1/advisory/sources.env
export PATH=/opt/dotnet:/opt/node/bin:/opt/go-$GO_VERSION/go/bin:/usr/bin:/bin
export DOTNET_ROOT=/opt/dotnet DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_MULTILEVEL_LOOKUP=0
export FSGG_QUALIFICATION_ROOT=/w/$ATTEMPT
export FSGG_ONCE_PACKED_ARCHIVE=/pkg/$ARCHIVE_NAME
export FSGG_QUALIFIED_DOTNET=/opt/dotnet/dotnet
export FSGG_POLYGLOT_TOOL_DLL=/w/stage/output/FS.GG.Templates.PolyglotProviderTool.dll
export FSGG_SDD_CLI_DLL=/dl/x-sdd/tools/net10.0/any/FS.GG.SDD.Cli.dll
export FSGG_GOVERNANCE_CLI_DLL=/dl/x-gov/tools/net10.0/any/FS.GG.Governance.Cli.dll
export FSGG_SDD_SOURCE_ROOT=/sddsrc
export FSGG_CATALOG_POLICY=/w/policy.json
export FSGG_CATALOG_PATH=/w/stage/catalog-first.json
export FSGG_GOVERNANCE_CATALOG=/w/gov-catalog
export FSGG_QUALIFICATION_WORK_END_MONOTONIC=$(python3 -I -c 'import time;print(time.monotonic()+7200)')
export FSGG_NPM_INPUT_CACHE=/w/npm-input-cache
export FSGG_RUST_ADVISORY_ROOT=/opt/q1/advisory/rust-db FSGG_RUST_ADVISORY_MANIFEST=/opt/q1/advisory/rust.manifest
export FSGG_RUST_ADVISORY_MANIFEST_SHA256=$(sha256sum /opt/q1/advisory/rust.manifest | cut -d' ' -f1)
export FSGG_RUST_ADVISORY_SOURCE_COMMIT=$RUST_ADVISORY_COMMIT FSGG_RUST_ADVISORY_SOURCE_EPOCH=$RUST_ADVISORY_EPOCH
export FSGG_GO_ADVISORY_ROOT=/opt/q1/advisory/go-db FSGG_GO_ADVISORY_MANIFEST=/opt/q1/advisory/go.manifest
export FSGG_GO_ADVISORY_MANIFEST_SHA256=$(sha256sum /opt/q1/advisory/go.manifest | cut -d' ' -f1)
export FSGG_GO_ADVISORY_SOURCE_COMMIT=$GO_ADVISORY_COMMIT FSGG_GO_ADVISORY_SOURCE_EPOCH=$GO_ADVISORY_EPOCH
export FSGG_POLYGLOT_PYTHON=/usr/bin/python3.14 FSGG_POLYGLOT_PYTHON_SHA256=$(sha256sum /usr/bin/python3.14 | cut -d' ' -f1)
export FSGG_CARGO_AUDIT=/usr/bin/cargo-audit FSGG_CARGO_AUDIT_SHA256=$(sha256sum /usr/bin/cargo-audit | cut -d' ' -f1)
export FSGG_GOVULNCHECK=/usr/bin/govulncheck FSGG_GOVULNCHECK_SHA256=$(sha256sum /usr/bin/govulncheck | cut -d' ' -f1)
export RUSTUP_HOME=/opt/q1/rustup CARGO_HOME=/opt/q1/cargo CC=/usr/bin/gcc
exec bash /src/scripts/polyglot/qualify-once-packed.sh
