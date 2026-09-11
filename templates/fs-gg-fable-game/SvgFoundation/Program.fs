module FableGameWorkspaceNamespace.SvgFoundation

open Browser.Dom
open Browser.Types
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser

let private color red green blue =
    { Red = red; Green = green; Blue = blue; Alpha = 255uy }

let private objectValue id label selectable nodes =
    { Id = id
      Selectable = selectable
      AccessibleLabel = label
      Content = { Nodes = nodes } }

let private stroke value width =
    { Fill = Some value
      Stroke = Some { Width = width; Cap = StrokeCap.Round; Join = StrokeJoin.RoundJoin; Miter = 4.0 }
      Opacity = 1.0
      Antialias = true
      BlendMode = BlendMode.SrcOver
      Shader = None
      ColorFilter = ColorFilter.NoColorFilter
      MaskFilter = MaskFilter.NoMaskFilter
      ImageFilter = ImageFilter.NoImageFilter
      PathEffect = PathEffect.NoPathEffect }

let gridScene =
    { RootId = "foundation-grid"
      Revision = 0
      Camera = { PanX = 8.0; PanY = 8.0; Zoom = 1.0 }
      Layers =
        [ { Id = "grid"
            Visible = true
            Objects =
              [ for row in 0 .. 2 do
                    for column in 0 .. 3 do
                        let id = $"cell:{column}:{row}"
                        yield objectValue id $"Cell {column}, {row}" true
                            [ SceneNode.Rectangle((float column * 32.0, float row * 32.0, 30.0, 30.0), color 235uy 240uy 248uy) ] ] } ] }

let continuousScene =
    { RootId = "foundation-continuous"
      Revision = 0
      Camera = { PanX = 14.5; PanY = 9.25; Zoom = 1.4 }
      Layers =
        [ { Id = "continuous"
            Visible = true
            Objects =
              [ objectValue "waypoint:alpha" "Fractional waypoint" true
                    [ SceneNode.Circle({ X = 18.75; Y = 23.5 }, 5.25, color 37uy 99uy 235uy) ]
                objectValue "route:alpha" "Continuous cubic route" false
                    [ SceneNode.Path(
                        { Commands =
                            [ PathCommand.MoveTo { X = 18.75; Y = 23.5 }
                              PathCommand.CubicTo({ X = 29.25; Y = 4.5 }, { X = 48.125; Y = 41.75 }, { X = 63.5; Y = 20.25 }) ]
                          FillType = PathFillType.Winding },
                        stroke (color 15uy 118uy 110uy) 2.0) ] ] } ] }

let private mount id label scene =
    let container = document.createElement("section")
    container.id <- id
    document.body.appendChild(container) |> ignore
    match SvgBrowser.mount container
              { Width = 220.0; Height = 140.0; AccessibleLabel = label; WheelZoomFactor = 1.1 }
              scene ignore with
    | Ok host -> host
    | Error error -> failwithf "SVG foundation fixture failed to mount: %A" error

let gridHost = mount "foundation-grid-host" "Neutral grid fixture" gridScene
let continuousHost = mount "foundation-continuous-host" "Neutral continuous-coordinate fixture" continuousScene

// Keep the mounted hosts alive for the lifetime of the generated sample.
window.addEventListener("beforeunload", fun _ ->
    (gridHost :> System.IDisposable).Dispose()
    (continuousHost :> System.IDisposable).Dispose())
