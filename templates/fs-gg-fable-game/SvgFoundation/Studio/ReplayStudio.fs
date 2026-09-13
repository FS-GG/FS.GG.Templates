module FableGameWorkspaceNamespace.SvgFoundation.Studio.ReplayStudio

open Browser.Dom
open Browser.Types
open Fable.Core.JsInterop
open FS.GG.Game.Core

type private Facts = { Energy: int; DoorOpen: bool }
type private Effect = SpendEnergy | EnterDoor

type ReplayStudioHost =
    abstract Snapshot: unit -> obj

let private success label = function
    | Ok value -> value
    | Error error -> failwithf "%s refused: %A" label error

let private compatibility =
    { ContractVersion = 1
      EngineId = "generated-neutral-counter"
      EngineVersion = "replay-candidate"
      ProfileId = "portable/1"
      SchemaId = "counter"
      SchemaVersion = 1 }

let private sessionSnapshot value =
    { SessionId = "generated-session"
      Revision = uint64 value
      Compatibility = compatibility
      Value = value }

let private contract: SessionContract<unit, int, int, int, int> =
    { Initialize = fun _ -> Ok 0
      AdmitInput = fun input state -> Ok(state + input.Value)
      Advance = fun command state -> Ok(state + int command.StepCount)
      Project = fun state -> { SessionId = "generated-session"; Revision = uint64 state; Value = state }
      Snapshot = sessionSnapshot
      Restore = fun snapshot -> Ok snapshot.Value }

let private recording () =
    ReplayRecorder.create (sessionSnapshot 0) "0"
    |> Result.bind (ReplayRecorder.appendInput
        { SessionId = "generated-session"; InputId = "counter.add"; Sequence = 1UL; Value = 2 } "2")
    |> Result.bind (ReplayRecorder.appendAdvance 3UL "5")
    |> Result.bind (ReplayRecorder.addCheckpoint (sessionSnapshot 5) "5")
    |> Result.bind (ReplayRecorder.appendInput
        { SessionId = "generated-session"; InputId = "counter.add"; Sequence = 2UL; Value = 4 } "9")
    |> success "record"

let private ruleCatalog () =
    let rule id dependencies evaluate =
        { Metadata = { Id = id; Version = 1; Title = id; Summary = id; DependsOn = dependencies }
          Evaluate = evaluate }
    let rules =
        [ rule "energy.available" [] (fun facts ->
            { RuleId = "energy.available"
              Applies = facts.Energy > 0
              Explanation = if facts.Energy > 0 then "Energy is available" else "Energy is exhausted"
              Causes = [ { Code = "public.energy"; Message = string facts.Energy } ]
              Effects = if facts.Energy > 0 then [ SpendEnergy ] else [] })
          rule "door.enter" [ "energy.available" ] (fun facts ->
            { RuleId = "door.enter"
              Applies = not facts.DoorOpen
              Explanation = "A closed door may be entered after spending energy"
              Causes =
                [ { Code = "public.door"; Message = if facts.DoorOpen then "open" else "closed" }
                  { Code = "hidden.authority-token"; Message = "server-only" } ]
              Effects = [ EnterDoor ] }) ]
    RuleCatalog.create
        { ModelId = "energy-rules/1"
          ModelSha256 = "generated-by-svg-replay-rule-evidence"
          Tool = "quint"
          ToolVersion = "0.32.0"
          Invariants = [ "energyNeverNegative"; "doorRequiresSpentEnergy" ]
          ImplementationBinding = "FS.GG.Game.Core.RuleCatalog/generated-neutral/v1" }
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

let mount announce =
    let timelinePanel, timelineOutput = addPanel "generated-replay-timeline" "Replay timeline"
    let inspectorPanel, inspectorOutput = addPanel "generated-replay-inspector" "Replay inspector"
    let plannerPanel, plannerOutput = addPanel "generated-scenario-planner" "Scenario planner"
    let rulesPanel, rulesOutput = addPanel "generated-rule-explorer" "Rule explorer"
    let value = recording ()
    let catalog = ruleCatalog ()
    let mutable lastOperation = "ready"
    let mutable acceptedValue = 0
    let mutable predictedValue = 0
    let mutable disclosureSafe = true

    let report (target: HTMLElement) operation text =
        lastOperation <- operation
        target.textContent <- text
        announce text

    addButton timelinePanel "Replay complete recording" (fun () ->
        match Replay.seek contract string (fun _ -> false) 3UL value with
        | Ok(ReplayRunOutcome.Completed(next, state)) ->
            acceptedValue <- state
            report timelineOutput "replay" $"Replayed {next} events; accepted state {state}"
        | other -> report timelineOutput "replay-error" (sprintf "%A" other))
    addButton timelinePanel "Seek replay checkpoint" (fun () ->
        match Replay.seek contract string (fun _ -> false) 2UL value with
        | Ok(ReplayRunOutcome.Completed(next, state)) -> report timelineOutput "seek" $"Seeked to {next}; state {state}"
        | other -> report timelineOutput "seek-error" (sprintf "%A" other))
    addButton timelinePanel "Cancel replay safely" (fun () ->
        match Replay.seek contract string ((=) 1UL) 3UL { value with Checkpoints = [] } with
        | Ok(ReplayRunOutcome.Cancelled(next, state)) -> report timelineOutput "cancel" $"Cancelled before event {next}; accepted state {state}"
        | other -> report timelineOutput "cancel-error" (sprintf "%A" other))
    addButton inspectorPanel "Diagnose replay divergence" (fun () ->
        let mutated =
            { value with
                Checkpoints = []
                Events = value.Events |> List.map (fun event -> if event.Index = 1UL then { event with StateDigest = "mutated" } else event) }
        match Replay.seek contract string (fun _ -> false) 3UL mutated with
        | Ok(ReplayRunOutcome.Diverged divergence) ->
            report inspectorOutput "divergence" $"First divergence at event {divergence.EventIndex}: expected {divergence.ExpectedDigest}; actual {divergence.ActualDigest}"
        | other -> report inspectorOutput "divergence-error" (sprintf "%A" other))

    let mutable planning: PlanningSession<string, int, int> =
        Planning.create
            { ContentId = "neutral-map"; Revision = 1UL; Value = "authored-map" }
            { SessionId = "generated-session"; Revision = 0UL; StateDigest = "0"; Value = 0 }
        |> success "planning"
    let adapter: ScenarioAdapter<int, int> =
        { Apply = fun delta state -> Ok(state + delta)
          StateDigest = string }
    addButton plannerPanel "Branch and compare scenario" (fun () ->
        planning <- planning |> Planning.beginScenario "route-a" |> success "begin scenario"
        planning <- planning |> Planning.apply adapter "route-a" 4 |> success "apply scenario"
        let comparison = Planning.compare "route-a" planning |> success "compare scenario"
        predictedValue <- planning.Scenarios.Head.Prediction.Value
        report plannerOutput "plan" $"Accepted {planning.Accepted.Value}; predicted {predictedValue}; basis {comparison.BasisRevision}"
    )
    addButton plannerPanel "Cancel scenario" (fun () ->
        planning <- planning |> Planning.cancel "route-a" |> success "cancel scenario"
        report plannerOutput "plan-cancel" $"Scenario cancelled; accepted remains {planning.Accepted.Value}")
    addButton rulesPanel "Explain door rule" (fun () ->
        let inspection = RuleCatalog.inspect "door.enter" { Energy = 2; DoorOpen = false } catalog |> success "inspect rule"
        let visibleCauses =
            inspection.Evaluations
            |> List.collect _.Causes
            |> List.filter (fun cause -> cause.Code.StartsWith "public.")
        disclosureSafe <- visibleCauses |> List.forall (fun cause -> not (cause.Code.StartsWith "hidden."))
        let ruleIds = inspection.Evaluations |> List.map _.RuleId |> String.concat " then "
        report rulesOutput "rule" $"{ruleIds}; {visibleCauses.Length} disclosed causes; applies {inspection.Applies}")

    { new ReplayStudioHost with
        member _.Snapshot () =
            createObj
                [ "lastOperation" ==> lastOperation
                  "recordedEvents" ==> value.Events.Length
                  "checkpoints" ==> value.Checkpoints.Length
                  "acceptedValue" ==> acceptedValue
                  "predictedValue" ==> predictedValue
                  "authoredValue" ==> planning.Authored.Value
                  "disclosureSafe" ==> disclosureSafe
                  "playerAnalysisExcluded" ==> true ] }
