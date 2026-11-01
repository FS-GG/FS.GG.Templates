namespace FableGameWorkspaceNamespace.Client

open Browser.Dom
open Browser.Types
open Fable.Core
open FS.GG.Game.Core
open FS.GG.Game.Render
open FS.GG.Game.Render.Browser
open FS.GG.UI.Scene

/// The renderer conformance run (GAME-RENDER-ADOPT-01.10, FS.GG.Templates#834).
///
/// `renderers.html` loads this module, which runs the FS.GG.Game.Render conformance kit
/// (`RendererConformance.run`) on `Renderers.conformance` against the SVG, Pixi and Babylon backends in the real
/// browser, and then writes the verdict into `#conformance-result` for `Browser.Tests/renderer-conformance.spec.ts`.
/// It is not part of the game page: `index.html` never imports it, so the game ships no renderer code it does not use.
///
/// What a game edits to bring its own state: `Renderers.view` (the Scene), `states` (at least two game states that
/// look different) and nothing else. `shows` reads each backend's output back from the page, independently of the
/// adapter: the SVG DOM for SVG, and a canvas pixel through `BrowserConformance.readPixel` for Pixi and Babylon.
module ConformancePage =

    /// Game states that look different from each other: an empty arena, this client alone, and a busy arena with
    /// another player and a selected path. They are values of the game's own Model.
    let states: App.Model list =
        let arena: App.Model =
            {
                PlayerId = None
                SessionCapability = None
                RoomId = "conformance"
                ArenaWidth = 20
                ArenaHeight = 12
                Players = Map.empty
                Tick = 0
                NextSequence = 1
                PreviewPath = []
                Status = "conformance"
            }

        let alone =
            { arena with
                PlayerId = Some "you"
                Players = Map.ofList [ "you", { Col = 2; Row = 3 } ]
                Tick = 1
            }

        let busy =
            { alone with
                Players = alone.Players |> Map.add "them" { Col = 10; Row = 6 }
                PreviewPath = [ { Col = 3; Row = 3 }; { Col = 4; Row = 3 } ]
                Tick = 2
            }

        [ arena; alone; busy ]

    let private rgbOf (color: Color) = [| int color.Red; int color.Green; int color.Blue |]

    /// Babylon draws the flat meshes lit at 0.75 of the scene colour (a known limit of that surface).
    let private litOf (color: Color) =
        rgbOf color |> Array.map (fun value -> int (System.Math.Round(float value * 0.75)))

    let private near (expected: int[]) (actual: int[]) (tolerance: int) =
        actual.Length >= 3
        && Array.forall2 (fun e a -> abs (e - a) <= tolerance) expected.[0..2] actual.[0..2]

    /// The colour the Scene puts at a point: the last node that covers it (later nodes are on top).
    let private colorAt (scene: Scene) (x: float) (y: float) : Color option =
        scene.Nodes
        |> List.fold
            (fun covering node ->
                match node with
                | SceneNode.Rectangle((rx, ry, rw, rh), color) when x >= rx && x < rx + rw && y >= ry && y < ry + rh ->
                    Some color
                | SceneNode.Circle(center, radius, color) when
                    (x - center.X) * (x - center.X) + (y - center.Y) * (y - center.Y) <= radius * radius
                    ->
                    Some color
                | _ -> covering)
            None

    /// One point inside every node of every state's Scene, and a point of the bare background. A backend's output must
    /// match the asked state at all of them, so a state whose nodes are a subset of the shown state's is still
    /// told apart: the shown state draws something else where the asked state does not.
    let private probePoints: (float * float) list =
        [
            yield 1.0, 1.0

            for state in states do
                for node in (Renderers.view state).Nodes do
                    match node with
                    | SceneNode.Rectangle((x, y, w, h), _) -> yield x + w / 2.0, y + h / 2.0
                    | SceneNode.Circle(center, _, _) -> yield center.X, center.Y
                    | _ -> ()
        ]
        |> List.distinct

    /// Whether the SVG root in `container` holds exactly the Scene's rectangles and circles, with their geometry and
    /// fill. It reads the DOM, not the adapter.
    let private svgShows (container: HTMLElement) (state: App.Model) : Result<unit, string> =
        let scene = Renderers.view state
        let fill (color: Color) = sprintf "rgb(%d %d %d)" color.Red color.Green color.Blue

        let attribute (element: Element) (name: string) =
            match element.getAttribute name with
            | null -> nan
            | text -> float text

        let elements (selector: string) =
            let found = container.querySelectorAll selector
            [ for index in 0 .. int found.length - 1 -> found.item index ]

        let rectangles = elements "rect"
        let circles = elements "circle"

        let missing =
            [
                for node in scene.Nodes do
                    match node with
                    | SceneNode.Rectangle((x, y, w, h), color) ->
                        let present =
                            rectangles
                            |> List.exists (fun element ->
                                attribute element "x" = x
                                && attribute element "y" = y
                                && attribute element "width" = w
                                && attribute element "height" = h
                                && (element.getAttribute "fill").Contains(fill color))

                        if not present then
                            yield sprintf "rect %g,%g %gx%g %s" x y w h (fill color)
                    | SceneNode.Circle(center, radius, color) ->
                        let present =
                            circles
                            |> List.exists (fun element ->
                                attribute element "cx" = center.X
                                && attribute element "cy" = center.Y
                                && attribute element "r" = radius
                                && (element.getAttribute "fill").Contains(fill color))

                        if not present then
                            yield sprintf "circle %g,%g r%g %s" center.X center.Y radius (fill color)
                    | _ -> ()
            ]

        let rectangleNodes =
            scene.Nodes
            |> List.filter (function
                | SceneNode.Rectangle _ -> true
                | _ -> false)
            |> List.length

        let circleNodes =
            scene.Nodes
            |> List.filter (function
                | SceneNode.Circle _ -> true
                | _ -> false)
            |> List.length

        if not missing.IsEmpty then
            Error("svg lacks " + String.concat "; " missing)
        elif rectangles.Length <> rectangleNodes || circles.Length <> circleNodes then
            Error(
                sprintf
                    "svg draws %d rects and %d circles, the state has %d and %d"
                    rectangles.Length
                    circles.Length
                    rectangleNodes
                    circleNodes
            )
        else
            Ok()

    /// Whether `backend`'s canvas shows `state`. It first waits (bounded) until the canvas shows the state the HOST
    /// presents, so an asynchronous first frame is not mistaken for a mismatch, then reads the asked state's points
    /// once: a state that is not shown is rejected without waiting.
    let private canvasShows
        (host: ConformanceHost<App.Model>)
        (container: HTMLElement)
        (backend: RendererBackend)
        (state: App.Model)
        : Async<Result<unit, string>> =
        async {
            let expect, tolerance =
                match backend with
                | RendererBackend.Babylon -> litOf, 4
                | _ -> rgbOf, 2

            let wanted (scene: Scene) (x: float) (y: float) =
                (colorAt scene x y |> Option.defaultValue Renderers.backgroundColor) |> expect

            let read (scene: Scene) (x: float, y: float) (frames: int) =
                BrowserConformance.readPixel
                    host
                    container
                    backend
                    (int x)
                    (int y)
                    (fun pixel -> near (wanted scene x y) pixel tolerance)
                    frames

            let presented = Renderers.view (host.Model()).State

            for point in probePoints do
                let! _ = read presented point 600
                ()

            let scene = Renderers.view state
            let problem: string option ref = ref None

            for (x, y) as point in probePoints do
                let! pixel = read scene point 0

                if problem.Value.IsNone && not (near (wanted scene x y) pixel tolerance) then
                    problem.Value <-
                        Some(
                            sprintf
                                "%s at %g,%g shows %A (want %A)"
                                (RendererBackend.id backend)
                                x
                                y
                                pixel
                                (wanted scene x y)
                        )

            return
                match problem.Value with
                | None -> Ok()
                | Some detail -> Error detail
        }

    let private shows
        (container: HTMLElement)
        (host: ConformanceHost<App.Model>)
        (backend: RendererBackend)
        (state: App.Model)
        : Async<Result<unit, string>> =
        match backend with
        | RendererBackend.Svg -> async { return svgShows container state }
        | _ -> canvasShows host container backend state

    [<Emit("console.log('RENDERER-CONFORMANCE checks=' + $0 + ' failures=' + $1)")>]
    let private announce (checks: int) (failures: int) : unit = jsNative

    /// Run the kit and the start path, and publish the verdict in `#conformance-result`.
    let run () : Async<unit> =
        async {
            let lines = ResizeArray<string>()
            let failures = ref 0
            let checks = ref 0

            let record (name: string) (passed: bool) (detail: string) =
                checks.Value <- checks.Value + 1

                if passed then
                    lines.Add("PASS " + name)
                else
                    failures.Value <- failures.Value + 1
                    lines.Add("FAIL " + name + ": " + detail)

            try
                BrowserConformance.installContextProbe ()

                let stage = document.createElement "div"
                stage.id <- "stage-conformance"
                document.body.appendChild stage |> ignore

                // The kit, on SVG, Pixi and Babylon: registry, round trip, switching, disposal, late and present
                // failures, each against what the page itself observes.
                let! results = RendererConformance.run (Renderers.conformance stage states (shows stage))

                for result in results do
                    record ("kit: " + result.Check) result.Passed result.Detail

                record "kit: ran its requirements" (results.Length >= 73) (sprintf "only %d requirements ran" results.Length)

                record
                    "kit: the stage is empty afterwards"
                    (stage.children.length = 0)
                    stage.innerHTML

                // The authoring path's start: SVG first, then a runtime switch to each canvas backend with the game
                // state kept, and disposal releasing the pending Pixi application.
                let initial = states.[2]
                let driver = Renderers.start stage initial ignore
                let offered = RendererSelection.available driver.Model
                driver.Dispatch(RendererMsg.SelectBackend RendererBackend.Babylon)
                let onBabylon = driver.Mounted = Some RendererBackend.Babylon && driver.Model.State = initial
                driver.Dispatch(RendererMsg.SelectBackend RendererBackend.Pixi)
                let onPixi = driver.Mounted = Some RendererBackend.Pixi && driver.Model.State = initial

                record
                    "start: offers all three backends and switches at runtime with the state kept"
                    (offered = RendererBackend.all && onBabylon && onPixi)
                    (sprintf "%A babylon=%b pixi=%b" offered onBabylon onPixi)

                (driver :> System.IDisposable).Dispose()
                let! released = BrowserConformance.waitUntil 600 (fun () -> (PixiSurface.live ()).Applications = 0)
                record "start: disposing releases the pending Pixi application" released (sprintf "%A" (PixiSurface.live ()))
            with ex ->
                record "conformance run raised" false ex.Message

            let pre = document.createElement "pre"
            pre.id <- "conformance-result"
            pre.setAttribute ("data-checks", string checks.Value)
            pre.setAttribute ("data-failures", string failures.Value)
            pre.textContent <- String.concat "\n" lines
            document.body.appendChild pre |> ignore
            document.body.setAttribute ("data-conformance", (if failures.Value = 0 then "pass" else "fail"))
            announce checks.Value failures.Value
        }

    // `renderers.html` loads this module, and loading it runs the kit.
    do run () |> Async.StartImmediate
