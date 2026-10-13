/// Optional opaque-byte policy advice. Guest output cannot grant product authority.
module FableGameWorkspaceNamespace.WasmPolicyExample

open FS.GG.Wasm.Contracts
open FS.GG.Wasm.Browser

type PreparationIssue =
    | ConfigurationRejected of ContractIssue list
    | UnsupportedPolicyProfile of CompatibilityPath
    | SettingsRejected of ProtocolIssue list
    | HostRejected of RuntimeIssue list

/// Use the strict SC2 ABI for an advisor. BAR has no shared advisor role capacity.
/// Digests and ceilings come from the selected guest artifact and its configuration.
let prepare (candidate: CandidateConfiguration) =
    match Validation.validateConfiguration candidate with
    | Error issues -> Error(ConfigurationRejected issues)
    | Ok configuration when candidate.Path <> Sc2ImportedStrict ->
        Error(UnsupportedPolicyProfile candidate.Path)
    | Ok configuration ->
        match HostSettings.create configuration (Some Advisor) with
        | Error issues -> Error(SettingsRejected issues)
        | Ok settings -> Ok(configuration, settings)

/// The installed host owns admission, clocks, queues, deadlines and Worker disposal.
/// The supplied transport must be the package-owned browser transport.
let connect settings (transport: HostTransport) (settled: BrowserResult -> unit) =
    Host.CreateConnected(settings, transport, settled)
    |> Result.mapError HostRejected

/// Only the caller's expected current processing result may become advisory bytes.
/// Recheck the host projection when consuming a retained callback after replacement.
/// The caller still decodes and validates its own domain result before using advice.
let currentAdvice (expected: HostIdentity) (projection: HostProjection) (result: BrowserResult) =
    if projection.Disposed
       || projection.Frozen
       || projection.ActiveWorker <> expected.WorkerInstance
       || projection.ActiveGeneration <> expected.Generation
       || not (List.contains expected.WorkerInstance projection.InitializedWorkers)
       || result.Identity <> expected
       || result.Disposition <> Current
       || result.Reason.IsSome then
        None
    else
        match result.Outcome with
        | Some outcome when outcome.Identity = expected
                            && outcome.Phase = Process
                            && outcome.State = Succeeded
                            && outcome.Dispatch = Dispatched
                            && outcome.CleanupFault.IsNone ->
            // A later guest buffer or consumer mutation cannot change retained advice.
            Some(Array.copy outcome.CopiedOutput)
        | _ -> None
