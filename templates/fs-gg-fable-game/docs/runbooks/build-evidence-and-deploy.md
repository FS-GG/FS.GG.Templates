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

## Container edge preparation

The generated workspace includes a production-shaped, Compose-spec container edge that can be completed before a public
host or domain is selected. `deploy/authority.Dockerfile` copies only the prepared authority from the named
immutable release. `deploy/Caddyfile` serves the release's static Player, optional Studio and selected content,
publishes only `VERSION` and `SHA256SUMS` under `/deployment/`, and proxies same-origin `/api`, `/hub` and
`/healthz` requests. The default ASP.NET and Caddy images are pinned by multi-platform manifest digest.

After `bash ./build.sh` has prepared the release, run:

```bash
SVG_RELEASE_VERSION=workspace-v1 bash deploy/run-local.sh
```

The runner prefers `podman compose` and falls back to `docker compose`; set `CONTAINER_ENGINE` to require one.
Podman therefore owns the intended local/VPS path while the same files remain executable on GitHub's Docker-based
hosted runners. Install a Podman Compose provider (`podman-compose` or another provider recognized by
`podman compose`) before invoking the script.

The verification refuses a bad release manifest, reads the exact served version and hashes back through Caddy,
compares the Player and optional Studio entry bytes, performs a real bootstrap, and opens and authorizes a
SignalR WebSocket session through the proxy. `KEEP_EDGE_RUNNING=true` leaves the stack running. The local
composition binds only to loopback and uses HTTP deliberately; it demonstrates routing, not public TLS.

The `GAME_UPSTREAM` setting is the future authority-location seam: Caddy may proxy to an HTTPS authority on
another host without rebuilding the static release. Dynamic game-server allocation, matchmaking and direct
browser-to-node capabilities are not implemented by this deployment and require their own contract and roadmap.

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

For the final hosted effect, use a dedicated Ubuntu 24.04 LTS (or Debian 12) VPS with an SSH account that has
passwordless `sudo`. Put its exact host key in the invoking machine's `known_hosts`; the deployment refuses
TOFU/changed-host-key shortcuts. Point one public DNS name at the VPS and allow inbound TCP 22, 80 and 443 in
the provider firewall. Then build the immutable release and deploy it:

```bash
export DEPLOY_TARGET=deploy@203.0.113.10
export GAME_SITE_ADDRESS=game.example.com
export BOOTSTRAP_VPS=true # first deployment only
bash deploy/deploy-production.sh <immutable-version>
```

The one-time bootstrap installs Podman/Compose and unattended security upgrades. Activation runs rootful because
ports 80/443 are privileged, but the ASP.NET process remains the image's non-root `$APP_UID`. Each uploaded
deployment is content-addressed below `/opt/fsgg-fable-game/deployments`; a changed archive cannot overwrite the
same retained identity. `/opt/fsgg-fable-game/current` changes atomically. Startup failure restores the prior
symlink and environment; a failed public TLS/journey/restart verification invokes the same host rollback before
the activation is finalized. A systemd oneshot owns boot activation while Compose owns container restart, and Caddy's
named `/data` and `/config` volumes retain certificate state across application versions.

Caddy obtains and renews the public certificate only after DNS reaches the host and ports 80/443 are open. The
deployer waits for public TLS, compares the served version, manifest, Player and optional Studio bytes, forces
two real V3 SignalR WebSocket sessions through Caddy, disconnects/reconnects one session, restarts the systemd
service, checks boot enablement and repeats the public verification. It writes a capability-free
`artifacts/deployment-evidence/<version>.json` containing the observation time, release-manifest digest and
certificate identity. A static-only host, localhost or a tunnel is still only development evidence.

Every successful deploy prints its content-addressed deployment id and the evidence records the release-manifest
SHA-256. Retain both values. Roll back later without reconstructing old bytes on the operator machine:

```bash
export DEPLOY_TARGET=deploy@203.0.113.10
export GAME_SITE_ADDRESS=game.example.com
export GAME_UPSTREAM=authority:8080
export EXPECTED_RELEASE_MANIFEST_SHA=<64-character digest from the prior receipt>
export SVG_DEPLOYMENT_EVIDENCE=artifacts/deployment-evidence/rollback-<version>.json
bash deploy/rollback-production.sh <version>-<archive-sha-prefix> <version> "$EXPECTED_RELEASE_MANIFEST_SHA"
```

The protected workflow exposes the same operation as `operation=rollback`; supply `retained_deployment_id` and
`expected_manifest_sha256`, and leave `bootstrap_vps=false`. It verifies the retained directory and every manifest
entry on the host before switching, then checks trusted TLS, exact served manifest/Player/Studio bytes, two-client
V3 WebSocket reconnect and a service restart. Failure automatically restores the deployment that was active when
rollback began. Redeploy the intended version after completing the exercise. Never write session capabilities
into evidence.

Set `GAME_UPSTREAM=https://authority.example.com` before deployment when the ASP.NET authority later moves to a
separate game-server provider. Static assets remain unchanged and browser traffic stays same-origin at Caddy.
That remote endpoint must independently provide trusted TLS; allocation and matchmaking remain a later contract.

Browser qualification names its boundary: Chromium is exercised locally. Firefox,
WebKit, screen-reader output, physical devices, and audibility remain unqualified until
observed on those runtimes.
