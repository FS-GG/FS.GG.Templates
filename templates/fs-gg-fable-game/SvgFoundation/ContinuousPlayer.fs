module FableGameWorkspaceNamespace.SvgFoundation.ContinuousPlayer

open FS.GG.Game.Core
open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.ArenaContent

[<RequireQualifiedAccess>]
type PlayerOutcome =
    | Playing
    | Won
    | Lost

[<RequireQualifiedAccess>]
type PlayerCommand =
    | Move of x: float * y: float
    | Stop
    | Damage
    | Collect

type PlayerState =
    { Player: FS.GG.Game.Core.Rect
      Velocity: FS.GG.Game.Core.Point
      Health: int
      Score: int
      Collected: int
      Outcome: PlayerOutcome
      Revision: uint64 }

let compatibility =
    { ContractVersion = 1
      EngineId = "fs-gg.svg-continuous-player"
      EngineVersion = "1"
      ProfileId = "generated-player"
      SchemaId = "continuous-arena"
      SchemaVersion = 1 }

let private initialState revision =
    { Player = { X = playerStartX; Y = playerStartY; Width = 10.0; Height = 10.0 }
      Velocity = { X = 0.0; Y = 0.0 }
      Health = 2
      Score = 0
      Collected = 0
      Outcome = PlayerOutcome.Playing
      Revision = revision }

let private colliders revision =
    [ { Id = "collectible"
        Shape = KinematicShape.AxisAlignedBox { X = collectibleX - 5.0; Y = collectibleY - 5.0; Width = 10.0; Height = 10.0 }
        Response = KinematicResponse.Trigger }
      { Id = "hazard"
        Shape = KinematicShape.AxisAlignedBox { X = movingHazardX revision; Y = hazardY; Width = 18.0; Height = 18.0 }
        Response = KinematicResponse.Trigger }
      { Id = "goal"
        Shape = KinematicShape.AxisAlignedBox { X = goalX; Y = goalY; Width = 20.0; Height = 24.0 }
        Response = KinematicResponse.Trigger }
      { Id = "thin-wall"
        Shape = KinematicShape.AxisAlignedBox { X = 112.0; Y = 0.0; Width = 2.0; Height = 48.0 }
        Response = KinematicResponse.Slide } ]

let private bound low high value = max low (min high value)

let private advanceOnce state =
    if state.Outcome <> PlayerOutcome.Playing then state
    else
        let motion = { Bounds = state.Player; Displacement = state.Velocity }
        let result = Kinematics.advance 24.0 motion (colliders state.Revision)
        let ids = result.Hits |> List.map _.ColliderId |> Set.ofList
        let collected = if Set.contains "collectible" ids then max 1 state.Collected else state.Collected
        let health = if Set.contains "hazard" ids then max 0 (state.Health - 1) else state.Health
        let score = if collected > state.Collected then state.Score + 100 else state.Score
        let outcome =
            if health = 0 then PlayerOutcome.Lost
            elif Set.contains "goal" ids && collected > 0 then PlayerOutcome.Won
            else PlayerOutcome.Playing
        { state with
            Player =
                { result.Bounds with
                    X = bound 0.0 (arenaWidth - 10.0) result.Bounds.X
                    Y = bound 0.0 (arenaHeight - 10.0) result.Bounds.Y }
            Health = health
            Score = score
            Collected = collected
            Outcome = outcome
            Revision = state.Revision + 1UL }

let private applyCommand command state =
    if state.Outcome <> PlayerOutcome.Playing then state
    else
        match command with
        | PlayerCommand.Move(x, y) -> { state with Velocity = { X = x; Y = y }; Revision = state.Revision + 1UL }
        | PlayerCommand.Stop -> { state with Velocity = { X = 0.0; Y = 0.0 }; Revision = state.Revision + 1UL }
        | PlayerCommand.Damage ->
            let health = max 0 (state.Health - 1)
            { state with
                Health = health
                Outcome = (if health = 0 then PlayerOutcome.Lost else state.Outcome)
                Revision = state.Revision + 1UL }
        | PlayerCommand.Collect ->
            { state with Collected = 1; Score = state.Score + 100; Outcome = PlayerOutcome.Won; Revision = state.Revision + 1UL }

let contract: SessionContract<unit, PlayerState, PlayerCommand, PlayerState, PlayerState> =
    { Initialize = fun _ -> Ok(initialState 1UL)
      AdmitInput = fun input state -> Ok(applyCommand input.Value state)
      Advance = fun value state ->
          let mutable current = state
          for _ in 1UL .. value.StepCount do current <- advanceOnce current
          Ok current
      Project = fun state -> { SessionId = "generated-player"; Revision = state.Revision; Value = state }
      Snapshot = fun state -> { SessionId = "generated-player"; Revision = state.Revision; Compatibility = compatibility; Value = state }
      Restore = fun snapshot -> Ok snapshot.Value }

let initialize () =
    SessionRuntime.initialize
        { StepMicroseconds = 16_667UL; MaxCatchUpSteps = 4u }
        contract
        { SessionId = "generated-player"; Compatibility = compatibility; Configuration = () }
    |> Result.defaultWith (fun error -> failwithf "Generated continuous player could not initialize: %A" error)

let private color red green blue = { Red = red; Green = green; Blue = blue; Alpha = 255uy }

let private objectValue id label selectable nodes =
    { Id = id; Selectable = selectable; AccessibleLabel = label; Content = { Nodes = nodes } }

let scene revision state =
    let outcome =
        match state.Outcome with
        | PlayerOutcome.Playing -> "playing"
        | PlayerOutcome.Won -> "won"
        | PlayerOutcome.Lost -> "lost"
    { RootId = "foundation-continuous-player"
      Revision = int revision
      Camera = { PanX = 0.0; PanY = 0.0; Zoom = 1.0 }
      Layers =
        [ { Id = "arena"
            Visible = true
            Objects =
              [ objectValue "arena" "Continuous arena" false [ SceneNode.Rectangle((0.0, 0.0, arenaWidth, arenaHeight), color 241uy 245uy 249uy) ]
                objectValue "thin-wall" "Thin wall" false [ SceneNode.Rectangle((112.0, 0.0, 2.0, 48.0), color 71uy 85uy 105uy) ]
                objectValue "collectible" "Collectible" true [ SceneNode.Circle({ X = collectibleX; Y = collectibleY }, 5.0, color 245uy 158uy 11uy) ]
                objectValue "hazard" "Moving hazard" true
                    [ SceneNode.Rectangle((movingHazardX state.Revision, hazardY, 18.0, 18.0), color 220uy 38uy 38uy) ]
                objectValue "goal" "Goal" true [ SceneNode.Rectangle((goalX, goalY, 20.0, 24.0), color 22uy 163uy 74uy) ]
                objectValue "player" $"Player, {outcome}, health {state.Health}, score {state.Score}" true
                    [ SceneNode.Rectangle((state.Player.X, state.Player.Y, state.Player.Width, state.Player.Height), color 37uy 99uy 235uy) ] ] } ] }
