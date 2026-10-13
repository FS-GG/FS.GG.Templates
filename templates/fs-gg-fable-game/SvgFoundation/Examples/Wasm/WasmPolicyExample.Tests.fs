/// Source conformance definitions; compilation and execution are separate qualifications.
module FableGameWorkspaceNamespace.WasmPolicyExampleTests

open FS.GG.Wasm.Contracts
open FS.GG.Wasm.Browser
open FableGameWorkspaceNamespace.WasmPolicyExample

let private require condition message =
    if not condition then failwith message

let run () =
    let profile = Profiles.tryFind Sc2ImportedStrict |> Option.get
    // Shape-valid fixture digests only; these do not identify a built guest artifact.
    let candidate =
        { Path = profile.Path
          ArtifactSha256 = String.replicate 64 "a"
          ConfigurationSha256 = String.replicate 64 "b"
          Limits = profile.Limits
          Deadline = profile.Deadline
          Scheduling = profile.Scheduling
          Replacement = profile.Replacement }
    let configuration, settings =
        match prepare candidate with
        | Ok values -> values
        | Error issue -> failwithf "fixture configuration rejected: %A" issue

    require
        (match prepare { candidate with ArtifactSha256 = "not-a-digest" } with
         | Error(ConfigurationRejected _) -> true
         | _ -> false)
        "malformed artifact identity accepted"
    let bar = Profiles.tryFind BarProtected |> Option.get
    let barCandidate =
        { candidate with
            Path = bar.Path
            Limits = bar.Limits
            Deadline = bar.Deadline
            Scheduling = bar.Scheduling
            Replacement = bar.Replacement }
    require
        (match prepare barCandidate with
         | Error(UnsupportedPolicyProfile BarProtected) -> true
         | _ -> false)
        "BAR profile entered the advisor example"

    let effects = ResizeArray<HostEffect>()
    let host =
        match Host.Create(settings, fun emitted -> effects.AddRange emitted) with
        | Ok value -> value
        | Error issue -> failwithf "fixture host rejected: %A" issue
    let identity: HostIdentity = { WorkerInstance = "policy-worker"; Request = 7UL; Generation = 2UL }
    // A projection fixture tests the advice boundary without simulating guest success.
    let ready =
        { host.Projection with
            ActiveWorker = identity.WorkerInstance
            ActiveGeneration = identity.Generation
            InitializedWorkers = [ identity.WorkerInstance ] }
    let output = [| 1uy; 2uy |]
    let outcome =
        { Identity = identity
          Phase = Process
          State = Succeeded
          Dispatch = Dispatched
          CleanupFault = None
          CopiedOutput = output
          EffectEligibility = ProductAdapterMustDecide }
    let result =
        { Identity = identity; Outcome = Some outcome; Disposition = Current; Reason = None }
    let refused projection value message =
        require (currentAdvice identity projection value |> Option.isNone) message

    let advice = currentAdvice identity ready result |> Option.get
    output.[0] <- 9uy
    require (advice = [| 1uy; 2uy |]) "advice aliases the delivered output"
    refused ready { result with Identity = { identity with Request = 8UL } } "wrong request accepted"
    refused ready { result with Outcome = Some { outcome with Identity = { identity with Generation = 1UL } } } "wrong outcome generation accepted"
    refused ready { result with Disposition = HistoricalOnly } "historical result accepted"
    refused ready { result with Reason = Some DeadlineExpired } "reason-bearing result accepted"
    refused ready { result with Outcome = None } "missing outcome accepted"
    refused ready { result with Outcome = Some { outcome with State = Faulted "guest trap" } } "fault accepted"
    refused ready { result with Outcome = Some { outcome with State = TimedOut } } "timeout accepted"
    refused ready { result with Outcome = Some { outcome with Dispatch = NotDispatched } } "undispatched result accepted"
    refused ready { result with Outcome = Some { outcome with Phase = Initialize } } "initialization exposed as policy advice"
    refused ready { result with Outcome = Some { outcome with CleanupFault = Some { Phase = Free; Diagnostic = "cleanup trap" } } } "cleanup fault accepted"
    refused { ready with ActiveGeneration = 3UL } result "retained result survived replacement"
    refused { ready with ActiveWorker = "replacement-worker" } result "wrong active worker accepted"
    refused { ready with InitializedWorkers = [] } result "uninitialized worker accepted"
    refused { ready with Frozen = true } result "frozen host advice accepted"
    refused { ready with Disposed = true } result "disposed host advice accepted"

    // Exercise the actual public facade with inert effects, rather than a second scheduler.
    host.LoadConfigured(0L, identity, configuration, [| 0uy |])
    require
        (effects |> Seq.exists (function CreateWorker _ -> true | _ -> false))
        "configured load did not request a Worker"
    require
        (effects |> Seq.exists (function
            | PostToWorker(_, command) ->
                match command.Operation with
                | InspectAndCompile _ -> true
                | _ -> false
            | _ -> false))
        "configured load did not enter the installed inspection/compile path"
    effects.Clear()
    host.Initialize(1L, { identity with Request = 8UL }, [| 1uy |])
    require
        (effects |> Seq.forall (function
            | PostToWorker(_, command) ->
                match command.Operation with
                | InitializeGuest _ -> false
                | _ -> true
            | _ -> true))
        "initialization dispatched before compilation settled"
    host.Dispose(2L)
    require host.Projection.Disposed "facade disposal was not retained"
    effects.Clear()
    host.LoadConfigured(3L, { identity with Request = 9UL; Generation = 3UL }, configuration, [| 0uy |])
    require
        (effects |> Seq.forall (function CreateWorker _ -> false | _ -> true))
        "disposed facade created a replacement Worker"
