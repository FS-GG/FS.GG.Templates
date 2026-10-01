module FableGameWorkspaceNamespace.SvgFoundation.FourDReference

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.Game.Core
open FS.GG.UI.KeyboardInput
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser

[<ImportDefault("./Examples/FourD/reference.json?raw")>]
let private fixtureJson: string = jsNative

type private FullCell = { A: int; B: int; C: int; D: int }

type private FourDProjection =
    {
        Agent: FullCell
        LegalDestination: FullCell
        Revision: uint64
    }

[<RequireQualifiedAccess>]
type private FourDSemanticCommand = MoveToFullCell of FullCell

[<RequireQualifiedAccess>]
type private NormalizedBrowserObservation =
    | Invoke of string
    | SemanticTarget of string
    | HeldChanged of string * bool

let private origin = { A = 0; B = 0; C = 0; D = 0 }
let private destination = { A = 1; B = 1; C = 1; D = 1 }

let private commandFor observation projection =
    let target = "full-cell:1:1:1:1"

    match observation with
    | NormalizedBrowserObservation.Invoke "fourd.move-full-cell" ->
        Some(FourDSemanticCommand.MoveToFullCell destination)
    | NormalizedBrowserObservation.SemanticTarget value when value = target ->
        Some(FourDSemanticCommand.MoveToFullCell destination)
    | _ -> None

let private compatibility =
    {
        ContractVersion = 1
        EngineId = "fs-gg.fourd-reference"
        EngineVersion = "1"
        ProfileId = "local-reference-fixture"
        SchemaId = "fourd-reference-encounter"
        SchemaVersion = 1
    }

let private initial =
    {
        Agent = origin
        LegalDestination = destination
        Revision = 1UL
    }

let private contract: SessionContract<unit, FourDProjection, FourDSemanticCommand, FourDProjection, FourDProjection> =
    let failure code message =
        Error({ Code = code; Message = message }: SessionFailure)

    {
        Initialize =
            fun request ->
                if
                    request.SessionId = "fourd-reference-encounter"
                    && request.Compatibility = compatibility
                then
                    Ok initial
                else
                    failure "fourd.initialize.identity" "reference session identity mismatch"
        AdmitInput =
            fun input state ->
                if input.SessionId <> "fourd-reference-encounter" then
                    failure "fourd.input.session" "reference input session mismatch"
                else
                    match input.Value with
                    | FourDSemanticCommand.MoveToFullCell cell when cell = state.LegalDestination ->
                        Ok
                            { state with
                                Agent = cell
                                Revision = state.Revision + 1UL
                            }
                    | _ -> failure "fourd.input.destination" "destination is not the projected legal full cell"
        Advance = fun _ state -> Ok state
        Project =
            fun state ->
                {
                    SessionId = "fourd-reference-encounter"
                    Revision = state.Revision
                    Value = state
                }
        Snapshot =
            fun state ->
                {
                    SessionId = "fourd-reference-encounter"
                    Revision = state.Revision
                    Compatibility = compatibility
                    Value = state
                }
        Restore =
            fun snapshot ->
                if
                    snapshot.SessionId = "fourd-reference-encounter"
                    && snapshot.Compatibility = compatibility
                then
                    Ok snapshot.Value
                else
                    failure "fourd.restore.identity" "reference snapshot identity mismatch"
    }

let private color red green blue =
    {
        Red = red
        Green = green
        Blue = blue
        Alpha = 255uy
    }

let private scene projection =
    let cell id label selected x y =
        {
            Id = id
            Selectable = true
            AccessibleLabel = label
            Content =
                {
                    Nodes =
                        [
                            SceneNode.Rectangle(
                                (x, y, 34.0, 34.0),
                                if selected then
                                    color 37uy 99uy 235uy
                                else
                                    color 226uy 232uy 240uy
                            )
                        ]
                }
        }

    {
        RootId = "fourd-reference-scene"
        Revision = int projection.Revision
        Camera = { PanX = 23.0; PanY = 17.0; Zoom = 1.6 }
        Layers =
            [
                {
                    Id = "full-cells"
                    Visible = true
                    Objects =
                        [
                            cell "full-cell:0:0:0:0" "Current full cell 0, 0, 0, 0" (projection.Agent = origin) 8.0 12.0
                            cell
                                "full-cell:1:1:1:1"
                                "Legal full cell 1, 1, 1, 1"
                                (projection.Agent = destination)
                                58.0
                                38.0
                        ]
                }
            ]
    }

let private commandDescriptor =
    {
        Id = "fourd.move-full-cell"
        Label = "Move to legal full cell"
        Contexts = [ "fourd.encounter" ]
        AvailabilityKey = None
        Trigger = CommandTriggerPolicy.OncePerPress
        Argument = CommandArgumentPolicy.NoArgument
        Alternatives = [ CommandAlternative.Pointer "Move to legal full cell" ]
    }

let private heldDescriptor =
    { commandDescriptor with
        Id = "fourd.inspect-held"
        Label = "Inspect while held"
        Trigger = CommandTriggerPolicy.Continuous
    }

let private catalog =
    {
        Contexts =
            [
                {
                    Id = "fourd.encounter"
                    Priority = 10
                    Exclusive = false
                    Overlaps = []
                }
            ]
        Commands = [ commandDescriptor; heldDescriptor ]
        ReservedGestures = []
        AllowTerminalPrefixes = false
    }

let private key value =
    InputGesture.KeyChord(InputKeyIdentity.LogicalKey value, CommandInput.noModifiers)

let private profile =
    {
        Schema = CommandInput.profileSchema
        Id = "fourd-reference"
        Defaults =
            [
                {
                    Gesture = key "Enter"
                    Command = "fourd.move-full-cell"
                    Context = "fourd.encounter"
                }
                {
                    Gesture = key "h"
                    Command = "fourd.inspect-held"
                    Context = "fourd.encounter"
                }
            ]
        Overrides = []
    }

let mount () : IDisposable =
    // Parsing the delivered fixture is intentional: it proves the complete template resource is in the Fable graph.
    let fixture: obj = JS.JSON.parse fixtureJson
    let root: HTMLElement = document.createElement "section"
    root.id <- "fourd-reference"
    root.setAttribute ("aria-label", "Four dimensional local authority reference")
    root.setAttribute ("tabindex", "0")
    root.setAttribute ("data-fixture-id", unbox<string> fixture?id)
    document.body.appendChild root |> ignore

    let heading = document.createElement "h2"
    heading.textContent <- "Four dimensional reference encounter"
    root.appendChild heading |> ignore

    let label = document.createElement "label"
    label.textContent <- "Encounter note"
    let editor: HTMLInputElement = document.createElement ("input") :?> HTMLInputElement
    editor.id <- "fourd-reference-note"
    editor.setAttribute ("aria-label", "Encounter note")
    label.appendChild editor |> ignore
    root.appendChild label |> ignore

    let canvas: HTMLElement = document.createElement "div"
    canvas.id <- "fourd-reference-canvas"
    root.appendChild canvas |> ignore

    let mutable runtime =
        SessionRuntime.initialize
            {
                StepMicroseconds = 16_667UL
                MaxCatchUpSteps = 1u
            }
            contract
            {
                SessionId = "fourd-reference-encounter"
                Compatibility = compatibility
                Configuration = ()
            }
        |> Result.defaultWith (fun error -> failwithf "FourD reference session failed: %A" error)

    let mutable commandSequence = 0UL
    let mutable commandOrder: string list = []
    let mutable held = false
    let mutable projectionRequests: uint64 list = []
    let mutable sessionHost: SvgSessionHost<FourDProjection> option = None
    let mutable disposed = false

    let mutable selectionHandler: string -> unit = ignore
    let mutable observedSelection: string option = None

    let svg =
        SvgBrowser.mount
            canvas
            {
                Width = 180.0
                Height = 120.0
                AccessibleLabel = "Four dimensional full-cell projection"
                WheelZoomFactor = 1.1
            }
            (scene runtime.Current)
            (fun transition ->
                let selected = transition.State.SelectedObjectId

                if selected <> observedSelection then
                    observedSelection <- selected
                    selected |> Option.iter selectionHandler)
        |> Result.defaultWith (fun error -> failwithf "FourD reference SVG failed: %A" error)

    let describe () =
        let cell = runtime.Current.Agent
        root.setAttribute ("data-agent-full-cell", $"{cell.A}:{cell.B}:{cell.C}:{cell.D}")
        root.setAttribute ("data-command-order", String.concat "," commandOrder)
        root.setAttribute ("data-held", string held)
        root.setAttribute ("data-projection-request-count", string projectionRequests.Length)

    let admit observation =
        commandFor observation runtime.Current
        |> Option.iter (fun command ->
            commandSequence <- commandSequence + 1UL

            let next, effects =
                SessionRuntime.update
                    contract
                    (SessionRuntimeObservation.AdmitInput
                        {
                            SessionId = "fourd-reference-encounter"
                            InputId = $"fourd:{commandSequence}"
                            Sequence = commandSequence
                            Value = command
                        })
                    runtime

            runtime <- next

            if
                effects
                |> List.exists (function
                    | SessionRuntimeEffect.InputAccepted _ -> true
                    | _ -> false)
            then
                commandOrder <- commandOrder @ [ string commandSequence ]
                sessionHost |> Option.iter _.DemandProjection()

            describe ())

    let callbacks =
        {
            AdvanceElapsed = ignore
            Pause = ignore
            Resume = ignore
            StepOnce = ignore
            Reset = ignore
            RequestRecovery = ignore
            RequestProjection =
                fun generation ->
                    projectionRequests <- projectionRequests @ [ generation ]
                    describe ()
            ApplyProjection =
                fun revision projection ->
                    svg.Dispatch(RetainedInteractionMessage.ReplaceScene(scene projection))
                    |> ignore

                    root.setAttribute ("data-applied-revision", string revision)
                    describe ()
            CancelGeneration = fun generation -> root.setAttribute ("data-cancelled-generation", string generation)
            Replace = fun generation -> root.setAttribute ("data-generation", string generation)
            Dispose = ignore
        }

    let clock =
        new SvgSessionHost<FourDProjection>(callbacks, SvgSessionHost.defaultConfig)

    sessionHost <- Some clock

    let effective =
        CommandInput.compile catalog profile
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)

    let input =
        new SvgInputHost(
            root,
            catalog,
            CommandResolver.init [ "fourd.encounter" ] effective,
            (fun () -> catalog.Commands |> List.map _.Id),
            (function
            | CommandResolverEffect.InvokeCommand invocation ->
                admit (NormalizedBrowserObservation.Invoke invocation.Command)
            | CommandResolverEffect.HeldActionChanged(command, value) ->
                held <- value
                admit (NormalizedBrowserObservation.HeldChanged(command, value))
                describe ()
            | _ -> ()),
            { SvgInputHost.defaultOptions with
                PollGamepads = false
            }
        )

    selectionHandler <-
        fun target ->
            // SvgBrowser produced this semantic target through its transform-aware hit test.
            root.setAttribute ("data-hit", target)
            admit (NormalizedBrowserObservation.SemanticTarget target)

    let button text action =
        let value = document.createElement "button"
        value.textContent <- text
        value.addEventListener ("click", fun _ -> action ())
        root.appendChild value |> ignore

    button "Move to legal full cell" (fun () -> admit (NormalizedBrowserObservation.Invoke "fourd.move-full-cell"))

    button "Request projection burst" (fun () ->
        clock.DemandProjection()
        clock.DemandProjection()
        clock.DemandProjection()
        describe ())

    button "Complete current projection" (fun () ->
        projectionRequests
        |> List.tryLast
        |> Option.iter (fun generation ->
            clock.CompleteProjection(generation, runtime.Current.Revision, runtime.Current))

        describe ())

    button "Complete oldest projection" (fun () ->
        projectionRequests
        |> List.tryHead
        |> Option.iter (fun generation ->
            clock.CompleteProjection(generation, runtime.Current.Revision, runtime.Current))

        describe ())

    button "Replace local session" (fun () ->
        clock.Replace()
        describe ())

    let dispose () =
        if not disposed then
            disposed <- true
            (input :> IDisposable).Dispose()
            (clock :> IDisposable).Dispose()
            (svg :> IDisposable).Dispose()
            let inputObservation = input.Observe()
            let sessionObservation = clock.Observe()
            root.setAttribute ("data-disposed", "true")

            root.setAttribute (
                "data-input-owned",
                string (
                    inputObservation.OwnedListenerCount
                    + inputObservation.OwnedDeadlineCount
                    + inputObservation.OwnedSourceCount
                )
            )

            root.setAttribute (
                "data-session-owned",
                string (
                    sessionObservation.OwnedListenerCount
                    + sessionObservation.ScheduledFrameCount
                    + sessionObservation.OwnedRequestCount
                )
            )

    button "Dispose FourD reference" dispose
    describe ()

    { new IDisposable with
        member _.Dispose() = dispose ()
    }
