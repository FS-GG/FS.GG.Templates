namespace FableGameWorkspaceNamespace.Server

open System.Threading.Tasks
open Microsoft.AspNetCore.SignalR
open FableGameWorkspaceNamespace.Protocol.Realtime
open FableGameWorkspaceNamespace.ArenaContent

/// One transport hosts the frozen grid V1 contract and the cooperative SVG V2 contract.
/// A hello binds the connection to exactly one versioned group before any input is accepted.
type GameHub() =
    inherit Hub()

    let binding (hub: GameHub) =
        match hub.Context.Items.TryGetValue "playerId" with
        | true, (:? string as value) -> Some value
        | _ -> None

    let capability (hub: GameHub) =
        match hub.Context.Items.TryGetValue "sessionCapability" with
        | true, (:? string as value) -> Some value
        | _ -> None

    let version (hub: GameHub) =
        match hub.Context.Items.TryGetValue "realtimeVersion" with
        | true, (:? int as value) -> Some value
        | _ -> None

    let group version = $"{RoomAuthority.RoomId}-v{version}"

    let playersV1 players : RealtimeV1.PlayerSnapshot list =
        players
        |> List.map (fun (playerId, col, row) ->
            {
                PlayerId = playerId
                Col = col
                Row = row
            })

    let playersV2 players : RealtimeV2.PlayerSnapshot list =
        players
        |> List.map (fun (playerId, col, row) ->
            {
                PlayerId = playerId
                Col = col
                Row = row
            })

    let playersV3 players : RealtimeV3.PlayerSnapshot list =
        players
        |> List.map (fun (playerId, col, row) ->
            {
                PlayerId = playerId
                Col = col
                Row = row
            })

    let snapshotV1 kind (tick, players) =
        let snapshot: RealtimeV1.Snapshot =
            {
                Version = 1
                Tick = tick
                Players = playersV1 players
            }

        let message =
            if kind = "snapshot" then
                RealtimeV1.SnapshotMessage snapshot
            else
                RealtimeV1.ResyncSnapshotMessage snapshot

        RealtimeV1.encodeMessage message

    let snapshotV2 kind (snapshot: RoomAuthority.Snapshot) =
        let snapshot: RealtimeV2.Snapshot =
            {
                Version = 2
                Tick = snapshot.Tick
                Round = snapshot.Round
                Players = playersV2 snapshot.Players
                Health = snapshot.Health
                Score = snapshot.Score
                Collected = snapshot.Collected
                Outcome = snapshot.Outcome
                ContentId = snapshot.ContentId
                ContentSchema = snapshot.ContentSchema
                CollectibleX = snapshot.Content.CollectibleX
                CollectibleY = snapshot.Content.CollectibleY
                HazardX = snapshot.Content.Hazard.X
                HazardY = snapshot.Content.Hazard.Y
                HazardWidth = snapshot.Content.Hazard.Width
                HazardHeight = snapshot.Content.Hazard.Height
                GoalX = snapshot.Content.Goal.X
                GoalY = snapshot.Content.Goal.Y
                GoalWidth = snapshot.Content.Goal.Width
                GoalHeight = snapshot.Content.Goal.Height
                ThinWallX = snapshot.Content.ThinWall.X
                ThinWallY = snapshot.Content.ThinWall.Y
                ThinWallWidth = snapshot.Content.ThinWall.Width
                ThinWallHeight = snapshot.Content.ThinWall.Height
                HazardCol = snapshot.HazardCol
                HazardRow = snapshot.HazardRow
            }

        let message =
            if kind = "snapshot" then
                RealtimeV2.SnapshotMessage snapshot
            else
                RealtimeV2.ResyncSnapshotMessage snapshot

        RealtimeV2.encodeMessage message

    let snapshotV3 kind (snapshot: RoomAuthority.Snapshot) =
        let content = snapshot.Content

        let value: RealtimeV3.Snapshot =
            {
                Version = 3
                Tick = snapshot.Tick
                Round = snapshot.Round
                Players = playersV3 snapshot.Players
                Health = snapshot.Health
                Score = snapshot.Score
                Collected = snapshot.Collected
                Outcome = snapshot.Outcome
                ContentId = snapshot.ContentId
                ContentSchema = snapshot.ContentSchema
                BoundaryX = content.Boundary.X
                BoundaryY = content.Boundary.Y
                BoundaryWidth = content.Boundary.Width
                BoundaryHeight = content.Boundary.Height
                SpawnCol = content.Spawn.Col
                SpawnRow = content.Spawn.Row
                CollectibleX = content.CollectibleX
                CollectibleY = content.CollectibleY
                HazardX = content.Hazard.X
                HazardY = content.Hazard.Y
                HazardWidth = content.Hazard.Width
                HazardHeight = content.Hazard.Height
                GoalX = content.Goal.X
                GoalY = content.Goal.Y
                GoalWidth = content.Goal.Width
                GoalHeight = content.Goal.Height
                ThinWallX = content.ThinWall.X
                ThinWallY = content.ThinWall.Y
                ThinWallWidth = content.ThinWall.Width
                ThinWallHeight = content.ThinWall.Height
                HazardCol = snapshot.HazardCol
                HazardRow = snapshot.HazardRow
            }

        let message =
            if kind = "snapshot" then
                RealtimeV3.SnapshotMessage value
            else
                RealtimeV3.ResyncSnapshotMessage value

        RealtimeV3.encodeMessage message

    let bindHello (hub: GameHub) wireVersion token =
        task {
            match binding hub with
            | Some _ -> return raise (HubException "a hub connection may bind only one session")
            | None ->
                let contentSchema = RoomAuthority.completeSnapshot().ContentSchema

                if wireVersion = 2 && contentSchema <> 2 then
                    return
                        raise (
                            HubException
                                $"realtime V2 supports content schema 2; authority uses schema {contentSchema}; reconnect with V3"
                        )

                match RoomAuthority.activateSession token hub.Context.ConnectionId with
                | None -> return raise (HubException "unknown, expired, or already-active game session")
                | Some(playerId, tick, players) ->
                    hub.Context.Items["playerId"] <- playerId
                    hub.Context.Items["sessionCapability"] <- token
                    hub.Context.Items["realtimeVersion"] <- wireVersion
                    do! hub.Groups.AddToGroupAsync(hub.Context.ConnectionId, group wireVersion)

                    let payload =
                        if wireVersion = 1 then
                            snapshotV1 "resync" (tick, players)
                        elif wireVersion = 2 then
                            snapshotV2 "resync" (RoomAuthority.completeSnapshot ())
                        else
                            snapshotV3 "resync" (RoomAuthority.completeSnapshot ())

                    do! hub.Clients.Caller.SendAsync("Message", payload)

                    if wireVersion = 1 then
                        let presence: RealtimeV1.Presence =
                            {
                                Version = 1
                                PlayerId = playerId
                                Joined = true
                            }

                        do!
                            hub.Clients
                                .OthersInGroup(group 1)
                                .SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
                    elif wireVersion = 2 then
                        let presence: RealtimeV2.Presence =
                            {
                                Version = 2
                                PlayerId = playerId
                                Joined = true
                            }

                        do!
                            hub.Clients
                                .OthersInGroup(group 2)
                                .SendAsync("Message", RealtimeV2.encodeMessage (RealtimeV2.PresenceMessage presence))
                    else
                        let presence: RealtimeV3.Presence =
                            {
                                Version = 3
                                PlayerId = playerId
                                Joined = true
                            }

                        do!
                            hub.Clients
                                .OthersInGroup(group 3)
                                .SendAsync("Message", RealtimeV3.encodeMessage (RealtimeV3.PresenceMessage presence))
        }

    override _.OnConnectedAsync() : Task = Task.CompletedTask

    override this.OnDisconnectedAsync(exn: exn) : Task =
        task {
            match binding this, version this with
            | Some playerId, Some wireVersion ->
                do! this.Groups.RemoveFromGroupAsync(this.Context.ConnectionId, group wireVersion)
                RoomAuthority.disconnect playerId this.Context.ConnectionId

                if wireVersion = 1 then
                    let presence: RealtimeV1.Presence =
                        {
                            Version = 1
                            PlayerId = playerId
                            Joined = false
                        }

                    do!
                        this.Clients
                            .Group(group 1)
                            .SendAsync("Message", RealtimeV1.encodeMessage (RealtimeV1.PresenceMessage presence))
                elif wireVersion = 2 then
                    let presence: RealtimeV2.Presence =
                        {
                            Version = 2
                            PlayerId = playerId
                            Joined = false
                        }

                    do!
                        this.Clients
                            .Group(group 2)
                            .SendAsync("Message", RealtimeV2.encodeMessage (RealtimeV2.PresenceMessage presence))
                else
                    let presence: RealtimeV3.Presence =
                        {
                            Version = 3
                            PlayerId = playerId
                            Joined = false
                        }

                    do!
                        this.Clients
                            .Group(group 3)
                            .SendAsync("Message", RealtimeV3.encodeMessage (RealtimeV3.PresenceMessage presence))
            | _ -> ()
        }

    member this.SendMessage(json: string) : Task =
        task {
            let wireVersion =
                try
                    use document = System.Text.Json.JsonDocument.Parse json
                    document.RootElement.GetProperty("payload").GetProperty("version").GetInt32()
                with _ ->
                    -1

            match wireVersion with
            | 3 ->
                match RealtimeV3.messageFromJson json with
                | Error message -> raise (HubException(sprintf "rejected realtime V3 message: %s" message))
                | Ok(RealtimeV3.SessionHelloMessage hello) -> do! bindHello this 3 hello.SessionCapability
                | Ok(RealtimeV3.InputMessage input) ->
                    match binding this, capability this, version this with
                    | Some playerId, Some token, Some 3 ->
                        match
                            RoomAuthority.submitInput
                                playerId
                                token
                                input.Sequence
                                input.Action
                                input.TargetCol
                                input.TargetRow
                        with
                        | Ok _ -> ()
                        | Error issue -> raise (HubException(sprintf "input refused: %s" issue))
                    | _ -> raise (HubException "V3 session hello is required before input")
                | Ok(RealtimeV3.ResyncRequestMessage request) ->
                    match binding this, version this with
                    | Some _, Some 3 ->
                        match RoomAuthority.resyncFrom request.LastKnownTick with
                        | Ok _ ->
                            do!
                                this.Clients.Caller.SendAsync(
                                    "Message",
                                    snapshotV3 "resync" (RoomAuthority.completeSnapshot ())
                                )
                        | Error issue -> raise (HubException issue)
                    | _ -> raise (HubException "V3 session hello is required before resync")
                | Ok _ -> raise (HubException "this V3 message kind is server-authoritative")
            | 2 ->
                match RealtimeV2.messageFromJson json with
                | Error message -> raise (HubException(sprintf "rejected realtime V2 message: %s" message))
                | Ok(RealtimeV2.SessionHelloMessage hello) -> do! bindHello this 2 hello.SessionCapability
                | Ok(RealtimeV2.InputMessage input) ->
                    match binding this, capability this, version this with
                    | Some playerId, Some token, Some 2 ->
                        match
                            RoomAuthority.submitInput
                                playerId
                                token
                                input.Sequence
                                input.Action
                                input.TargetCol
                                input.TargetRow
                        with
                        | Ok _ -> ()
                        | Error issue -> raise (HubException(sprintf "input refused: %s" issue))
                    | _ -> raise (HubException "V2 session hello is required before input")
                | Ok(RealtimeV2.ResyncRequestMessage request) ->
                    match binding this, version this with
                    | Some _, Some 2 ->
                        match RoomAuthority.resyncFrom request.LastKnownTick with
                        | Ok _ ->
                            do!
                                this.Clients.Caller.SendAsync(
                                    "Message",
                                    snapshotV2 "resync" (RoomAuthority.completeSnapshot ())
                                )
                        | Error issue -> raise (HubException issue)
                    | _ -> raise (HubException "V2 session hello is required before resync")
                | Ok _ -> raise (HubException "this V2 message kind is server-authoritative")
            | 1 ->
                match RealtimeV1.messageFromJson json with
                | Error message -> raise (HubException(sprintf "rejected realtime V1 message: %s" message))
                | Ok(RealtimeV1.SessionHelloMessage hello) -> do! bindHello this 1 hello.SessionCapability
                | Ok(RealtimeV1.InputMessage input) ->
                    match binding this, capability this, version this with
                    | Some playerId, Some token, Some 1 ->
                        match
                            RoomAuthority.submitLegacyInput
                                playerId
                                token
                                input.Sequence
                                input.TargetCol
                                input.TargetRow
                        with
                        | Ok _ -> ()
                        | Error issue -> raise (HubException(sprintf "input refused: %s" issue))
                    | _ -> raise (HubException "V1 session hello is required before input")
                | Ok(RealtimeV1.ResyncRequestMessage request) ->
                    match binding this, version this with
                    | Some _, Some 1 ->
                        match RoomAuthority.resyncFrom request.LastKnownTick with
                        | Ok snapshot -> do! this.Clients.Caller.SendAsync("Message", snapshotV1 "resync" snapshot)
                        | Error issue -> raise (HubException issue)
                    | _ -> raise (HubException "V1 session hello is required before resync")
                | Ok _ -> raise (HubException "this V1 message kind is server-authoritative")
            | _ -> raise (HubException "unsupported realtime version")
        }
