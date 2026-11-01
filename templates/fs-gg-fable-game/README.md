# FableGameWorkspace

A server-authoritative multiplayer SVG game workspace: one F# ASP.NET Core server,
one Fable/Elmish browser client, and a package-backed SVG player sharing a
product-owned `Domain` and an explicit, versioned wire protocol.

## The transport boundary (ADR-0073)

- **Plain ASP.NET Core HTTP endpoints** (`Server/Program.fs`'s `/api/bootstrap`) own
  typed request/response operations. Every operation is an explicit, versioned DTO
  pair in `Protocol/Http.fs`, encoded and decoded by named codec functions on both
  the .NET side (`Thoth.Json.Net`) and the Fable side (`Thoth.Json`) -- never
  reflection-driven serialization, never a generated RPC proxy.
- **ASP.NET Core SignalR** (`Server/GameHub.fs`, `Client/SignalR.fs`) owns
  connection-oriented traffic: input, snapshots, presence, and resync, through a
  narrow, hand-written binding over the official `@microsoft/signalr` npm client.
- `Protocol/Http.fs` and `Protocol/Realtime.fs` are compiled *twice* from the same
  source: once by `Protocol/Protocol.fsproj` (against `Thoth.Json.Net`, for the
  server) and once as a direct `Compile Include` from `Client/Client.fsproj`
  (against `Thoth.Json`, via `dotnet fable`). `#if FABLE_COMPILER` guards only the
  `open` statement; every codec call is the same named function on both sides.
  `Protocol.Tests/cross-runtime/` proves this pairing for real: it builds both
  targets and round-trips every DTO .NET-encode/Fable-decode and the reverse,
  including two deliberately rejected cases.

Fable.Remoting is not used (superseded by ADR-0073; see
`docs/reports/2026-08-01-fable-full-stack-toolchain-compatibility-spike.md` and
`FS.GG.Templates#370` for why).

## The sample

`Domain/ArenaContent.fs` and `Domain/ArenaRules.fs` define the pure authoritative
arena shared by the .NET server and the Fable Studio. Players occupy cells on a fixed
grid, and `Pathfinding.astar` -- the `LockstepExact` surface of the
published `FS.GG.Game.Core` Fable compatibility profile
(`fs-gg-game-core-fable-lockstep-v1`) -- resolves movement. Both `Domain` (server)
and `Client/Movement.fs` (browser, local path preview only) call the *same*
published package function. The shared arena transition uses Game.Core kinematics
for solid geometry, interaction proximity, moving-hazard contact, health, score,
win, and restart. The server's `Server/RoomAuthority.fs` is the only place a networked
move is committed. `Server/RoomAuthority.fs` also enforces the
stale-input guard (a non-increasing input sequence is dropped) and the
disconnect/reconnect contract: a reconnecting client always gets a bounded, full
authoritative resync, never a delta log.

The SVG player is the default product composition in Templates 0.14. Choose it explicitly
with `--bundle player`, or select `studio`, `tactical`, `arcade`, or `complete`. Studio adds
the integrated Create/Arrange/Play/Review tools; tactical and arcade add their editable
examples plus Studio; complete includes both. The player bundle contains no Studio or example
source. Rendering's profile remains independent from this product composition choice.

When lifecycle is omitted, this fable-game provider selects Quint-backed `typed-sdd`.
Explicit `none`, `sdd`, `typed-sdd`, and `spec-kit` keep their distinct selections. Raw
`dotnet new` emits product files; use `fsgg-sdd scaffold` to create the SDD-owned root lifecycle.

The compatibility flag remains readable for existing scripts: explicit
`--svgFoundation true` selects the retained preview-compatible complete composition, while
explicit `--svgFoundation false` retains the pre-0.14 non-SVG product. The old and new selectors
are mutually exclusive, including redundant combinations; using both is rejected during template
argument validation, before the destination is written. Bundle selection does not select or
activate a lifecycle.

The selected tool payload carries separate player and `SvgFoundation/Studio` entries. The composition binds
both to exact public producer versions and enables the product-owned command profiles.
Build them with `bash SvgFoundation/build.sh` and `bash SvgFoundation/Studio/build.sh`. The Studio
build copies its worker, verified font data, notices and npm lock from the restored producer package
into ignored output. The generated workspace exposes Create, Arrange, Play and Review modes, responsive
docks, palette/help/rebind flows, and keyboard, pointer, touch and gamepad routes over the same effective
profile. Templates `0.14.0` uses Rendering `0.31.0`, Game `0.16.0`, Net `0.6.0`, and Audio `0.6.0` as one
qualified public set.

The SVG runtime renders complete version 3 authority snapshots through monotonic retained
scene replacement. `W/A/S/D` submits movement to the required server, `E` interacts with nearby game
content, and `R` requests a restart after a terminal outcome. The server owns position, health, score,
collectible state, win state, moving-hazard time, and restart; every connected SVG player renders those snapshots. The
gesture-unlocked Audio host plays the shipped non-silent movement cue for accepted game actions. The
separately bundled Studio is never linked into the player output. Studio opens the same
`continuous-arena` document, compiles its typed gameplay elements into the same `ArenaContent` contract,
and runs the same pure `ArenaRules` transition in Play. Create, Arrange, Play, Review, browser persistence,
and reload retain one authored scene root, camera, selection, and history while runtime preview geometry
stays transient. **Export playable arena content** writes the validated content file consumed by the authority.

The realtime baseline has four deliberately small but production-relevant rules:

- Bootstrap issues an opaque session capability. The hub URL carries neither player
  identity nor capability; the client sends a versioned `sessionHello` only after the
  SignalR transport opens, and the server rejects unknown, duplicate-live, or
  incompatible bindings.
- A reconnect performs that hello again and receives one full authoritative snapshot.
  Explicit resync cursors are accepted only from zero through the current tick; a
  negative or future cursor is rejected instead of being treated as a valid frontier.
  Client transport callbacks only dispatch Elmish messages, making connecting,
  reconnecting, closed, and failed states explicit rather than retaining a hidden
  second UI state.
- Inputs are admitted at hub arrival but resolve at the next server tick frontier,
  sorted by player identity and sequence. Transport scheduling therefore cannot decide
  gameplay order; snapshots with an older tick cannot rewind the client view.
- Realtime DTO version 1 remains frozen for the retained legacy grid client. It uses a separate legacy
  authority path, so new walls, hazards, and terminal rules cannot silently change that client's gameplay.
  Version 2 retains its frozen cooperative arena format. Version 3 adds immutable authored boundary and spawn
  alongside complete gameplay state and exact content/schema identity. Missing fields,
  unknown actions, stale input, wrong snapshot compatibility, and content mismatches fail before gameplay
  changes. Replay digests use the same complete canonical state on .NET and Fable. Saved Studio scene
  envelopes retain the Rendering-owned schema identifier; the authority consumes only a separately exported,
  validated arena-content file.
- Admission is bounded to the arena's 240 cells, with no occupied-cell fallback. A
  bootstrap that would exceed that bound returns HTTP 429. Unbound and disconnected
  capabilities expire after two minutes; the tick loop cleans them up and releases
  their reserved authority.
- `stop`/disconnect removes a connection's group membership and room presence. The
  capability remains available for its bounded reconnect window, keeping the starter
  zero-config while making the resource boundary visible and testable.

## Renderers: a game playable on SVG, Pixi and Babylon

The Fable client carries the published `FS.GG.Game.Render` and `FS.GG.Game.Render.Browser` `0.18.0` authoring
path (FS.GG.Game's "Three-adapter authoring path" and "Interaction contract"), and its game page is playable on all
three backends.

**What a player gets.** The page `Client/index.html` shows the arena as the DOM grid `App.view` maintains (the default,
and the page the existing journeys drive) or drawn by the SVG, PixiJS or BabylonJS renderer. The `Renderer` selector
(`#renderer-backend`) switches between them at run time, and the game state, which is the Elmish `App.Model`, survives
every switch. On every renderer a cell is selected the same three ways, and each becomes the `CellClicked` message a
click or Enter on a DOM grid cell dispatches (so the server stays the only authority for movement):

| Input | SVG, Pixi and Babylon |
|---|---|
| Pointer | a primary press on a cell (each backend's own hit test; they agree with `SceneInteraction.hitTest`) |
| Keyboard | the surface is a focusable `role=application`; the arrows move a focus through the cells in row-major order (the published contract: right or down is the next cell, left or up the previous), Enter or Space selects the focused cell, Escape clears the selection (`SelectionCleared`) |
| Accessible mirror | one labelled button per cell (`Column 3, row 2: empty`), `aria-pressed` on the selected one and a polite status, kept out of sight until a button has the focus |

The DOM grid keeps its own two-dimensional arrow keys; the renderers' arrows are the contract's linear order. The
selected cell (`Model.Selected`) is game state, so each backend draws it and the mirror reports it after a switch.

**Where the pieces are.** `Client/Renderers.fs` is the module `scripts/new-game-renderers.sh` of FS.GG.Game `0.18.0`
generates (`--module Renderers --state App.Model`), with `view`, `objects` (one selectable object per arena cell) and
`select` (the game's selection rule) written for this arena. `Client/Stage.fs` mounts them in `#renderer-stage`,
starts a `RendererDriver`, binds the `SelectionRoute` to `CellClicked` and `SelectionCleared`, and keeps the renderers
presenting the model; `Program.fs` calls it after `App.view`. To bring your own game, edit `view`, `objects` and
`select`, and the `states` list in `Conformance.fs` (at least two states that look different).

**Which page is served.** The default product serves the static SVG player (`SvgFoundation/`) from the authority
server, and this client only when the product has no `SvgFoundation` (the legacy composition). Run the renderer page
with `cd Client && npm run dev` beside `dotnet run --project Server/Server.fsproj`, or serve the built `Client/dist`
(`vite preview`, with `FSGG_AUTHORITY` naming the server).

**The conformance kit and the journeys.** `Client/Conformance.fs` runs the kit (`RendererConformance.run`) on
`Renderers.conformance`, including its `interaction` section (hit test, keyboard, accessible mirror, input-host
disposal, selection across a switch), each checked against what the page itself observes. `Client/renderers.html`
loads it. `Browser.Tests/renderer-conformance.spec.ts` requires every requirement to pass on all three backends, driven
with real pointer and keyboard input (`renderer-support.ts` exposes the test driver the kit asks for), and a control
that gives the same objects a selection rule that ignores requests, which the kit must refuse on every backend.
`Browser.Tests/renderer-journey.spec.ts` plays the real page against the authority server: on each backend a move by
pointer, by keyboard and through the mirror, a switch through svg, pixi, babylon, svg, babylon, pixi and the DOM grid with
the state kept, and a press outside the board that must play nothing. Both run as the last step of `build.sh`
(`cd Browser.Tests && npm run test:renderers`), in Chromium with software WebGL; set `PLAYWRIGHT_CHROMIUM_ARGS` to add
launch flags (for example a GPU host's ANGLE flags).

**Cost.** The game page's JavaScript (measured with the built page loaded in Chromium, uncompressed and gzip): the
page without renderers was 145,909 bytes (40,402 gzip) in 2 files; with all three it is 1,591,588 bytes (413,107 gzip)
in 2 files at load, and choosing Pixi then Babylon loads 11 more files, 1,932,195 bytes (497,913 gzip) in all. Pixi and
Babylon are imported statically by `BrowserRenderers`, so a page that starts on the DOM grid still pays for them until
FS.GG.Game#774 (lazy loading) ships. `renderer-journey.spec.ts` records the number and bounds it at 4 MB.

**Known limits.** Keep the board unscaled: Babylon's picking under CSS scaling and its pixel offsets are FS.GG.Game#753
and #778. Babylon draws lit at about 0.75 of the scene colour. `SelectionRequest` carries no modifier keys
(FS.GG.Game#771), so a shift or control click is a plain selection. The retained SVG surface does not tag `data-renderer`
(FS.GG.Game#767), so the page uses the interactive `SvgSurface`.

The client's Game.Core is `FsGgGameVersion` (and `FsGgGameNetworkVersion`, the server's), `0.18.0`, because
`FS.GG.Game.Render` of a version depends on Game.Core of that version. The static SVG player and Studio under
`SvgFoundation/` keep their own Game.Core pins (`FsGgGameRuntimeVersion`, `FsGgGameReplayVersion`).

## Running it

For local authority development, run `dotnet run --project Server/Server.fsproj`; the
browser client proxies `/api` and the `/hub` WebSocket upgrade to
`http://localhost:5000`. To run the authority with Studio-authored geometry, export
the content JSON and set `ArenaContentPath` to that file before starting the server;
invalid schema, identity, or geometry refuses startup. The root build writes the selected static SVG player to
`artifacts/static-player`, optional Studio to `artifacts/static-studio`, and the required
independently deployable ASP.NET Core authority to `artifacts/authority-server`. Deploy the
static artifact and authority together; a static host alone is not a complete multiplayer game.

After the root build prepares `artifacts/releases/<version>`, exercise the production-shaped local edge:

```bash
SVG_RELEASE_VERSION=<version> bash deploy/run-local.sh
```

This prefers `podman compose`, falls back to `docker compose`, builds the non-root ASP.NET authority image,
and places the digest-pinned Caddy image in front of it. Set `CONTAINER_ENGINE=podman` or `docker` to require
a particular compatible engine.
Caddy serves the hashed Player, optional Studio and selected content while proxying same-origin `/api` and
`/hub` traffic—including WebSocket upgrades—to the authority. Set `KEEP_EDGE_RUNNING=true` to retain the
local stack after verification. The public host uses the same base composition with
`deploy/compose.production.yaml`. `deploy/deploy-production.sh` installs an immutable activation over strict
host-key-checked SSH, verifies trusted TLS and a forced two-client V3 WebSocket reconnect, restarts the boot-enabled
systemd service, and repeats the verification. `deploy/rollback-production.sh` reactivates retained VPS bytes by
content-addressed deployment id and expected manifest digest, without requiring an old local build.
See `docs/runbooks/build-evidence-and-deploy.md` for the exact VPS bootstrap, DNS and deployment commands.

`bash ./build.sh` runs the product qualification build: locked restore/build/test the `.NET` solution
(`Domain`, `Protocol`, `Server`, and their `.Tests` projects), the cross-runtime
V1/V2/V3 codec and replay proof, bounded authored-rule Quint simulation, the Fable/Vite client production build, and the
selected SVG player (plus Studio when present), authority publish, the Playwright
`Browser.Tests` two-context scenario, and the renderer conformance kit on SVG, Pixi and Babylon. It writes TRX/JUnit evidence to
`artifacts/test-results/`; import those observed reports with
`fsgg-sdd evidence --from-test-report`. SDD remains the single lifecycle owner.
Set `QUINT_BIN` to the executable for Quint 0.32.0 before running the build. The
checked workflow downloads `quint-linux-amd64`, verifies SHA-256
`939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f`, and exports
that path only for the build; use the same recipe locally rather than an unpinned
global or npm executable.

## Lanes

`Domain`, `Domain.Tests`, `Protocol`, `Protocol.Tests` (plus its
`Protocol.Tests/cross-runtime/` cross-runtime codec proof), `Server`, `Server.Tests`,
`Client`, and `Browser.Tests`.

## Package locking

This workspace restores in **locked mode** (`RestoreLockedMode` in
`Directory.Build.props`), so every `packages.lock.json` beside a project is
enforced: a package whose content hash differs from the committed one fails the
restore rather than being silently substituted.

Locked mode is only meaningful if the lock can be regenerated, so here is the path.
After changing any `PackageReference`, regenerate and commit the affected locks:

```bash
dotnet restore FableGameWorkspace.slnx --force-evaluate
dotnet restore Client/Client.fsproj --force-evaluate
dotnet restore SvgFoundation/SvgFoundation.fsproj --force-evaluate
dotnet restore SvgFoundation/Studio/Studio.fsproj --force-evaluate
dotnet restore Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj --force-evaluate
dotnet restore Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj --force-evaluate
```

`Client`, the selected SVG projects, and the two `cross-runtime` probes need their
own lines because they are not members of the solution. Never hand-edit a lock file; a hash typed by a human
is a hash no restore can reproduce.

Two settings keep those hashes reproducible, and both are load-bearing (see
`FS.GG.Templates#380`):

- **`NuGet.config` pins the source.** Its `<clear />` drops every source inherited
  from the machine, so a package is never served by whatever local feed the host
  happens to configure. To use a private or mirrored feed, add it there and then
  regenerate the locks with the commands above.
- **`DisableImplicitLibraryPacksFolder` in `Directory.Build.props`** stops the F#
  SDK appending its own bundled `library-packs` folder to the restore sources. That
  folder ships an `FSharp.Core` archive with the same version as nuget.org's but
  different bytes, so leaving it enabled lets one restore record one content hash
  and the next restore reject it with
  `NU1403: Package content hash validation failed`.
- **`RestorePackagesPath` in `Directory.Build.props`** gives this workspace its own
  `.nuget/packages` folder instead of the machine-wide one. Source pinning alone is
  not enough: NuGet's shared package folder is keyed by id and version only, so
  whichever build reached it first decides which of the two `FSharp.Core` archives
  lives there, and a later restore validates the committed hash against *that*
  entry. A private folder is what makes the committed hash enforceable on any
  machine rather than only on machines that happen to agree.

  Two consequences worth knowing. Packages are not shared with your other
  checkouts, so a cold build downloads its own copies. And `.nuget/` belongs in
  your ignore file — this workspace ships without one, in common with `bin/`,
  `obj/`, `artifacts/` and `node_modules/`.

`build.sh` refuses to restore at all if the lock files are missing, because a
locked-mode restore with no lock on disk does not fail — it quietly writes a new
lock from whatever the machine resolves, which defeats the entire mechanism.

## Explicit managed portal example

`--portalExample true` includes a separately invoked .NET 10 `PortalExample` project,
independently of bundle/lifecycle. Omission or false keeps it absent. The legacy
`--svgFoundation` selector cannot be combined with this option. See
[PortalExample/README.md](PortalExample/README.md) for exact public pins and the
explicit `dotnet run --project PortalExample/Consumer.fsproj -- --presentation` command.
The ordinary solution, server and browser player do not consume this project.
Candidate source/generation proof, public template installation, provider forwarding
and preserving retained adoption/removal are separate acceptance boundaries.
