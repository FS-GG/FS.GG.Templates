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
    let enabled = configuration.GetValue("TickBroadcasterEnabled", true)

    override _.ExecuteAsync(stoppingToken: CancellationToken) : Task =
        task {
            if enabled then
                while not stoppingToken.IsCancellationRequested do
                    do! Task.Delay(TimeSpan.FromMilliseconds intervalMilliseconds, stoppingToken)
                    let snapshot = RoomAuthority.advanceTick ()
                    let tick, players = snapshot.Tick, snapshot.Players
                    let v1Players: RealtimeV1.PlayerSnapshot list = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row })
                    let v1: RealtimeV1.Snapshot = { Version = 1; Tick = tick; Players = v1Players }
                    do! hub.Clients.Group($"{RoomAuthority.RoomId}-v1").SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.SnapshotMessage v1))
                    let v2Players: RealtimeV2.PlayerSnapshot list = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row })
                    let v2: RealtimeV2.Snapshot =
                        { Version = 2; Tick = tick; Round = snapshot.Round; Players = v2Players
                          Health = snapshot.Health; Score = snapshot.Score; Collected = snapshot.Collected; Outcome = snapshot.Outcome
                          ContentId = snapshot.ContentId
                          ContentSchema = snapshot.ContentSchema
                          CollectibleX = snapshot.Content.CollectibleX; CollectibleY = snapshot.Content.CollectibleY
                          HazardX = snapshot.Content.Hazard.X; HazardY = snapshot.Content.Hazard.Y; HazardWidth = snapshot.Content.Hazard.Width; HazardHeight = snapshot.Content.Hazard.Height
                          GoalX = snapshot.Content.Goal.X; GoalY = snapshot.Content.Goal.Y; GoalWidth = snapshot.Content.Goal.Width; GoalHeight = snapshot.Content.Goal.Height
                          ThinWallX = snapshot.Content.ThinWall.X; ThinWallY = snapshot.Content.ThinWall.Y; ThinWallWidth = snapshot.Content.ThinWall.Width; ThinWallHeight = snapshot.Content.ThinWall.Height
                          HazardCol = snapshot.HazardCol
                          HazardRow = snapshot.HazardRow }
                    do! hub.Clients.Group($"{RoomAuthority.RoomId}-v2").SendAsync("Message", RealtimeV2.encodeMessage (RealtimeV2.SnapshotMessage v2))
                    let content = snapshot.Content
                    let v3Players: RealtimeV3.PlayerSnapshot list = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row })
                    let v3: RealtimeV3.Snapshot =
                        { Version = 3; Tick = tick; Round = snapshot.Round; Players = v3Players
                          Health = snapshot.Health; Score = snapshot.Score; Collected = snapshot.Collected; Outcome = snapshot.Outcome
                          ContentId = snapshot.ContentId; ContentSchema = snapshot.ContentSchema
                          BoundaryX = content.Boundary.X; BoundaryY = content.Boundary.Y; BoundaryWidth = content.Boundary.Width; BoundaryHeight = content.Boundary.Height
                          SpawnCol = content.Spawn.Col; SpawnRow = content.Spawn.Row
                          CollectibleX = content.CollectibleX; CollectibleY = content.CollectibleY
                          HazardX = content.Hazard.X; HazardY = content.Hazard.Y; HazardWidth = content.Hazard.Width; HazardHeight = content.Hazard.Height
                          GoalX = content.Goal.X; GoalY = content.Goal.Y; GoalWidth = content.Goal.Width; GoalHeight = content.Goal.Height
                          ThinWallX = content.ThinWall.X; ThinWallY = content.ThinWall.Y; ThinWallWidth = content.ThinWall.Width; ThinWallHeight = content.ThinWall.Height
                          HazardCol = snapshot.HazardCol; HazardRow = snapshot.HazardRow }
                    do! hub.Clients.Group($"{RoomAuthority.RoomId}-v3").SendAsync("Message", RealtimeV3.encodeMessage (RealtimeV3.SnapshotMessage v3))
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

    let bootstrap (request: BootstrapV1.Request) : Result<BootstrapV1.Response, RoomAuthority.AdmissionError> =
        let playerId = Guid.NewGuid().ToString "N"
        RoomAuthority.createSession playerId
        |> Result.map (fun (capability, spawn) ->
            { Version = 1
              PlayerId = playerId
              SessionCapability = capability
              RoomId = RoomAuthority.RoomId
              SpawnCol = spawn.Col
              SpawnRow = spawn.Row
              ArenaWidth = RoomAuthority.ArenaWidth
              ArenaHeight = RoomAuthority.ArenaHeight })

    [<EntryPoint>]
    let main args =
        let builder = WebApplication.CreateBuilder args
        match builder.Configuration["ArenaContentPath"] with
        | null | "" -> ()
        | path ->
            match ArenaContentFile.load path |> Result.bind RoomAuthority.configureDefinition with
            | Ok () -> ()
            | Error issue -> invalidOp $"configured arena content refused before server start: {issue}"
        builder.Services.AddSignalR() |> ignore
        builder.Services.AddHostedService<TickBroadcaster>() |> ignore
        let app = builder.Build()

        // The edge/container health probe deliberately exercises the real ASP.NET
        // pipeline without allocating a player session or disclosing authority state.
        app.MapGet(
            "/healthz",
            Func<IResult>(fun () -> Results.Json {| status = "ok"; roomId = RoomAuthority.RoomId |})
        )
        |> ignore

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
                        match bootstrap parsed with
                        | Ok response -> return Results.Text(BootstrapV1.encodeResponse response, "application/json")
                        | Error error ->
                            return Results.Json(
                                {| error = RoomAuthority.admissionError error |},
                                statusCode = StatusCodes.Status429TooManyRequests)
                })
        )
        |> ignore

        app.MapHub<GameHub>("/hub/game") |> ignore
#if SVG_NETWORK_CANDIDATE
        app.MapGet(
            "/api/review",
            Func<IResult>(fun () ->
                let accepted, replay, eventCount = RoomAuthority.review ()
                Results.Json {| accepted = accepted; replay = replay; eventCount = eventCount |})
        )
        |> ignore
#endif
        app.UseDefaultFiles() |> ignore
        app.UseStaticFiles() |> ignore
        app.MapFallbackToFile("index.html") |> ignore

        app.Run()
        0
