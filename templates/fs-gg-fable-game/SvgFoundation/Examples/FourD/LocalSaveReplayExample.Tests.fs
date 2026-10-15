/// Finite source conformance definitions; not yet compiled, connected, or executed.
module FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayExampleTests

open FS.GG.Game.Core
open FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayExample

let private require condition message =
    if not condition then failwith message

let private unwrap = function
    | Ok value -> value
    | Error issue -> failwithf "Unexpected refusal: %A" issue

let private origin: FullCell = { A = -7; B = 23; C = -41; D = 89 }
let private destination: FullCell = { A = 5; B = -11; C = 37; D = -83 }
let private fresh () = initialize origin destination |> unwrap
let private input sequence cell: SessionInput<Command> =
    { SessionId = sessionId; InputId = "synthetic.inspect:" + string sequence
      Sequence = sequence; Value = InspectFullCell cell }

let private accept sequence example =
    let next, result = admit (input sequence destination) example
    unwrap result |> ignore
    next

let private expectRestoreRefused predicate candidate example =
    let next, result = restore candidate example
    require (next = example) "Refused restore changed accepted runtime or recording."
    match result with
    | Error(RuntimeRefused issues) -> require (List.exists predicate issues) "Wrong restore refusal."
    | other -> failwithf "Expected runtime refusal: %A" other

let private completed expectedCount expected recording =
    match replay expectedCount recording with
    | Ok(ReplayRunOutcome.Completed(count, state)) ->
        require (count = expectedCount && state = expected) "Replay payload or cursor differs."
    | other -> failwithf "Expected completed replay: %A" other

let run () =
    // Snapshot/restore includes four distinct signed coordinates and the accepted trace.
    let initial = fresh ()
    let once = accept 10UL initial
    let saved = snapshot once
    let later = accept 20UL once
    let restored, result = restore saved later
    unwrap result |> ignore
    require (restored.Runtime.Current = once.Runtime.Current) "Snapshot payload did not round trip."
    require (restored.Runtime.Current.Agent = origin) "Inspect command moved the agent."
    require (restored.Runtime.Current.LegalDestination = destination) "Full destination coordinates lost."
    require (restored.Runtime.LastInputSequence = None) "Restore did not start a new input epoch."
    require (restored.Recording.Events.IsEmpty) "Restore retained events from the old epoch."
    completed 0UL once.Runtime.Current restored.Recording

    expectRestoreRefused
        (function SessionRuntimeRefusal.WrongSession _ -> true | _ -> false)
        { saved with SessionId = "unrelated-session" } later
    expectRestoreRefused
        (function
         | SessionRuntimeRefusal.IncompatibleSnapshot issues ->
             issues |> List.exists (function SessionCompatibilityIssue.SchemaVersion _ -> true | _ -> false)
         | _ -> false)
        { saved with Compatibility = { compatibility with SchemaVersion = 2 } } later
    expectRestoreRefused
        (function
         | SessionRuntimeRefusal.IncompatibleSnapshot issues ->
             issues |> List.exists (function SessionCompatibilityIssue.ProfileId _ -> true | _ -> false)
         | _ -> false)
        { saved with Compatibility = { compatibility with ProfileId = "other-profile" } } later

    // Check the actual replayed trace before adding a checkpoint: seek must execute events.
    completed 2UL later.Runtime.Current later.Recording
    require (later.Runtime.Current.Accepted = [ 10UL, destination; 20UL, destination ]) "Semantic order lost."
    require
        (later.Recording.Events |> List.map (fun event ->
            match event.Kind with
            | ReplayEventKind.Input value -> value.Sequence
            | _ -> failwith "Unexpected advance event.") = [ 10UL; 20UL ])
        "Recording omitted or reordered accepted commands."

    // A legal envelope with an illegal destination fails in the contract.
    // Changes on each coordinate independently must be refused; stale sequences fail in the runtime.
    let illegalCells =
        [ { destination with A = destination.A + 1 }; { destination with B = destination.B + 1 }
          { destination with C = destination.C + 1 }; { destination with D = destination.D + 1 } ]
    for cell in illegalCells do
        let next, rejected = admit (input 30UL cell) later
        require (next = later) "Rejected command entered runtime or recording."
        match rejected with
        | Error(RuntimeRefused [ SessionRuntimeRefusal.ContractFailure failure ]) ->
            require (failure.Code = "synthetic.input.destination") "Wrong contract failure."
        | other -> failwithf "Illegal destination was not refused: %A" other
    let next, stale = admit (input 10UL destination) later
    require (next = later) "Stale input entered recording."
    match stale with
    | Error(RuntimeRefused [ SessionRuntimeRefusal.StaleInputSequence(20UL, 10UL) ]) -> ()
    | other -> failwithf "Stale sequence was not refused: %A" other

    // Event digest mismatch is detected during genuine replay, not just envelope validation.
    let changedEvents =
        later.Recording.Events |> List.map (fun event ->
            if event.Index = 0UL then { event with StateDigest = "altered" } else event)
    match replay 2UL { later.Recording with Events = changedEvents } with
    | Ok(ReplayRunOutcome.Diverged divergence) ->
        require (divergence.EventIndex = 0UL) "Divergence cursor differs."
    | other -> failwithf "Altered event digest accepted: %A" other

    // Reordered sequence envelopes fail producer validation before semantic execution.
    let reordered =
        later.Recording.Events |> List.map (fun event ->
            match event.Kind with
            | ReplayEventKind.Input value ->
                let sequence = if event.Index = 0UL then 20UL else 10UL
                { event with Kind = ReplayEventKind.Input { value with Sequence = sequence } }
            | _ -> event)
    require (Replay.validate { later.Recording with Events = reordered } |> List.isEmpty |> not)
        "Reordered semantic sequence passed producer validation."

    let checked = checkpoint later |> unwrap
    completed 2UL later.Runtime.Current checked.Recording
    completed 1UL once.Runtime.Current checked.Recording
    let point = List.exactlyOne checked.Recording.Checkpoints
    match replay 2UL { checked.Recording with Checkpoints = [ { point with StateDigest = "altered" } ] } with
    | Ok(ReplayRunOutcome.Diverged divergence) ->
        require (divergence.EventIndex = 2UL) "Checkpoint divergence cursor differs."
    | Error issues -> require (not issues.IsEmpty) "Empty checkpoint refusal."
    | other -> failwithf "Altered checkpoint digest accepted: %A" other
    let incompatiblePoint =
        { point with Snapshot =
            { point.Snapshot with Compatibility = { compatibility with SchemaVersion = 2 } } }
    match replay 2UL { checked.Recording with Checkpoints = [ incompatiblePoint ] } with
    | Error issues ->
        require (issues |> List.exists (function ReplayIssue.IncompatibleSnapshot _ -> true | _ -> false))
            "Wrong checkpoint compatibility refusal."
    | other -> failwithf "Incompatible checkpoint accepted: %A" other

    // Payload alteration with an unchanged digest is not silently accepted by checkpoint seek.
    let changedPayload = { point.Snapshot.Value with Agent = { origin with D = 90 } }
    let alteredPoint = { point with Snapshot = { point.Snapshot with Value = changedPayload } }
    match replay 2UL { checked.Recording with Checkpoints = [ alteredPoint ] } with
    | Ok(ReplayRunOutcome.Diverged _) -> ()
    | other -> failwithf "Altered payload accepted: %A" other

    // Producer checkpoint admission refuses index zero and duplicate checkpoint positions.
    require (match checkpoint initial with Error(RecordingRefused _) -> true | _ -> false)
        "Checkpoint at zero events accepted."
    require (match checkpoint checked with Error(RecordingRefused _) -> true | _ -> false)
        "Duplicate checkpoint position accepted."
