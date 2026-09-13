module FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema

open FS.GG.UI.Scene

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

let emptyDocument =
    { Schema = SvgDocument.schema
      Id = "generated-authoring-scene"
      ViewBox = { X = 0.0; Y = 0.0; Width = 320.0; Height = 180.0 }
      Definitions = []
      Children = [] }

let initialState () =
    let metadata =
        { SceneId = "generated-authoring-scene"
          Layers = []
          Entities = []
          Grid = None
          ResourceReferences = [] }
    SvgAuthoring.tryCreateScene 0 metadata emptyDocument { Schema = SvgAsset.catalogSchema; Assets = [] } []
    |> Result.defaultWith (fun error -> failwithf "Initial generated SVG scene refused: %A" error)
