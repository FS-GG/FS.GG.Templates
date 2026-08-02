namespace FableGameWorkspaceNamespace.Domain

open FS.GG.Game.Core

/// Product-owned, pure, server-only domain: the authoritative multiplayer arena.
/// This project is never Fable-compiled -- it owns the domain model, not the wire
/// boundary. The wire boundary to the browser is `FableGameWorkspaceNamespace.Protocol`
/// (see ../Protocol), which maps this domain explicitly to/from versioned DTOs; nothing
/// here is assumed serializer-compatible.
[<RequireQualifiedAccess>]
module Room =

    /// Bound so an adversarial or buggy client cannot make pathfinding scan unbounded
    /// state; matches the arena's own cell budget for the walkable predicate below.
    let private maxVisited = 4096

    type PlayerState = { PlayerId: string; Cell: Cell }

    type State =
        { Tick: int
          Width: int
          Height: int
          Players: Map<string, PlayerState> }

    /// The authoritative walkability predicate: everything inside the arena bounds and
    /// not currently occupied by another player. Deterministic given `state.Players`,
    /// which is why the server can safely recompute it every `planMove` call rather than
    /// caching it -- caching a walkability predicate against a `Map` that changes under it
    /// is a stale-state trap the server never risks.
    /// `excludePlayerId` leaves the mover's own current cell out of the occupied set --
    /// without it, a player's own cell would make its own start cell "unwalkable" and
    /// `Pathfinding.astar` (which requires `isWalkable start`) would never find a route
    /// for anyone, including a player who has not moved at all.
    let private walkable (excludePlayerId: string) (state: State) : Cell -> bool =
        let occupied =
            state.Players
            |> Map.toSeq
            |> Seq.filter (fun (id, _) -> id <> excludePlayerId)
            |> Seq.map (fun (_, p) -> p.Cell)
            |> Set.ofSeq
        fun cell ->
            cell.Col >= 0 && cell.Col < state.Width
            && cell.Row >= 0 && cell.Row < state.Height
            && not (occupied.Contains cell)

    let create (width: int) (height: int) : State =
        { Tick = 0; Width = width; Height = height; Players = Map.empty }

    let join (playerId: string) (spawn: Cell) (state: State) : State =
        { state with Players = state.Players |> Map.add playerId { PlayerId = playerId; Cell = spawn } }

    let leave (playerId: string) (state: State) : State =
        { state with Players = state.Players |> Map.remove playerId }

    /// Authoritative move planning: an A* path from the player's current cell to
    /// `target` over the current occupancy. `None` means "no player" or "no route" --
    /// callers treat both the same way (the input is simply not honoured this tick).
    ///
    /// `Pathfinding.astar` is `LockstepExact` under profile
    /// `fs-gg-game-core-fable-lockstep-v1`: the Fable client (`Client/Movement.fs`) calls
    /// the *same* published package function to render a local path preview, so client
    /// prediction never runs logic the server does not also run byte-identically -- it is
    /// still only ever a preview, because this function (the authoritative recomputation)
    /// is what actually commits movement.
    let planMove (playerId: string) (target: Cell) (state: State) : Cell list option =
        state.Players
        |> Map.tryFind playerId
        |> Option.bind (fun player -> Pathfinding.astar Neighbourhood.FourWay maxVisited (walkable playerId state) player.Cell target)

    /// Commits one authoritative step of movement for `playerId`, ignoring unknown
    /// players and steps landing on an already-occupied or out-of-bounds cell (the
    /// planned path may have been invalidated by another player's own step landing on
    /// the same cell earlier in the same tick).
    let applyStep (playerId: string) (next: Cell) (state: State) : State =
        match state.Players |> Map.tryFind playerId with
        | Some player when (walkable playerId state) next -> { state with Players = state.Players |> Map.add playerId { player with Cell = next } }
        | _ -> state

    let advanceTick (state: State) : State = { state with Tick = state.Tick + 1 }

    let toSnapshotPairs (state: State) : (string * int * int) list =
        state.Players |> Map.toList |> List.map (fun (id, p) -> id, p.Cell.Col, p.Cell.Row)
