module FableGameWorkspaceNamespace.TacticalCompatibility

open FS.GG.UI.Scene

/// Product-neutral disclosed object used by the tactical compatibility fixture.
type DisclosedObject =
    { Id: string
      AccessibleLabel: string
      Selectable: bool
      Center: Point
      Radius: float
      Color: Color }

/// Layer policy remains product-owned because locking is not part of the portable renderer contract.
type DisclosedLayer =
    { Id: string
      Order: int
      Visible: bool
      Locked: bool
      Objects: DisclosedObject list }

type DisclosedSelection =
    { SelectedObjectId: string option
      FocusedObjectId: string option }

/// The adapter deliberately accepts disclosed presentation data only.
type DisclosedProjection =
    { RevisionIdentity: string
      Revision: int
      Camera: SvgCamera
      Layers: DisclosedLayer list
      Selection: DisclosedSelection }

type RetainedLayerCharacterization =
    { Id: string
      Order: int
      Visible: bool
      Locked: bool }

type TacticalCompatibilityProjection =
    { RevisionIdentity: string
      Scene: RetainedScene
      Layers: RetainedLayerCharacterization list
      Interaction: RetainedInteractionState }

let private sceneObject (value: DisclosedObject) =
    { Id = value.Id
      Selectable = value.Selectable
      AccessibleLabel = value.AccessibleLabel
      Content = { Nodes = [ SceneNode.Circle(value.Center, value.Radius, value.Color) ] } }

let private retainedLayer (value: DisclosedLayer) =
    { Id = value.Id
      Visible = value.Visible
      Objects = value.Objects |> List.map sceneObject }

let private isVisibleSelectable id (layers: DisclosedLayer list) =
    layers
    |> List.filter (fun layer -> layer.Visible)
    |> List.collect (fun layer -> layer.Objects)
    |> List.exists (fun value -> value.Id = id && value.Selectable)

/// Reimplement the audited disclosed-projection contract against the portable retained scene package.
/// No product domain type, implementation source, dependency or asset enters this fixture.
let project (projection: DisclosedProjection) =
    let orderedLayers = projection.Layers |> List.sortBy (fun layer -> layer.Order)
    let scene =
        { RootId = "tactical-compatibility"
          Revision = projection.Revision
          Camera = projection.Camera
          Layers = orderedLayers |> List.map retainedLayer }
    let retainRelevant value = value |> Option.filter (fun id -> isVisibleSelectable id orderedLayers)
    { RevisionIdentity = projection.RevisionIdentity
      Scene = scene
      Layers =
        orderedLayers
        |> List.map (fun layer ->
            { Id = layer.Id
              Order = layer.Order
              Visible = layer.Visible
              Locked = layer.Locked })
      Interaction =
        { Scene = scene
          SelectedObjectId = retainRelevant projection.Selection.SelectedObjectId
          FocusedObjectId = retainRelevant projection.Selection.FocusedObjectId
          CapturedPointerId = None } }

let accessibleProjection value =
    value.Scene.Layers
    |> List.filter (fun layer -> layer.Visible)
    |> List.collect (fun layer -> layer.Objects)
    |> List.filter (fun value -> value.Selectable)
    |> List.map (fun value -> value.Id, value.AccessibleLabel)

let private fixtureColor red green blue =
    { Red = red; Green = green; Blue = blue; Alpha = 255uy }

/// Bounded disclosed-state characterization used by the opt-in sample and its package consumer gate.
let characterizedProjection revision revisionIdentity =
    { RevisionIdentity = revisionIdentity
      Revision = revision
      Camera = { PanX = 13.5; PanY = -4.25; Zoom = 1.75 }
      Layers =
        [ { Id = "terrain"
            Order = 10
            Visible = true
            Locked = true
            Objects =
              [ { Id = "terrain:objective:2"
                  AccessibleLabel = "Disclosed objective"
                  Selectable = false
                  Center = { X = 72.25; Y = 18.5 }
                  Radius = 8.0
                  Color = fixtureColor 217uy 175uy 55uy } ] }
          { Id = "units"
            Order = 20
            Visible = true
            Locked = false
            Objects =
              [ { Id = "unit:7"
                  AccessibleLabel = "Disclosed unit seven"
                  Selectable = true
                  Center = { X = 22.5; Y = 35.75 }
                  Radius = 6.5
                  Color = fixtureColor 37uy 99uy 235uy }
                { Id = "unit:11"
                  AccessibleLabel = "Disclosed unit eleven"
                  Selectable = true
                  Center = { X = 51.125; Y = 29.5 }
                  Radius = 6.5
                  Color = fixtureColor 15uy 118uy 110uy } ] }
          { Id = "commands"
            Order = 30
            Visible = false
            Locked = false
            Objects = [] } ]
      Selection =
        { SelectedObjectId = Some "unit:7"
          FocusedObjectId = Some "unit:11" } }
