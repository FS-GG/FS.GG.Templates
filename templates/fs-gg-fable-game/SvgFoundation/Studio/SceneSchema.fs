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
    { Schema = SvgDocument.schema
      Id = "continuous-arena"
      ViewBox = { X = 0.0; Y = 0.0; Width = arenaWidth; Height = arenaHeight }
      Definitions = []
      Children =
        [ leaf "arena" [ SceneNode.Rectangle((0.0, 0.0, arenaWidth, arenaHeight), color 241uy 245uy 249uy) ]
          leaf "collectible" [ SceneNode.Circle({ X = collectibleX; Y = collectibleY }, 5.0, color 245uy 158uy 11uy) ]
          leaf "hazard" [ SceneNode.Rectangle((movingHazardX 1UL, hazardY, 18.0, 18.0), color 220uy 38uy 38uy) ]
          leaf "goal" [ SceneNode.Rectangle((goalX, goalY, 20.0, 24.0), color 22uy 163uy 74uy) ]
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
