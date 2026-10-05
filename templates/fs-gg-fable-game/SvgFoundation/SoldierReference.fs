module FableGameWorkspaceNamespace.SvgFoundation.SoldierReference

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.UI.KeyboardInput
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.SoldierWorkload

module Art = FableGameWorkspaceNamespace.SoldierDocument
module Local = FableGameWorkspaceNamespace.SvgFoundation.SoldierReferenceLocal
module External = FableGameWorkspaceNamespace.SvgFoundation.SoldierReferenceExternal

type private Authority = Local of Local.Owner | External of External.Owner

let private actions =
    [ "select", "Select focused soldier"; "next", "Focus next soldier"; "previous", "Focus previous soldier"
      "move", "Move selected soldier"; "pose", "Change selected pose"; "appearance", "Change selected appearance"
      "spawn", "Spawn soldier"; "remove", "Remove selected soldier"; "pan", "Pan to offscreen soldiers"
      "definitions", "Revise soldier definitions" ]
let private descriptor (id, label) =
    { Id = "soldier." + id; Label = label; Contexts = [ "soldier.reference" ]; AvailabilityKey = None
      Trigger = CommandTriggerPolicy.OncePerPress; Argument = CommandArgumentPolicy.NoArgument
      Alternatives = [ CommandAlternative.Pointer label ] }
let private catalog =
    { Contexts = [ { Id = "soldier.reference"; Priority = 10; Exclusive = false; Overlaps = [] } ]
      Commands = List.map descriptor actions; ReservedGestures = []; AllowTerminalPrefixes = false }
let private profile =
    let binding gesture action = { Gesture = gesture; Command = "soldier." + action; Context = "soldier.reference" }
    { Schema = CommandInput.profileSchema; Id = "soldier-reference"
      Defaults =
        [ for key, action in [ "Enter", "select"; "ArrowDown", "next"; "ArrowUp", "previous"; "ArrowRight", "move"
                              "p", "pose"; "f", "appearance"; "Delete", "remove"; "n", "spawn"; "c", "pan" ] do
              yield binding (InputGesture.KeyChord(InputKeyIdentity.LogicalKey key, CommandInput.noModifiers)) action
          for action, _ in actions do
              yield binding (InputGesture.Pointer action) action
              yield binding (InputGesture.Touch action) action ]
      Overrides = [] }

[<Emit("((p) => ({X:p.x,Y:p.y}))(new DOMPoint($1,$2).matrixTransform($0.getScreenCTM().inverse()))")>]
let private svgPoint (_root: Element) (_clientX: float) (_clientY: float) : Point = jsNative

[<Emit("(function(text){const url=URL.createObjectURL(new Blob([text],{type:'image/svg+xml'}));const a=document.createElement('a');a.href=url;a.download='soldier-world.svg';a.click();URL.revokeObjectURL(url);})($0)">]
let private download (_svg: string) : unit = jsNative

let mount () : IDisposable =
    let root = document.createElement "section"
    root.id <- "soldier-reference"
    root.setAttribute("aria-label", "Equipped soldier reference")
    root.setAttribute("tabindex", "0")
    root.setAttribute("data-asset-sha256", "3e6e631625a71e3df3dc33940bb23460f9c9568b7d3a84804348b370be18ebd3")
    document.body.appendChild root |> ignore
    let heading = document.createElement "h2"
    heading.textContent <- "Equipped soldier reference"
    root.appendChild heading |> ignore
    let note = document.createElement "input"
    note.setAttribute("aria-label", "Soldier reference note")
    root.appendChild note |> ignore
    let status = document.createElement "output"
    status.setAttribute("aria-live", "polite")
    root.appendChild status |> ignore
    let controls = document.createElement "div"
    root.appendChild controls |> ignore
    let canvas = document.createElement "div"
    canvas.setAttribute("data-soldier-canvas", "true")
    root.appendChild canvas |> ignore
    let roster = document.createElement "div"
    roster.setAttribute("aria-label", "Soldier roster")
    root.appendChild roster |> ignore
    let export = document.createElement "output"
    export.id <- "soldier-reference-export"
    export.setAttribute("hidden", "")
    root.appendChild export |> ignore
    let snapshot = document.createElement "output"
    snapshot.id <- "soldier-reference-state"
    snapshot.setAttribute("hidden", "")
    root.appendChild snapshot |> ignore
    let mutable state = initial 100 100 |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    let mutable accepted: Art.AcceptedProjection option = None
    let mutable renderer: SvgDocumentBrowserHost option = None
    let mutable authority: Authority option = None
    let mutable mode = "local"
    let mutable visibleCount = 100
    let mutable worldCount = 100
    let mutable mountGeneration = 0
    let mutable spawnSequence = 0
    let mutable observationSequence = 0UL
    let mutable selectionTarget: string option = None
    let mutable disposed = false
    let mutable failReplacement = false
    let listeners = ResizeArray<HTMLElement * string * (Event -> unit)>()
    let rosterButtons = System.Collections.Generic.Dictionary<string, HTMLElement>()
    let rosterHandlers = System.Collections.Generic.Dictionary<string, Event -> unit>()
    let mutable invoke: string -> unit = ignore
    let mutable refresh: unit -> unit = ignore
    let report message = status.textContent <- message; root.setAttribute("data-refusal", message)
    let listen element event handler =
        element.addEventListener(event, handler)
        listeners.Add(element, event, handler)
    let button parent label action =
        let element = document.createElement "button"
        element.textContent <- label
        listen element "click" (fun _ -> if not disposed then action (); refresh ())
        parent.appendChild element |> ignore
        element
    let describe () =
        root.setAttribute("data-mode", mode)
        root.setAttribute("data-authority-revision", string state.Workload.AuthorityRevision)
        root.setAttribute("data-presentation-revision", string state.Presentation.Revision)
        root.setAttribute("data-selected", state.Presentation.Selected |> Option.defaultValue "")
        root.setAttribute("data-focused", state.Presentation.Focused |> Option.defaultValue "")
        root.setAttribute("data-world-count", string state.Workload.Soldiers.Length)
        root.setAttribute("data-definition-revision", string state.Workload.DefinitionRevision)
        match authority with
        | Some(Local owner) ->
            let value = owner.Observe()
            root.setAttribute("data-status", string value.Status)
            root.setAttribute("data-local-owned", string (value.OwnedListenerCount + value.ScheduledFrameCount + value.OwnedRequestCount))
            root.setAttribute("data-external-owned", "0")
        | Some(External owner) ->
            let value = owner.Observe()
            let epoch, revision, receipts, pending = owner.Describe()
            root.setAttribute("data-status", string value.State.Status)
            root.setAttribute("data-gateway-epoch", epoch)
            root.setAttribute("data-gateway-revision", string revision)
            root.setAttribute("data-receipts", receipts)
            root.setAttribute("data-gateway-owned", string pending)
            root.setAttribute("data-callback-failure", string value.CallbackFailureObserved)
            root.setAttribute("data-cancellation-unknown", string value.CancellationSettlementUnknown)
            root.setAttribute("data-last-outcome", sprintf "%A" value.State.LastOutcome)
            root.setAttribute("data-local-owned", "0")
            root.setAttribute("data-external-owned", string (value.OwnedListenerCount + value.OwnedRequestCount))
        | None -> ()
        snapshot.textContent <- JS.JSON.stringify (createObj [
            "revision" ==> state.Workload.AuthorityRevision
            "definitionRevision" ==> state.Workload.DefinitionRevision
            "soldiers" ==> (state.Workload.Soldiers |> List.map (fun soldier -> createObj [
                "id" ==> soldier.Id; "x" ==> soldier.Position.X; "y" ==> soldier.Position.Y
                "facing" ==> soldier.FacingDegrees; "health" ==> soldier.Health
                "faction" ==> string soldier.Faction; "pose" ==> string soldier.Pose ])) ])
    let synchronizeRoster () =
        let ids = state.Workload.Soldiers |> List.map _.Id |> Set.ofList
        for id in rosterButtons.Keys |> Seq.toArray do
            if not (Set.contains id ids) then
                let element = rosterButtons[id]
                element.removeEventListener("click", rosterHandlers[id])
                element.remove()
                rosterButtons.Remove id |> ignore
                rosterHandlers.Remove id |> ignore
        for soldier in state.Workload.Soldiers do
            let element =
                match rosterButtons.TryGetValue soldier.Id with
                | true, element -> element
                | _ ->
                    let element = document.createElement "button"
                    element.setAttribute("data-soldier-id", soldier.Id)
                    let handler = fun (_: Event) ->
                        if not disposed then selectionTarget <- Some soldier.Id; invoke "select"
                    element.addEventListener("click", handler)
                    rosterButtons.Add(soldier.Id, element)
                    rosterHandlers.Add(soldier.Id, handler)
                    roster.appendChild element |> ignore
                    element
            element.textContent <- sprintf "%s, %A, %A, health %d" soldier.Id soldier.Faction soldier.Pose soldier.Health
            element.setAttribute("aria-pressed", if state.Presentation.Selected = Some soldier.Id then "true" else "false")
            element.setAttribute("data-focused", if state.Presentation.Focused = Some soldier.Id then "true" else "false")
    let commit candidate =
        let all = candidate.Workload.Soldiers |> List.map _.Id |> Set.ofList
        let projected, issues = Art.tryAccept candidate all accepted
        match projected, issues with
        | Some projection, None ->
            // Full scene: viewport differs, but no soldier or definition is filtered out.
            let display = { projection.Full with ViewBox = { X = 0.; Y = 0.; Width = 400.; Height = 300. } }
            let display = if failReplacement then { display with Schema = "invalid-fixture-schema" } else display
            failReplacement <- false
            let result =
                match renderer with
                | Some host -> host.Replace display
                | None ->
                    match SvgBrowser.mountDocument canvas (sprintf "soldier-mount-%d" mountGeneration) display with
                    | Error error -> Error error
                    | Ok host ->
                        renderer <- Some host
                        host.Root.setAttribute("width", "600")
                        host.Root.setAttribute("height", "450")
                        Ok ()
            match result with
            | Error error -> failwithf "Soldier document replacement refused: %A" error
            | Ok () ->
                let removedFocus = state.Presentation.Focused |> Option.exists (fun id -> not (Set.contains id all))
                state <- candidate
                accepted <- Some projection
                export.textContent <- projection.ExportedSvg
                synchronizeRoster ()
                describe ()
                if removedFocus then
                    status.textContent <- "Focused soldier removed; focus moved to the first survivor or panel"
                    match state.Presentation.Focused with
                    | Some id -> rosterButtons[id].focus()
                    | None -> root.focus()
        | _, Some issues -> failwith (String.concat "," issues)
        | _ -> failwith "Soldier projection did not produce an accepted value"
    let apply workload =
        let ids = workload.Soldiers |> List.map _.Id |> Set.ofList
        let retained value = value |> Option.filter (fun id -> Set.contains id ids)
        let focused =
            match state.Presentation.Focused with
            | Some id when not (Set.contains id ids) -> workload.Soldiers |> List.tryHead |> Option.map _.Id
            | other -> other
        let selected = retained state.Presentation.Selected
        let changed = selected <> state.Presentation.Selected || focused <> state.Presentation.Focused
        if changed && state.Presentation.Revision = Int32.MaxValue then failwith "presentation revision overflow"
        let presentation =
            { state.Presentation with Selected = selected; Focused = focused
                                      Revision = state.Presentation.Revision + (if changed then 1 else 0) }
        commit { Workload = workload; Presentation = presentation }
    let retire () =
        match authority with
        | Some(Local owner) ->
            owner.Dispose()
            let value = owner.Observe()
            root.setAttribute("data-retired-authority-owned", string (value.OwnedListenerCount + value.ScheduledFrameCount + value.OwnedRequestCount))
        | Some(External owner) ->
            owner.Dispose()
            let value = owner.Observe()
            let _, _, _, gatewayOwned = owner.Describe()
            root.setAttribute("data-retired-authority-owned", string (value.OwnedListenerCount + value.OwnedRequestCount + gatewayOwned))
        | None -> ()
        authority <- None
        renderer |> Option.iter (fun host ->
            (host :> IDisposable).Dispose()
            root.setAttribute("data-retired-svg-connected", string host.Root.isConnected))
        renderer <- None
    let start selectedMode =
        retire ()
        mode <- selectedMode
        mountGeneration <- mountGeneration + 1
        state <- initial visibleCount worldCount |> Result.defaultWith (fun issues -> failwithf "%A" issues)
        accepted <- None
        commit state
        authority <-
            if mode = "local" then Some(Local(Local.create state.Workload apply report))
            else Some(External(External.create state.Workload apply report))
        describe ()
    let submit command =
        match command with
        | Command.Select _ | Command.Focus _ | Command.Camera _ ->
            let next, issues = tryApply command state
            match issues with Some issues -> report (String.concat "," issues) | None -> commit next
        | _ ->
            match authority with
            | Some(Local owner) -> owner.Submit(Local.Intent.Product command)
            | Some(External owner) -> owner.Submit command
            | None -> ()
    let selected () = state.Workload.Soldiers |> List.tryFind (fun soldier -> state.Presentation.Selected = Some soldier.Id)
    let moveFocus direction =
        let ids = state.Workload.Soldiers |> List.map _.Id |> List.toArray
        if ids.Length > 0 then
            let current = ids |> Array.tryFindIndex (fun id -> state.Presentation.Focused = Some id) |> Option.defaultValue (if direction > 0 then -1 else 0)
            submit (Command.Focus(Some ids[(current + direction + ids.Length) % ids.Length]))
    let dispatch action =
        try
            match action with
            | "soldier.select" ->
                let id = selectionTarget |> Option.orElse state.Presentation.Focused |> Option.orElse (state.Workload.Soldiers |> List.tryHead |> Option.map _.Id)
                selectionTarget <- None
                submit (Command.Focus id)
                submit (Command.Select id)
            | "soldier.next" -> moveFocus 1
            | "soldier.previous" -> moveFocus -1
            | "soldier.move" -> selected () |> Option.iter (fun soldier ->
                submit (Command.Move(soldier.Id, { soldier.Position with X = soldier.Position.X + 16. }, soldier.FacingDegrees + 5.)))
            | "soldier.pose" -> selected () |> Option.iter (fun soldier ->
                let pose = match soldier.Pose with Pose.Ready -> Pose.March | Pose.March -> Pose.Kneel | Pose.Kneel -> Pose.Ready
                submit (Command.ChangePose(soldier.Id, pose)))
            | "soldier.appearance" -> selected () |> Option.iter (fun soldier ->
                let faction = if soldier.Faction = Faction.Blue then Faction.Amber else Faction.Blue
                submit (Command.ChangeAppearance(soldier.Id, faction, max 0 (soldier.Health - 10))))
            | "soldier.remove" -> selected () |> Option.iter (fun soldier -> submit (Command.Remove soldier.Id))
            | "soldier.spawn" ->
                spawnSequence <- spawnSequence + 1
                submit (Command.Spawn { Id = sprintf "soldier-browser-spawn-%d" spawnSequence; Position = { X = 96.; Y = 96. }
                                        FacingDegrees = 15.; Faction = Faction.Amber; Pose = Pose.March; Health = 80 })
            | "soldier.pan" ->
                let x = if state.Presentation.Camera.E = 0. then -10000. else 0.
                submit (Command.Camera(SvgAffine.translate x 0.))
            | "soldier.definitions" -> submit (Command.ReviseDefinitions(if state.Workload.DefinitionRevision = 1 then 2 else 1))
            | _ -> ()
            root.setAttribute("data-last-command", action)
            describe ()
        with error -> report error.Message
    let effective = CommandInput.compile catalog profile |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    let input =
        new SvgInputHost(root, catalog, CommandResolver.init [ "soldier.reference" ] effective,
            (fun () ->
                let active = document.activeElement
                if not (isNull active) && active.tagName = "BUTTON" then []
                else catalog.Commands |> List.map _.Id),
            (function CommandResolverEffect.InvokeCommand invocation -> dispatch invocation.Command | _ -> ()),
            { SvgInputHost.defaultOptions with PollGamepads = false })
    invoke <- fun action ->
        observationSequence <- observationSequence + 1UL
        for phase in [ InputGesturePhase.Pressed; InputGesturePhase.Released ] do
            input.Update(CommandResolverObservation.InputEvent
                { Id = sprintf "soldier-observation:%d:%A" observationSequence phase; Source = "soldier-reference-alternative"
                  Gesture = InputGesture.Pointer action; Phase = phase; IsRepeat = false
                  NativeEditable = false; HostReserved = false; IsComposing = false
                  AvailableCommands = catalog.Commands |> List.map _.Id }) |> ignore
    refresh <- describe
    listen canvas "pointerup" (fun event ->
        if not disposed then
            let pointer = event :?> PointerEvent
            renderer |> Option.iter (fun host ->
                selectionTarget <- host.HitTest(svgPoint host.Root pointer.clientX pointer.clientY)
                if selectionTarget.IsSome then invoke "select"))
    for action, label in actions do button controls label (fun () -> invoke action) |> ignore
    button controls "Use local soldier authority" (fun () -> start "local") |> ignore
    button controls "Use external soldier authority" (fun () -> start "external") |> ignore
    let local action = match authority with Some(Local owner) -> action owner | _ -> report "Local authority required"
    let external action = match authority with Some(External owner) -> action owner | _ -> report "External authority required"
    button controls "Pause soldiers" (fun () -> local (fun owner -> owner.Pause())) |> ignore
    button controls "Resume soldiers" (fun () -> local (fun owner -> owner.Resume())) |> ignore
    button controls "Step soldiers" (fun () -> local (fun owner -> owner.Step())) |> ignore
    button controls "Reset soldiers" (fun () -> local (fun owner -> owner.Reset())) |> ignore
    for percentage in updatePercentages do
        button controls (sprintf "Update %d%% soldiers" percentage) (fun () ->
            match authority with
            | Some(Local owner) -> owner.Submit(Local.Intent.Independent percentage)
            | Some(External owner) -> owner.Independent percentage
            | None -> ()) |> ignore
    button controls "Animate 10% soldiers" (fun () -> local (fun owner -> owner.Submit(Local.Intent.Motion(Some 10)))) |> ignore
    button controls "Stop soldier motion" (fun () -> local (fun owner -> owner.Submit(Local.Intent.Motion None))) |> ignore
    for count in visibleCounts do
        button controls (sprintf "Load %d soldiers" count) (fun () -> visibleCount <- count; worldCount <- count; start mode) |> ignore
    button controls "Load 2000 world / 200 visible" (fun () -> visibleCount <- 200; worldCount <- 2000; start mode) |> ignore
    button controls "Connect soldier authority" (fun () -> external (fun owner -> owner.Connect())) |> ignore
    button controls "Disconnect soldier authority" (fun () -> external (fun owner -> owner.Disconnect())) |> ignore
    button controls "Replace soldier authority" (fun () -> external (fun owner -> owner.Replace())) |> ignore
    button controls "Request soldier burst" (fun () -> external (fun owner -> owner.Burst())) |> ignore
    button controls "Request cached soldier snapshot" (fun () -> external (fun owner -> owner.Cached())) |> ignore
    button controls "Complete soldier snapshot" (fun () -> external (fun owner -> owner.Complete())) |> ignore
    button controls "Complete oldest soldier snapshot" (fun () -> external (fun owner -> owner.CompleteOldest())) |> ignore
    button controls "Fail next soldier presentation" (fun () -> external (fun owner -> owner.FailNext())) |> ignore
    button controls "Refuse next soldier replacement" (fun () -> failReplacement <- true) |> ignore
    button controls "Export full soldier world" (fun () ->
        accepted |> Option.iter (fun projection ->
            download projection.ExportedSvg)) |> ignore
    let dispose () =
        if not disposed then
            disposed <- true
            retire ()
            for element, event, handler in listeners do element.removeEventListener(event, handler)
            listeners.Clear()
            for pair in rosterButtons do pair.Value.removeEventListener("click", rosterHandlers[pair.Key])
            rosterHandlers.Clear()
            (input :> IDisposable).Dispose()
            let observation = input.Observe()
            root.setAttribute("data-input-owned", string (observation.OwnedListenerCount + observation.OwnedDeadlineCount + observation.OwnedSourceCount))
            root.setAttribute("data-adapter-listeners", string (listeners.Count + rosterHandlers.Count))
            root.setAttribute("data-svg-count", string (canvas.querySelectorAll("svg").length))
            root.remove()
    button controls "Dispose soldier reference" dispose |> ignore
    start "local"
    { new IDisposable with member _.Dispose() = dispose () }

let install () : IDisposable =
    let button = document.createElement "button"
    button.id <- "mount-soldier-reference"
    button.textContent <- "Mount soldier reference"
    document.body.appendChild button |> ignore
    let mutable mounted: IDisposable option = None
    let mutable disposed = false
    let handler (_: Event) =
        if not disposed then
            // A disposed panel may be mounted again through the actual entry control.
            if isNull (document.getElementById "soldier-reference") then
                mounted |> Option.iter _.Dispose()
                mounted <- Some(mount ())
    button.addEventListener("click", handler)
    { new IDisposable with
        member _.Dispose() =
            if not disposed then
                disposed <- true
                button.removeEventListener("click", handler)
                mounted |> Option.iter _.Dispose()
                mounted <- None
                button.remove() }
