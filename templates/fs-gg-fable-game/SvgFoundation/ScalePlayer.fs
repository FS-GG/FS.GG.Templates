module FableGameWorkspaceNamespace.SvgFoundation.ScalePlayer

open Browser.Dom
open Browser.Types
open Fable.Core.JsInterop
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser

let private color red green blue =
    {
        Red = red
        Green = green
        Blue = blue
        Alpha = 255uy
    }

let private entries: SpatialEntry<int> list =
    [
        for index in 0..1999 ->
            let visible = index < 200

            let x =
                if visible then
                    float (index % 20) * 16.0
                else
                    10000.0 + float index * 16.0

            let y = if visible then float (index / 20) * 16.0 else 10000.0

            {
                Id = $"entity-{index}"
                Bounds =
                    {
                        X = x
                        Y = y
                        Width = 14.0
                        Height = 14.0
                    }
                Value = index
            }
    ]

let private index =
    SpatialWorkingSet.create 64.0 entries
    |> Result.defaultWith (fun issues -> failwithf "Generated scale index refused: %A" issues)

let private workingSet =
    SpatialWorkingSet.query
        {
            Viewport =
                {
                    X = 0.0
                    Y = 0.0
                    Width = 320.0
                    Height = 160.0
                }
            Overscan = 0.0
            PinnedIds = Set.empty
            MaxVisitedChunks = 32
        }
        index
    |> Result.defaultWith (fun issues -> failwithf "Generated scale query refused: %A" issues)

let private sceneObject (entry: SpatialEntry<int>) =
    let value = entry.Value
    let x = float (value % 20) * 16.0
    let y = float (value / 20) * 16.0

    {
        Id = entry.Id
        Selectable = true
        AccessibleLabel = $"Scale entity {value + 1} of 200"
        Content =
            {
                Nodes = [ SceneNode.Rectangle((x, y, 14.0, 14.0), color 37uy 99uy 235uy) ]
            }
    }

let private scene =
    {
        RootId = "generated-scale-world"
        Revision = 1
        Camera = { PanX = 0.0; PanY = 0.0; Zoom = 1.0 }
        Layers =
            [
                {
                    Id = "visible-entities"
                    Visible = true
                    Objects = workingSet.Entries |> List.map sceneObject
                }
            ]
    }

let mutable private mounted: SvgBrowserHost option = None
let mutable private alternatives: HTMLElement option = None

let mount () =
    let section = document.createElement ("section")
    section.id <- "foundation-scale-host"
    section.setAttribute ("aria-labelledby", "foundation-scale-heading")

    section.innerHTML <-
        "<h2 id='foundation-scale-heading'>Dense scale scene</h2><p id='foundation-scale-summary'>200 visible entities from a 2,000-entity world. Use the SVG objects or the alternative list.</p><ol id='foundation-scale-alternatives' aria-label='Visible entity alternatives'></ol>"

    document.body.appendChild (section) |> ignore

    let alternativeList: HTMLElement =
        document.getElementById ("foundation-scale-alternatives")

    for entry in workingSet.Entries do
        let item = document.createElement ("li")
        let button = document.createElement ("button")
        button.textContent <- $"Scale entity {entry.Value + 1}"
        button.setAttribute ("data-scale-entity", entry.Id)
        item.appendChild (button) |> ignore
        alternativeList.appendChild (item) |> ignore

    let surface = document.createElement ("div")
    surface.id <- "foundation-scale-surface"
    section.insertBefore (surface, alternativeList) |> ignore

    let host =
        SvgBrowser.mount
            surface
            {
                Width = 320.0
                Height = 160.0
                AccessibleLabel = "Dense generated scale scene"
                WheelZoomFactor = 1.1
            }
            scene
            ignore
        |> Result.defaultWith (fun issues -> failwithf "Generated scale scene refused: %A" issues)

    host.Root.setAttribute ("aria-describedby", "foundation-scale-summary")
    host.Root.setAttribute ("style", "display:block;max-width:100%;height:auto")
    mounted <- Some host
    alternatives <- Some alternativeList

let snapshot () =
    let host = mounted.Value
    let alternativeList = alternatives.Value

    createObj
        [
            "worldEntries" ==> workingSet.TotalEntryCount
            "visibleEntries" ==> workingSet.Entries.Length
            "visitedChunks" ==> workingSet.VisitedChunkCount
            "candidateEntries" ==> workingSet.CandidateCount
            "svgObjects" ==> host.Root.querySelectorAll("[data-scene-object-id]").length
            "alternativeButtons" ==> alternativeList.querySelectorAll("button").length
        ]

let dispose () =
    mounted |> Option.iter (fun host -> (host :> System.IDisposable).Dispose())
    mounted <- None
