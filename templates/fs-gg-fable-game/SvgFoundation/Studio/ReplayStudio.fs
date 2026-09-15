module FableGameWorkspaceNamespace.SvgFoundation.Studio.ReplayStudio

open Browser.Dom
open Browser.Types
open Fable.Core.JsInterop
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace.ArenaContent
open FableGameWorkspaceNamespace.ArenaRules
module RuleModel = FableGameWorkspaceNamespace.SvgFoundation.Studio.GeneratedArenaRuleModel

type private RuleEffect = Collect | Win | Damage

type ReplayStudioHost =
    abstract Snapshot: unit -> obj
    abstract ObserveInput: before: State * command: Command * after: State -> unit
    abstract ObserveAdvance: before: State * steps: uint64 * after: State -> unit

let private success label = function
    | Ok value -> value
    | Error error -> failwithf "%s refused: %A" label error

let private ruleCatalog () =
    let rule id title dependencies evaluate =
        { Metadata = { Id = id; Version = 1; Title = title; Summary = title; DependsOn = dependencies }
          Evaluate = evaluate }
    let rules =
        [ rule "arena.collect" "Collect a nearby collectible" [] (fun state ->
            { RuleId = "arena.collect"
              Applies =
                state.Status.Outcome = "playing" && not state.Status.Collected &&
                (state.Room.Players |> Map.exists (fun _ player -> (interact state.Definition { Col = player.Cell.Col; Row = player.Cell.Row } state.Status).Collected))
              Explanation = "Interact collects only when the player overlaps the authored collectible geometry."
              Causes = [ { Code = "public.collectible"; Message = state.Definition.ContentId } ]
              Effects = if state.Status.Collected then [] else [ Collect ] })
          rule "arena.goal" "Win after collecting" [ "arena.collect" ] (fun state ->
            { RuleId = "arena.goal"
              Applies =
                state.Status.Collected && state.Status.Outcome = "playing" &&
                (state.Room.Players |> Map.exists (fun _ player -> (interact state.Definition { Col = player.Cell.Col; Row = player.Cell.Row } state.Status).Outcome = "won"))
              Explanation = "The authored goal accepts a win only after collection."
              Causes = [ { Code = "public.outcome"; Message = state.Status.Outcome } ]
              Effects = if state.Status.Collected then [ Win ] else [] })
          rule "arena.hazard" "Damage on hazard contact entry" [] (fun state ->
            { RuleId = "arena.hazard"
              Applies = state.Status.Outcome = "playing"
              Explanation = "The authoritative moving hazard damages once on contact entry."
              Causes = [ { Code = "public.health"; Message = string state.Status.Health } ]
              Effects = if state.HazardContacts.IsEmpty then [] else [ Damage ] }) ]
    RuleCatalog.create
        { ModelId = RuleModel.modelId
          ModelSha256 = RuleModel.modelSha256
          Tool = RuleModel.tool
          ToolVersion = RuleModel.toolVersion
          Invariants = RuleModel.invariants
          ImplementationBinding = RuleModel.implementationBinding }
        rules
    |> success "rule catalog"

let private addPanel id label =
    let panel: HTMLElement = document.createElement("section")
    panel.id <- id
    panel.setAttribute("aria-label", label)
    panel.setAttribute("tabindex", "0")
    let heading: HTMLElement = document.createElement("h2")
    heading.textContent <- label
    panel.appendChild heading |> ignore
    let output: HTMLElement = document.createElement("output")
    output.setAttribute("aria-live", "polite")
    panel.appendChild output |> ignore
    document.getElementById("generated-scene-actions").appendChild panel |> ignore
    panel, output

let private addButton (panel: HTMLElement) label action =
    let button: HTMLElement = document.createElement("button")
    button.setAttribute("type", "button")
    button.setAttribute("aria-label", label)
    button.textContent <- label
    button.addEventListener("click", fun _ -> action ())
    panel.appendChild button |> ignore

let mount announce (getAcceptedState: unit -> State) =
    let timelinePanel, timelineOutput = addPanel "generated-replay-timeline" "Replay timeline"
    let inspectorPanel, inspectorOutput = addPanel "generated-replay-inspector" "Replay inspector"
    let plannerPanel, plannerOutput = addPanel "generated-scenario-planner" "Scenario planner"
    let rulesPanel, rulesOutput = addPanel "generated-rule-explorer" "Rule explorer"
    let mutable lastOperation = "ready"
    let mutable acceptedDigest = canonicalState (getAcceptedState ())
    let mutable predictedDigest = acceptedDigest
    let mutable recordedEvents = 0
    let mutable checkpoints = 0
    let mutable disclosureSafe = true
    let mutable observedState = getAcceptedState ()
    let mutable contract = contractForDefinition observedState.Definition
    let mutable recording = ReplayRecorder.create (contract.Snapshot observedState) (canonicalState observedState) |> success "record"
    let mutable sequence = 0UL

    let resetObserved before =
        observedState <- before
        contract <- contractForDefinition before.Definition
        recording <- ReplayRecorder.create (contract.Snapshot before) (canonicalState before) |> success "record reset"
        sequence <- 0UL

    let observeInput before command after =
        if canonicalState before <> canonicalState observedState then resetObserved before
        sequence <- sequence + 1UL
        let input = { SessionId = "arena-1"; InputId = "studio.play"; Sequence = sequence; Value = command }
        recording <- ReplayRecorder.appendInput input (canonicalState after) recording |> success "append observed input"
        observedState <- after
        recordedEvents <- recording.Events.Length

    let observeAdvance before steps after =
        if canonicalState before <> canonicalState observedState then resetObserved before
        recording <- ReplayRecorder.appendAdvance steps (canonicalState after) recording |> success "append observed advance"
        observedState <- after
        recordedEvents <- recording.Events.Length

    let report (target: HTMLElement) operation text =
        lastOperation <- operation
        target.textContent <- text
        announce text

    addButton timelinePanel "Replay complete arena recording" (fun () ->
        recordedEvents <- recording.Events.Length
        checkpoints <- recording.Checkpoints.Length
        match Replay.seek contract canonicalState (fun _ -> false) (uint64 recording.Events.Length) recording with
        | Ok(ReplayRunOutcome.Completed(next, state)) when canonicalState state = canonicalState observedState ->
            acceptedDigest <- canonicalState state
            report timelineOutput "replay" $"Replayed {next} arena events; round {state.Round}; outcome {state.Status.Outcome}"
        | other -> report timelineOutput "replay-error" (sprintf "%A" other))
    addButton timelinePanel "Seek arena replay checkpoint" (fun () ->
        let target = min 4UL (uint64 recording.Events.Length)
        match Replay.seek contract canonicalState (fun _ -> false) target recording with
        | Ok(ReplayRunOutcome.Completed(next, state)) -> report timelineOutput "seek" $"Seeked to {next}; collected {state.Status.Collected}; score {state.Status.Score}"
        | other -> report timelineOutput "seek-error" (sprintf "%A" other))
    addButton timelinePanel "Cancel arena replay safely" (fun () ->
        match Replay.seek contract canonicalState ((=) 2UL) (uint64 recording.Events.Length) { recording with Checkpoints = [] } with
        | Ok(ReplayRunOutcome.Cancelled(next, state)) -> report timelineOutput "cancel" $"Cancelled before event {next}; health {state.Status.Health}"
        | other -> report timelineOutput "cancel-error" (sprintf "%A" other))
    addButton inspectorPanel "Diagnose arena replay divergence" (fun () ->
        let mutated = { recording with Checkpoints = []; Events = recording.Events |> List.map (fun event -> if event.Index = 2UL then { event with StateDigest = "mutated" } else event) }
        match Replay.seek contract canonicalState (fun _ -> false) (uint64 mutated.Events.Length) mutated with
        | Ok(ReplayRunOutcome.Diverged divergence) -> report inspectorOutput "divergence" $"First divergence at event {divergence.EventIndex}: expected {divergence.ExpectedDigest}; actual {divergence.ActualDigest}"
        | other -> report inspectorOutput "divergence-error" (sprintf "%A" other))

    addButton plannerPanel "Branch and compare arena scenario" (fun () ->
        let basis = getAcceptedState ()
        let mutable planning: PlanningSession<string, State, Intent> =
            Planning.create
                { ContentId = basis.Definition.ContentId; Revision = uint64 basis.Room.Tick; Value = basis.Definition.ContentId }
                { SessionId = "arena-1"; Revision = uint64 basis.Room.Tick; StateDigest = canonicalState basis; Value = basis }
            |> success "planning"
        let playerId = basis.Room.Players |> Map.toList |> List.tryHead |> Option.map fst |> Option.defaultValue "studio-player"
        let adapter: ScenarioAdapter<State, Intent> =
            { Apply = fun intent state -> Ok(applyIntent playerId intent state)
              StateDigest = canonicalState }
        planning <- planning |> Planning.beginScenario "collect-next" |> success "begin scenario"
        planning <- planning |> Planning.apply adapter "collect-next" Intent.Interact |> success "apply scenario"
        let comparison = Planning.compare "collect-next" planning |> success "compare scenario"
        predictedDigest <- planning.Scenarios.Head.Prediction.StateDigest
        acceptedDigest <- planning.Accepted.StateDigest
        planning <- planning |> Planning.cancel "collect-next" |> success "cancel scenario"
        predictedDigest <- planning.Accepted.StateDigest
        report plannerOutput "plan" $"Accepted and predicted arena states compared at revision {comparison.BasisRevision}; scenario cancelled through Planning.cancel")
    addButton rulesPanel "Explain arena goal rule" (fun () ->
        let catalog = ruleCatalog ()
        let inspection = RuleCatalog.inspect "arena.goal" (getAcceptedState ()) catalog |> success "inspect rule"
        let causes = inspection.Evaluations |> List.collect _.Causes
        disclosureSafe <- causes |> List.forall (fun cause -> cause.Code.StartsWith "public.")
        let ruleIds = inspection.Evaluations |> List.map _.RuleId |> String.concat " then "
        report rulesOutput "rule" $"{ruleIds}; {causes.Length} disclosed causes; applies {inspection.Applies}")

    { new ReplayStudioHost with
        member _.ObserveInput(before, command, after) = observeInput before command after
        member _.ObserveAdvance(before, steps, after) = observeAdvance before steps after
        member _.Snapshot () =
            createObj
                [ "lastOperation" ==> lastOperation
                  "recordedEvents" ==> recordedEvents
                  "checkpoints" ==> checkpoints
                  "acceptedDigest" ==> acceptedDigest
                  "predictedDigest" ==> predictedDigest
                  "authoredContentId" ==> (getAcceptedState ()).Definition.ContentId
                  "disclosureSafe" ==> disclosureSafe
                  "playerAnalysisExcluded" ==> true ] }
