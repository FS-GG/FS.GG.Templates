namespace FableGameWorkspaceNamespace.Server

open System
open System.Collections.Concurrent
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain

/// The single authoritative room this minimal template hosts. A generated product
/// replaces this module with a keyed room registry; its important baseline invariant
/// remains the same: hub arrival only admits an intent. State changes at the next
/// deterministic tick frontier, never in whatever order transports happen to arrive.
[<RequireQualifiedAccess>]
module RoomAuthority =

    [<Literal>]
    let ArenaWidth = 20

    [<Literal>]
    let ArenaHeight = 12

    [<Literal>]
    let RoomId = "arena-1"

    type private Session =
        { PlayerId: string
          mutable ConnectionId: string option }

    type private PendingInput =
        { PlayerId: string
          Sequence: int
          TargetCol: int
          TargetRow: int }

    let mutable private state = Room.create ArenaWidth ArenaHeight
    let private sessions = ConcurrentDictionary<string, Session>()
    let private lastSequence = ConcurrentDictionary<string, int>()
    let private pending = ConcurrentDictionary<string, PendingInput>()
    let private gate = obj ()

    let private snapshotLocked () = state.Tick, Room.toSnapshotPairs state

    let resetForTests () : unit =
        lock gate (fun () ->
            state <- Room.create ArenaWidth ArenaHeight
            sessions.Clear()
            lastSequence.Clear()
            pending.Clear())

    let private joinLocked (playerId: string) : Cell =
        match state.Players |> Map.tryFind playerId with
        | Some existing -> existing.Cell
        | None ->
            let occupied = state.Players |> Map.toSeq |> Seq.map (fun (_, p) -> p.Cell) |> Set.ofSeq
            let spawn =
                seq {
                    for row in 0 .. ArenaHeight - 1 do
                        for col in 0 .. ArenaWidth - 1 do
                            yield { Col = col; Row = row }
                }
                |> Seq.tryFind (occupied.Contains >> not)
                |> Option.defaultValue { Col = 0; Row = 0 }
            state <- Room.join playerId spawn state
            lastSequence.[playerId] <- 0
            spawn

    /// Creates an opaque bootstrap capability. It is exchanged in the explicit SignalR
    /// hello message, never in a query string, so a URL cannot persist it in logs,
    /// history, referrers, or browser diagnostics. Reserving the spawn preserves the
    /// starter's immediately playable bootstrap behaviour; `joinLocked` is idempotent.
    let createSession (playerId: string) : string * Cell =
        lock gate (fun () ->
            let capability = Guid.NewGuid().ToString "N"
            sessions.[capability] <- { PlayerId = playerId; ConnectionId = None }
            capability, joinLocked playerId)

    /// Binds a just-opened hub connection to exactly one bootstrap-issued capability.
    /// A capability already owned by another live connection is rejected rather than
    /// letting two tabs silently act as one player.
    let activateSession (capability: string) (connectionId: string) : (string * int * (string * int * int) list) option =
        lock gate (fun () ->
            match sessions.TryGetValue capability with
            | true, session when session.ConnectionId |> Option.forall ((=) connectionId) ->
                session.ConnectionId <- Some connectionId
                joinLocked session.PlayerId |> ignore
                let tick, players = snapshotLocked ()
                Some(session.PlayerId, tick, players)
            | _ -> None)

    /// Releases only the transport binding. The player is retired from the room, but
    /// its bootstrap capability can safely complete a later reconnect.
    let disconnect (playerId: string) (connectionId: string) : unit =
        lock gate (fun () ->
            sessions
            |> Seq.iter (fun pair ->
                if pair.Value.PlayerId = playerId && pair.Value.ConnectionId = Some connectionId then
                    pair.Value.ConnectionId <- None)
            state <- Room.leave playerId state
            lastSequence.TryRemove playerId |> ignore
            pending.TryRemove playerId |> ignore)

    /// Queues the highest strictly-increasing input for this player. The accepted
    /// intent is not applied here: every queued player is resolved together at the
    /// next tick frontier in stable player/sequence order.
    let submitInput (playerId: string) (sequence: int) (targetCol: int) (targetRow: int) : bool =
        lock gate (fun () ->
            match lastSequence.TryGetValue playerId with
            | true, last when sequence > last ->
                lastSequence.[playerId] <- sequence
                pending.[playerId] <- { PlayerId = playerId; Sequence = sequence; TargetCol = targetCol; TargetRow = targetRow }
                true
            | _ -> false)

    let snapshot () : int * (string * int * int) list = lock gate snapshotLocked

    /// Commits the complete input frontier deterministically, then advances time once.
    /// `ConcurrentDictionary` is only the admission buffer; its enumeration order is
    /// deliberately never a game rule.
    let advanceTick () : int * (string * int * int) list =
        lock gate (fun () ->
            let frontier =
                pending.Values
                |> Seq.sortBy (fun input -> input.PlayerId, input.Sequence)
                |> Seq.toList
            pending.Clear()
            for input in frontier do
                match Room.planMove input.PlayerId { Col = input.TargetCol; Row = input.TargetRow } state with
                | Some(_ :: next :: _) -> state <- Room.applyStep input.PlayerId next state
                | _ -> ()
            state <- Room.advanceTick state
            snapshotLocked ())
