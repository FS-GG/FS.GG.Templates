namespace FableGameWorkspaceNamespace.Server

open System.Collections.Concurrent
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain

/// The single authoritative room this minimal template hosts, wrapping
/// `FableGameWorkspaceNamespace.Domain.Room` with the mutable, concurrency-safe shell an
/// ASP.NET Core process needs. A generated product that needs many concurrent rooms
/// swaps this module for a keyed registry; the pure decision logic underneath (in
/// `Domain/Room.fs`) does not change. The template stays honestly minimal per #348's
/// acceptance: "a minimal playable server-authoritative sample".
[<RequireQualifiedAccess>]
module RoomAuthority =

    [<Literal>]
    let ArenaWidth = 20

    [<Literal>]
    let ArenaHeight = 12

    [<Literal>]
    let RoomId = "arena-1"

    let mutable private state = Room.create ArenaWidth ArenaHeight

    /// The last-accepted input sequence per player -- the stale-input guard.
    let private lastSequence = ConcurrentDictionary<string, int>()

    /// All state mutation is serialised through this lock. Hub methods for different
    /// connections run concurrently (ASP.NET Core does not serialise them), so every
    /// authoritative read-modify-write below takes it -- this is what "authoritative"
    /// means operationally, not just narratively.
    let private gate = obj ()

    /// Test-only reset. `RoomAuthority`'s authoritative state is deliberately process-wide
    /// static state, not scoped per `WebApplicationFactory` host -- so two hosts created in
    /// the same test process (as `Server.Tests` does, one per test method) still share one
    /// room unless a test resets it first. A real multi-room product replaces this whole
    /// module with a keyed, per-room-scoped registry instead of reaching for this escape
    /// hatch; the template stays intentionally minimal (see module doc).
    let resetForTests () : unit =
        lock gate (fun () ->
            state <- Room.create ArenaWidth ArenaHeight
            lastSequence.Clear())

    /// Idempotent by design: both the HTTP bootstrap endpoint and `GameHub.OnConnectedAsync`
    /// call `join` for the *same* playerId (bootstrap registers the identity; the
    /// subsequent SignalR connect only needs to confirm/rejoin it, never to reassign a
    /// fresh spawn). Recomputing a spawn on every call was a real bug caught by
    /// `Browser.Tests/two-client.spec.ts` running flaky: the second call's own
    /// occupancy scan saw the player's *own* first-call cell as "taken by someone
    /// else" (nothing had removed it) and skipped forward to the next free cell,
    /// silently shifting every player by one cell on each reconnect/re-join.
    let join (playerId: string) : Cell =
        lock gate (fun () ->
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
                spawn)

    let leave (playerId: string) : unit =
        lock gate (fun () ->
            state <- Room.leave playerId state
            lastSequence.TryRemove playerId |> ignore)

    /// The stale-input / backpressure guard: an input whose sequence does not
    /// strictly increase past the last *accepted* sequence for this player is
    /// dropped -- out-of-order delivery, a duplicate retransmit, or a burst of
    /// buffered input arriving after a newer one already committed can never move a
    /// player backwards in time. Returns `true` iff the input was accepted and applied.
    let submitInput (playerId: string) (sequence: int) (targetCol: int) (targetRow: int) : bool =
        lock gate (fun () ->
            let accepted =
                match lastSequence.TryGetValue playerId with
                | true, last -> sequence > last
                | false, _ -> false // unknown player: no join was ever recorded, never authoritative
            if accepted then
                lastSequence.[playerId] <- sequence
                // `Room.planMove`'s path is endpoint-inclusive: its head is the player's
                // *current* cell (see FS.GG.Game.Core.Pathfinding.astar), not the first
                // step. The second element, if any, is the one authoritative step this
                // tick commits.
                match Room.planMove playerId { Col = targetCol; Row = targetRow } state with
                | Some(_ :: next :: _) -> state <- Room.applyStep playerId next state
                | _ -> ()
            accepted)

    let snapshot () : int * (string * int * int) list =
        lock gate (fun () -> state.Tick, Room.toSnapshotPairs state)

    let advanceTick () : unit = lock gate (fun () -> state <- Room.advanceTick state)
