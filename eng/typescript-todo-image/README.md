# TypeScript todo browser image source

This directory prepares one Linux amd64 OCI candidate for the TypeScript todo route. It pins the Playwright
1.63.0 Noble image by its amd64 manifest digest, replaces its runtime with the official Node 24.8.0 archive,
installs the locked TypeScript and Playwright npm graph offline, and retains the corresponding licences. The
browser archive URLs and independently observed SHA-256 values in `inputs.json` describe the assets closed by
the pinned Playwright base; the build does not download them again.

The only runtime entry point is `fsgg-typescript-todo-qualify`. The qualifier supplies no caller-controlled
command or arguments. It mounts the committed source at `/source` read only, disables container networking
while preserving loopback for the local HTTP journey, and writes compilation, reports, caches, temporary
browser profiles and its result only below `/output`. Rootless `keep-id` maps the calling host user to the
fixed container uid/gid `32768:32768`; private evidence therefore remains owned and readable by the calling
user for validation, upload and scoped cleanup.

Local checks validate source decisions and do not build or qualify an image:

```console
python3 -m unittest eng/typescript-todo-image/test_qualify.py
python3 eng/typescript-todo-image/qualify.py check
```

The dedicated workflow owns the strict native run. Its exact manual equivalent, from a clean committed
Linux amd64 checkout with rootless Podman and the pinned base already present, is:

```console
python3 eng/typescript-todo-image/qualify.py qualify \
  --expected-source-revision "$(git rev-parse HEAD)" \
  --state-dir /absolute/private/state \
  --root /absolute/private/podman-root \
  --runroot /absolute/private/podman-runroot
```

A source-only run is preparation. Qualification requires the exact-revision native result, candidate archive,
OCI image ID and digest, and operation journal emitted by that command.
