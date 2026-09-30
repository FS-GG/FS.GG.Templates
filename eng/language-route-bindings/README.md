# Rust and Go portable executor binding

This directory prepares two closed `PortableReviewedOperation` bindings for the
qualified Rust Tic-Tac-Toe and Go Snake images. `prepare.py` verifies the exact
hosted artifact, its qualification manifest, both OCI archives, the fixed
executor assembly, and the source wrappers before it emits `binding.json`.

Preparation does not load an image or execute a container. The retained hosted
artifact expires after 14 days. Native admission must download artifact
`11112465308`, preserve its GitHub artifact SHA-256, and run:

```text
python3 eng/language-route-bindings/prepare.py \
  --artifact-zip <downloaded-artifact.zip> \
  --executor-assembly <c069-release/FS.GG.Coordination.Orchestration.Execution.dll> \
  --executor-compile-dependency <akka-1.5.71-net6/Akka.dll> \
  --source-root "$PWD" --source-revision "$(git rev-parse HEAD)" \
  --output <private-new-directory>
```

The policy keeps the hosted qualified build digest separate from the retained
OCI archive's manifest digest and config/image ID. The qualified Docker build
reference cannot be recreated by loading the retained OCI archive: export
changed the manifest identity, and its index annotation contains the old name
joined to the Docker digest. `derive-import.py` therefore creates a bounded
successor archive for each route. It requires the committed original archive,
index, full member inventory, manifest, config and every layer digest and size;
changes only the index image-name annotation; then verifies every other file is
byte-identical and the derived archive matches its committed hashes. It never
extracts archive paths and never modifies the original files.

`execute.fsx` selects the committed derived OCI name and retained manifest
digest. Values copied into `binding.json` cannot select another image. The
hosted build digest remains provenance for the original qualification and is
not presented as a fresh-store selector. Create the private derived archives
without loading either image:

```text
python3 eng/language-route-bindings/derive-import.py \
  --rust-archive <read-only-original>/rust-candidate.oci.tar \
  --go-archive <read-only-original>/go-candidate.oci.tar \
  --source-root "$PWD" --source-revision "$(git rev-parse HEAD)" \
  --output <private-new-derived-directory>
```

This emits two `0600` archives and a `0600` receipt with both original and
derived archive/index identities, all manifest/config/layer identities, member
inventory hashes, and the isolated metadata change. Source preparation accepts
neither native import nor execution.

The resulting plan is input to `execute.fsx`. The native gate must run each
operation once, cancel one actually running operation, reconstruct the executor
from the same durable state root, observe duplicate execution without a second
launch, and retain an unknown result when termination or cleanup cannot be
proved. Source preparation alone is not native binding acceptance.

Before downloading, the effect owner must read the GitHub artifact API and
require `expired=false`, run `36744671457`, artifact `11112465308`, and digest
`sha256:d3ede…56027`. Download the archive through the artifact API without
repacking it. `prepare.py` retains the two byte-verified original OCI archives
in its private output. For each route, `load-derived.py` rechecks the committed
source, policy, derived receipt, archive closure and exact archive bytes before
issuing one fixed load into new scoped rootless VFS roots. It then inspects the
committed OCI reference and requires the retained manifest and config
identities:

```text
python3 eng/language-route-bindings/load-derived.py \
  --kind rust \
  --archive <private-derived>/rust-derived.oci.tar \
  --receipt <private-derived>/derived-import.json \
  --source-root "$PWD" --source-revision "$(git rev-parse HEAD)" \
  --store-root <private-new-store> --runroot <private-new-runroot> \
  --output <private-new-rust-load-receipt.json> --podman /usr/bin/podman
```

Repeat for Go with its own fresh store and runroot. Local source checks do not
run this command. A later native gate must retain both load receipts and prove
the real operations through those same stores. Create each command once with
an owner-selected fixed deadline:

```text
dotnet fsi --reference:<verified-Akka> --reference:<verified-c069-executor> \
  eng/language-route-bindings/prepare-command.fsx -- \
  --kind rust --source-revision <binding-source-revision> \
  --command-id <owner-guid> --idempotency-id <owner-key> \
  --deadline <UTC-with-exactly-six-fractional-digits> \
  --output <private-new-command.json>
```

Retain those exact command bytes for execution, duplicate observation, and
recovery. Then invoke the harness with both pinned references:

```text
dotnet fsi \
  --reference:<verified-Akka-1.5.71-net6.dll> \
  --reference:<verified-c069-executor.dll> \
  eng/language-route-bindings/execute.fsx -- \
  --binding <private-output>/binding.json --kind rust \
  --command <private-command.json> \
  --source-root "$PWD" --source-revision "$(git rev-parse HEAD)" \
  --state-root <private-state> --store-root <loaded-private-store> \
  --runroot <loaded-private-runroot> --podman /usr/bin/podman \
  --git /usr/bin/git --tar /usr/bin/tar \
  --output <private-new-execution-evidence.json>
```

Repeat with `--kind go`. For cancellation, add
`--cancel-after-ms <bounded-ms>`; for reconstruction, start a fresh FSI process with the same inputs and
add `--recover true`. Repeating the original idempotency key must return the P2
duplicate disposition. A pending duplicate or an operation whose termination
or cleanup is unproved stays pending/unknown and cannot satisfy the native gate.

## Protected-main hosted qualification

`.github/workflows/rust-go-hosted-bind-qualification.yml` is the sole native
qualification route for these two bindings. It is manual and accepts one
`expected_head`; the job can start only when that value is both the dispatch
SHA and the current `origin/main` SHA. Rootless VFS, policy identities, wrapper
hashes, a clean source tree and the public artifact's live metadata are checked
before the large artifact download or the exact c069 executor build.

The job preserves the downloaded ZIP bytes, prepares the binding, derives and
fresh-loads each policy-selected OCI reference into its own store, and checks
the loaded manifest and config. It freezes each canonical command once. New
FSI processes then run the real Rust and Go journey, observe the same command
as a duplicate, and reconstruct the settled receipt through `RecoverAsync`.
A separate Rust command requests cancellation during execution and performs
one bounded recovery. Wrong toolchain, image reference and source inputs must
be refused by P2 before launch.

`hosted-qualification.py` validates the native evidence schema. It accepts the
job only from actual P2 receipt fields: execution started, termination was
observed, cleanup completed, the verification succeeded, and reconstructed
calls retained the exact command hash and container identity. Cancellation is
`unknown` unless the receipt proves the process started, cancellation was
requested, termination was observed, cleanup completed, and recovery returned
the settled duplicate. Helper exit flags, source preparation and OCI load alone
cannot set `accepted`. The cleanup phase removes all containers and both owned
VFS namespaces before final validation. The retained artifact contains the
exact downloaded ZIP and bounded JSON evidence for 14 days; it publishes or
activates nothing.

Local nested Podman is unsupported. Run source validation without creating
bytecode:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests/language-route-bindings -p 'test_*.py' -v
```
