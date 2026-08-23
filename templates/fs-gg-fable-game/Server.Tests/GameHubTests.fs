module FableGameWorkspaceNamespace.Server.Tests.GameHubTests

open System
open System.Threading
open System.Threading.Tasks
open Microsoft.AspNetCore.Http.Connections
open Microsoft.AspNetCore.Http.Connections.Client
open Microsoft.AspNetCore.Mvc.Testing
open Microsoft.Extensions.Configuration
open Microsoft.AspNetCore.SignalR
open Microsoft.AspNetCore.SignalR.Client
open Xunit
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime
open FableGameWorkspaceNamespace.Server

/// Production-route tests for the starter's security and tick-frontier contracts:
/// no query identity, one validated hello, bounded resync, and inputs changing state
/// only when the server's next tick commits the sorted frontier.
type GameHubTests() =
    do RoomAuthority.resetForTests ()
    let factory =
        (new WebApplicationFactory<Program>())
            .WithWebHostBuilder(fun builder ->
                builder.ConfigureAppConfiguration(fun _ config ->
                    config.AddInMemoryCollection(dict [ "TickIntervalMilliseconds", "25" ]) |> ignore)
                |> ignore)

    let buildConnection () : HubConnection =
        HubConnectionBuilder()
            .WithUrl(
                Uri(factory.Server.BaseAddress, "/hub/game"),
                fun (opts: HttpConnectionOptions) ->
                    opts.HttpMessageHandlerFactory <- fun _ -> factory.Server.CreateHandler()
                    opts.Transports <- HttpTransportType.LongPolling)
            .Build()

    let nextMatching (connection: HubConnection) (predicate: RealtimeV1.Message -> bool) : Task<RealtimeV1.Message> =
        let tcs = TaskCompletionSource<RealtimeV1.Message>()
        let subscription =
            connection.On<string>("Message", fun json ->
                match RealtimeV1.messageFromJson json with
                | Ok message when predicate message -> tcs.TrySetResult message |> ignore
                | Ok _ -> ()
                | Error error -> tcs.TrySetException(Exception error) |> ignore)
        task {
            use _ = subscription
            use cts = new CancellationTokenSource(5000)
            use _ = cts.Token.Register(fun () -> tcs.TrySetCanceled() |> ignore)
            return! tcs.Task
        }

    let bootstrap name = Program.bootstrap { Version = 1; PlayerName = name }

    let hello (connection: HubConnection) capability =
        let json = RealtimeV1.encodeMessage (RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = capability })
        connection.InvokeAsync("SendMessage", json)

    let startBound name =
        task {
            let response = bootstrap name
            let connection = buildConnection ()
            let waiting = nextMatching connection (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! connection.StartAsync()
            do! hello connection response.SessionCapability
            let! resync = waiting
            return response, connection, resync
        }

    [<Fact>]
    member _.``the hub URL contains no player identity and a validated hello returns a full resync``() =
        task {
            let response = bootstrap "p-hello"
            use connection = buildConnection ()
            let waiting = nextMatching connection (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! connection.StartAsync()
            do! hello connection response.SessionCapability
            let! message = waiting
            match message with
            | RealtimeV1.ResyncSnapshotMessage snapshot -> Assert.Contains(snapshot.Players, fun p -> p.PlayerId = response.PlayerId)
            | other -> Assert.Fail $"expected resync, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``unknown capability and mismatched protocol version are rejected before authority is granted``() =
        task {
            use connection = buildConnection ()
            do! connection.StartAsync()
            let unknown = RealtimeV1.encodeMessage (RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = "not-issued" })
            let! unknownError = Assert.ThrowsAsync<HubException>(fun () -> connection.InvokeAsync("SendMessage", unknown))
            Assert.Contains("unknown", unknownError.Message)
            let badVersion = RealtimeV1.encodeMessage (RealtimeV1.SessionHelloMessage { Version = 2; SessionCapability = "not-issued" })
            let! versionError = Assert.ThrowsAsync<HubException>(fun () -> connection.InvokeAsync("SendMessage", badVersion))
            Assert.Contains("unsupported realtime version", versionError.Message)
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``input is not applied on hub arrival and commits at the next tick frontier``() =
        task {
            let! response, connection, _ = startBound "p-frontier"
            use connection = connection
            let beforeTick, beforePlayers = RoomAuthority.snapshot ()
            let before = beforePlayers |> List.find (fun (id, _, _) -> id = response.PlayerId)
            let input = RealtimeV1.encodeMessage (RealtimeV1.InputMessage { Version = 1; Sequence = 1; TargetCol = 1; TargetRow = 0 })
            do! connection.InvokeAsync("SendMessage", input)
            let immediateTick, immediatePlayers = RoomAuthority.snapshot ()
            Assert.Equal(beforeTick, immediateTick)
            Assert.Equal(before, immediatePlayers |> List.find (fun (id, _, _) -> id = response.PlayerId))
            let! committed =
                nextMatching connection (function
                    | RealtimeV1.SnapshotMessage snapshot -> snapshot.Tick > beforeTick
                    | _ -> false)
            match committed with
            | RealtimeV1.SnapshotMessage snapshot ->
                let player = snapshot.Players |> List.find (fun p -> p.PlayerId = response.PlayerId)
                Assert.Equal((1, 0), (player.Col, player.Row))
            | other -> Assert.Fail $"expected tick snapshot, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``a duplicate sequence cannot replace an already admitted frontier intent``() =
        task {
            let! response, connection, _ = startBound "p-stale"
            use connection = connection
            let first = RealtimeV1.encodeMessage (RealtimeV1.InputMessage { Version = 1; Sequence = 1; TargetCol = 1; TargetRow = 0 })
            let duplicate = RealtimeV1.encodeMessage (RealtimeV1.InputMessage { Version = 1; Sequence = 1; TargetCol = 0; TargetRow = 10 })
            do! connection.InvokeAsync("SendMessage", first)
            do! connection.InvokeAsync("SendMessage", duplicate)
            let! committed =
                nextMatching connection (function
                    | RealtimeV1.SnapshotMessage snapshot -> snapshot.Players |> List.exists (fun p -> p.PlayerId = response.PlayerId && p.Col = 1 && p.Row = 0)
                    | _ -> false)
            match committed with
            | RealtimeV1.SnapshotMessage _ -> ()
            | other -> Assert.Fail $"expected committed tick snapshot, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``disconnect then rehello with the same capability gets a bounded full resync``() =
        task {
            let! response, first, _ = startBound "p-reconnect"
            use first = first
            do! first.StopAsync()
            use second = buildConnection ()
            let waiting = nextMatching second (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! second.StartAsync()
            do! hello second response.SessionCapability
            let! message = waiting
            match message with
            | RealtimeV1.ResyncSnapshotMessage snapshot -> Assert.Contains(snapshot.Players, fun p -> p.PlayerId = response.PlayerId)
            | other -> Assert.Fail $"expected resync, got {other}"
            do! second.StopAsync()
        }

    interface IDisposable with
        member _.Dispose() = factory.Dispose()
