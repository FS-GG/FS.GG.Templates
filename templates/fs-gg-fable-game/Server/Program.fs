namespace FableGameWorkspaceNamespace.Server

open System
open System.Threading
open System.Threading.Tasks
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Http
open Microsoft.AspNetCore.SignalR
open Microsoft.Extensions.Configuration
open Microsoft.Extensions.DependencyInjection
open Microsoft.Extensions.Hosting
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime

/// Periodically advances and broadcasts the authoritative tick, independent of
/// per-input pushes -- so a room with no input still keeps every connected client's
/// `Tick` moving, and a client can detect a stalled connection by its absence (the
/// server is the timing authority per #348's acceptance, not just the position
/// authority).
type TickBroadcaster(hub: IHubContext<GameHub>, configuration: IConfiguration) =
    inherit BackgroundService()

    // Overridable so `Server.Tests` (an in-process `WebApplicationFactory`, running this
    // same hosted service for real, not a fake) can push the interval out to
    // effectively "never" -- a 200ms real-world default would otherwise race with tests
    // that assert on the very next inbound `Message` after a specific action.
    let intervalMilliseconds = configuration.GetValue("TickIntervalMilliseconds", 200.0)

    override _.ExecuteAsync(stoppingToken: CancellationToken) : Task =
        task {
            while not stoppingToken.IsCancellationRequested do
                do! Task.Delay(TimeSpan.FromMilliseconds intervalMilliseconds, stoppingToken)
                let tick, players = RoomAuthority.advanceTick ()
                let snapshot: RealtimeV1.Snapshot =
                    { Version = 1; Tick = tick; Players = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row }) }
                do! hub.Clients.Group(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.SnapshotMessage snapshot))
        }

/// Marker type for `WebApplicationFactory<Program>` in Server.Tests. An F# `module`
/// (below) is a value/function container, not a usable type expression -- `typeof<...>`
/// and generic type arguments cannot name a bare module cross-assembly, only a real
/// type. Giving the entry-point-holding module the same name as this empty marker type
/// is the standard F#-on-ASP.NET-Core pattern: the compiler auto-disambiguates the
/// module internally (`ProgramModule`) while both `Program` (the type, for
/// `WebApplicationFactory<Program>`) and `Program.bootstrap` (the module member) resolve
/// as expected.
type Program() =
    class end

module Program =

    let bootstrap (request: BootstrapV1.Request) : BootstrapV1.Response =
        let playerId = Guid.NewGuid().ToString "N"
        let capability, spawn = RoomAuthority.createSession playerId
        { Version = 1
          PlayerId = playerId
          SessionCapability = capability
          RoomId = RoomAuthority.RoomId
          SpawnCol = spawn.Col
          SpawnRow = spawn.Row
          ArenaWidth = RoomAuthority.ArenaWidth
          ArenaHeight = RoomAuthority.ArenaHeight }

    [<EntryPoint>]
    let main args =
        let builder = WebApplication.CreateBuilder args
        builder.Services.AddSignalR() |> ignore
        builder.Services.AddHostedService<TickBroadcaster>() |> ignore
        let app = builder.Build()

        // The plain-HTTP typed request/response leg (ADR-0073): an ordinary minimal-API
        // handler, an explicit versioned DTO pair, and named codec functions on both
        // sides -- never Decode.Auto, never a generated RPC proxy.
        app.MapPost(
            "/api/bootstrap",
            Func<HttpRequest, Task<IResult>>(fun request ->
                task {
                    use reader = new IO.StreamReader(request.Body)
                    let! body = reader.ReadToEndAsync()
                    match BootstrapV1.requestFromJson body with
                    | Error message -> return Results.BadRequest {| error = message |}
                    | Ok parsed when parsed.Version <> 1 -> return Results.BadRequest {| error = "unsupported bootstrap version" |}
                    | Ok parsed ->
                        let response = bootstrap parsed
                        return Results.Text(BootstrapV1.encodeResponse response, "application/json")
                })
        )
        |> ignore

        app.MapHub<GameHub>("/hub/game") |> ignore
        app.UseDefaultFiles() |> ignore
        app.UseStaticFiles() |> ignore
        app.MapFallbackToFile("index.html") |> ignore

        app.Run()
        0
