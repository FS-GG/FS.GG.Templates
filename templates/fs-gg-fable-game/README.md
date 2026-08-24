# FableGameWorkspace

A minimal, server-authoritative multiplayer game workspace: one F# ASP.NET Core
server and one Fable/Elmish browser client, sharing a product-owned `Domain` and an
explicit, versioned wire protocol.

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

`Domain/Room.fs` is a pure, server-only authoritative arena: players occupy cells
on a fixed grid, and `Pathfinding.astar` -- the `LockstepExact` surface of the
published `FS.GG.Game.Core` Fable compatibility profile
(`fs-gg-game-core-fable-lockstep-v1`) -- resolves movement. Both `Domain` (server)
and `Client/Movement.fs` (browser, local path preview only) call the *same*
published package function; the server's `Server/RoomAuthority.fs` is the only
place a move is actually committed. `Server/RoomAuthority.fs` also enforces the
stale-input guard (a non-increasing input sequence is dropped) and the
disconnect/reconnect contract: a reconnecting client always gets a bounded, full
authoritative resync, never a delta log.

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
- Admission is bounded to the arena's 240 cells, with no occupied-cell fallback. A
  bootstrap that would exceed that bound returns HTTP 429. Unbound and disconnected
  capabilities expire after two minutes; the tick loop cleans them up and releases
  their reserved authority.
- `stop`/disconnect removes a connection's group membership and room presence. The
  capability remains available for its bounded reconnect window, keeping the starter
  zero-config while making the resource boundary visible and testable.

## Running it

Two terminals for development: `dotnet run --project Server/Server.fsproj` and
`npm run dev --prefix Client`; Vite proxies `/api` and the `/hub` WebSocket upgrade
to `http://localhost:5000`. For production, `Client/dist` is published into
`Server`'s `wwwroot`; run `dotnet artifacts/publish/Server.dll` from the publish
directory (not the source checkout).

`./build.sh` runs the whole lifecycle: restore/build/test the `.NET` solution
(`Domain`, `Protocol`, `Server`, and their `.Tests` projects), the cross-runtime
codec proof, the Fable/Vite client production build, the server publish, and the
Playwright `Browser.Tests` two-context scenario. It writes TRX/JUnit evidence to
`artifacts/test-results/`; import those observed reports with
`fsgg-sdd evidence --from-test-report`. SDD remains the single lifecycle owner.

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
dotnet restore Protocol.Tests/cross-runtime/CodecProbe.Net/CodecProbe.Net.fsproj --force-evaluate
dotnet restore Protocol.Tests/cross-runtime/CodecProbe.Fable/CodecProbe.Fable.fsproj --force-evaluate
```

`Client` and the two `cross-runtime` probes need their own lines because they are
not members of the solution. Never hand-edit a lock file; a hash typed by a human
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
