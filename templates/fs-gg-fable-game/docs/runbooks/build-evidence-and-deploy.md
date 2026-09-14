# Build, evidence, and deployment runbook

Run `bash ./build.sh` from the workspace root with .NET SDK 10.0.400. NuGet and npm lock
files are required. The build emits `artifacts/static-player`, optional
`artifacts/static-studio`, `artifacts/authority-server`, and TRX/JUnit reports below
`artifacts/test-results`.

The same build stages a versioned deployment set at
`artifacts/releases/${SVG_RELEASE_VERSION:-workspace-v1}`. `SHA256SUMS` covers the
static player, optional Studio, authority, selected example content, and `VERSION`.
The version directory is created by one rename only after every staged file passes
its hash readback. Repeating identical bytes is idempotent; different bytes under an
existing version refuse without changing its retained rollback set. Set
`SVG_RELEASE_VERSION` to a new application release when bytes change; the default
names the generated workspace's first local release.

Provide Quint 0.32.0 explicitly. Download the release's `quint-linux-amd64`, verify
SHA-256 `939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f`, make it
executable, and run `QUINT_BIN=/absolute/path/to/quint bash ./build.sh`. Product CI uses
this exact command-local identity.

Import only those observed reports through the installed SDD 1.8 evidence command.
For each existing verification work item, run
`fsgg-sdd evidence --root "$PWD" --work WORK-ID --from-test-report artifacts/test-results/domain.trx`
and repeat for the protocol/server TRX and browser JUnit reports that satisfy that
item's declared obligations. The command parses and hashes the real report; it does
not create missing obligations or substitute a claimed pass. Each verification
declaration must name that report in its `sourceRefs` before import. Afterward, read
back every affected `observedRun.source`, exact digest, and passed/failed/skipped
counts; `noChange` or `evidenceReady` by itself does not show that the supplied report
was imported.
Preserve the exact candidate directory and record SHA-256 hashes before deployment.

The browser suite treats startup as a separate integration scorecard. Its candidate
regression limits are synchronization, DOM readiness, and first visible gameplay
interaction under 5 seconds, transferred resources under 2 MB, fewer than 64
resources, and at most four scripts. These deliberately broad limits detect a stalled
authority or accidental Studio/tool closure without replacing the renderer's tighter
first-usable and workload budgets. The JUnit/JSON attachment records the actual
Chromium version, isolated cold-context condition, loopback published authority,
viewport, selected bundle, and observed values. A boundary-valued controlled fixture
must be rejected by every limit. The Arcade attachment records a 120-frame smoke
window and missed-frame ratio as an observation; it is not sustained-runtime release
qualification and has no invented acceptance threshold.

The public Rendering 0.31.0 producer owns the unchanged 100/200-entity latency,
world-extent culling, retained-resource, and lifecycle harness. This workspace reuses
that evidence only for those unchanged renderer subjects. Its changed composition is
covered here by current Chromium interaction, reduced-motion and 320 CSS-pixel reflow
tests. Heap trend, compositor/display timestamps, Firefox, WebKit, screen-reader
speech output, physical devices, and audible output remain unavailable until observed
on those runtimes; synthesized touch/gamepad input and WebAudio dispatch do not claim
physical presentation.

Deploy the static files and authority to a durable destination that supports ASP.NET
Core, same-origin `/api` and `/hub` WebSocket upgrades, TLS, and application rollback.
Read back the deployed version and served static hashes, then repeat the two-browser
reconnect/content journey. A static-only host and localhost are development checks.

Rollback by redeploying the retained compatible release directory and matching content
file. Confirm health, static hashes, bootstrap, WebSocket reconnect, and full snapshot
before removing the failed release. Never write session capabilities into evidence.

Browser qualification names its boundary: Chromium is exercised locally. Firefox,
WebKit, screen-reader output, physical devices, and audibility remain unqualified until
observed on those runtimes.
