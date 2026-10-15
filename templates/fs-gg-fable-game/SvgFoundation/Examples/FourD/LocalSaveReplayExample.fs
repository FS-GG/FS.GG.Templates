/// Source preparation only: not included in the generated project compile graph.
module FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayExample

open FS.GG.Game.Core

// Synthetic fixture data; these identifiers do not name a product save format.
type FullCell = { A: int; B: int; C: int; D: int }

type Command = InspectFullCell of FullCell

type Payload =
    {
        Agent: FullCell
        LegalDestination: FullCell
        Accepted: (uint64 * FullCell) list
    }

type Example =
    {
        Runtime: SessionRuntimeState<Payload, Payload>
        Recording: ReplayRecording<Command, Payload>
    }

type PreparationFailure =
    | RuntimeRefused of SessionRuntimeRefusal list
    | RecordingRefused of ReplayIssue list

let sessionId = "synthetic.fourd.local-save-replay"

let compatibility: SessionCompatibility =
    {
        ContractVersion = 1
        EngineId = "synthetic.fourd.local-save-replay"
        EngineVersion = "1"
        ProfileId = "pure-inspection-fixture"
        SchemaId = "synthetic-full-cell-trace"
        SchemaVersion = 1
    }

// An injective canonical text for this integer-only payload, used directly as a
// comparison digest. A caller can replace it with a hash over its own canonical codec.
// This is not a cryptographic authenticator, serializer, or product compatibility claim.
let private cellText (cell: FullCell) =
    String.concat ":" [ string cell.A; string cell.B; string cell.C; string cell.D ]

let stateDigest (payload: Payload) =
    let trace =
        payload.Accepted
        |> List.map (fun (sequence, cell) -> string sequence + "@" + cellText cell)
        |> String.concat ";"

    "synthetic-v1|" + cellText payload.Agent + "|" + cellText payload.LegalDestination + "|" + trace

let private failure code message = Error({ Code = code; Message = message }: SessionFailure)
let private revision (payload: Payload) = 1UL + uint64 payload.Accepted.Length

let private contract: SessionContract<Payload, Payload, Command, Payload, Payload> =
    {
        Initialize =
            fun request ->
                if request.SessionId = sessionId && request.Compatibility = compatibility then
                    Ok request.Configuration
                else
                    failure "synthetic.initialize.identity" "Synthetic identity mismatch."
        AdmitInput =
            fun input state ->
                match input.Value with
                | InspectFullCell cell when input.SessionId = sessionId && cell = state.LegalDestination ->
                    // Record semantic order without moving the fixture's agent.
                    Ok { state with Accepted = state.Accepted @ [ input.Sequence, cell ] }
                | _ -> failure "synthetic.input.destination" "Expected the complete legal full cell."
        Advance = fun _ state -> Ok state
        Project = fun state -> { SessionId = sessionId; Revision = revision state; Value = state }
        Snapshot =
            fun state ->
                { SessionId = sessionId; Revision = revision state; Compatibility = compatibility; Value = state }
        Restore =
            fun snapshot ->
                if snapshot.SessionId <> sessionId || snapshot.Compatibility <> compatibility then
                    failure "synthetic.restore.identity" "Synthetic identity mismatch."
                elif snapshot.Revision <> revision snapshot.Value then
                    failure "synthetic.restore.revision" "Payload and envelope revision differ."
                else
                    Ok snapshot.Value
    }

let private startRecording runtime =
    ReplayRecorder.create (SessionRuntime.snapshot contract runtime) (stateDigest runtime.Current)
    |> Result.mapError RecordingRefused
    |> Result.map (fun recording -> { Runtime = runtime; Recording = recording })

let initialize agent legalDestination =
    SessionRuntime.initialize
        { StepMicroseconds = 16_667UL; MaxCatchUpSteps = 1u }
        contract
        { SessionId = sessionId
          Compatibility = compatibility
          Configuration = { Agent = agent; LegalDestination = legalDestination; Accepted = [] } }
    |> Result.mapError (fun refusal -> RuntimeRefused [ refusal ])
    |> Result.bind startRecording

let snapshot example = SessionRuntime.snapshot contract example.Runtime

let private refusals effects =
    effects |> List.choose (function SessionRuntimeEffect.Refused refusal -> Some refusal | _ -> None)

/// Refusal returns the original immutable example. Recorder failures also roll back admission.
let admit (input: SessionInput<Command>) example =
    let next, effects = SessionRuntime.update contract (SessionRuntimeObservation.AdmitInput input) example.Runtime
    match refusals effects with
    | _ :: _ as issues -> example, Error(RuntimeRefused issues)
    | [] ->
        ReplayRecorder.appendInput input (stateDigest next.Current) example.Recording
        |> function
            | Error issues -> example, Error(RecordingRefused issues)
            | Ok recording -> { Runtime = next; Recording = recording }, Ok effects

/// Starts a new recording epoch at the restored payload. SessionRuntime resets its
/// input sequence and elapsed accumulator; this is not an entire host checkpoint.
let restore checkpoint example =
    let next, effects = SessionRuntime.update contract (SessionRuntimeObservation.Restore checkpoint) example.Runtime
    match refusals effects with
    | _ :: _ as issues -> example, Error(RuntimeRefused issues)
    | [] ->
        match startRecording next with
        | Error failure -> example, Error failure
        | Ok restored -> restored, Ok effects

/// Producer validation requires a nonzero event index and strictly increasing checkpoints.
let checkpoint example =
    ReplayRecorder.addCheckpoint (snapshot example) (stateDigest example.Runtime.Current) example.Recording
    |> Result.mapError RecordingRefused
    |> Result.map (fun recording -> { example with Recording = recording })

/// Uses the producer replay engine and the same real contract as admission.
/// The returned payload is a preview; this function does not replace accepted state.
let replay targetEventCount recording =
    Replay.seek contract stateDigest (fun _ -> false) targetEventCount recording
