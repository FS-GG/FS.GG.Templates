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
                    | FourDSemanticCommand.MoveToFullCell cell when cell = state.LegalDestination -> Ok state
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

    // A broader DOM island: ordinary labelled native controls (a select, a checkbox and a radio group) beside the retained
    // scene. Their state is presentation-only; the encounter rules, saves and replay never read it. SvgInputHost already
    // treats these controls as native-editable targets, so Enter or Space inside them never becomes gameplay input.
    // The island is created once; retained scene updates and session replacement only rewrite its status text.
    let options: HTMLElement = document.createElement "fieldset"
    options.id <- "fourd-reference-options"
    let optionsLegend = document.createElement "legend"
    optionsLegend.textContent <- "Encounter options"
    options.appendChild optionsLegend |> ignore

    let difficultyLabel: HTMLLabelElement = document.createElement ("label") :?> HTMLLabelElement
    difficultyLabel.htmlFor <- "fourd-reference-difficulty"
    difficultyLabel.textContent <- "Difficulty"
    let difficulty: HTMLSelectElement = document.createElement ("select") :?> HTMLSelectElement
    difficulty.id <- "fourd-reference-difficulty"

    for (value, text) in [ "calm", "Calm"; "standard", "Standard"; "severe", "Severe" ] do
        let choice: HTMLOptionElement = document.createElement ("option") :?> HTMLOptionElement
        choice.value <- value
        choice.textContent <- text
        difficulty.appendChild choice |> ignore

    difficulty.value <- "standard"
    options.appendChild difficultyLabel |> ignore
    options.appendChild difficulty |> ignore

    let hintsLabel = document.createElement "label"
    let hints: HTMLInputElement = document.createElement ("input") :?> HTMLInputElement
    hints.id <- "fourd-reference-hints"
    hints.``type`` <- "checkbox"
    hintsLabel.appendChild hints |> ignore
    hintsLabel.appendChild (document.createTextNode "Show hints") |> ignore
    options.appendChild hintsLabel |> ignore

    let camera = document.createElement "fieldset"
    let cameraLegend = document.createElement "legend"
    cameraLegend.textContent <- "Camera"
    camera.appendChild cameraLegend |> ignore

    let cameraChoice (value: string) (text: string) (selected: bool) =
        let wrapper = document.createElement "label"
        let radio: HTMLInputElement = document.createElement ("input") :?> HTMLInputElement
        radio.``type`` <- "radio"
        radio.name <- "fourd-reference-camera"
        radio.value <- value
        radio.``checked`` <- selected
        wrapper.appendChild radio |> ignore
        wrapper.appendChild (document.createTextNode text) |> ignore
        camera.appendChild wrapper |> ignore
        radio

    let overviewCamera = cameraChoice "overview" "Overview" true
    let closeCamera = cameraChoice "close" "Close focus" false
    options.appendChild camera |> ignore

    let optionsStatus: HTMLElement = document.createElement "output"
    optionsStatus.id <- "fourd-reference-options-status"
    optionsStatus.setAttribute ("aria-live", "polite")
    options.appendChild optionsStatus |> ignore
    root.appendChild options |> ignore

    let optionListeners = ResizeArray<HTMLElement * (Event -> unit)>()

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
    let buttonListeners = ResizeArray<HTMLElement * (Event -> unit)>()

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

    let describeOptions () =
        let camera = if closeCamera.``checked`` then "close" else "overview"
        let shown = if hints.``checked`` then "on" else "off"
        root.setAttribute ("data-option-difficulty", difficulty.value)
        root.setAttribute ("data-option-hints", shown)
        root.setAttribute ("data-option-camera", camera)
        // Rewritten on every describe, including each retained scene update and session replacement.
        optionsStatus.textContent <-
            $"Options: difficulty {difficulty.value}, hints {shown}, camera {camera}; revision {runtime.Current.Revision}."

    let describe () =
        describeOptions ()
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
                root.setAttribute ("data-last-command-destination", "1:1:1:1")
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

    for control in [ difficulty :> HTMLElement; hints :> HTMLElement; overviewCamera :> HTMLElement; closeCamera :> HTMLElement ] do
        let handler = fun (_: Event) -> describeOptions ()
        control.addEventListener ("change", handler)
        optionListeners.Add(control, handler)

    let button text action =
        let value = document.createElement "button"
        value.textContent <- text
        let handler = fun (_: Event) -> action ()
        value.addEventListener ("click", handler)
        buttonListeners.Add(value, handler)
        root.appendChild value |> ignore

#if LOCAL_SAVE_REPLAY_EXAMPLE
    // This separate synthetic inspection trace never changes the encounter's gameplay state.
    let syntheticOrigin: LocalSaveReplayExample.FullCell = { A = -7; B = 23; C = -41; D = 89 }
    let syntheticDestination: LocalSaveReplayExample.FullCell = { A = 5; B = -11; C = 37; D = -83 }
    let mutable localExample =
        LocalSaveReplayExample.initialize syntheticOrigin syntheticDestination
        |> Result.defaultWith (fun issue -> failwithf "Synthetic local example initialization: %A" issue)
    let mutable localSequence = 0UL
    let mutable localSaved: SessionSnapshot<LocalSaveReplayExample.Payload> option = None
    let mutable localReplayCount: int option = None
    let localStatus = document.createElement "output"
    localStatus.id <- "local-save-replay-status"
    localStatus.setAttribute ("aria-live", "polite")
    root.appendChild localStatus |> ignore
    let describeLocal result =
        let cell = localExample.Runtime.Current.Agent
        let accepted = localExample.Runtime.Current.Accepted.Length
        root.setAttribute ("data-local-agent", $"{cell.A}:{cell.B}:{cell.C}:{cell.D}")
        root.setAttribute ("data-local-accepted", string accepted)
        root.setAttribute ("data-local-saved", if localSaved.IsSome then "true" else "false")
        root.setAttribute ("data-local-replay-count", localReplayCount |> Option.map string |> Option.defaultValue "none")
        localStatus.textContent <- $"Synthetic local save/replay: {result}; accepted inspections {accepted}. Agent {cell.A}, {cell.B}, {cell.C}, {cell.D}."
    button "Synthetic inspect full cell" (fun () ->
        localSequence <- localSequence + 1UL
        let next, result =
            LocalSaveReplayExample.admit
                { SessionId = LocalSaveReplayExample.sessionId
                  InputId = $"synthetic.inspect:{localSequence}"
                  Sequence = localSequence
                  Value = LocalSaveReplayExample.InspectFullCell syntheticDestination }
                localExample
        localExample <- next
        describeLocal (match result with Ok _ -> "inspection accepted" | Error _ -> "inspection refused"))
    button "Save synthetic local snapshot" (fun () ->
        localSaved <- Some(LocalSaveReplayExample.snapshot localExample)
        describeLocal "snapshot saved in memory")
    button "Restore synthetic local snapshot" (fun () ->
        match localSaved with
        | None -> describeLocal "no snapshot saved"
        | Some saved ->
            let next, result = LocalSaveReplayExample.restore saved localExample
            localExample <- next
            localReplayCount <- None
            describeLocal (match result with Ok _ -> "snapshot restored; new recording epoch" | Error _ -> "restore refused"))
    button "Replay synthetic local recording" (fun () ->
        match LocalSaveReplayExample.replay (uint64 localExample.Recording.Events.Length) localExample.Recording with
        | Ok(ReplayRunOutcome.Completed(_, payload)) ->
            localReplayCount <- Some payload.Accepted.Length
            describeLocal "replay preview completed"
        | _ ->
            localReplayCount <- None
            describeLocal "replay preview refused or diverged")
    describeLocal "ready"
#endif

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

            for element, handler in buttonListeners do
                element.removeEventListener ("click", handler)

            buttonListeners.Clear()

            for element, handler in optionListeners do
                element.removeEventListener ("change", handler)

            optionListeners.Clear()
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

            root.remove ()

    button "Dispose FourD reference" dispose
    describe ()

    { new IDisposable with
        member _.Dispose() = dispose ()
    }
