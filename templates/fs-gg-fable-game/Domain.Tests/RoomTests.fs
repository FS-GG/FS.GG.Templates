module FableGameWorkspaceNamespace.Domain.Tests.RoomTests

open Xunit
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain

[<Fact>]
let ``join adds a player at the spawn cell`` () =
    let state = Room.create 10 10 |> Room.join "p-1" { Col = 2; Row = 3 }
    Assert.Equal({ Col = 2; Row = 3 }, state.Players.["p-1"].Cell)

[<Fact>]
let ``leave removes the player`` () =
    let state =
        Room.create 10 10
        |> Room.join "p-1" { Col = 0; Row = 0 }
        |> Room.leave "p-1"
    Assert.False(state.Players.ContainsKey "p-1")

[<Fact>]
let ``planMove returns a path for an unoccupied straight line`` () =
    let state = Room.create 10 10 |> Room.join "p-1" { Col = 0; Row = 0 }
    match Room.planMove "p-1" { Col = 3; Row = 0 } state with
    | Some path -> Assert.Equal({ Col = 3; Row = 0 }, List.last path)
    | None -> Assert.Fail "expected a route across an empty arena"

[<Fact>]
let ``planMove returns None for an unknown player`` () =
    let state = Room.create 10 10
    Assert.Equal(None, Room.planMove "ghost" { Col = 1; Row = 1 } state)

[<Fact>]
let ``applyStep is authoritative: it refuses a step onto another player's cell`` () =
    let state =
        Room.create 10 10
        |> Room.join "p-1" { Col = 0; Row = 0 }
        |> Room.join "p-2" { Col = 1; Row = 0 }
    let after = Room.applyStep "p-1" { Col = 1; Row = 0 } state
    // The step is rejected: p-1 stays put rather than overlapping p-2, even though the
    // caller (e.g. a stale client-planned path) asked for it.
    Assert.Equal({ Col = 0; Row = 0 }, after.Players.["p-1"].Cell)

[<Fact>]
let ``applyStep commits a legal step`` () =
    let state = Room.create 10 10 |> Room.join "p-1" { Col = 0; Row = 0 }
    let after = Room.applyStep "p-1" { Col = 1; Row = 0 } state
    Assert.Equal({ Col = 1; Row = 0 }, after.Players.["p-1"].Cell)

[<Fact>]
let ``advanceTick increments monotonically`` () =
    let state = Room.create 5 5 |> Room.advanceTick |> Room.advanceTick
    Assert.Equal(2, state.Tick)

[<Fact>]
let ``toSnapshotPairs reflects every joined player`` () =
    let state =
        Room.create 5 5
        |> Room.join "p-1" { Col = 0; Row = 0 }
        |> Room.join "p-2" { Col = 4; Row = 4 }
    let pairs = Room.toSnapshotPairs state |> List.sort
    Assert.Equal<(string * int * int) list>([ "p-1", 0, 0; "p-2", 4, 4 ], pairs)
