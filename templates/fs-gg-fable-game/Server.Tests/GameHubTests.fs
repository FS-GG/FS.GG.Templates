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
    let createFactory settings =
        (new WebApplicationFactory<Program>())
            .WithWebHostBuilder(fun builder ->
                builder.ConfigureAppConfiguration(fun _ config ->
                    config.AddInMemoryCollection(dict settings) |> ignore)
                |> ignore)
    let factory = createFactory [ "TickIntervalMilliseconds", "25" ]

    let buildConnectionFor (host: WebApplicationFactory<Program>) : HubConnection =
        HubConnectionBuilder()
            .WithUrl(
                Uri(host.Server.BaseAddress, "/hub/game"),
                fun (opts: HttpConnectionOptions) ->
                    opts.HttpMessageHandlerFactory <- fun _ -> host.Server.CreateHandler()
                    opts.Transports <- HttpTransportType.LongPolling)
            .Build()

    let buildConnection () : HubConnection = buildConnectionFor factory

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

    let nextMatchingV3 (connection: HubConnection) (predicate: RealtimeV3.Message -> bool) : Task<RealtimeV3.Message> =
        let tcs = TaskCompletionSource<RealtimeV3.Message>()
        let subscription =
            connection.On<string>("Message", fun json ->
                match RealtimeV3.messageFromJson json with
                | Ok message when predicate message -> tcs.TrySetResult message |> ignore
                | Ok _ -> ()
                | Error error -> tcs.TrySetException(Exception error) |> ignore)
        task {
            use _ = subscription
            use cts = new CancellationTokenSource(5000)
            use _ = cts.Token.Register(fun () -> tcs.TrySetCanceled() |> ignore)
            return! tcs.Task
        }

    let nextRaw (connection: HubConnection) : Task<string> =
        let tcs = TaskCompletionSource<string>()
        let subscription = connection.On<string>("Message", fun json -> tcs.TrySetResult json |> ignore)
        task {
            use _ = subscription
            use cts = new CancellationTokenSource(5000)
            use _ = cts.Token.Register(fun () -> tcs.TrySetCanceled() |> ignore)
            return! tcs.Task
        }

    let bootstrap name =
        match Program.bootstrap { Version = 1; PlayerName = name } with
        | Ok response -> response
        | Error error -> failwith $"bootstrap unexpectedly rejected: {RoomAuthority.admissionError error}"

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
    member _.``undisclosed bootstrap input never enters the authoritative V3 wire payload``() =
        task {
            let sentinel = "UNDISCLOSED-AUTHORITY-SENTINEL-014"
            let response = bootstrap sentinel
            Assert.DoesNotContain(sentinel, BootstrapV1.encodeResponse response)
            use connection = buildConnection ()
            let waiting = nextRaw connection
            do! connection.StartAsync()
            let hello = RealtimeV3.encodeMessage (RealtimeV3.SessionHelloMessage { Version = 3; SessionCapability = response.SessionCapability })
            do! connection.InvokeAsync("SendMessage", hello)
            let! wire = waiting
            Assert.DoesNotContain(sentinel, wire)
            Assert.DoesNotContain(response.SessionCapability, wire)
            match RealtimeV3.messageFromJson wire with
            | Ok(RealtimeV3.ResyncSnapshotMessage snapshot) -> Assert.Equal(3, snapshot.Version)
            | other -> Assert.Fail $"expected V3 resync, got {other}"
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
            let badVersion = RealtimeV1.encodeMessage (RealtimeV1.SessionHelloMessage { Version = 4; SessionCapability = "not-issued" })
            let! versionError = Assert.ThrowsAsync<HubException>(fun () -> connection.InvokeAsync("SendMessage", badVersion))
            Assert.Contains("unsupported realtime version", versionError.Message)
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``a rejected second hello does not consume or strand its capability``() =
        task {
            let firstResponse = bootstrap "p-first-binding"
            let secondResponse = bootstrap "p-second-binding"
            use first = buildConnection ()
            let firstWaiting = nextMatching first (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! first.StartAsync()
            do! hello first firstResponse.SessionCapability
            let! _ = firstWaiting

            let! rejected =
                Assert.ThrowsAsync<HubException>(fun () -> hello first secondResponse.SessionCapability)
            Assert.Contains("only one session", rejected.Message)
            do! first.StopAsync()

            use second = buildConnection ()
            let secondWaiting = nextMatching second (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! second.StartAsync()
            do! hello second secondResponse.SessionCapability
            let! rebound = secondWaiting
            match rebound with
            | RealtimeV1.ResyncSnapshotMessage snapshot ->
                Assert.Contains(snapshot.Players, fun player -> player.PlayerId = secondResponse.PlayerId)
            | other -> Assert.Fail $"expected second capability to remain usable, got {other}"
            do! second.StopAsync()
        }

    [<Fact>]
    member _.``resync rejects an inconsistent future cursor and accepts a reached frontier``() =
        task {
            let! _, connection, initial = startBound "p-resync-cursor"
            use connection = connection
            let initialTick =
                match initial with
                | RealtimeV1.ResyncSnapshotMessage snapshot -> snapshot.Tick
                | other -> failwith $"expected initial resync, got {other}"

            let future =
                RealtimeV1.encodeMessage (
                    RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = Int32.MaxValue }
                )
            let! rejected = Assert.ThrowsAsync<HubException>(fun () -> connection.InvokeAsync("SendMessage", future))
            Assert.Contains("inconsistent resync cursor", rejected.Message)

            let waiting = nextMatching connection (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            let reached =
                RealtimeV1.encodeMessage (
                    RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = initialTick }
                )
            do! connection.InvokeAsync("SendMessage", reached)
            let! response = waiting
            match response with
            | RealtimeV1.ResyncSnapshotMessage snapshot -> Assert.True(snapshot.Tick >= initialTick)
            | other -> Assert.Fail $"expected bounded resync snapshot, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``input is not applied on hub arrival and commits at the next tick frontier``() =
        task {
            // Pause only the hosted wall-clock driver for this boundary test. The test owns the
            // frontier explicitly, so no scheduler tick can race the before/immediate snapshots.
            use controlledFactory = createFactory [ "TickBroadcasterEnabled", "false" ]
            let response = bootstrap "p-frontier"
            let connection = buildConnectionFor controlledFactory
            use connection = connection
            let waiting = nextMatching connection (function | RealtimeV1.ResyncSnapshotMessage _ -> true | _ -> false)
            do! connection.StartAsync()
            do! hello connection response.SessionCapability
            let! _ = waiting
            let beforeTick, beforePlayers = RoomAuthority.snapshot ()
            let before = beforePlayers |> List.find (fun (id, _, _) -> id = response.PlayerId)
            let input = RealtimeV1.encodeMessage (RealtimeV1.InputMessage { Version = 1; Sequence = 1; TargetCol = 1; TargetRow = 0 })
            do! connection.InvokeAsync("SendMessage", input)
            let immediateTick, immediatePlayers = RoomAuthority.snapshot ()
            Assert.Equal(beforeTick, immediateTick)
            Assert.Equal(before, immediatePlayers |> List.find (fun (id, _, _) -> id = response.PlayerId))
            let committed = RoomAuthority.advanceTick ()
            Assert.Equal(beforeTick + 1, committed.Tick)
            let _, col, row = committed.Players |> List.find (fun (id, _, _) -> id = response.PlayerId)
            Assert.Equal((1, 0), (col, row))
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
            let! refused = Assert.ThrowsAsync<HubException>(fun () -> connection.InvokeAsync("SendMessage", duplicate))
#if SVG_NETWORK_CANDIDATE
            Assert.Contains("DuplicateInputSequence", refused.Message)
#else
            Assert.Contains("duplicate or stale", refused.Message)
#endif
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

#if SVG_NETWORK_CANDIDATE
    [<Fact>]
    member _.``authoritative arena owns collection win refusal and restart``() =
        let response = bootstrap "arena-rules"
        let submit sequence action col row =
            RoomAuthority.submitInput response.PlayerId response.SessionCapability sequence action col row
            |> Result.defaultWith failwith
            |> ignore
            RoomAuthority.advanceTick () |> ignore
        for sequence in 1 .. 7 do submit sequence "move" 5 2
        submit 8 "interact" 5 2
        Assert.Equal((3, 100, true, "playing"), RoomAuthority.gameStatus ())
        Assert.True(RoomAuthority.submitInput response.PlayerId "forged" 99 "interact" 5 2 |> Result.isError)
        Assert.True(RoomAuthority.submitInput response.PlayerId response.SessionCapability 8 "interact" 5 2 |> Result.isError)
        Assert.Equal((3, 100, true, "playing"), RoomAuthority.gameStatus ())
        for sequence in 9 .. 22 do submit sequence "move" 16 5
        submit 23 "interact" 16 5
        Assert.Equal((3, 100, true, "won"), RoomAuthority.gameStatus ())
        submit 24 "restart" 16 5
        Assert.Equal((3, 0, false, "playing"), RoomAuthority.gameStatus ())
        Assert.True(RoomAuthority.verifyReplay () |> Result.defaultWith failwith)

    [<Fact>]
    member _.``accepted network input is recorded by the replay authority``() =
        let response = bootstrap "p-review"
        let targetRow = response.SpawnRow + 1
        let accepted =
            RoomAuthority.submitInput response.PlayerId response.SessionCapability 1 "move" response.SpawnCol targetRow
            |> Result.defaultWith failwith
        Assert.Equal(0UL, accepted)
        RoomAuthority.advanceTick () |> ignore
        let acceptedText, replayText, eventCount = RoomAuthority.review ()
        Assert.Contains(response.PlayerId, acceptedText)
        Assert.Contains("move", replayText)
        Assert.True(eventCount >= 3)

    [<Fact>]
    member _.``configured V2 content bytes drive the authority geometry``() =
        let json = """{"schemaVersion":2,"contentId":"continuous-arena/studio-edit","collectibleX":33,"collectibleY":44,"hazardX":55,"hazardY":66,"hazardWidth":11,"hazardHeight":10,"goalX":77,"goalY":88,"goalWidth":11,"goalHeight":10,"thinWallX":99,"thinWallY":1,"thinWallWidth":2,"thinWallHeight":48}"""
        let content = ArenaContentFile.decode json |> Result.defaultWith failwith
        RoomAuthority.configureDefinition content |> Result.defaultWith failwith
        let snapshot = RoomAuthority.completeSnapshot ()
        Assert.Equal("continuous-arena/studio-edit", snapshot.ContentId)
        Assert.Equal((33.0, 44.0), (snapshot.Content.CollectibleX, snapshot.Content.CollectibleY))
        Assert.Equal((55.0, 66.0), (snapshot.Content.Hazard.X, snapshot.Content.Hazard.Y))
        RoomAuthority.resetForTests ()

    [<Fact>]
    member _.``configured V3 content preserves explicit boundary and authored spawn``() =
        let json = """{"schemaVersion":3,"contentId":"continuous-arena/studio-v3","boundaryX":0,"boundaryY":0,"boundaryWidth":220,"boundaryHeight":120,"spawnCol":2,"spawnRow":1,"collectibleX":33,"collectibleY":44,"hazardX":55,"hazardY":66,"hazardWidth":11,"hazardHeight":10,"goalX":77,"goalY":88,"goalWidth":11,"goalHeight":10,"thinWallX":99,"thinWallY":1,"thinWallWidth":2,"thinWallHeight":48}"""
        let content = ArenaContentFile.decode json |> Result.defaultWith failwith
        Assert.Equal(3, content.SchemaVersion)
        Assert.Equal((2, 1), (content.Spawn.Col, content.Spawn.Row))
        Assert.Equal((220.0, 120.0), (content.Boundary.Width, content.Boundary.Height))
        RoomAuthority.configureDefinition content |> Result.defaultWith failwith
        let response = bootstrap "authored-spawn"
        Assert.Equal((2, 1), (response.SpawnCol, response.SpawnRow))
        Assert.Equal(3, RoomAuthority.completeSnapshot().ContentSchema)
        RoomAuthority.resetForTests ()

    [<Fact>]
    member _.``V3 hello and reconnect preserve authored immutable content and spawn``() =
        task {
            let json = """{"schemaVersion":3,"contentId":"continuous-arena/reconnect-v3","boundaryX":0,"boundaryY":0,"boundaryWidth":220,"boundaryHeight":120,"spawnCol":2,"spawnRow":1,"collectibleX":33,"collectibleY":44,"hazardX":55,"hazardY":66,"hazardWidth":11,"hazardHeight":10,"goalX":77,"goalY":88,"goalWidth":11,"goalHeight":10,"thinWallX":99,"thinWallY":1,"thinWallWidth":2,"thinWallHeight":48}"""
            RoomAuthority.configureDefinition (ArenaContentFile.decode json |> Result.defaultWith failwith)
            |> Result.defaultWith failwith
            let response = bootstrap "v3-reconnect"
            let connectAndRead () =
                task {
                    let connection = buildConnection ()
                    let waiting = nextMatchingV3 connection (function RealtimeV3.ResyncSnapshotMessage _ -> true | _ -> false)
                    do! connection.StartAsync()
                    let hello = RealtimeV3.encodeMessage (RealtimeV3.SessionHelloMessage { Version = 3; SessionCapability = response.SessionCapability })
                    do! connection.InvokeAsync("SendMessage", hello)
                    let! message = waiting
                    return connection, message
                }
            let! first, firstMessage = connectAndRead ()
            use first = first
            let assertSnapshot = function
                | RealtimeV3.ResyncSnapshotMessage snapshot ->
                    Assert.Equal((0.0, 0.0, 220.0, 120.0), (snapshot.BoundaryX, snapshot.BoundaryY, snapshot.BoundaryWidth, snapshot.BoundaryHeight))
                    Assert.Equal((2, 1), (snapshot.SpawnCol, snapshot.SpawnRow))
                    Assert.Equal((33.0, 44.0), (snapshot.CollectibleX, snapshot.CollectibleY))
                    Assert.Contains(snapshot.Players, fun player -> player.PlayerId = response.PlayerId && player.Col = 2 && player.Row = 1)
                | other -> Assert.Fail $"expected V3 resync, got {other}"
            assertSnapshot firstMessage
            do! first.StopAsync()
            let! second, secondMessage = connectAndRead ()
            use second = second
            assertSnapshot secondMessage
            do! second.StopAsync()
            RoomAuthority.resetForTests ()
        }

    [<Fact>]
    member _.``V2 client refuses schema3 before consuming capability while V3 can bind``() =
        task {
            let json = """{"schemaVersion":3,"contentId":"continuous-arena/v3-only","boundaryX":0,"boundaryY":0,"boundaryWidth":220,"boundaryHeight":120,"spawnCol":19,"spawnRow":11,"collectibleX":33,"collectibleY":44,"hazardX":55,"hazardY":66,"hazardWidth":11,"hazardHeight":10,"goalX":77,"goalY":88,"goalWidth":11,"goalHeight":10,"thinWallX":99,"thinWallY":1,"thinWallWidth":2,"thinWallHeight":48}"""
            RoomAuthority.configureDefinition (ArenaContentFile.decode json |> Result.defaultWith failwith)
            |> Result.defaultWith failwith
            let response = bootstrap "schema3-version-boundary"
            use oldClient = buildConnection ()
            do! oldClient.StartAsync()
            let oldHello = RealtimeV2.encodeMessage (RealtimeV2.SessionHelloMessage { Version = 2; SessionCapability = response.SessionCapability })
            let! refused = Assert.ThrowsAsync<HubException>(fun () -> oldClient.InvokeAsync("SendMessage", oldHello))
            Assert.Contains("reconnect with V3", refused.Message)
            do! oldClient.StopAsync()

            use currentClient = buildConnection ()
            do! currentClient.StartAsync()
            let currentHello = RealtimeV3.encodeMessage (RealtimeV3.SessionHelloMessage { Version = 3; SessionCapability = response.SessionCapability })
            do! currentClient.InvokeAsync("SendMessage", currentHello)
            do! currentClient.StopAsync()
            RoomAuthority.resetForTests ()
        }

    [<Fact>]
    member _.``legacy V1 traversal retains grid behavior across V2 wall and hazard regions``() =
        let response = bootstrap "legacy-cross-arena"
        Assert.Equal(
            Error "move.out-of-bounds",
            RoomAuthority.submitLegacyInput response.PlayerId response.SessionCapability 0 999 999)
        for sequence in 1 .. 40 do
            RoomAuthority.submitLegacyInput response.PlayerId response.SessionCapability sequence 16 8
            |> Result.defaultWith failwith |> ignore
            RoomAuthority.advanceTick () |> ignore
        let _, players = RoomAuthority.snapshot ()
        let _, col, row = players |> List.find (fun (id, _, _) -> id = response.PlayerId)
        Assert.Equal((16, 8), (col, row))
        Assert.Equal((3, 0, false, "playing"), RoomAuthority.gameStatus ())
#endif

    interface IDisposable with
        member _.Dispose() = factory.Dispose()
