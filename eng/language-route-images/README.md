# Rust and Go language route image qualification

This directory prepares two independent Linux amd64 OCI candidates for the Rust 1.98.1 tic-tac-toe and Go
1.27.1 Snake route fixtures. `inputs.json` pins the single-platform base manifests and every official toolchain
archive by SHA-256. The qualifier refuses a dirty or different Git revision, changed recipes, a non-rootless
runtime, missing uid mapping, mutable image identity, or an image whose configured user is not `32768:32768`.

The hosted workflow performs the only claimed qualification. It builds without network access, then runs the
actual route tests and built-entrypoint journeys with the exact checkout mounted read-only. Each container has
networking disabled, all capabilities dropped, `no-new-privileges`, a read-only root, an empty inherited
environment, and only bounded `/tmp` and `/output` writable storage. Journals retain image and container identity,
exit status, and bounded output digests. Candidate archives and evidence expire after 14 days; they are
qualification artifacts and are neither published nor adopted route images.

The workflow is one linear job. Static preflight is placed before base pulls and archive downloads because it can
cheaply reject source, recipe, platform, user-mapping, and rootless-runtime drift. A custom state model is deferred:
there is no fan-out, shared cache, retry, evidence reuse, publication, or conditional admission state. Reassess if
those interactions are introduced.

Local source checks do not claim native image success:

```console
python3 -m unittest eng/language-route-images/test_qualify.py
python3 eng/language-route-images/qualify.py check
python3 -m py_compile eng/language-route-images/qualify.py eng/language-route-images/test_qualify.py
```

V2-LANG-01.5 binding remains gated by Coordination P2. These candidates do not establish portable executor
acceptance, publication, receiver installation, generated workspace availability, or route adoption.
