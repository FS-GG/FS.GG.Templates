namespace FableGameWorkspaceNamespace.Server

open System.Threading.Tasks
open Microsoft.AspNetCore.SignalR
open FableGameWorkspaceNamespace.Protocol.Realtime

/// SignalR owns connection/session-oriented traffic (ADR-0073 leaves this unchanged):
/// input, snapshots, presence, acknowledgement, reconnect, and resync. Every hub
/// method and broadcast carries one `RealtimeV1.Message` case, always as its
/// *already-encoded* JSON string -- SignalR's own default JSON protocol never sees the
/// `Message` discriminated union, so the codec discipline in `Protocol/Realtime.fs` is
/// what actually crosses the wire, not SignalR's automatic parameter serialization
/// (which cannot express an F# DU faithfully without the same reflection-driven
/// serialization ADR-0073 rules out).
type GameHub() =
    inherit Hub()

    let playerId (hub: GameHub) : string =
        match hub.Context.Items.TryGetValue "playerId" with
        | true, (:? string as value) -> value
        | _ -> hub.Context.ConnectionId

    override this.OnConnectedAsync() : Task =
        task {
            let id =
                match this.Context.GetHttpContext() with
                | null -> this.Context.ConnectionId
                | httpContext ->
                    match httpContext.Request.Query.TryGetValue "playerId" with
                    | true, value when value.Count > 0 && value.[0] <> null && value.[0] <> "" -> value.[0]
                    | _ -> this.Context.ConnectionId
            this.Context.Items.["playerId"] <- id
            RoomAuthority.join id |> ignore
            do! this.Groups.AddToGroupAsync(this.Context.ConnectionId, RoomAuthority.RoomId)
            let tick, players = RoomAuthority.snapshot ()
            let snapshot: RealtimeV1.Snapshot =
                { Version = 1; Tick = tick; Players = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row }) }
            do! this.Clients.Caller.SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.ResyncSnapshotMessage snapshot))
            let presence: RealtimeV1.Presence = { Version = 1; PlayerId = id; Joined = true }
            do! this.Clients.OthersInGroup(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
        }

    /// Subscription cleanup: remove the connection from the broadcast group (so a
    /// leaked hub-side callback can never fire against a torn-down connection), retire
    /// the authoritative player, and tell the remaining clients. `Server.Tests`
    /// exercises this by asserting a disconnected client's group is empty and that no
    /// further broadcast reaches it.
    override this.OnDisconnectedAsync(exn: exn) : Task =
        task {
            let id = playerId this
            do! this.Groups.RemoveFromGroupAsync(this.Context.ConnectionId, RoomAuthority.RoomId)
            RoomAuthority.leave id
            let presence: RealtimeV1.Presence = { Version = 1; PlayerId = id; Joined = false }
            do! this.Clients.Group(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
        }

    /// The single hub entry point every client message arrives through. Decoding
    /// through `RealtimeV1.messageFromJson` first means a malformed or unrecognised
    /// payload is rejected here, symmetrically with the browser-side decoder -- see
    /// `Protocol.Tests` for the DU round-trip and rejected-case proof this depends on.
    member this.SendMessage(json: string) : Task =
        task {
            match RealtimeV1.messageFromJson json with
            | Error message -> raise (HubException(sprintf "rejected realtime message: %s" message))
            | Ok(RealtimeV1.InputMessage input) ->
                let id = playerId this
                RoomAuthority.submitInput id input.Sequence input.TargetCol input.TargetRow |> ignore
                let tick, players = RoomAuthority.snapshot ()
                let snapshot: RealtimeV1.Snapshot =
                    { Version = 1; Tick = tick; Players = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row }) }
                do! this.Clients.Group(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.SnapshotMessage snapshot))
            | Ok(RealtimeV1.ResyncRequestMessage _) ->
                // Always a bounded *full* authoritative resync, never a delta log -- see
                // #348's acceptance ("Disconnect/reconnect performs a bounded full
                // authoritative resync").
                let tick, players = RoomAuthority.snapshot ()
                let snapshot: RealtimeV1.Snapshot =
                    { Version = 1; Tick = tick; Players = players |> List.map (fun (pid, col, row) -> { PlayerId = pid; Col = col; Row = row }) }
                do! this.Clients.Caller.SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.ResyncSnapshotMessage snapshot))
            | Ok(RealtimeV1.SnapshotMessage _)
            | Ok(RealtimeV1.PresenceMessage _)
            | Ok(RealtimeV1.ResyncSnapshotMessage _) ->
                // These three cases are server -> client only; a client sending one is
                // never authoritative and is rejected rather than silently accepted.
                raise (HubException "this message kind is server-authoritative and may not be sent by a client")
        }
