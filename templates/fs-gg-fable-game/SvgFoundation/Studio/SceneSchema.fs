module FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema

open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.ArenaContent

let descriptors =
    [ { KindId = "sample.terrain"
        DisplayName = "Terrain region"
        Properties =
            [ { Key = "terrain"; Kind = SvgScenePropertyKind.Text; Required = true }
              { Key = "cost"; Kind = SvgScenePropertyKind.Number; Required = true } ] }
      { KindId = "sample.boundary"
        DisplayName = "Boundary"
        Properties = [ { Key = "closed"; Kind = SvgScenePropertyKind.Flag; Required = true } ] }
      { KindId = "sample.object"
        DisplayName = "Object"
        Properties =
            [ { Key = "position"; Kind = SvgScenePropertyKind.Coordinate; Required = true }
              { Key = "label"; Kind = SvgScenePropertyKind.Text; Required = false } ] } ]

/// Product-owned grid adapter: region and boundary meaning stays outside Rendering.
let gridAdapter existing =
    { existing with
        Grid = Some { Origin = { X = 3.0; Y = 5.0 }; Step = { X = 8.0; Y = 8.0 } }
        Entities =
            existing.Entities @
            [ { EntityId = "sample-grid-region"
                KindId = "sample.terrain"
                VisualElementId = None
                PrefabInstanceId = Some "sample-instance-a"
                Properties =
                    [ { Key = "terrain"; Value = SvgScenePropertyValue.Text "walkable" }
                      { Key = "cost"; Value = SvgScenePropertyValue.Number 1.0 } ] }
              { EntityId = "sample-grid-boundary"
                KindId = "sample.boundary"
                VisualElementId = None
                PrefabInstanceId = Some "sample-instance-a"
                Properties = [ { Key = "closed"; Value = SvgScenePropertyValue.Flag true } ] } ] }

/// Product-owned continuous adapter: fractional placement remains exact scene metadata.
let continuousAdapter existing =
    { existing with
        Entities =
            existing.Entities @
            [ { EntityId = "sample-freeform-object"
                KindId = "sample.object"
                VisualElementId = None
                PrefabInstanceId = Some "sample-instance-b"
                Properties =
                    [ { Key = "position"; Value = SvgScenePropertyValue.Coordinate { X = 121.375; Y = 66.625 } }
                      { Key = "label"; Value = SvgScenePropertyValue.Text "freeform" } ] } ] }

let private color red green blue = { Red = red; Green = green; Blue = blue; Alpha = 255uy }

let private leaf id nodes =
    { Id = id
      SemanticId = Some("arena:" + id)
      Visible = true
      Transform = SvgAffine.identity
      ClipId = None
      MaskId = None
      Presentation = None
      Content = SvgElementContent.SceneLeaf { Nodes = nodes } }

/// The Studio opens the same editable arena content used by the production player.
let arenaDocument =
    let content = contentAt 1UL
    { Schema = SvgDocument.schema
      Id = "continuous-arena"
      ViewBox = { X = 0.0; Y = 0.0; Width = arenaWidth; Height = arenaHeight }
      Definitions = []
      Children =
        [ leaf "arena" [ SceneNode.Rectangle((0.0, 0.0, arenaWidth, arenaHeight), color 241uy 245uy 249uy) ]
          leaf "collectible" [ SceneNode.Circle({ X = content.CollectibleX; Y = content.CollectibleY }, 5.0, color 245uy 158uy 11uy) ]
          leaf "hazard" [ SceneNode.Rectangle((content.Hazard.X, content.Hazard.Y, content.Hazard.Width, content.Hazard.Height), color 220uy 38uy 38uy) ]
          leaf "goal" [ SceneNode.Rectangle((content.Goal.X, content.Goal.Y, content.Goal.Width, content.Goal.Height), color 22uy 163uy 74uy) ]
          leaf "player" [ SceneNode.Rectangle((playerStartX, playerStartY, 10.0, 10.0), color 37uy 99uy 235uy) ] ] }

let initialState () =
    let metadata =
        { SceneId = "continuous-arena"
          Layers = []
          Entities = []
          Grid = None
          ResourceReferences = [] }
    SvgAuthoring.tryCreateScene 0 metadata arenaDocument { Schema = SvgAsset.catalogSchema; Assets = [] } []
    |> Result.defaultWith (fun error -> failwithf "Initial generated SVG scene refused: %A" error)

let private gameplayElement id (document: SvgDocument) =
    match document.Children |> List.tryFind (fun element -> element.Id = id) with
    | None -> Error($"missing gameplay role {id}")
    | Some element when not (SvgAffine.isFinite element.Transform) -> Error($"gameplay role {id} has a non-finite transform")
    | Some element -> Ok element

let private transformedPoint id point document =
    gameplayElement id document
    |> Result.map (fun element -> SvgAffine.transformPoint element.Transform point)

let private transformedRect id document =
    gameplayElement id document
    |> Result.bind (fun element ->
        match element.Content with
        | SvgElementContent.SceneLeaf leaf ->
            match leaf.Nodes |> List.choose (function SceneNode.Rectangle((x, y, width, height), _) -> Some(x, y, width, height) | _ -> None) with
            | [ x, y, width, height ] ->
                let points =
                    [ { X = x; Y = y }; { X = x + width; Y = y }
                      { X = x; Y = y + height }; { X = x + width; Y = y + height } ]
                    |> List.map (SvgAffine.transformPoint element.Transform)
                let xs = points |> List.map _.X
                let ys = points |> List.map _.Y
                let left, right = List.min xs, List.max xs
                let top, bottom = List.min ys, List.max ys
                if right <= left || bottom <= top then Error($"gameplay role {id} has empty transformed bounds")
                else
                    let bounds: FS.GG.Game.Core.Rect = { X = left; Y = top; Width = right - left; Height = bottom - top }
                    Ok bounds
            | _ -> Error($"gameplay role {id} must contain exactly one rectangle")
        | _ -> Error($"gameplay role {id} must be a scene leaf"))

/// Compile accepted authoring geometry into the product rules model. Gameplay
/// rectangles use their transformed axis-aligned bounds; decorative SVG remains
/// under Rendering without invented rules.
let compileArenaContent (document: SvgDocument) =
    let baseline = contentAt 1UL
    match
        transformedPoint "collectible" { X = baseline.CollectibleX; Y = baseline.CollectibleY } document,
        transformedRect "hazard" document,
        transformedRect "goal" document with
    | Ok collectible, Ok hazard, Ok goal ->
        Ok
            { baseline with
                ContentId = "continuous-arena/" + (SvgAsset.contentHash document |> Result.defaultValue "invalid")
                CollectibleX = collectible.X
                CollectibleY = collectible.Y
                Hazard = hazard
                Goal = goal }
    | Error issue, _, _
    | _, Error issue, _
    | _, _, Error issue -> Error issue
