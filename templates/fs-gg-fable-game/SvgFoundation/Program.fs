module FableGameWorkspaceNamespace.SvgFoundation

open Browser.Dom
open Browser.Types
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.TacticalCompatibility
#if SVG_INPUT_CANDIDATE
open FS.GG.UI.KeyboardInput
module GameInput = FableGameWorkspaceNamespace.SvgFoundation.PlayerInput
#endif
#if SVG_RUNTIME_CANDIDATE
open FS.GG.Game.Core
module ContinuousPlayer = FableGameWorkspaceNamespace.SvgFoundation.ContinuousPlayer
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
#if SVG_RUNTIME_CANDIDATE
let private initialPlayerRuntime = ContinuousPlayer.initialize ()
let continuousHost =
    mount "foundation-continuous-host" "Generated continuous SVG game" (ContinuousPlayer.scene 1 initialPlayerRuntime.Current)
#else
let continuousHost = mount "foundation-continuous-host" "Neutral continuous-coordinate fixture" continuousScene
#endif
let tacticalCompatibilityHost =
    mount "foundation-tactical-compatibility-host" "Disclosed tactical compatibility fixture" tacticalCompatibilityScene

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

let private requireTransition name (result: RetainedInteractionResult) =
    match result.Error with
    | None -> ()
    | Some error -> failwithf "SVG foundation %s transition failed: %A" name error
requireTransition "tactical selection"
    (tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.Select(41, "unit:7")))
requireTransition "tactical focus"
    (tacticalCompatibilityHost.Dispatch(RetainedInteractionMessage.FocusNext 41))

#if SVG_INPUT_CANDIDATE
let private playerInputScope: HTMLElement =
#if SVG_RUNTIME_CANDIDATE
    document.getElementById("foundation-continuous-host")
#else
    document.getElementById("foundation-tactical-compatibility-host")
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
    | "game.lose" -> submit command ContinuousPlayer.PlayerCommand.Damage
    | _ -> ()
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
      "step", "Single step"; "reset", "Reset"; "win", "Win"; "lose", "Take damage"; "restart", "Restart" ] do
    addControl action label
#else
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
#if SVG_INPUT_CANDIDATE
    (playerInputHost :> System.IDisposable).Dispose()
#if SVG_RUNTIME_CANDIDATE
    window.removeEventListener("gamepadconnected", refreshGamepads)
    (playerSessionHost :> System.IDisposable).Dispose()
#endif
#endif
    (gridHost :> System.IDisposable).Dispose()
    (continuousHost :> System.IDisposable).Dispose()
    (tacticalCompatibilityHost :> System.IDisposable).Dispose()
    (previewDocumentHost :> System.IDisposable).Dispose())
