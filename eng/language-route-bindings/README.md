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

The resulting plan is input to `execute.fsx`. The native gate must run each
operation once, cancel one actually running operation, reconstruct the executor
from the same durable state root, observe duplicate execution without a second
launch, and retain an unknown result when termination or cleanup cannot be
proved. Source preparation alone is not native binding acceptance.

Before downloading, the effect owner must read the GitHub artifact API and
require `expired=false`, run `36744671457`, artifact `11112465308`, and digest
`sha256:d3ede…56027`. Download the archive through the artifact API without
repacking it. `prepare.py` retains the two byte-verified OCI archives in its
private output. Load each archive into a new scoped rootless VFS store and
retain the returned image identity. Create each command once with an
owner-selected fixed deadline:

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
  --state-root <private-state> --store-root <private-store> \
  --runroot <private-runroot> --podman /usr/bin/podman \
  --git /usr/bin/git --tar /usr/bin/tar
```

Repeat with `--kind go`. For cancellation, add
`--cancel-after-ms <bounded-ms>`; for reconstruction, start a fresh FSI process with the same inputs and
add `--recover true`. Repeating the original idempotency key must return the P2
duplicate disposition. A pending duplicate or an operation whose termination
or cleanup is unproved stays pending/unknown and cannot satisfy the native gate.
