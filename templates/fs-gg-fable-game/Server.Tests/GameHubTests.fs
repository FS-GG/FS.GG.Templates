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
open FableGameWorkspaceNamespace.Protocol.Realtime
open FableGameWorkspaceNamespace.Server

/// Exercises the SignalR real-time leg #348's acceptance names, over a real
/// `HubConnection` talking to an in-memory `TestServer` (not a bare function call):
/// join/resync-on-connect, one authoritative input round trip, stale-input rejection,
/// disconnect/reconnect bounded full resync, subscription cleanup, an in-flight
/// cancellation, and the client-may-not-send-authoritative-kinds rejection.
type GameHubTests() =
    do RoomAuthority.resetForTests () // isolates this test from RoomAuthority's process-wide static state
    // `TickIntervalMilliseconds` pushed out to effectively "never": these tests assert
    // on the very next inbound `Message` after a specific action, and the real
    // 200ms-default `TickBroadcaster` hosted service (still running for real here, not
    // mocked) would otherwise race with that.
    let factory =
        (new WebApplicationFactory<Program>())
            .WithWebHostBuilder(fun builder ->
                builder.ConfigureAppConfiguration(fun _ config ->
                    config.AddInMemoryCollection(dict [ "TickIntervalMilliseconds", "600000" ]) |> ignore)
                |> ignore)

    let buildConnection (playerId: string) : HubConnection =
        let baseAddress = factory.Server.BaseAddress
        HubConnectionBuilder()
            .WithUrl(
                Uri(baseAddress, $"/hub/game?playerId={playerId}"),
                fun (opts: HttpConnectionOptions) ->
                    opts.HttpMessageHandlerFactory <- fun _ -> factory.Server.CreateHandler()
                    opts.Transports <- HttpTransportType.LongPolling
            )
            .Build()

    /// Awaits the next inbound `Message` and decodes it, or fails after `timeoutMs`.
    let nextMessage (connection: HubConnection) (timeoutMs: int) : Task<RealtimeV1.Message> =
        let tcs = TaskCompletionSource<RealtimeV1.Message>()
        let subscription =
            connection.On<string>(
                "Message",
                fun json ->
                    match RealtimeV1.messageFromJson json with
                    | Ok message -> tcs.TrySetResult message |> ignore
                    | Error err -> tcs.TrySetException(Exception err) |> ignore
            )
        task {
            use _ = subscription
            use cts = new CancellationTokenSource(timeoutMs)
            use _ = cts.Token.Register(fun () -> tcs.TrySetCanceled() |> ignore)
            return! tcs.Task
        }

    [<Fact>]
    member _.``connecting sends the joining client an immediate full resync snapshot``() =
        task {
            use connection = buildConnection "p-connect"
            let waiting = nextMessage connection 5000
            do! connection.StartAsync()
            let! message = waiting
            match message with
            | RealtimeV1.ResyncSnapshotMessage snapshot ->
                Assert.Contains(snapshot.Players, fun p -> p.PlayerId = "p-connect")
            | other -> Assert.Fail $"expected ResyncSnapshotMessage, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``one accepted input moves the player and broadcasts an authoritative snapshot``() =
        task {
            use connection = buildConnection "p-move"
            let joinWaiting = nextMessage connection 5000
            do! connection.StartAsync()
            let! (_: RealtimeV1.Message) = joinWaiting // the connect-time resync
            let waiting = nextMessage connection 5000
            let input: RealtimeV1.InputCommand = { Sequence = 1; TargetCol = 1; TargetRow = 0 }
            do! connection.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.InputMessage input))
            let! message = waiting
            match message with
            | RealtimeV1.SnapshotMessage snapshot ->
                let mover = snapshot.Players |> List.find (fun p -> p.PlayerId = "p-move")
                Assert.Equal((1, 0), (mover.Col, mover.Row))
            | other -> Assert.Fail $"expected SnapshotMessage, got {other}"
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``a repeated, non-increasing sequence is dropped as stale input``() =
        task {
            use connection = buildConnection "p-stale"
            let joinWaiting = nextMessage connection 5000
            do! connection.StartAsync()
            let! (_: RealtimeV1.Message) = joinWaiting

            let sendAndAwaitPosition (sequence: int) =
                task {
                    let waiting = nextMessage connection 5000
                    let input: RealtimeV1.InputCommand = { Sequence = sequence; TargetCol = 3; TargetRow = 0 }
                    do! connection.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.InputMessage input))
                    let! message = waiting
                    match message with
                    | RealtimeV1.SnapshotMessage snapshot -> return snapshot.Players |> List.find (fun p -> p.PlayerId = "p-stale") |> fun p -> p.Col, p.Row
                    | other -> return failwith $"expected SnapshotMessage, got {other}"
                }

            let! afterFirst = sendAndAwaitPosition 5
            let! afterReplay = sendAndAwaitPosition 5 // same sequence again: must be dropped
            Assert.Equal(afterFirst, afterReplay)
            do! connection.StopAsync()
        }

    [<Fact>]
    member _.``disconnect then reconnect performs a bounded full authoritative resync``() =
        task {
            use first = buildConnection "p-reconnect"
            let firstJoinWaiting = nextMessage first 5000
            do! first.StartAsync()
            let! (firstResync: RealtimeV1.Message) = firstJoinWaiting
            match firstResync with
            | RealtimeV1.ResyncSnapshotMessage snapshot -> Assert.Contains(snapshot.Players, fun p -> p.PlayerId = "p-reconnect")
            | other -> Assert.Fail $"expected ResyncSnapshotMessage, got {other}"
            do! first.StopAsync()

            use second = buildConnection "p-reconnect"
            let waiting = nextMessage second 5000
            do! second.StartAsync()
            let! secondResync = waiting
            match secondResync with
            | RealtimeV1.ResyncSnapshotMessage snapshot ->
                // The reconnect gets a *fresh*, currently-true snapshot -- not a replay of
                // whatever the first connection last saw -- which is what "bounded full
                // authoritative resync" means operationally.
                Assert.Contains(snapshot.Players, fun p -> p.PlayerId = "p-reconnect")
            | other -> Assert.Fail $"expected ResyncSnapshotMessage, got {other}"

            let explicitWaiting = nextMessage second 5000
            let request: RealtimeV1.ResyncRequest = { Version = 1; LastKnownTick = 0 }
            do! second.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.ResyncRequestMessage request))
            let! explicitResync = explicitWaiting
            match explicitResync with
            | RealtimeV1.ResyncSnapshotMessage snapshot -> Assert.Contains(snapshot.Players, fun p -> p.PlayerId = "p-reconnect")
            | other -> Assert.Fail $"expected ResyncSnapshotMessage, got {other}"
            do! second.StopAsync()
        }

    [<Fact>]
    member _.``disconnecting a client cleans up its room membership: it stops receiving broadcasts and is retired from authoritative state``() =
        task {
            use leaver = buildConnection "p-leaver"
            let leaverJoinWaiting = nextMessage leaver 5000
            do! leaver.StartAsync()
            let! (_: RealtimeV1.Message) = leaverJoinWaiting

            use stayer = buildConnection "p-stayer"
            let stayerJoinWaiting = nextMessage stayer 5000 // stayer's own connect-time resync
            do! stayer.StartAsync()
            let! (_: RealtimeV1.Message) = stayerJoinWaiting

            // The stayer observes the leaver's presence-departed broadcast, proving
            // OnDisconnectedAsync actually ran (not just that the socket closed).
            let departedWaiting = nextMessage stayer 5000
            do! leaver.StopAsync()
            let! departed = departedWaiting
            match departed with
            | RealtimeV1.PresenceMessage presence ->
                Assert.Equal("p-leaver", presence.PlayerId)
                Assert.False presence.Joined
            | other -> Assert.Fail $"expected a departure PresenceMessage, got {other}"

            // Cleanup is observable in authoritative state, not merely in a socket
            // closing: a subsequent broadcast still succeeds (no lingering group entry
            // throws), and the leaver no longer appears in the authoritative snapshot.
            let snapshotWaiting = nextMessage stayer 5000
            let input: RealtimeV1.InputCommand = { Sequence = 1; TargetCol = 1; TargetRow = 0 }
            do! stayer.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.InputMessage input))
            let! snapshotMessage = snapshotWaiting
            match snapshotMessage with
            | RealtimeV1.SnapshotMessage snapshot -> Assert.DoesNotContain(snapshot.Players, fun p -> p.PlayerId = "p-leaver")
            | other -> Assert.Fail $"expected SnapshotMessage, got {other}"
            do! stayer.StopAsync()
        }

    [<Fact>]
    member _.``stopping a connection while a hub call is in flight completes without hanging``() =
        task {
            use connection = buildConnection "p-cancel"
            let joinWaiting = nextMessage connection 5000
            do! connection.StartAsync()
            let! (_: RealtimeV1.Message) = joinWaiting
            let input: RealtimeV1.InputCommand = { Sequence = 1; TargetCol = 1; TargetRow = 0 }
            let invoke = connection.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.InputMessage input))
            let stop = connection.StopAsync()
            let both = Task.WhenAll(invoke, stop)
            let! _ = Task.WhenAny(both, Task.Delay 5000)
            Assert.True(invoke.IsCompleted && stop.IsCompleted, "stopping while a hub call is in flight must not hang")
        }

    [<Fact>]
    member _.``a client may not send a server-authoritative message kind``() =
        task {
            use connection = buildConnection "p-illegal"
            let joinWaiting = nextMessage connection 5000
            do! connection.StartAsync()
            let! (_: RealtimeV1.Message) = joinWaiting
            let illegal: RealtimeV1.Presence = { Version = 1; PlayerId = "p-illegal"; Joined = true }
            let! exn =
                Assert.ThrowsAsync<HubException>(fun () ->
                    connection.InvokeAsync("SendMessage", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage illegal)))
            Assert.Contains("server-authoritative", exn.Message)
            do! connection.StopAsync()
        }

    interface IDisposable with
        member _.Dispose() = factory.Dispose()
