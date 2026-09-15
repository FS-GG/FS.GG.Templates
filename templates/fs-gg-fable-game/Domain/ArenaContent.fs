module FableGameWorkspaceNamespace.ArenaContent

open System
open FS.GG.Game.Core

type ArenaCell = { Col: int; Row: int }

/// Product-owned arena content shared by the authority, SVG player, and Studio.
type ArenaContent =
    { SchemaVersion: int
      ContentId: string
      Boundary: Rect
      Spawn: ArenaCell
      CollectibleX: float
      CollectibleY: float
      Hazard: Rect
      Goal: Rect
      ThinWall: Rect }

type ArenaStatus =
    { Health: int
      Score: int
      Collected: bool
      Outcome: string }

let arenaColumns = 20
let arenaRows = 12
let cellWidth = 11.0
let cellHeight = 10.0
let arenaWidth = float arenaColumns * cellWidth
let arenaHeight = float arenaRows * cellHeight
let playerWidth = 10.0
let playerHeight = 10.0
let playerStartX = 0.0
let playerStartY = 0.0

/// Lossless portable IEEE-754 identity used anywhere authored gameplay numbers
/// cross the .NET/Fable boundary.
let canonicalFloat (value: float) =
    let hexDigit value = if value < 10 then char (int '0' + value) else char (int 'a' + value - 10)
    let bytes = BitConverter.GetBytes value
    let ordered = if BitConverter.IsLittleEndian then Array.rev bytes else bytes
    ordered
    |> Array.collect (fun value -> [| hexDigit (int value >>> 4); hexDigit (int value &&& 15) |])
    |> String
let collectibleCell = { Col = 5; Row = 2 }
let goalCell = { Col = 16; Row = 5 }
let hazardRow = 8

let cellX cell = float cell.Col * cellWidth
let cellY cell = float cell.Row * cellHeight
let playerBounds cell = { X = cellX cell; Y = cellY cell; Width = playerWidth; Height = playerHeight }
let hazardCell tick = { Col = 7 + int ((tick / 20UL) % 7UL); Row = hazardRow }

let contentAt tick =
    let hazard = hazardCell tick
    { SchemaVersion = 2
      ContentId = "continuous-arena/default-v2"
      Boundary = { X = 0.0; Y = 0.0; Width = arenaWidth; Height = arenaHeight }
      Spawn = { Col = 0; Row = 0 }
      CollectibleX = cellX collectibleCell + playerWidth / 2.0
      CollectibleY = cellY collectibleCell + playerHeight / 2.0
      Hazard = { X = cellX hazard; Y = cellY hazard; Width = cellWidth; Height = cellHeight }
      Goal = { X = cellX goalCell; Y = cellY goalCell; Width = cellWidth; Height = cellHeight }
      ThinWall = { X = 112.0; Y = 0.0; Width = 2.0; Height = 48.0 } }

/// Apply deterministic hazard motion to an accepted authored definition. Editing the
/// base hazard changes both rendering and collision; time never recreates defaults.
let atTick tick content =
    let phase = int ((tick / 20UL) % 7UL)
    { content with Hazard = { content.Hazard with X = content.Hazard.X + float phase * cellWidth } }

let withHazardCell cell content =
    { content with Hazard = { content.Hazard with X = cellX cell; Y = cellY cell } }

let initialStatus = { Health = 3; Score = 0; Collected = false; Outcome = "playing" }

let private overlaps a b =
    a.X < b.X + b.Width && a.X + a.Width > b.X &&
    a.Y < b.Y + b.Height && a.Y + a.Height > b.Y

let hazardContact content cell = overlaps (playerBounds cell) content.Hazard

let interact content cell status =
    let player = playerBounds cell
    let collectible =
        { X = content.CollectibleX - 5.0; Y = content.CollectibleY - 5.0; Width = 10.0; Height = 10.0 }
    if status.Outcome <> "playing" then status
    elif not status.Collected && overlaps player collectible then
        { status with Collected = true; Score = status.Score + 100 }
    elif status.Collected && overlaps player content.Goal then { status with Outcome = "won" }
    else status

let private collider id response bounds =
    { Id = id; Shape = KinematicShape.AxisAlignedBox bounds; Response = response }

/// Resolve one authoritative grid step through Game.Core's collision engine. The
/// returned bounds drive the accepted cell, while trigger hits drive product rules.
let resolveMove content current target status =
    if status.Outcome <> "playing" then current, status, Set.empty
    else
        let motion =
            { Bounds = playerBounds current
              Displacement = { X = cellX target - cellX current; Y = cellY target - cellY current } }
        let boundary = content.Boundary
        let boundaryThickness = max arenaWidth arenaHeight
        let colliders =
            [ collider "collectible" KinematicResponse.Trigger
                { X = content.CollectibleX - 5.0; Y = content.CollectibleY - 5.0; Width = 10.0; Height = 10.0 }
              collider "hazard" KinematicResponse.Trigger content.Hazard
              collider "goal" KinematicResponse.Trigger content.Goal
              collider "thin-wall" KinematicResponse.Slide content.ThinWall
              collider "boundary-left" KinematicResponse.Slide { X = boundary.X - boundaryThickness; Y = boundary.Y - boundaryThickness; Width = boundaryThickness; Height = boundary.Height + boundaryThickness * 2.0 }
              collider "boundary-right" KinematicResponse.Slide { X = boundary.X + boundary.Width; Y = boundary.Y - boundaryThickness; Width = boundaryThickness; Height = boundary.Height + boundaryThickness * 2.0 }
              collider "boundary-top" KinematicResponse.Slide { X = boundary.X; Y = boundary.Y - boundaryThickness; Width = boundary.Width; Height = boundaryThickness }
              collider "boundary-bottom" KinematicResponse.Slide { X = boundary.X; Y = boundary.Y + boundary.Height; Width = boundary.Width; Height = boundaryThickness } ]
        let result = Kinematics.advance 24.0 motion colliders
        let hits = result.Hits |> List.map _.ColliderId |> Set.ofList
        let requested = playerBounds target
        let exact value expected = abs (value - expected) <= 0.000001
        let accepted =
            if exact result.Bounds.X requested.X && exact result.Bounds.Y requested.Y then target
            else current
        accepted, status, hits
