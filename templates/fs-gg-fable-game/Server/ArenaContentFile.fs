namespace FableGameWorkspaceNamespace.Server

open System
open System.IO
open System.Text.Json
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.ArenaContent

[<CLIMutable>]
type ArenaContentFileV2 =
    { SchemaVersion: int
      ContentId: string
      BoundaryX: float
      BoundaryY: float
      BoundaryWidth: float
      BoundaryHeight: float
      SpawnCol: int
      SpawnRow: int
      CollectibleX: float
      CollectibleY: float
      HazardX: float
      HazardY: float
      HazardWidth: float
      HazardHeight: float
      GoalX: float
      GoalY: float
      GoalWidth: float
      GoalHeight: float
      ThinWallX: float
      ThinWallY: float
      ThinWallWidth: float
      ThinWallHeight: float }

[<RequireQualifiedAccess>]
module ArenaContentFile =
    let private finite value = not (Double.IsNaN value || Double.IsInfinity value)
    let private positive value = finite value && value > 0.0

    let decode (json: string) =
        try
            let value = JsonSerializer.Deserialize<ArenaContentFileV2>(json, JsonSerializerOptions(PropertyNameCaseInsensitive = true))
            if isNull (box value) then Error "arena content is empty"
            elif value.SchemaVersion <> 2 && value.SchemaVersion <> 3 then Error $"unsupported arena content schema {value.SchemaVersion}"
            elif String.IsNullOrWhiteSpace value.ContentId || not (value.ContentId.StartsWith("continuous-arena/", StringComparison.Ordinal)) then Error "arena content id must use continuous-arena/"
            elif value.SchemaVersion = 3 && not ([ value.BoundaryX; value.BoundaryY; value.BoundaryWidth; value.BoundaryHeight ] |> List.forall finite) then Error "arena content contains a non-finite boundary"
            elif value.SchemaVersion = 3 && (value.BoundaryX <> 0.0 || value.BoundaryY <> 0.0 || value.BoundaryWidth <> arenaWidth || value.BoundaryHeight <> arenaHeight) then Error "arena content boundary is outside the supported 220x120 grid envelope"
            elif value.SchemaVersion = 3 && (value.SpawnCol < 0 || value.SpawnCol >= arenaColumns || value.SpawnRow < 0 || value.SpawnRow >= arenaRows) then Error "arena content contains an invalid spawn"
            elif not ([ value.CollectibleX; value.CollectibleY; value.HazardX; value.HazardY; value.GoalX; value.GoalY; value.ThinWallX; value.ThinWallY ] |> List.forall finite) then Error "arena content contains a non-finite position"
            elif not ([ value.HazardWidth; value.HazardHeight; value.GoalWidth; value.GoalHeight; value.ThinWallWidth; value.ThinWallHeight ] |> List.forall positive) then Error "arena content contains an invalid collider size"
            else
                Ok
                    { SchemaVersion = value.SchemaVersion
                      ContentId = value.ContentId
                      Boundary = if value.SchemaVersion = 3 then { X = value.BoundaryX; Y = value.BoundaryY; Width = value.BoundaryWidth; Height = value.BoundaryHeight } else (contentAt 0UL).Boundary
                      Spawn = if value.SchemaVersion = 3 then { Col = value.SpawnCol; Row = value.SpawnRow } else (contentAt 0UL).Spawn
                      CollectibleX = value.CollectibleX
                      CollectibleY = value.CollectibleY
                      Hazard = { X = value.HazardX; Y = value.HazardY; Width = value.HazardWidth; Height = value.HazardHeight }
                      Goal = { X = value.GoalX; Y = value.GoalY; Width = value.GoalWidth; Height = value.GoalHeight }
                      ThinWall = { X = value.ThinWallX; Y = value.ThinWallY; Width = value.ThinWallWidth; Height = value.ThinWallHeight } }
        with error -> Error("arena content JSON refused: " + error.Message)

    let load path = File.ReadAllText path |> decode
