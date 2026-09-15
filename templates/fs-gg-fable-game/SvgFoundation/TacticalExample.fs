module FableGameWorkspaceNamespace.SvgFoundation.TacticalExample

open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.Game.Core
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.Domain
module RuleModel = FableGameWorkspaceNamespace.SvgFoundation.TacticalRuleModel
module Control = FableGameWorkspaceNamespace.TacticalRules

[<ImportDefault("./Examples/Tactical/scene.json?raw")>]
let private seedJson: string = jsNative

[<Emit("$0[$1]")>]
let private index (_values: obj) (_index: int) : obj = jsNative
let private integer (value: obj) = int (unbox<float> value)

type private Seed =
    { Id: string; Columns: int; Rows: int; CellWidth: float; CellHeight: float
      FirstId: string; First: Cell; SecondId: string; Second: Cell; Target: Cell }

[<Literal>]
let private seedSha256 = "fd3a16eedd57a312f456a0d9851a5d1d40e7af1aea3f621e66a2c37b25873cca"

type private TacticalEffect = RouteAvailable | RouteBlocked

let private decodeSeed () =
    let parsed: obj = JS.JSON.parse seedJson
    let first, second = index (parsed?units) 0, index (parsed?units) 1
    { Id = unbox<string> parsed?id
      Columns = integer parsed?grid?columns; Rows = integer parsed?grid?rows
      CellWidth = unbox<float> parsed?grid?cellWidth; CellHeight = unbox<float> parsed?grid?cellHeight
      FirstId = unbox<string> first?id; First = { Col = integer first?col; Row = integer first?row }
      SecondId = unbox<string> second?id; Second = { Col = integer second?col; Row = integer second?row }
      Target = { Col = integer parsed?planningTarget?col; Row = integer parsed?planningTarget?row } }

let private ruleCatalog seed =
    let routeRule =
        { Metadata =
            { Id = "tactical.route"; Version = 1; Title = "Find an authored-grid route"
              Summary = "Plan from the selected unit to the authored target around accepted occupancy."; DependsOn = [] }
          Evaluate = fun state ->
            let planned = Room.planMove seed.FirstId seed.Target state
            { RuleId = "tactical.route"
              Applies = planned.IsSome
              Explanation = "The route uses the authored grid and target with the accepted room occupancy."
              Causes =
                [ { Code = "public.unit"; Message = seed.FirstId }
                  { Code = "public.target"; Message = $"{seed.Target.Col},{seed.Target.Row}" }
                  { Code = "public.occupied"; Message = seed.SecondId } ]
              Effects = [ if planned.IsSome then RouteAvailable else RouteBlocked ] } }
    RuleCatalog.create
        { ModelId = RuleModel.modelId; ModelSha256 = RuleModel.modelSha256
          Tool = RuleModel.tool; ToolVersion = RuleModel.toolVersion
          Invariants = RuleModel.invariants; ImplementationBinding = RuleModel.implementationBinding }
        [ routeRule ]
    |> Result.defaultWith (fun issues -> failwithf "tactical rule catalog refused: %A" issues)

let private color red green blue = { Red = red; Green = green; Blue = blue; Alpha = 255uy }
let private item id label selectable nodes =
    { Id = id; Selectable = selectable; AccessibleLabel = label; Content = { Nodes = nodes } }

let private projection seed revision (state: Room.State) route =
    let routeCells = route |> Set.ofList
    { RootId = "selected-tactical-scene"
      Revision = revision
      Camera = { PanX = 13.5; PanY = -4.25; Zoom = 1.75 }
      Layers =
        [ { Id = "terrain"
            Visible = true
            Objects =
                [ for row in 0 .. seed.Rows - 1 do
                    for col in 0 .. seed.Columns - 1 do
                        yield item $"tile:{col}:{row}" $"Terrain {col}, {row}" false
                            [ SceneNode.Rectangle((float col * seed.CellWidth, float row * seed.CellHeight, seed.CellWidth - 1.0, seed.CellHeight - 1.0), color 226uy 232uy 240uy) ] ] }
          { Id = "route"
            Visible = true
            Objects =
                [ for cell in routeCells do
                    yield item $"route:{cell.Col}:{cell.Row}" "Planned route" false
                        [ SceneNode.Rectangle((float cell.Col * seed.CellWidth, float cell.Row * seed.CellHeight, seed.CellWidth - 1.0, seed.CellHeight - 1.0), color 147uy 197uy 253uy) ] ] }
          { Id = "units"
            Visible = true
            Objects =
                state.Players
                |> Map.toList
                |> List.map (fun (id, player) ->
                    item id $"Tactical unit {id}" true
                        [ SceneNode.Circle({ X = float player.Cell.Col * seed.CellWidth + seed.CellWidth / 2.0; Y = float player.Cell.Row * seed.CellHeight + seed.CellHeight / 2.0 }, 6.0, color 30uy 64uy 175uy) ]) } ] }

let mount () =
    let seed = decodeSeed ()
    let root: HTMLElement = document.createElement("section")
    root.id <- "selected-tactical-example"
    root.setAttribute("aria-label", "Selected editable tactical example")
    root.setAttribute("data-source-id", seed.Id)
    root.setAttribute("data-source-sha256", seedSha256)
    document.body.appendChild root |> ignore
    let status: HTMLElement = document.createElement("output")
    status.setAttribute("aria-live", "polite")
    status.textContent <- "Tactical example loaded"
    root.appendChild status |> ignore
    let canvas: HTMLElement = document.createElement("div")
    root.appendChild canvas |> ignore
    let definition: Control.Content =
        { Id = seed.Id; ContentIdentity = $"{seed.Id}@sha256:{seedSha256}"
          Columns = seed.Columns; Rows = seed.Rows; FirstId = seed.FirstId; First = seed.First
          SecondId = seed.SecondId; Second = seed.Second; Target = seed.Target }
    let mutable session = Control.create definition
    let mutable revision = 0
    let catalog = ruleCatalog seed
    let host =
        SvgBrowser.mount canvas
            { Width = 220.0; Height = 140.0; AccessibleLabel = "Tactical planning example"; WheelZoomFactor = 1.1 }
            (projection seed revision session.Room session.Route) ignore
        |> Result.defaultWith (fun error -> failwithf "%A" error)
    let render label =
        revision <- revision + 1
        host.Dispatch(RetainedInteractionMessage.ReplaceScene(projection seed revision session.Room session.Route)) |> ignore
        root.setAttribute("data-operation", label)
        root.setAttribute("data-route-length", string session.Route.Length)
        root.setAttribute("data-unit-col", string session.Room.Players.[seed.FirstId].Cell.Col)
        root.setAttribute("data-authored-content-id", definition.ContentIdentity)
        let acceptedDigest = Control.digest definition session.Room
        let predictedDigest =
            session.Planning
            |> Option.bind (fun planning -> planning.Scenarios |> List.tryLast)
            |> Option.map _.Prediction.StateDigest
            |> Option.defaultValue acceptedDigest
        root.setAttribute("data-accepted-digest", acceptedDigest)
        root.setAttribute("data-predicted-digest", predictedDigest)
        root.setAttribute("data-committed-digest", acceptedDigest)
        status.textContent <- label
    let add label action =
        let button: HTMLElement = document.createElement("button")
        button.textContent <- label
        button.setAttribute("aria-label", label)
        button.addEventListener("click", fun _ -> action())
        root.appendChild button |> ignore
    add "Plan tactical route" (fun () ->
        match Control.plan session with
        | Error issue -> render $"plan-refused:{issue}"
        | Ok planned -> session <- planned; render "planned")
    add "Compare tactical scenario" (fun () ->
        match Control.compare session with
        | Error issue -> render $"compare-refused:{issue}"
        | Ok(comparison, compared) ->
            session <- compared
            root.setAttribute("data-comparison-unchanged", string comparison.IsUnchanged)
            render "compared")
    add "Cancel tactical scenario" (fun () ->
        let acceptedBefore = Control.digest definition session.Room
        match Control.cancel session with
        | Error issue -> render $"cancel-refused:{issue}"
        | Ok cancelled ->
            session <- cancelled
            root.setAttribute("data-cancel-preserved-accepted", string (Control.digest definition session.Room = acceptedBefore))
            render "cancelled")
    add "Commit tactical scenario" (fun () ->
        match Control.commit session with
        | Error issue -> render $"commit-refused:{issue}"
        | Ok committed -> session <- committed; render "committed")
    add "Simulate tactical step" (fun () ->
        match Control.simulate session with
        | Error issue -> render $"simulate-refused:{issue}"
        | Ok simulated -> session <- simulated; render "simulated")
    add "Review tactical state" (fun () ->
        match Control.review session with
        | Error issue -> render $"review-refused:{issue}"
        | Ok reviewed -> session <- reviewed; render $"review:{Control.digest definition session.Room}")
    add "Explain tactical route rule" (fun () ->
        match RuleCatalog.inspect "tactical.route" session.Room catalog with
        | Error issues -> render $"rule-refused:{issues}"
        | Ok inspection ->
            let causes = inspection.Evaluations |> List.collect _.Causes
            root.setAttribute("data-rule-causes", causes |> List.map (fun cause -> $"{cause.Code}:{cause.Message}") |> String.concat ";")
            root.setAttribute("data-rule-applies", string inspection.Applies)
            root.setAttribute("data-rule-model-sha256", (RuleCatalog.evidence catalog).ModelSha256)
            let explanations = inspection.Evaluations |> List.map _.Explanation |> String.concat " "
            render $"rule: {explanations}")
    render "loaded"
