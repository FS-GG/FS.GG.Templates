/// Explicitly selected browser composition; advice never changes the game.
module FableGameWorkspaceNamespace.WasmPolicyBrowser

open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.Wasm.Contracts
open FS.GG.Wasm.Browser

[<Import("createHostTransport", "@fsgg-wasm/worker-client.mjs")>]
let private createTransport (assetBase: string): HostTransport = jsNative

// These are byte acquisition and hashing mechanics. The package owns execution.
[<Emit("fetch($0).then(r => { if (!r.ok) throw Error('Policy artifact unavailable'); return r.arrayBuffer(); }).then(async b => { const bytes = new Uint8Array(b); const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join(''); $1([bytes, digest]); }).catch(e => $2(String(e)))")>]
let private fetchArtifact (url: string) (ready: byte array * string -> unit) (failed: string -> unit): unit = jsNative

[<Emit("crypto.subtle.digest('SHA-256', new TextEncoder().encode($0)).then(b => $1(Array.from(new Uint8Array(b), x => x.toString(16).padStart(2, '0')).join(''))).catch(e => $2(String(e)))")>]
let private hashConfiguration (text: string) (ready: string -> unit) (failed: string -> unit): unit = jsNative

[<Emit("new URL($0, document.baseURI).href")>]
let private assetUrl (relative: string): string = jsNative

type MountedPolicy = { Dispose: unit -> unit }

let mount () =
    let root = document.createElement "section"
    root.id <- "wasm-policy-example"
    root.setAttribute("data-game-effects", "0")
    let status = document.createElement "p"
    status.id <- "wasm-policy-status"
    status.setAttribute("role", "status")
    status.textContent <- "Policy is unloaded. Advice has no game authority."
    root.appendChild status |> ignore
    let select = document.createElement "select" :?> HTMLSelectElement
    select.setAttribute("aria-label", "Policy guest")
    for value in [ "c-normal"; "rust-normal"; "c-malformed"; "c-trap"; "c-loop" ] do
        let option = document.createElement "option" :?> HTMLOptionElement
        option.value <- value
        option.textContent <- value
        select.appendChild option |> ignore
    root.appendChild select |> ignore
    document.body.appendChild root |> ignore

    let transport = createTransport (assetUrl "./_content/FS.GG.Wasm.Browser/")
    let mutable host: Host option = None
    let mutable request = 0UL
    let mutable disposed = false
    let mutable preparing = false
    let mutable selection = 0
    let mutable retained: (HostIdentity * BrowserResult) option = None
    let mutable candidateControl: (string * uint64 * string) option = None
    let mutable shutdownControl: (HostIdentity * int * uint64 * string) option = None
    let identity worker generation : HostIdentity =
        request <- request + 1UL
        { WorkerInstance = worker; Request = request; Generation = generation }
    let show state text =
        root.setAttribute("data-state", state)
        status.textContent <- text
    let refuse detail = show "refused" ("Refused: " + detail + ". No game effects.")
    let renderAdvice expected result =
        match host with
        | Some current ->
            match WasmPolicyExample.currentAdvice expected current.Projection result with
            | Some bytes when bytes.Length = 3 && bytes[0] = 80uy && bytes[1] = 1uy && bytes[2] <= 2uy ->
                show "advice" ("Advice: " + [| "hold"; "observe"; "wait" |][int bytes[2]] + ". No game effects.")
            | Some _ ->
                current.RejectAdapterOutput(transport.Now(), expected, "Invalid PolicyAdviceV1")
                refuse "invalid recommendation"
            | None -> refuse "stale, disposed or failed recommendation"
        | None -> refuse "no current host"
    let settled (result: BrowserResult) =
        if not disposed then
            match host, result.Outcome with
            | Some current, Some outcome when result.Reason.IsNone
                                             && outcome.State = Succeeded && outcome.CleanupFault.IsNone ->
                let projection = current.Projection
                let activeControl = not projection.Frozen && not projection.Disposed
                                    && result.Disposition = Current
                                    && result.Identity.WorkerInstance = projection.ActiveWorker
                                    && result.Identity.Generation = projection.ActiveGeneration
                let candidateCurrent =
                    match candidateControl with
                    | Some(worker, generation, transaction) ->
                        not projection.Frozen && not projection.Disposed
                        && result.Disposition = HistoricalOnly
                        && result.Identity.WorkerInstance = worker && result.Identity.Generation = generation
                        && projection.CandidateWorker = worker && projection.CandidateGeneration = generation
                        && projection.CandidateTransaction = transaction
                    | None -> false
                let shutdownCurrent =
                    match shutdownControl with
                    | Some(expected, ownerSelection, nextGeneration, transaction) ->
                        ownerSelection = selection && not preparing
                        && result.Disposition = Current && result.Identity = expected
                        && not projection.Frozen && not projection.Disposed
                        && projection.ActiveWorker = "" && projection.CandidateWorker = ""
                        && projection.CandidateTransaction = transaction && transaction = ""
                        && projection.NextGeneration = nextGeneration
                        && not (List.contains expected.WorkerInstance projection.CompiledWorkers)
                        && not (List.contains expected.WorkerInstance projection.InitializedWorkers)
                    | None -> false
                match outcome.Phase with
                // Public 0.3 reports ABI-validated compile completion as Instantiate.
                | Instantiate when (activeControl || candidateCurrent)
                                   && List.contains result.Identity.WorkerInstance projection.CompiledWorkers ->
                    current.Initialize(transport.Now(), identity result.Identity.WorkerInstance result.Identity.Generation, [| 1uy |])
                | Initialize when candidateCurrent ->
                    current.ValidateCandidate(transport.Now(), projection.CandidateTransaction, projection.CandidateGeneration)
                    let validated = current.Projection
                    if validated.CandidateReady && validated.CandidateWorker = projection.CandidateWorker
                       && validated.CandidateGeneration = projection.CandidateGeneration
                       && validated.CandidateTransaction = projection.CandidateTransaction then
                        current.CommitCandidate(transport.Now(), validated.CandidateTransaction, validated.ActiveGeneration, validated.CandidateGeneration)
                        candidateControl <- None
                        show "ready" "Replacement initialized and committed. No game effects."
                    else refuse "candidate validation"
                | Initialize when activeControl -> show "ready" "Policy initialized. Request advice explicitly."
                | Process when activeControl ->
                    retained <- Some(result.Identity, result)
                    renderAdvice result.Identity result
                | Shutdown when shutdownCurrent ->
                    shutdownControl <- None
                    show "shutdown" "Guest shutdown settled and retired its Worker."
                | _ -> refuse "stale or unrelated lifecycle settlement"
            | _, _ -> refuse (sprintf "%A" result.Reason)

    let load replace =
        if disposed then refuse "component disposed"
        elif preparing then refuse "artifact preparation already active"
        elif shutdownControl.IsSome then refuse "shutdown settlement is pending"
        else
            selection <- selection + 1
            let capturedSelection = selection
            let variant = select.value
            preparing <- true
            show "preparing" "Reading the independently built policy artifact."
            let failed detail =
                if not disposed && capturedSelection = selection then
                    preparing <- false
                    refuse detail
            fetchArtifact (assetUrl ("./wasm-policy/" + variant + ".wasm"))
                (fun (bytes, digest) ->
                    let profile = Profiles.tryFind Sc2ImportedStrict |> Option.get
                    let limits = { profile.Limits with MaximumOutputBytes = 16 }
                    // The digest identifies the actual selected local configuration, not a fixture.
                    let text = sprintf "PolicyAdviceV1\n%s\n%A\n%A\n%A\n%A" digest limits profile.Deadline profile.Scheduling profile.Replacement
                    hashConfiguration text
                        (fun configurationDigest ->
                            if not disposed && capturedSelection = selection then
                                preparing <- false
                                let candidate =
                                    { Path = profile.Path; ArtifactSha256 = digest; ConfigurationSha256 = configurationDigest
                                      Limits = limits; Deadline = profile.Deadline; Scheduling = profile.Scheduling; Replacement = profile.Replacement }
                                match WasmPolicyExample.prepare candidate with
                                | Error issue -> failed (sprintf "%A" issue)
                                | Ok(configuration, settings) ->
                                    let current =
                                        match host with
                                        | Some current -> Ok current
                                        | None -> WasmPolicyExample.connect settings transport settled
                                    match current with
                                    | Error issue -> failed (sprintf "%A" issue)
                                    | Ok current ->
                                        host <- Some current
                                        let projection = current.Projection
                                        let next = identity ("template-policy-" + string capturedSelection) projection.NextGeneration
                                        if replace && projection.ActiveWorker <> "" then
                                            let transaction = "replace-" + string capturedSelection
                                            candidateControl <- Some(next.WorkerInstance, next.Generation, transaction)
                                            current.PrepareConfiguredCandidate(transport.Now(), next, transaction, Some projection.ActiveGeneration, configuration, bytes)
                                        elif projection.ActiveWorker = "" then
                                            current.LoadConfigured(transport.Now(), next, configuration, bytes)
                                        else refuse "active policy requires explicit replacement")
                        failed)
                failed

    let button label action =
        let value = document.createElement "button" :?> HTMLButtonElement
        value.textContent <- label
        value.addEventListener("click", fun _ -> action ())
        root.appendChild value |> ignore
    button "Load policy" (fun () -> load false)
    button "Replace policy" (fun () -> load true)
    button "Request advice" (fun () ->
        match host with
        | Some current when not disposed && shutdownControl.IsNone ->
            let projection = current.Projection
            let next = identity projection.ActiveWorker projection.ActiveGeneration
            current.Invoke(transport.Now(), next, Ordinary, [| 1uy; 1uy |])
        | _ -> refuse "no initialized policy")
    button "Use retained advice" (fun () ->
        match retained with
        | Some(expected, result) -> renderAdvice expected result
        | None -> refuse "no retained advice")
    button "Shutdown policy" (fun () ->
        match host with
        | Some current when not disposed ->
            let projection = current.Projection
            if preparing || shutdownControl.IsSome || projection.Frozen || projection.Disposed
               || projection.ActiveWorker = "" || projection.CandidateWorker <> "" then
                refuse "shutdown requires the current settled owner without a candidate"
            else
                let next = identity projection.ActiveWorker projection.ActiveGeneration
                shutdownControl <- Some(next, selection, projection.NextGeneration, projection.CandidateTransaction)
                current.Shutdown(transport.Now(), next)
        | _ -> refuse "no current policy")
    let dispose () =
        if not disposed then
            disposed <- true
            selection <- selection + 1
            candidateControl <- None
            shutdownControl <- None
            host |> Option.iter (fun current -> current.Dispose(transport.Now()))
            show "disposed" "Disposed. Retained callbacks cannot become advice. No game effects."
    button "Dispose policy" dispose
    { Dispose = dispose }
