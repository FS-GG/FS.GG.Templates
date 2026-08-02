namespace FableGameWorkspaceNamespace.Client

open FS.GG.Game.Core

/// Client-side movement *preview* only -- never authoritative. Calls the same
/// published `FS.GG.Game.Core` `Pathfinding.astar` (the `LockstepExact` surface under
/// profile `fs-gg-game-core-fable-lockstep-v1`) the server calls in
/// `Server/RoomAuthority.fs`, from the same package, not a copy -- so the preview this
/// module renders and the route the server actually commits agree whenever the two
/// runtimes see the same occupancy. `App.fs` only ever *displays* this result; it
/// never applies it to `Model.Players` -- that only happens when a `SnapshotMessage`
/// arrives from the server (see #348's acceptance: "client prediction is limited to
/// qualified shared logic").
[<RequireQualifiedAccess>]
module Movement =

    let private maxVisited = 4096

    let previewPath (width: int) (height: int) (occupied: Set<Cell>) (start: Cell) (target: Cell) : Cell list option =
        let walkable (cell: Cell) =
            cell.Col >= 0 && cell.Col < width && cell.Row >= 0 && cell.Row < height
            && (cell = start || not (occupied.Contains cell))
        Pathfinding.astar Neighbourhood.FourWay maxVisited walkable start target
