module FableGameWorkspaceNamespace.ArcadeRules

open FS.GG.Game.Core
open FableGameWorkspaceNamespace.ArenaContent

type ArcadeContent =
    { Id: string
      ContentId: string
      Width: float
      Height: float
      Spawn: Rect
      InitialHealth: int
      CollectibleX: float
      CollectibleY: float
      CollectibleScore: int
      Hazard: Rect
      HazardVelocity: float
      HazardDamage: int
      Goal: Rect }

[<RequireQualifiedAccess>]
type ArcadeOutcome = Playing | Won | Lost

type ArcadeState =
    { Player: Rect
      Velocity: Point
      Health: int
      Score: int
      Collected: bool
      Outcome: ArcadeOutcome
      HazardX: float
      HazardDirection: float
      HazardContact: bool
      Content: ArcadeContent
      Revision: uint64 }

[<RequireQualifiedAccess>]
type ArcadeCommand = SetVelocity of Point | Interact | Restart

let initialState content =
    { Player = content.Spawn; Velocity = { X = 0.0; Y = 0.0 }; Health = content.InitialHealth
      Score = 0; Collected = false; Outcome = ArcadeOutcome.Playing; HazardX = content.Hazard.X
      HazardDirection = 1.0; HazardContact = false; Content = content; Revision = 1UL }

let private overlaps (a: Rect) (b: Rect) =
    a.X < b.X + b.Width && a.X + a.Width > b.X && a.Y < b.Y + b.Height && a.Y + a.Height > b.Y

let advanceOnce state =
    if state.Outcome <> ArcadeOutcome.Playing then state else
    let content = state.Content
    let minimum, maximum = content.Hazard.X, content.Hazard.X + 60.0
    let proposed = state.HazardX + content.HazardVelocity * state.HazardDirection
    let hazardX, direction =
        if proposed > maximum then maximum, -1.0
        elif proposed < minimum then minimum, 1.0
        else proposed, state.HazardDirection
    let movingHazard = { content.Hazard with X = hazardX }
    let collider id response bounds = { Id = id; Shape = KinematicShape.AxisAlignedBox bounds; Response = response }
    let colliders =
        [ collider "arcade-hazard" KinematicResponse.Trigger movingHazard
          collider "arcade-boundary-left" KinematicResponse.Slide { X = -content.Width; Y = -content.Height; Width = content.Width; Height = content.Height * 3.0 }
          collider "arcade-boundary-right" KinematicResponse.Slide { X = content.Width; Y = -content.Height; Width = content.Width; Height = content.Height * 3.0 }
          collider "arcade-boundary-top" KinematicResponse.Slide { X = 0.0; Y = -content.Height; Width = content.Width; Height = content.Height }
          collider "arcade-boundary-bottom" KinematicResponse.Slide { X = 0.0; Y = content.Height; Width = content.Width; Height = content.Height } ]
    let moved = Kinematics.advance 3.0 { Bounds = state.Player; Displacement = state.Velocity } colliders
    let contact = overlaps moved.Bounds movingHazard || (moved.Hits |> List.exists (fun hit -> hit.ColliderId = "arcade-hazard"))
    let health = if contact && not state.HazardContact then max 0 (state.Health - content.HazardDamage) else state.Health
    { state with Player = moved.Bounds; Health = health
                 Outcome = if health = 0 then ArcadeOutcome.Lost else state.Outcome
                 HazardX = hazardX; HazardDirection = direction; HazardContact = contact
                 Revision = state.Revision + 1UL }

let applyCommand command state =
    match command with
    | ArcadeCommand.Restart -> initialState state.Content
    | _ when state.Outcome <> ArcadeOutcome.Playing -> state
    | ArcadeCommand.SetVelocity velocity -> { state with Velocity = velocity; Revision = state.Revision + 1UL }
    | ArcadeCommand.Interact ->
        let near x y = abs (state.Player.X + 5.0 - x) <= 8.0 && abs (state.Player.Y + 5.0 - y) <= 8.0
        if not state.Collected && near state.Content.CollectibleX state.Content.CollectibleY then
            { state with Collected = true; Score = state.Score + state.Content.CollectibleScore; Revision = state.Revision + 1UL }
        elif state.Collected && overlaps state.Player state.Content.Goal then
            { state with Outcome = ArcadeOutcome.Won; Velocity = { X = 0.0; Y = 0.0 }; Revision = state.Revision + 1UL }
        else { state with Revision = state.Revision + 1UL }

let compatibilityFor content =
    { ContractVersion = 1; EngineId = "fs-gg.svg-continuous-arcade"; EngineVersion = "1"
      ProfileId = content.ContentId; SchemaId = content.Id; SchemaVersion = 1 }

let contractForDefinition content : SessionContract<unit, ArcadeState, ArcadeCommand, ArcadeState, ArcadeState> =
    let compatibility = compatibilityFor content
    { Initialize = fun initialization ->
          if initialization.SessionId <> content.Id || initialization.Compatibility <> compatibility then
              Error { Code = "arcade.initialize.identity"; Message = "arcade session identity mismatch" }
          else Ok(initialState content)
      AdmitInput = fun input state ->
          if input.SessionId <> content.Id then Error { Code = "arcade.input.session"; Message = "arcade input session mismatch" }
          else Ok(applyCommand input.Value state)
      Advance = fun value state ->
          if value.SessionId <> content.Id then Error { Code = "arcade.advance.session"; Message = "arcade advance session mismatch" }
          else
              let mutable current = state
              for _ in 1UL .. value.StepCount do current <- advanceOnce current
              Ok current
      Project = fun state -> { SessionId = content.Id; Revision = state.Revision; Value = state }
      Snapshot = fun state -> { SessionId = content.Id; Revision = state.Revision; Compatibility = compatibility; Value = state }
      Restore = fun snapshot ->
          if snapshot.SessionId <> content.Id then Error { Code = "arcade.snapshot.session"; Message = "arcade snapshot session mismatch" }
          elif snapshot.Compatibility <> compatibility then Error { Code = "arcade.snapshot.compatibility"; Message = "arcade snapshot compatibility mismatch" }
          elif snapshot.Value.Content <> content then Error { Code = "arcade.snapshot.content"; Message = "arcade snapshot content mismatch" }
          else Ok snapshot.Value }

let canonicalState state =
    let outcome = match state.Outcome with ArcadeOutcome.Playing -> "playing" | ArcadeOutcome.Won -> "won" | ArcadeOutcome.Lost -> "lost"
    let boolean value = if value then "true" else "false"
    let point (value: Point) = $"{canonicalFloat value.X},{canonicalFloat value.Y}"
    let rect (value: Rect) = $"{canonicalFloat value.X},{canonicalFloat value.Y},{canonicalFloat value.Width},{canonicalFloat value.Height}"
    let content = state.Content
    let immutable =
        $"{content.Id}|{content.ContentId}|{canonicalFloat content.Width},{canonicalFloat content.Height}|{rect content.Spawn}|{content.InitialHealth}|{canonicalFloat content.CollectibleX},{canonicalFloat content.CollectibleY},{content.CollectibleScore}|{rect content.Hazard},{canonicalFloat content.HazardVelocity},{content.HazardDamage}|{rect content.Goal}"
    $"arcade/v1|{immutable}|{rect state.Player}|{point state.Velocity}|{state.Health}|{state.Score}|{boolean state.Collected}|{outcome}|{canonicalFloat state.HazardX}|{canonicalFloat state.HazardDirection}|{boolean state.HazardContact}|{state.Revision}"
