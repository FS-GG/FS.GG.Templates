module FableGameWorkspaceNamespace.Domain.Tests.RoomTests

open Xunit
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
module ArenaContent = FableGameWorkspaceNamespace.ArenaContent
module ArenaRules = FableGameWorkspaceNamespace.ArenaRules

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

[<Fact>]
let ``edited hazard geometry controls the real collision transition`` () =
    let start: ArenaContent.ArenaCell = { Col = 0; Row = 0 }
    let target: ArenaContent.ArenaCell = { Col = 1; Row = 0 }
    let far = ArenaContent.contentAt 1UL |> ArenaContent.withHazardCell { Col = 18; Row = 10 }
    let initial = ArenaRules.createWith far |> ArenaRules.join "p" ({ Col = 0; Row = 0 }: Cell)
    let farState = ArenaRules.applyIntent "p" (ArenaRules.Intent.Move target) initial
    Assert.Equal(1, farState.Room.Players.["p"].Cell.Col)
    Assert.Equal(3, farState.Status.Health)
    let contact = far |> ArenaContent.withHazardCell target
    let hitState = initial |> ArenaRules.withDefinition contact |> ArenaRules.applyIntent "p" (ArenaRules.Intent.Move target)
    Assert.Equal(1, hitState.Room.Players.["p"].Cell.Col)
    Assert.Equal(2, hitState.Status.Health)
    Assert.Contains("p", hitState.HazardContacts)

[<Fact>]
let ``solid collision retains the atomic source cell`` () =
    let start: ArenaContent.ArenaCell = { Col = 9; Row = 2 }
    let target: ArenaContent.ArenaCell = { Col = 10; Row = 2 }
    let accepted, _, hits = ArenaContent.resolveMove (ArenaContent.contentAt 1UL) start target ArenaContent.initialStatus
    Assert.Equal(start, accepted)
    Assert.Contains("thin-wall", hits)

[<Fact>]
let ``interaction reads accepted content geometry`` () =
    let edited =
        { ArenaContent.contentAt 1UL with
            CollectibleX = ArenaContent.cellX { Col = 2; Row = 3 } + ArenaContent.playerWidth / 2.0
            CollectibleY = ArenaContent.cellY { Col = 2; Row = 3 } + ArenaContent.playerHeight / 2.0 }
    Assert.False((ArenaContent.interact edited { Col = 5; Row = 2 } ArenaContent.initialStatus).Collected)
    let collected = ArenaContent.interact edited { Col = 2; Row = 3 } ArenaContent.initialStatus
    Assert.True(collected.Collected)
    Assert.Equal(100, collected.Score)

[<Fact>]
let ``moving hazard damages a stationary player once per contact`` () =
    let stationary = ArenaRules.create () |> ArenaRules.join "p" ({ Col = 7; Row = 8 }: Cell)
    let entered = ArenaRules.advance stationary
    Assert.Equal(2, entered.Status.Health)
    let retained = ArenaRules.advance entered
    Assert.Equal(2, retained.Status.Health)
    let left = ArenaRules.advance { retained with Room = { retained.Room with Tick = 19 } }
    let reentered = ArenaRules.advance { left with Room = { left.Room with Tick = 139 } }
    Assert.Equal(1, reentered.Status.Health)

[<Fact>]
let ``complete collect win and restart sequence is one pure state transition`` () =
    let content = ArenaContent.contentAt 1UL
    let atCollectible =
        ArenaRules.createWith content
        |> ArenaRules.join "p" ({ Col = ArenaContent.collectibleCell.Col; Row = ArenaContent.collectibleCell.Row }: Cell)
        |> ArenaRules.applyIntent "p" ArenaRules.Intent.Interact
    Assert.Equal((100, true, "playing"), (atCollectible.Status.Score, atCollectible.Status.Collected, atCollectible.Status.Outcome))
    let atGoalRoom =
        { atCollectible.Room with
            Players = atCollectible.Room.Players |> Map.add "p" { PlayerId = "p"; Cell = { Col = ArenaContent.goalCell.Col; Row = ArenaContent.goalCell.Row } } }
    let won = ArenaRules.applyIntent "p" ArenaRules.Intent.Interact { atCollectible with Room = atGoalRoom }
    Assert.Equal("won", won.Status.Outcome)
    let restarted = ArenaRules.applyIntent "p" ArenaRules.Intent.Restart won
    Assert.Equal(ArenaContent.initialStatus, restarted.Status)
    Assert.Equal(2, restarted.Round)
    Assert.Equal(({ Col = 0; Row = 0 }: Cell), restarted.Room.Players.["p"].Cell)

[<Fact>]
let ``terminal outcome remains stable through hazard time until restart`` () =
    let state =
        ArenaRules.create ()
        |> ArenaRules.join "p" ({ Col = 7; Row = 8 }: Cell)
        |> fun current -> { current with Status = { current.Status with Outcome = "won"; Health = 1 } }
        |> ArenaRules.advance
    Assert.Equal("won", state.Status.Outcome)
    Assert.Equal(1, state.Status.Health)

[<Fact>]
let ``V2 restore refuses wrong contract and content identity before effects`` () =
    let state = ArenaRules.create ()
    let saved: SessionSnapshot<ArenaRules.State> =
        { SessionId = "arena-1"; Revision = 0UL; Compatibility = ArenaRules.compatibility; Value = state }
    let wrongContract = { saved with Compatibility = { saved.Compatibility with SchemaVersion = 1 } }
    Assert.True(ArenaRules.contract.Restore wrongContract |> Result.isError)
    let wrongContent = { state with Definition = { state.Definition with ContentId = "continuous-arena/other-valid-export" } }
    Assert.True((ArenaRules.contractFor state.Definition.ContentId).Restore { saved with Value = wrongContent } |> Result.isError)
    let canonical = ArenaRules.canonicalState state
    Assert.Contains(state.Definition.ContentId, canonical)
    Assert.Contains(string state.Definition.SchemaVersion, canonical)
