namespace FableGameWorkspaceNamespace.Server

open System
open System.Collections.Concurrent
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace.ArenaContent

/// The single authoritative room this minimal template hosts. A generated product
/// replaces this module with a keyed room registry; its important baseline invariant
/// remains the same: hub arrival only admits an intent. State changes at the next
/// deterministic tick frontier, never in whatever order transports happen to arrive.
[<RequireQualifiedAccess>]
module RoomAuthority =

    let ArenaWidth = arenaColumns
    let ArenaHeight = arenaRows

    [<Literal>]
    let RoomId = "arena-1"

    let SessionLifetime = TimeSpan.FromMinutes 2.0

    let MaxSessions = ArenaWidth * ArenaHeight

    type AdmissionError =
        | SessionLimitReached
        | ArenaFull

    let admissionError = function
        | SessionLimitReached -> "session capacity reached"
        | ArenaFull -> "arena has no free spawn"

    type private Session =
        { PlayerId: string
          mutable ConnectionId: string option
          mutable ExpiresAt: DateTimeOffset option }

    type private PendingInput =
        { PlayerId: string
          AcceptedOrder: uint64
          Action: string
          TargetCol: int
          TargetRow: int }

    /// One lock-consistent V2 projection. Consumers must not combine independently
    /// sampled position, rules, and moving-content reads.
    type Snapshot =
        { Tick: int
          Players: (string * int * int) list
          Round: int
          Health: int
          Score: int
          Collected: bool
          Outcome: string
          ContentId: string
          ContentSchema: int
          Content: ArenaContent
          HazardCol: int
          HazardRow: int }

    let mutable private definition = contentAt 0UL
    let mutable private state = FableGameWorkspaceNamespace.ArenaRules.createWith definition
    let private sessions = ConcurrentDictionary<string, Session>()
    let private lastSequence = ConcurrentDictionary<string, int>()
    let private pending = ConcurrentDictionary<string, PendingInput>()
    let private gate = obj ()

    let private snapshotLocked () = state.Room.Tick, Room.toSnapshotPairs state.Room

    let private completeSnapshotLocked () =
        let content = FableGameWorkspaceNamespace.ArenaRules.currentContent state
        { Tick = state.Room.Tick
          Players = Room.toSnapshotPairs state.Room
          Round = state.Round
          Health = state.Status.Health
          Score = state.Status.Score
          Collected = state.Status.Collected
          Outcome = state.Status.Outcome
          ContentId = state.Definition.ContentId
          ContentSchema = state.Definition.SchemaVersion
          Content = content
          HazardCol = int (content.Hazard.X / cellWidth)
          HazardRow = int (content.Hazard.Y / cellHeight) }

    let resetForTests () : unit =
        lock gate (fun () ->
            definition <- contentAt 0UL
            state <- FableGameWorkspaceNamespace.ArenaRules.createWith definition
            sessions.Clear()
            lastSequence.Clear()
            pending.Clear()
#if SVG_NETWORK_CANDIDATE
            NetworkAuthority.reset state
#endif
        )

    /// Installs validated authored content before serving requests. Reconfiguration
    /// after admission is refused so content identity cannot change under a live room.
    let configureDefinition content : Result<unit, string> =
        lock gate (fun () ->
            if not sessions.IsEmpty then Error "arena content cannot change after session admission"
            else
                definition <- content
                state <- FableGameWorkspaceNamespace.ArenaRules.createWith definition
#if SVG_NETWORK_CANDIDATE
                NetworkAuthority.reset state
#endif
                Ok())

    let private retirePlayerLocked (playerId: string) : unit =
        state <- FableGameWorkspaceNamespace.ArenaRules.leave playerId state
        lastSequence.TryRemove playerId |> ignore
        pending.TryRemove playerId |> ignore
#if SVG_NETWORK_CANDIDATE
        NetworkAuthority.unbind playerId state
#endif

    let private pruneExpiredLocked (now: DateTimeOffset) : unit =
        sessions
        |> Seq.choose (fun pair ->
            match pair.Value.ConnectionId, pair.Value.ExpiresAt with
            | None, Some expiresAt when expiresAt <= now -> Some(pair.Key, pair.Value.PlayerId)
            | _ -> None)
        |> Seq.toList
        |> List.iter (fun (capability, playerId) ->
            sessions.TryRemove capability |> ignore
            retirePlayerLocked playerId)

    let private joinLocked (playerId: string) : Cell option =
        match state.Room.Players |> Map.tryFind playerId with
        | Some existing -> Some existing.Cell
        | None ->
            let occupied = state.Room.Players |> Map.toSeq |> Seq.map (fun (_, p) -> p.Cell) |> Set.ofSeq
            seq {
                for row in 0 .. ArenaHeight - 1 do
                    for col in 0 .. ArenaWidth - 1 do
                        yield ({ Col = col; Row = row }: Cell)
            }
            |> Seq.tryFind (occupied.Contains >> not)
            |> Option.map (fun spawn ->
                state <- FableGameWorkspaceNamespace.ArenaRules.join playerId spawn state
                lastSequence.[playerId] <- 0
                spawn)

    /// Creates an opaque, expiring bootstrap capability within the arena-sized session
    /// bound. It is exchanged in the explicit SignalR hello message, never in a query
    /// string, so a URL cannot persist it in logs, history, referrers, or browser
    /// diagnostics. No admission path falls back to an occupied cell.
    let createSessionAt (now: DateTimeOffset) (playerId: string) : Result<string * Cell, AdmissionError> =
        lock gate (fun () ->
            pruneExpiredLocked now
            if sessions.Count >= MaxSessions then
                Error SessionLimitReached
            else
                match joinLocked playerId with
                | None -> Error ArenaFull
                | Some spawn ->
                    let capability = Guid.NewGuid().ToString "N"
                    sessions.[capability] <-
                        { PlayerId = playerId
                          ConnectionId = None
                          ExpiresAt = Some(now.Add SessionLifetime) }
#if SVG_NETWORK_CANDIDATE
                    NetworkAuthority.bind playerId capability (uint64 state.Room.Tick) state
#endif
                    Ok(capability, spawn))

    let createSession (playerId: string) : Result<string * Cell, AdmissionError> =
        createSessionAt DateTimeOffset.UtcNow playerId

    /// The tick loop calls this cleanup implicitly; the explicit core boundary keeps
    /// expiry deterministic and directly testable without sleeping for wall-clock time.
    let expireSessionsAt (now: DateTimeOffset) : unit = lock gate (fun () -> pruneExpiredLocked now)

    /// Binds a just-opened hub connection to exactly one bootstrap-issued capability.
    /// A capability already owned by another live connection is rejected rather than
    /// letting two tabs silently act as one player.
    let activateSession (capability: string) (connectionId: string) : (string * int * (string * int * int) list) option =
        lock gate (fun () ->
            pruneExpiredLocked DateTimeOffset.UtcNow
            match sessions.TryGetValue capability with
            | true, session when session.ConnectionId |> Option.forall ((=) connectionId) ->
                match joinLocked session.PlayerId with
                | None -> None
                | Some _ ->
                    session.ConnectionId <- Some connectionId
                    session.ExpiresAt <- None
#if SVG_NETWORK_CANDIDATE
                    match NetworkAuthority.reconnect session.PlayerId capability (uint64 (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())) with
                    | Error _ -> None
                    | Ok _ ->
                        let tick, players = snapshotLocked ()
                        Some(session.PlayerId, tick, players)
#else
                    let tick, players = snapshotLocked ()
                    Some(session.PlayerId, tick, players)
#endif
            | _ -> None)

    /// Releases the transport binding and room presence. The capability remains valid
    /// only for the bounded reconnect window, after which tick cleanup retires it.
    let disconnect (playerId: string) (connectionId: string) : unit =
        lock gate (fun () ->
            sessions
            |> Seq.iter (fun pair ->
                if pair.Value.PlayerId = playerId && pair.Value.ConnectionId = Some connectionId then
                    pair.Value.ConnectionId <- None
                    pair.Value.ExpiresAt <- Some(DateTimeOffset.UtcNow.Add SessionLifetime))
#if SVG_NETWORK_CANDIDATE
            NetworkAuthority.disconnect playerId (uint64 (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()))
#else
            retirePlayerLocked playerId
#endif
        )

    /// Queues the highest strictly-increasing input for this player. The accepted
    /// intent is not applied here: every queued player is resolved together at the
    /// next tick frontier in stable player/sequence order.
    let private submitInputCore legacy (playerId: string) (capability: string) (sequence: int) (action: string) (targetCol: int) (targetRow: int) : Result<uint64, string> =
        lock gate (fun () ->
            if (legacy && action <> "legacy-move") || (not legacy && not (Set.contains action (Set.ofList [ "move"; "interact"; "restart" ]))) then
                Error "unknown arena action"
            else
#if SVG_NETWORK_CANDIDATE
              if sequence < 0 then Error "input sequence must be non-negative"
              else
                match NetworkAuthority.admit playerId capability (uint64 sequence) action targetCol targetRow with
                | Error "PayloadRefused \"intent.out-of-bounds\"" when legacy -> Error "move.out-of-bounds"
                | Error issue -> Error issue
                | Ok acceptedOrder ->
                    pending.[playerId] <-
                        { PlayerId = playerId
                          AcceptedOrder = acceptedOrder
                          Action = action
                          TargetCol = targetCol
                          TargetRow = targetRow }
                    Ok acceptedOrder
#else
              match lastSequence.TryGetValue playerId with
              | true, last when sequence > last ->
                lastSequence.[playerId] <- sequence
                pending.[playerId] <-
                    { PlayerId = playerId
                      AcceptedOrder = uint64 sequence
                      Action = action
                      TargetCol = targetCol
                      TargetRow = targetRow }
                Ok(uint64 sequence)
              | _ -> Error "input sequence is duplicate or stale"
#endif
        )

    let submitInput playerId capability sequence action targetCol targetRow =
        submitInputCore false playerId capability sequence action targetCol targetRow

    let submitLegacyInput playerId capability sequence targetCol targetRow =
        submitInputCore true playerId capability sequence "legacy-move" targetCol targetRow

    let snapshot () : int * (string * int * int) list = lock gate snapshotLocked

    let completeSnapshot () : Snapshot = lock gate completeSnapshotLocked

    let gameStatus () = lock gate (fun () -> state.Status.Health, state.Status.Score, state.Status.Collected, state.Status.Outcome)

    let arenaContent () = lock gate (fun () -> FableGameWorkspaceNamespace.ArenaRules.currentContent state)

    /// A cursor is consistent only when it names a frontier this authority has already
    /// reached. This starter keeps no unbounded delta log, so every valid cursor gets
    /// one bounded authoritative snapshot; a negative or future cursor is rejected.
    let resyncFrom (lastKnownTick: int) : Result<int * (string * int * int) list, string> =
        lock gate (fun () ->
            let tick, players = snapshotLocked ()
#if SVG_NETWORK_CANDIDATE
            match NetworkAuthority.resync (uint64 (max 0 lastKnownTick)) (uint64 tick) with
            | NetworkResyncDecision.ClientAhead _ -> Error $"inconsistent resync cursor {lastKnownTick}; authoritative tick is {tick}"
            | _ -> Ok(tick, players)
#else
            if lastKnownTick < 0 || lastKnownTick > tick then
                Error $"inconsistent resync cursor {lastKnownTick}; authoritative tick is {tick}"
            else
                Ok(tick, players)
#endif
        )

    let acknowledge (playerId: string) (revision: int) : Result<unit, string> =
#if SVG_NETWORK_CANDIDATE
        lock gate (fun () ->
            if revision < 0 then Error "acknowledgement must be non-negative"
            else NetworkAuthority.acknowledge playerId (uint64 revision))
#else
        Ok()
#endif

    let review () : string * string * int =
#if SVG_NETWORK_CANDIDATE
        lock gate NetworkAuthority.review
#else
        "", "", 0
#endif

    let verifyReplay () : Result<bool, string> =
#if SVG_NETWORK_CANDIDATE
        lock gate (fun () ->
            match NetworkAuthority.verifyReplay () with
            | Ok(ReplayRunOutcome.Completed(_, replayed)) -> Ok(replayed = state)
            | Ok(ReplayRunOutcome.Cancelled(index, _)) -> Error $"replay unexpectedly cancelled at {index}"
            | Ok(ReplayRunOutcome.Diverged divergence) -> Error $"replay diverged at {divergence.EventIndex}"
            | Ok(ReplayRunOutcome.ContractRefused(index, issue)) -> Error $"replay contract refused event {index}: {issue}"
            | Error issues -> Error(sprintf "%A" issues))
#else
        Ok true
#endif

    /// Commits the complete input frontier deterministically, then advances time once.
    /// `ConcurrentDictionary` is only the admission buffer; its enumeration order is
    /// deliberately never a game rule.
    let advanceTick () : Snapshot =
        lock gate (fun () ->
            pruneExpiredLocked DateTimeOffset.UtcNow
            let frontier =
                pending.Values
                |> Seq.sortBy (fun input -> input.AcceptedOrder)
                |> Seq.toList
            pending.Clear()
            for input in frontier do
                let intent =
                    match input.Action with
                    | "restart" -> FableGameWorkspaceNamespace.ArenaRules.Intent.Restart
                    | "interact" -> FableGameWorkspaceNamespace.ArenaRules.Intent.Interact
                    | "legacy-move" -> FableGameWorkspaceNamespace.ArenaRules.Intent.LegacyMove { Col = input.TargetCol; Row = input.TargetRow }
                    | _ -> FableGameWorkspaceNamespace.ArenaRules.Intent.Move { Col = input.TargetCol; Row = input.TargetRow }
                state <- FableGameWorkspaceNamespace.ArenaRules.applyIntent input.PlayerId intent state
#if SVG_NETWORK_CANDIDATE
                NetworkAuthority.recordIntent input.PlayerId intent state
#endif
            state <- FableGameWorkspaceNamespace.ArenaRules.advance state
            let snapshot = snapshotLocked ()
#if SVG_NETWORK_CANDIDATE
            NetworkAuthority.recordAdvance (uint64 state.Room.Tick) state
            NetworkAuthority.publish (uint64 state.Room.Tick) state
#endif
            completeSnapshotLocked ())
