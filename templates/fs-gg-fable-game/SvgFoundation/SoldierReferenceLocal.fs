module FableGameWorkspaceNamespace.SvgFoundation.SoldierReferenceLocal

open System
open FS.GG.Game.Core
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.SoldierWorkload

[<RequireQualifiedAccess>]
type Intent = Product of Command | Independent of int | Motion of int option

type Authority = { Workload: Workload; Motion: int option }

let private sessionId = "soldier-reference-local"
let private compatibility =
    { ContractVersion = 1; EngineId = sessionId; EngineVersion = "1"
      ProfileId = "soldier-reference"; SchemaId = "soldier-workload"; SchemaVersion = 1 }
let private failure issues : Result<'value, SessionFailure> =
    Error { Code = "soldier-reference.refused"; Message = String.concat "," issues }
let private presentation = { Revision = 0; Camera = SvgAffine.identity; Selected = None; Focused = None }

// Only workload authority enters Game. Selection, focus and camera stay in the product panel.
let private contract: SessionContract<Workload, Authority, Intent, Workload, Authority> =
    { Initialize = fun request ->
        match validate request.Configuration with
        | [] -> Ok { Workload = request.Configuration; Motion = None }
        | issues -> failure issues
      AdmitInput = fun input current ->
        match input.Value with
        | Intent.Product command ->
            let next, issues = tryApply command { Workload = current.Workload; Presentation = presentation }
            match issues with
            | Some issues -> failure issues
            | None -> Ok { current with Workload = next.Workload }
        | Intent.Independent percentage ->
            updatedSoldiers percentage current.Workload |> Result.map (fun workload -> { current with Workload = workload })
            |> Result.mapError (fun issues -> { Code = "soldier-reference.refused"; Message = String.concat "," issues })
        | Intent.Motion percentage ->
            if percentage |> Option.forall (fun value -> List.contains value updatePercentages) then
                Ok { current with Motion = percentage }
            else failure [ "invalid-percentage" ]
      Advance = fun advance current ->
        let rec steps remaining accepted =
            if remaining = 0UL then Ok accepted
            else
                match accepted.Motion with
                | None -> Ok accepted
                | Some percentage ->
                    match updatedSoldiers percentage accepted.Workload with
                    | Error issues -> failure issues
                    | Ok workload -> steps (remaining - 1UL) { accepted with Workload = workload }
        steps advance.StepCount current
      Project = fun current -> { SessionId = sessionId; Revision = uint64 current.Workload.AuthorityRevision; Value = current.Workload }
      Snapshot = fun current ->
        { SessionId = sessionId; Revision = uint64 current.Workload.AuthorityRevision; Compatibility = compatibility; Value = current }
      Restore = fun snapshot ->
        if snapshot.SessionId <> sessionId || snapshot.Compatibility <> compatibility then failure [ "snapshot-identity" ]
        elif not (validate snapshot.Value.Workload).IsEmpty then failure (validate snapshot.Value.Workload)
        else Ok snapshot.Value }

type Owner =
    { Submit: Intent -> unit; Pause: unit -> unit; Resume: unit -> unit
      Step: unit -> unit; Reset: unit -> unit; Observe: unit -> SvgSessionHostObservation
      Current: unit -> Workload; Dispose: unit -> unit }

let create initial (apply: Workload -> unit) (report: string -> unit) =
    let mutable runtime =
        SessionRuntime.initialize { StepMicroseconds = 16_667UL; MaxCatchUpSteps = 4u } contract
            { SessionId = sessionId; Compatibility = compatibility; Configuration = initial }
        |> Result.defaultWith (fun refusal -> failwithf "Soldier session initialization refused: %A" refusal)
    let mutable sequence = 0UL
    let mutable projectionRevision = 0UL
    let mutable disposed = false
    let mutable hostOption: SvgSessionHost<Workload> option = None
    let demand () = hostOption |> Option.iter _.DemandProjection()
    let update observation =
        if not disposed then
            let before = runtime.Current.Workload
            let next, effects = SessionRuntime.update contract observation runtime
            runtime <- next
            for effect in effects do
                match effect with SessionRuntimeEffect.Refused refusal -> report (sprintf "%A" refusal) | _ -> ()
            if before <> runtime.Current.Workload then demand ()
    let host =
        new SvgSessionHost<Workload>(
            { AdvanceElapsed = fun elapsed -> update (SessionRuntimeObservation.AdvanceElapsed elapsed)
              Pause = fun () -> update SessionRuntimeObservation.Pause
              Resume = fun () -> update SessionRuntimeObservation.Resume
              StepOnce = fun () -> update SessionRuntimeObservation.StepOnce; demand ()
              Reset = fun () -> update SessionRuntimeObservation.Reset; demand ()
              RequestRecovery = fun _ -> report "Local session suspended; resume explicitly"
              RequestProjection = fun generation ->
                projectionRevision <- projectionRevision + 1UL
                hostOption |> Option.iter (fun host -> host.CompleteProjection(generation, projectionRevision, runtime.Current.Workload))
              ApplyProjection = fun _ workload ->
                try apply workload with error ->
                    report error.Message
                    hostOption |> Option.iter _.Pause()
              CancelGeneration = ignore; Replace = ignore; Dispose = ignore }, SvgSessionHost.defaultConfig)
    hostOption <- Some host
    host.DemandProjection()
    { Submit = fun intent ->
        if not disposed then
            sequence <- sequence + 1UL
            update (SessionRuntimeObservation.AdmitInput
                { SessionId = sessionId; InputId = sprintf "soldier:%d" sequence; Sequence = sequence; Value = intent })
      Pause = host.Pause; Resume = host.Resume; Step = host.StepOnce; Reset = host.Reset
      Observe = host.Observe; Current = fun () -> runtime.Current.Workload
      Dispose = fun () ->
        if not disposed then
            update SessionRuntimeObservation.Dispose
            disposed <- true
            (host :> IDisposable).Dispose() }
