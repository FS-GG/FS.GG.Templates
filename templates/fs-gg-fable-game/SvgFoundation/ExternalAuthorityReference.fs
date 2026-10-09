module FableGameWorkspaceNamespace.SvgFoundation.ExternalAuthorityReference

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.UI.KeyboardInput
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser

[<ImportDefault("./Examples/ExternalAuthority/reference.json?raw")>]
let private fixtureJson: string = jsNative

type private Projection = { Epoch: string; Revision: uint64; Value: int }
type private Acquisition =
    { Generation: uint64; Id: uint64; Snapshot: Projection; mutable Settled: bool }

[<RequireQualifiedAccess>]
type private ReceiptOutcome = Accepted | Rejected | Unknown

type private CommandReceipt =
    { Correlation: string; Epoch: string; Generation: uint64; Outcome: ReceiptOutcome }

[<RequireQualifiedAccess>]
type private Recovery = Awaiting | Reconciled | Abandoned | Rearmed

type private CommandState =
    { Receipts: CommandReceipt list
      Unknown: CommandReceipt option
      Recovery: Recovery
      LoseNextReceipt: bool }

[<RequireQualifiedAccess>]
type private CommandObservation =
    | LoseNext
    | Recorded of CommandReceipt
    | Reconcile of uint64 * string
    | Abandon
    | Rearm

// Receipt evidence is immutable. Recovery annotates the unknown original rather
// than rewriting it as rejected or reissuing its command.
let private updateCommands observation state =
    match observation with
    | CommandObservation.LoseNext -> { state with LoseNextReceipt = true }
    | CommandObservation.Recorded receipt ->
        { state with
            Receipts = state.Receipts @ [ receipt ]
            Unknown = if receipt.Outcome = ReceiptOutcome.Unknown then Some receipt else state.Unknown
            Recovery = if receipt.Outcome = ReceiptOutcome.Unknown then Recovery.Awaiting else state.Recovery
            LoseNextReceipt = receipt.Outcome = ReceiptOutcome.Rejected && state.LoseNextReceipt }
    | CommandObservation.Reconcile(generation, epoch) ->
        match state.Unknown with
        | Some receipt when state.Recovery = Recovery.Awaiting && receipt.Generation = generation && receipt.Epoch = epoch ->
            { state with Recovery = Recovery.Reconciled }
        | _ -> state
    | CommandObservation.Abandon when state.Recovery = Recovery.Awaiting ->
        { state with Recovery = Recovery.Abandoned }
    | CommandObservation.Rearm when state.Recovery = Recovery.Reconciled || state.Recovery = Recovery.Abandoned ->
        { state with Recovery = Recovery.Rearmed }
    | _ -> state

let private commandsSuspended state =
    state.Unknown.IsSome && state.Recovery <> Recovery.Rearmed

let private receiptOutcome = function
    | ReceiptOutcome.Accepted -> "accepted"
    | ReceiptOutcome.Rejected -> "rejected"
    | ReceiptOutcome.Unknown -> "unknown"

let private scene projection =
    { RootId = "external-authority-scene"
      Revision = int projection.Revision
      Camera = { PanX = 23.0; PanY = 17.0; Zoom = 1.6 }
      Layers =
        [ { Id = "authority"; Visible = true
            Objects =
              [ { Id = "external.increment"; Selectable = true; AccessibleLabel = "Increment external value"
                  Content = { Nodes = [ SceneNode.Rectangle((8.0, 12.0, 34.0, 34.0),
                    { Red = 37uy; Green = 99uy; Blue = 235uy; Alpha = 255uy }) ] } } ] } ] }

let private descriptor id label =
    { Id = id; Label = label; Contexts = [ "external.reference" ]; AvailabilityKey = None
      Trigger = CommandTriggerPolicy.OncePerPress; Argument = CommandArgumentPolicy.NoArgument
      Alternatives = [ CommandAlternative.Pointer label ] }

let private catalog =
    { Contexts = [ { Id = "external.reference"; Priority = 10; Exclusive = false; Overlaps = [] } ]
      Commands = [ descriptor "external.increment" "Increment external value"; descriptor "external.reject" "Reject sample command" ]
      ReservedGestures = []; AllowTerminalPrefixes = false }

let private profile =
    { Schema = CommandInput.profileSchema; Id = "external-reference"
      Defaults =
        [ { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "Enter", CommandInput.noModifiers)
            Command = "external.increment"; Context = "external.reference" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "r", CommandInput.noModifiers)
            Command = "external.reject"; Context = "external.reference" }
          { Gesture = InputGesture.Pointer "external.increment"
            Command = "external.increment"; Context = "external.reference" }
          { Gesture = InputGesture.Pointer "external.reject"
            Command = "external.reject"; Context = "external.reference" } ]
      Overrides = [] }

/// Deterministic sample gateway. It proves composition, not engine identity or authentication.
let mount () : IDisposable =
    let fixture: obj = JS.JSON.parse fixtureJson
    let root = document.createElement "section"
    root.id <- "external-authority-reference"
    root.setAttribute("tabindex", "0")
    root.setAttribute("aria-label", "Deterministic external authority reference")
    root.setAttribute("data-fixture-id", unbox<string> fixture?id)
    document.body.appendChild root |> ignore
    let heading = document.createElement "h2"
    heading.textContent <- "Deterministic external authority reference"
    root.appendChild heading |> ignore
    let editor = document.createElement "input"
    editor.setAttribute("aria-label", "External reference note")
    root.appendChild editor |> ignore
    let canvas = document.createElement "div"
    root.appendChild canvas |> ignore
    let mutable authority = { Epoch = "epoch-A"; Revision = 1UL; Value = 0 }
    let mutable replacement = 0UL
    let mutable sequence = 0UL
    let mutable commands: string list = []
    let mutable commandState =
        { Receipts = []; Unknown = None; Recovery = Recovery.Rearmed; LoseNextReceipt = false }
    let mutable commandGeneration = 0UL
    let mutable delayedReceipt: CommandReceipt option = None
    let receiptStatus = document.createElement "p"
    receiptStatus.setAttribute("role", "status")
    receiptStatus.setAttribute("aria-live", "polite")
    root.appendChild receiptStatus |> ignore
    let acquisitions = ResizeArray<Acquisition>()
    let listeners = ResizeArray<HTMLElement * (Event -> unit)>()
    let mutable disposed = false
    let mutable failApply = false
    let mutable cachedSnapshot: Projection option = None
    let mutable selected: string option = None
    let mutable invoke: string -> unit = ignore
    let svg =
        SvgBrowser.mount canvas
            { Width = 180.0; Height = 120.0; AccessibleLabel = "External authority projection"; WheelZoomFactor = 1.1 }
            (scene authority)
            (fun transition ->
                if selected <> transition.State.SelectedObjectId then
                    selected <- transition.State.SelectedObjectId
                    selected |> Option.iter invoke)
        |> Result.defaultWith (fun error -> failwithf "%A" error)
    let mutable hostOption: SvgExternalSessionHost<Projection> option = None
    let describe () =
        root.setAttribute("data-authority-epoch", authority.Epoch)
        root.setAttribute("data-authority-revision", string authority.Revision)
        root.setAttribute("data-command-order", String.concat "," commands)
        root.setAttribute("data-receipt-order", commandState.Receipts |> List.map (fun receipt -> $"{receipt.Correlation}:{receiptOutcome receipt.Outcome}") |> String.concat ",")
        root.setAttribute("data-command-suspended", string (commandsSuspended commandState))
        root.setAttribute("data-command-recovery", string commandState.Recovery)
        root.setAttribute("data-command-owned", if disposed then "0" else string (delayedReceipt |> Option.map (fun _ -> 1) |> Option.defaultValue 0))
        commandState.Unknown |> Option.iter (fun receipt ->
            root.setAttribute("data-unknown-correlation", receipt.Correlation)
            root.setAttribute("data-unknown-epoch", receipt.Epoch)
            root.setAttribute("data-unknown-generation", string receipt.Generation))
        receiptStatus.textContent <-
            if disposed then "Reference disposed. Command evidence is retained; controls are inactive."
            else
                match commandState.Unknown, commandState.Recovery with
                | Some receipt, Recovery.Awaiting -> $"Command {receipt.Correlation} outcome is unknown. Commands are suspended. Reconcile the original receipt or abandon it before rearming; reconnect never retries it."
                | Some receipt, Recovery.Reconciled -> $"Original command {receipt.Correlation} was confirmed accepted. Its unknown receipt is retained. Rearm explicitly to send a new command."
                | Some receipt, Recovery.Abandoned -> $"Original command {receipt.Correlation} remains unknown and was abandoned. Rearm explicitly to send a new command."
                | _ when commandState.LoseNextReceipt -> "The next accepted command receipt will be lost. Its effect may occur; commands will then wait for explicit recovery."
                | _ -> "Commands are ready. The sample gateway can lose the next accepted receipt without retrying its command."
        root.setAttribute("data-request-count", string acquisitions.Count)
        root.setAttribute("data-gateway-owned", string (acquisitions |> Seq.filter (fun a -> not a.Settled) |> Seq.length))
        hostOption |> Option.iter (fun host ->
            let observation = host.Observe()
            root.setAttribute("data-status", string observation.State.Status)
            root.setAttribute("data-pending", string observation.State.AcquisitionPending)
            root.setAttribute("data-queued", string observation.State.PresentationQueued)
            root.setAttribute("data-host-owned", string (observation.OwnedListenerCount + observation.OwnedRequestCount))
            root.setAttribute("data-cancellation-unknown", string observation.CancellationSettlementUnknown)
            root.setAttribute("data-callback-failure", string observation.CallbackFailureObserved)
            root.setAttribute("data-disposed", string observation.IsDisposed))
    let host =
        new SvgExternalSessionHost<Projection>(
            { RequestPresentation = fun generation id epoch ->
                // Capture the genuine fixture envelope now, before asynchronous completion.
                if epoch <> authority.Epoch then failwith "gateway epoch mismatch"
                let snapshot = cachedSnapshot |> Option.defaultValue authority
                cachedSnapshot <- None
                acquisitions.Add { Generation = generation; Id = id; Snapshot = snapshot; Settled = false }
              ApplyPresentation = fun epoch revision projection ->
                if failApply then
                    failApply <- false
                    failwith "sample presentation failure"
                svg.Dispatch(RetainedInteractionMessage.ReplaceScene(scene projection)) |> ignore
                root.setAttribute("data-applied-epoch", epoch)
                root.setAttribute("data-applied-revision", string revision)
                root.setAttribute("data-applied-value", string projection.Value)
              CancelAcquisition = fun generation id ->
                acquisitions |> Seq.tryFind (fun a -> a.Generation = generation && a.Id = id)
                |> Option.iter (fun a -> a.Settled <- true)
              EpochBound = fun generation epoch preserved ->
                commandGeneration <- generation
                root.setAttribute("data-generation", string generation)
                root.setAttribute("data-preserved-baseline", string preserved)
              Disconnected = ignore
              Dispose = fun () -> acquisitions |> Seq.iter (fun a -> a.Settled <- true) })
    hostOption <- Some host
    let availableCommands () =
        if disposed || commandsSuspended commandState then [] else catalog.Commands |> List.map _.Id
    let admit command =
        if not disposed && not (commandsSuspended commandState) then
            sequence <- sequence + 1UL
            let correlation = $"sample:{sequence}"
            commands <- commands @ [ $"{correlation}:{command}" ]
            let accepted = host.Observe().State.Status = SvgExternalSessionStatus.Connected && command = "external.increment"
            if accepted then
                authority <- { authority with Revision = authority.Revision + 1UL; Value = authority.Value + 1 }
            // This mock applies once before losing a receipt. Presentation cannot
            // settle the command; only explicit inspection of its original reply can.
            let outcome =
                if accepted && commandState.LoseNextReceipt then ReceiptOutcome.Unknown
                elif accepted then ReceiptOutcome.Accepted
                else ReceiptOutcome.Rejected
            let receipt =
                { Correlation = correlation; Epoch = authority.Epoch
                  Generation = commandGeneration; Outcome = outcome }
            commandState <- updateCommands (CommandObservation.Recorded receipt) commandState
            if outcome = ReceiptOutcome.Unknown then delayedReceipt <- Some receipt
            host.DemandPresentation()
            describe ()
    let effective = CommandInput.compile catalog profile |> Result.defaultWith (fun error -> failwithf "%A" error)
    let input =
        new SvgInputHost(root, catalog, CommandResolver.init [ "external.reference" ] effective,
            availableCommands,
            (function CommandResolverEffect.InvokeCommand invocation -> admit invocation.Command | _ -> ()),
            { SvgInputHost.defaultOptions with PollGamepads = false })
    let mutable observationSequence = 0UL
    invoke <- fun command ->
        observationSequence <- observationSequence + 1UL
        let observation phase =
            CommandResolverObservation.InputEvent
                { Id = $"external-observation:{observationSequence}:{phase}"
                  Source = "external-reference-invoke"
                  Gesture = InputGesture.Pointer command
                  Phase = phase; IsRepeat = false; NativeEditable = false
                  HostReserved = false; IsComposing = false
                  AvailableCommands = availableCommands () }
        input.Update(observation InputGesturePhase.Pressed) |> ignore
        input.Update(observation InputGesturePhase.Released) |> ignore
    let button label action =
        let element = document.createElement "button"
        element.textContent <- label
        let handler = fun (_: Event) -> action (); describe ()
        element.addEventListener("click", handler)
        listeners.Add(element, handler)
        root.appendChild element |> ignore
    let complete (acquisition: Acquisition) =
        // Even cancelled old replies keep their captured epoch/revision; the host fences them.
        acquisition.Settled <- true
        let snapshot = acquisition.Snapshot
        host.CompletePresentation(acquisition.Generation, acquisition.Id, snapshot.Epoch, snapshot.Revision, snapshot)
    let current () = acquisitions |> Seq.tryFindBack (fun a -> not a.Settled)
    button "Connect sample authority" (fun () -> host.BindEpoch authority.Epoch; host.DemandPresentation())
    button "Disconnect sample authority" host.Disconnect
    button "Replace sample authority" (fun () ->
        replacement <- replacement + 1UL
        let epoch = if replacement = 1UL then "epoch-B" else $"epoch-replacement:{replacement}"
        authority <- { Epoch = epoch; Revision = 1UL; Value = 0 }
        host.BindEpoch authority.Epoch
        host.DemandPresentation())
    button "Increment external value" (fun () -> invoke "external.increment")
    button "Reject sample command" (fun () -> invoke "external.reject")
    button "Lose next command receipt" (fun () ->
        if not disposed && not (commandsSuspended commandState) then
            commandState <- updateCommands CommandObservation.LoseNext commandState)
    let reconcile () =
        commandState <- updateCommands (CommandObservation.Reconcile(commandGeneration, authority.Epoch)) commandState
        if commandState.Recovery = Recovery.Reconciled then delayedReceipt <- None
    button "Reconcile unknown command" reconcile
    button "Abandon unknown command" (fun () ->
        commandState <- updateCommands CommandObservation.Abandon commandState
        delayedReceipt <- None)
    button "Rearm sample commands" (fun () ->
        commandState <- updateCommands CommandObservation.Rearm commandState)
    button "Complete delayed command receipt" (fun () ->
        // The captured reply has no authority to apply a command a second time.
        // An old generation/epoch cannot resolve current recovery state.
        delayedReceipt |> Option.iter (fun receipt ->
            if receipt.Generation = commandGeneration && receipt.Epoch = authority.Epoch then reconcile ()
            delayedReceipt <- None))
    button "Request external burst" (fun () -> host.DemandPresentation(); host.DemandPresentation(); host.DemandPresentation())
    button "Request cached external snapshot" (fun () ->
        cachedSnapshot <- acquisitions |> Seq.tryFind (fun a -> a.Snapshot.Epoch = authority.Epoch) |> Option.map _.Snapshot
        host.DemandPresentation())
    button "Complete current external snapshot" (fun () -> current () |> Option.iter complete)
    button "Complete oldest external snapshot" (fun () -> acquisitions |> Seq.tryHead |> Option.iter complete)
    for label, failure in
        [ "Lose external acquisition", SvgExternalCompletionFailure.Lost
          "Cancel external acquisition", SvgExternalCompletionFailure.Cancelled
          "Fail external acquisition", SvgExternalCompletionFailure.CallbackFailed ] do
        button label (fun () -> current () |> Option.iter (fun a ->
            a.Settled <- true
            host.FailAcquisition(a.Generation, a.Id, a.Snapshot.Epoch, failure)))
    button "Fail next external presentation" (fun () -> failApply <- true)
    let dispose () =
        if not disposed then
            disposed <- true
            delayedReceipt <- None
            for element, handler in listeners do element.removeEventListener("click", handler)
            listeners.Clear()
            (input :> IDisposable).Dispose()
            (host :> IDisposable).Dispose()
            (svg :> IDisposable).Dispose()
            let observation = input.Observe()
            let renderingObservation = svg.Observe()
            root.setAttribute("data-svg-owned", string (renderingObservation.OwnedListenerCount + renderingObservation.ScheduledFrameCount))
            root.setAttribute("data-input-owned", string (observation.OwnedListenerCount + observation.OwnedDeadlineCount + observation.OwnedSourceCount))
            describe ()
            root.setAttribute("data-button-owned", string listeners.Count)
    button "Dispose external reference" dispose
    describe ()
    { new IDisposable with member _.Dispose() = dispose () }

/// Complete-bundle mounting is an explicit user action; connection is a second action.
let install () : IDisposable =
    let button = document.createElement "button"
    button.id <- "mount-external-authority-reference"
    button.textContent <- "Mount external authority reference"
    document.body.appendChild button |> ignore
    let mutable mounted: IDisposable option = None
    let rec handler (_: Event) =
        if mounted.IsNone then
            mounted <- Some(mount ())
            button.removeEventListener("click", handler)
            button.remove()
    button.addEventListener("click", handler)
    { new IDisposable with
        member _.Dispose() =
            button.removeEventListener("click", handler)
            mounted |> Option.iter (fun value -> value.Dispose())
            mounted <- None
            button.remove() }
