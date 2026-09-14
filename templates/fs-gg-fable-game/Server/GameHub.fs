namespace FableGameWorkspaceNamespace.Server

open System.Threading.Tasks
open Microsoft.AspNetCore.SignalR
open FableGameWorkspaceNamespace.Protocol.Realtime

/// SignalR transports only explicit `RealtimeV1.Message` JSON. Connections open
/// unauthenticated; the first accepted message must be the versioned session hello
/// carrying the opaque capability issued by bootstrap. No player identity or secret is
/// taken from the hub URL.
type GameHub() =
    inherit Hub()

    let binding (hub: GameHub) : string option =
        match hub.Context.Items.TryGetValue "playerId" with
        | true, (:? string as value) -> Some value
        | _ -> None

    let capability (hub: GameHub) : string option =
        match hub.Context.Items.TryGetValue "sessionCapability" with
        | true, (:? string as value) -> Some value
        | _ -> None

    let snapshotMessage (tick, players) =
        let health, score, collected, outcome = RoomAuthority.gameStatus ()
        let snapshot: RealtimeV1.Snapshot =
            { Version = 1
              Tick = tick
              Players = players |> List.map (fun (playerId, col, row) -> { PlayerId = playerId; Col = col; Row = row })
              Health = health; Score = score; Collected = collected; Outcome = outcome }
        RealtimeV1.encodeMessage (RealtimeV1.ResyncSnapshotMessage snapshot)

    override _.OnConnectedAsync() : Task = Task.CompletedTask

    override this.OnDisconnectedAsync(exn: exn) : Task =
        task {
            match binding this with
            | None -> ()
            | Some playerId ->
                do! this.Groups.RemoveFromGroupAsync(this.Context.ConnectionId, RoomAuthority.RoomId)
                RoomAuthority.disconnect playerId this.Context.ConnectionId
                let presence: RealtimeV1.Presence = { Version = 1; PlayerId = playerId; Joined = false }
                do! this.Clients.Group(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
        }

    member this.SendMessage(json: string) : Task =
        task {
            match RealtimeV1.messageFromJson json with
            | Error message -> raise (HubException(sprintf "rejected realtime message: %s" message))
            | Ok(RealtimeV1.SessionHelloMessage hello) when hello.Version <> 1 ->
                raise (HubException "unsupported realtime version")
            | Ok(RealtimeV1.SessionHelloMessage hello) ->
                match binding this with
                | Some _ -> raise (HubException "a hub connection may bind only one session")
                | None ->
                    match RoomAuthority.activateSession hello.SessionCapability this.Context.ConnectionId with
                    | Some(playerId, tick, players) ->
                        this.Context.Items["playerId"] <- playerId
                        this.Context.Items["sessionCapability"] <- hello.SessionCapability
                        do! this.Groups.AddToGroupAsync(this.Context.ConnectionId, RoomAuthority.RoomId)
                        do! this.Clients.Caller.SendAsync("Message", snapshotMessage (tick, players))
                        let presence: RealtimeV1.Presence = { Version = 1; PlayerId = playerId; Joined = true }
                        do! this.Clients.OthersInGroup(RoomAuthority.RoomId).SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
                    | None -> raise (HubException "unknown, expired, or already-active game session")
            | Ok(RealtimeV1.InputMessage input) when input.Version <> 1 ->
                raise (HubException "unsupported realtime version")
            | Ok(RealtimeV1.InputMessage input) ->
                match binding this with
                | None -> raise (HubException "session hello is required before input")
                | Some playerId ->
                    match capability this with
                    | None -> raise (HubException "session capability is missing from the live binding")
                    | Some token ->
                        match RoomAuthority.submitInput playerId token input.Sequence input.Action input.TargetCol input.TargetRow with
                        | Ok _ -> ()
                        | Error issue -> raise (HubException(sprintf "input refused: %s" issue))
                    // Input acknowledgement is the next broadcast tick. Mutating or
                    // broadcasting here would make hub-arrival order a game rule.
            | Ok(RealtimeV1.ResyncRequestMessage request) when request.Version <> 1 ->
                raise (HubException "unsupported realtime version")
            | Ok(RealtimeV1.ResyncRequestMessage request) ->
                match binding this with
                | None -> raise (HubException "session hello is required before resync")
                | Some _ ->
                    match RoomAuthority.resyncFrom request.LastKnownTick with
                    | Error message -> raise (HubException message)
                    | Ok snapshot ->
                        // Always one bounded full authoritative resync, never a delta log.
                        do! this.Clients.Caller.SendAsync("Message", snapshotMessage snapshot)
            | Ok(RealtimeV1.SnapshotMessage _)
            | Ok(RealtimeV1.PresenceMessage _)
            | Ok(RealtimeV1.ResyncSnapshotMessage _) ->
                raise (HubException "this message kind is server-authoritative and may not be sent by a client")
        }
