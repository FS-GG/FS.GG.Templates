module FableGameWorkspaceNamespace.SvgFoundation

open Browser.Dom
open Browser.Types
open Fable.Core.JsInterop
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
#if LEGACY_SVG_PREVIEW
open FableGameWorkspaceNamespace.TacticalCompatibility
#endif
#if SVG_INPUT_CANDIDATE
open FS.GG.UI.KeyboardInput
module GameInput = FableGameWorkspaceNamespace.SvgFoundation.PlayerInput
#endif
#if SVG_RUNTIME_CANDIDATE
open FS.GG.Game.Core
module ContinuousPlayer = FableGameWorkspaceNamespace.SvgFoundation.ContinuousPlayer
#endif
#if SVG_PRESENT_CANDIDATE
open FS.GG.Audio.Core
open FS.GG.Audio.WebBrowser
#endif
#if SVG_SCALE_CANDIDATE
module ScalePlayer = FableGameWorkspaceNamespace.SvgFoundation.ScalePlayer
#endif

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

let private mount id label scene =
    let container = document.createElement("section")
    container.id <- id
    document.body.appendChild(container) |> ignore
    match SvgBrowser.mount container
              { Width = 220.0; Height = 140.0; AccessibleLabel = label; WheelZoomFactor = 1.1 }
              scene ignore with
    | Ok host -> host
    | Error error -> failwithf "SVG product failed to mount: %A" error

let private requireTransition name (result: RetainedInteractionResult) =
    match result.Error with
    | None -> ()
    | Some error -> failwithf "SVG product %s transition failed: %A" name error

#if LEGACY_SVG_PREVIEW
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

let tacticalCompatibilityScene = (characterizedProjection 41 "shared-scene:41" |> project).Scene

let _, previewExport, previewState = PreviewDocument.verifyPortable ()

let gridHost = mount "foundation-grid-host" "Neutral grid fixture" gridScene
#endif
#if SVG_RUNTIME_CANDIDATE
let private initialPlayerRuntime = ContinuousPlayer.initialize ()
let continuousHost =
    mount "foundation-continuous-host" "Generated continuous SVG game" (ContinuousPlayer.scene 1 initialPlayerRuntime.Current)
#else
#if LEGACY_SVG_PREVIEW
let continuousHost = mount "foundation-continuous-host" "Neutral continuous-coordinate fixture" continuousScene
#else
#error The production SVG player requires FsGgSvgRuntimeCandidate=true.
#endif
#endif
#if LEGACY_SVG_PREVIEW
let tacticalCompatibilityHost =
    mount "foundation-tactical-compatibility-host" "Disclosed tactical compatibility fixture" tacticalCompatibilityScene

#if SVG_SCALE_CANDIDATE
ScalePlayer.mount ()
window?svgGeneratedScale <- createObj [ "snapshot" ==> ScalePlayer.snapshot; "dispose" ==> ScalePlayer.dispose ]
#endif

let previewContainer = document.createElement("section")
previewContainer.id <- "foundation-preview-document-host"
document.body.appendChild(previewContainer) |> ignore

let previewDocumentHost =
    match SvgBrowser.mountDocument previewContainer "generated-preview" PreviewDocument.document with
    | Ok host -> host
    | Error error -> failwithf "SVG Preview-A document failed to mount: %A" error

previewDocumentHost.Root.setAttribute(
    "data-preview-selected-semantic",
    previewState.SelectedSemanticId |> Option.defaultValue "")

let previewExportOutput = document.createElement("output")
previewExportOutput.id <- "foundation-preview-export"
previewExportOutput.setAttribute("hidden", "")
previewExportOutput.textContent <- previewExport
document.body.appendChild(previewExportOutput) |> ignore

requireTransition "tactical selection"
    (tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.Select(41, "unit:7")))
requireTransition "tactical focus"
    (tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.FocusNext 41))
#endif

#if SVG_INPUT_CANDIDATE
let private playerInputScope: HTMLElement =
#if SVG_RUNTIME_CANDIDATE
    document.getElementById("foundation-continuous-host")
#else
#if LEGACY_SVG_PREVIEW
    document.getElementById("foundation-tactical-compatibility-host")
#else
    document.body
#endif
#endif
playerInputScope.setAttribute("tabindex", "-1")
let private playerInputStatus = document.createElement("output")
playerInputStatus.id <- "foundation-player-input-status"
playerInputStatus.setAttribute("aria-live", "polite")
playerInputStatus.setAttribute("hidden", "")
playerInputScope.appendChild(playerInputStatus) |> ignore

#if SVG_RUNTIME_CANDIDATE
let mutable private playerRuntime = initialPlayerRuntime
let mutable private playerSequence = 0UL
let mutable private presentationRevision = 1UL
let mutable private sessionHost: SvgSessionHost<ContinuousPlayer.PlayerState> option = None

let private updatePlayer observation =
    let next, _ = SessionRuntime.update ContinuousPlayer.contract observation playerRuntime
    playerRuntime <- next

let private describePlayer (revision: uint64) (state: ContinuousPlayer.PlayerState) =
    let outcome =
        match state.Outcome with
        | ContinuousPlayer.PlayerOutcome.Playing -> "playing"
        | ContinuousPlayer.PlayerOutcome.Won -> "won"
        | ContinuousPlayer.PlayerOutcome.Lost -> "lost"
    playerInputScope.setAttribute("data-player-revision", string revision)
    playerInputScope.setAttribute("data-player-x", string state.Player.X)
    playerInputScope.setAttribute("data-player-y", string state.Player.Y)
    playerInputScope.setAttribute("data-player-health", string state.Health)
    playerInputScope.setAttribute("data-player-score", string state.Score)
    playerInputScope.setAttribute("data-player-outcome", outcome)

#if SVG_PRESENT_CANDIDATE
let private audioEvents = ResizeArray<WebAudioHostEvent>()
let mutable private refreshAudioObservation: unit -> unit = ignore
let private onAudioEvent event =
    audioEvents.Add event
    playerInputScope.setAttribute("data-audio-event", string event)
    refreshAudioObservation()
let private audioHost = new WebAudioHost(WebAudioHost.defaultConfig, onAudioEvent)
let private movementSound = SoundId "generated-movement"
let private toneUrl = "data:audio/wav;base64,UklGRiUAAABXQVZFZm10IBAAAAABAAEARKwAAESsAAABAAgAZGF0YQEAAACA"

let private audioUnlock = document.createElement("button")
audioUnlock.id <- "foundation-audio-unlock"
audioUnlock.textContent <- "Enable game audio"
audioUnlock.addEventListener("click", fun _ ->
    audioHost.UnlockFromGesture()
    audioHost.LoadSound(movementSound, toneUrl))
playerInputScope.appendChild(audioUnlock) |> ignore
refreshAudioObservation <- fun () ->
    let value = audioHost.Observe()
    playerInputScope.setAttribute("data-audio-status", string value.Status)
    playerInputScope.setAttribute("data-audio-ready-assets", string value.ReadyAssetCount)
    playerInputScope.setAttribute("data-audio-voices", string value.GraphVoiceCount)
refreshAudioObservation()

let private persistenceEvents = ResizeArray<BrowserPersistenceEvent>()
let mutable private handlePersistenceEvent: BrowserPersistenceEvent -> unit = ignore
let private persistenceHost =
    new BrowserPersistenceHost(
        { DatabaseName = "FableGameWorkspaceNamespace-svg-player"
          MaxPayloadCharacters = 4096
          MaxArchiveCharacters = 32768 },
        fun event ->
            persistenceEvents.Add event
            handlePersistenceEvent event)
let mutable private autosave =
    Autosave.initialize { DebounceMilliseconds = 50UL } None
    |> Result.defaultWith (fun error -> failwithf "Generated autosave could not initialize: %A" error)
let mutable private requestCurrentProjection: unit -> unit = ignore
let mutable private lastArchive = ""
let mutable private archiveOperation = 1000000UL

let private persistenceOutput = document.createElement("output")
persistenceOutput.id <- "foundation-persistence-status"
persistenceOutput.setAttribute("aria-live", "polite")
playerInputScope.appendChild(persistenceOutput) |> ignore

let private operationId (value: SaveOperationId) =
    { BrowserStorageOperationId.Generation = value.Generation; Operation = value.Operation }

let private saveOperationId (value: BrowserStorageOperationId) =
    { SaveOperationId.Generation = value.Generation; Operation = value.Operation }

let rec private observeAutosave observation =
    let next, effects = Autosave.update observation autosave
    autosave <- next
    playerInputScope.setAttribute("data-autosave-status", string next.Status)
    for effect in effects do
        match effect with
        | AutosaveEffect.Persist(operation, payload) ->
            persistenceHost.Persist(
                operationId operation,
                { Key = { Family = BrowserStorageFamily.GameSave; Slot = "primary" }
                  SchemaVersion = 1
                  PayloadHash = PresentationPlayer.hashPayload payload
                  Payload = payload })
        | AutosaveEffect.Committed(operation, _) ->
            playerInputScope.setAttribute("data-autosave-operation", string operation.Operation)
            persistenceOutput.textContent <- "Game saved"
        | AutosaveEffect.Refused refusal -> persistenceOutput.textContent <- $"Save refused: {refusal}"
        | _ -> ()

let private scheduleAutosave payload =
    let now = uint64 (System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds())
    observeAutosave (AutosaveObservation.Edit(now, payload))
    window.setTimeout((fun () -> observeAutosave (AutosaveObservation.Tick(now + 50UL))), 50) |> ignore

let private animationEvents = ResizeArray<string>()
let mutable private lastAnimationId = ""
let private animationCallbacks =
    { ApplySample = fun _ _ revision sample ->
          let player = continuousHost.Root.querySelector("[data-scene-object-id='player']")
          let scalar property fallback =
              match sample.Values |> Map.tryFind property with
              | Some(ScalarValue value) -> value
              | _ -> fallback
          let offset = scalar PositionX 0.0
          let scaleX = scalar ScaleX 1.0
          let scaleY = scalar ScaleY 1.0
          player.setAttribute("transform", $"translate({offset} 0) scale({scaleX} {scaleY})")
          player.setAttribute("opacity", string (scalar Opacity 1.0))
          playerInputScope.setAttribute("data-animation-revision", string revision)
      DispatchCues = fun _ _ cues ->
          for cue in cues do
              animationEvents.Add cue.Cue.Payload
              audioHost.Dispatch(FS.GG.Audio.Core.Audio.playSfx movementSound 0.65)
              playerInputScope.setAttribute("data-last-live-cue", cue.Cue.Payload)
              playerInputScope.setAttribute("data-live-cue-count", string animationEvents.Count)
      Refused = fun refusal -> playerInputScope.setAttribute("data-animation-refusal", string refusal)
      Dispose = fun () -> () }
let private animationHost = new SvgAnimationHost(animationCallbacks, SvgAnimationHost.defaultConfig, playerRuntime.Current.Revision)

let private startPresentation outcome =
    animationHost.ReplaceAuthority(playerRuntime.Current.Revision)
    let clip = if outcome then PresentationPlayer.outcomeClip else PresentationPlayer.movementClip
    lastAnimationId <- $"generated-effect-{playerSequence}"
    animationHost.Start(
        { Id = lastAnimationId
          AuthorityRevision = playerRuntime.Current.Revision
          Clip = clip
          Importance = if outcome then Essential else Decorative SvgReducedMotionBehavior.Settle })
    scheduleAutosave (PresentationPlayer.encode playerRuntime.Current)

handlePersistenceEvent <- function
    | BrowserPersistenceEvent.Ready -> playerInputScope.setAttribute("data-persistence-ready", "true")
    | BrowserPersistenceEvent.Persisted operation -> observeAutosave (AutosaveObservation.Persisted(saveOperationId operation))
    | BrowserPersistenceEvent.Failed(Some operation, failure) ->
        match autosave.InFlight with
        | Some(expected, _) when expected = saveOperationId operation ->
            observeAutosave (AutosaveObservation.PersistFailed(expected, string failure))
            persistenceOutput.textContent <- "Autosave failed; edit or retry remains available"
        | _ -> persistenceOutput.textContent <- $"Persistence refused: {failure}"
    | BrowserPersistenceEvent.Loaded(_, Some value) ->
        match PresentationPlayer.acceptEnvelope value.SchemaVersion value.PayloadHash value.Payload with
        | Ok payload ->
            match PresentationPlayer.decode payload with
            | Ok state ->
                let snapshot: SessionSnapshot<ContinuousPlayer.PlayerState> =
                    { SessionId = "generated-player"
                      Revision = state.Revision
                      Compatibility = ContinuousPlayer.compatibility
                      Value = state }
                updatePlayer (SessionRuntimeObservation.Restore snapshot)
                describePlayer state.Revision state
                requestCurrentProjection()
                persistenceOutput.textContent <- "Game loaded"
            | Error diagnostic -> persistenceOutput.textContent <- "Load refused: " + diagnostic
        | Error refusal -> persistenceOutput.textContent <- $"Load refused: {refusal}"
    | BrowserPersistenceEvent.Loaded(_, None) -> persistenceOutput.textContent <- "No saved game"
    | BrowserPersistenceEvent.Exported archive ->
        lastArchive <- archive
        playerInputScope.setAttribute("data-archive-length", string archive.Length)
        persistenceOutput.textContent <- "Archive exported"
    | BrowserPersistenceEvent.Imported _ ->
        persistenceHost.Load({ Family = BrowserStorageFamily.GameSave; Slot = "primary" })
        persistenceOutput.textContent <- "Archive imported"
    | BrowserPersistenceEvent.Failed(_, failure) -> persistenceOutput.textContent <- $"Persistence refused: {failure}"
    | _ -> ()
#endif

let private callbacks =
    { AdvanceElapsed = fun elapsed -> updatePlayer (SessionRuntimeObservation.AdvanceElapsed elapsed)
      Pause = fun () -> updatePlayer SessionRuntimeObservation.Pause
      Resume = fun () -> updatePlayer SessionRuntimeObservation.Resume
      StepOnce = fun () -> updatePlayer SessionRuntimeObservation.StepOnce
      Reset = fun () -> updatePlayer SessionRuntimeObservation.Reset
      RequestRecovery = fun _ -> window.setTimeout((fun () -> sessionHost |> Option.iter _.Resume()), 0) |> ignore
      RequestProjection = fun generation ->
          presentationRevision <- presentationRevision + 1UL
          sessionHost |> Option.iter (fun host -> host.CompleteProjection(generation, presentationRevision, playerRuntime.Current))
      ApplyProjection = fun revision projection ->
          requireTransition "continuous projection" (continuousHost.Dispatch(RetainedInteractionMessage.ReplaceScene(ContinuousPlayer.scene (int revision) projection)))
          describePlayer revision projection
      CancelGeneration = ignore
      Replace = ignore
      Dispose = fun () -> () }

let private playerSessionHost = new SvgSessionHost<ContinuousPlayer.PlayerState>(callbacks, SvgSessionHost.defaultConfig)
sessionHost <- Some playerSessionHost
describePlayer presentationRevision playerRuntime.Current
#if SVG_PRESENT_CANDIDATE
requestCurrentProjection <- fun () -> playerSessionHost.DemandProjection()
#endif

let private submit commandId command =
    playerSequence <- playerSequence + 1UL
    updatePlayer
        (SessionRuntimeObservation.AdmitInput
            { SessionId = "generated-player"; InputId = commandId; Sequence = playerSequence; Value = command })
    playerSessionHost.DemandProjection()

let private dispatchGameCommand command =
    match command with
    | "game.move-up" -> submit command (ContinuousPlayer.PlayerCommand.Move(0.0, -3.0))
    | "game.move-down" -> submit command (ContinuousPlayer.PlayerCommand.Move(0.0, 3.0))
    | "game.move-left" -> submit command (ContinuousPlayer.PlayerCommand.Move(-3.0, 0.0))
    | "game.move-right" -> submit command (ContinuousPlayer.PlayerCommand.Move(3.0, 0.0))
    | "game.stop" -> submit command ContinuousPlayer.PlayerCommand.Stop
    | "game.pause" ->
        if playerSessionHost.Observe().Status = SvgSessionStatus.Running then playerSessionHost.Pause()
        else playerSessionHost.Resume()
    | "game.step" -> playerSessionHost.StepOnce()
    | "game.reset"
    | "game.restart" -> playerSessionHost.Reset()
    | "game.win" -> submit command ContinuousPlayer.PlayerCommand.Collect
    | "game.interact" -> submit command ContinuousPlayer.PlayerCommand.Collect
    | "game.lose" -> submit command ContinuousPlayer.PlayerCommand.Damage
    | _ -> ()
#if SVG_PRESENT_CANDIDATE
    if command.StartsWith("game.") && command <> "game.pause" && command <> "game.step" then
        startPresentation (playerRuntime.Current.Outcome <> ContinuousPlayer.PlayerOutcome.Playing)
#endif
    playerInputScope.setAttribute("data-last-game-command", command)
    playerInputStatus.textContent <- "Accepted " + command

let private addControl action label =
    let control = document.createElement("span")
    control.textContent <- label
    control.setAttribute("data-fsgg-input-action", action)
    control.setAttribute("role", "button")
    control.setAttribute("tabindex", "0")
    playerInputScope.appendChild(control) |> ignore

for action, label in
    [ "move-right", "Move right"; "move-left", "Move left"; "pause", "Pause or resume"
      "step", "Single step"; "reset", "Reset"; "interact", "Interact"; "win", "Win"
      "lose", "Take damage"; "restart", "Restart" ] do
    addControl action label
#if SVG_PRESENT_CANDIDATE
let private addPresentationControl id label action =
    let control = document.createElement("button")
    control.id <- id
    control.textContent <- label
    control.addEventListener("click", fun _ -> action())
    playerInputScope.appendChild(control) |> ignore

addPresentationControl "foundation-load" "Load game" (fun () -> persistenceHost.Load({ Family = BrowserStorageFamily.GameSave; Slot = "primary" }))
addPresentationControl "foundation-retry-save" "Retry save" (fun () -> observeAutosave AutosaveObservation.Retry)
addPresentationControl "foundation-export" "Export archive" (fun () -> persistenceHost.ExportArchive())
addPresentationControl "foundation-import" "Import archive" (fun () ->
    if not (System.String.IsNullOrEmpty lastArchive) then
        archiveOperation <- archiveOperation + 1UL
        persistenceHost.ImportArchive({ Generation = autosave.Generation; Operation = archiveOperation }, lastArchive))
addPresentationControl "foundation-animation-seek" "Seek animation" (fun () ->
    if not (System.String.IsNullOrEmpty lastAnimationId) then
        animationHost.Seek(lastAnimationId, System.TimeSpan.FromMilliseconds 100.0))
addPresentationControl "foundation-fail-save" "Exercise failed autosave" (fun () -> scheduleAutosave (System.String('x', 4097)))
#endif
#else
#if LEGACY_SVG_PREVIEW
let private dispatchGameCommand command =
    let revision = tacticalCompatibilityHost.State.Scene.Revision
    let result =
        match command with
        | "game.focus-next" -> tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.FocusNext revision) |> Some
        | "game.focus-previous" -> tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.FocusPrevious revision) |> Some
        | "game.activate" ->
            tacticalCompatibilityHost.State.FocusedObjectId
            |> Option.map (fun id -> tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.Select(revision, id)))
        | _ -> None
    match result with
    | Some accepted when accepted.Error.IsNone ->
        playerInputScope.setAttribute("data-last-game-command", command)
        playerInputStatus.textContent <- "Accepted " + command
    | _ -> ()
#endif
#endif

let private playerInputHost =
    new SvgInputHost(
        playerInputScope,
        GameInput.catalog,
        CommandResolver.init [ "game.play" ] GameInput.effective,
        (fun () -> GameInput.catalog.Commands |> List.map _.Id),
        (function CommandResolverEffect.InvokeCommand value -> dispatchGameCommand value.Command | _ -> ()),
        SvgInputHost.defaultOptions)
#if SVG_RUNTIME_CANDIDATE
let private refreshGamepads (_: Event) =
    playerInputHost.PollGamepadsOnce()
    playerInputScope.setAttribute("data-gamepad-active-sources", string (playerInputHost.Observe().OwnedSourceCount))
window.addEventListener("gamepadconnected", refreshGamepads)
#endif
#endif

// Keep the mounted hosts alive for the lifetime of the generated sample.
window.addEventListener("beforeunload", fun _ ->
#if SVG_SCALE_CANDIDATE
    ScalePlayer.dispose ()
#endif
#if SVG_INPUT_CANDIDATE
    (playerInputHost :> System.IDisposable).Dispose()
#if SVG_RUNTIME_CANDIDATE
    window.removeEventListener("gamepadconnected", refreshGamepads)
    (playerSessionHost :> System.IDisposable).Dispose()
#if SVG_PRESENT_CANDIDATE
    (animationHost :> System.IDisposable).Dispose()
    (audioHost :> System.IDisposable).Dispose()
    (persistenceHost :> System.IDisposable).Dispose()
#endif
#endif
#endif
    (continuousHost :> System.IDisposable).Dispose()
#if LEGACY_SVG_PREVIEW
    (gridHost :> System.IDisposable).Dispose()
    (tacticalCompatibilityHost :> System.IDisposable).Dispose()
    (previewDocumentHost :> System.IDisposable).Dispose()
#endif
    )
