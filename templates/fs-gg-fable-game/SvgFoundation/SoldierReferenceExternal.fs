module FableGameWorkspaceNamespace.SvgFoundation.SoldierReferenceExternal

open System
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.SoldierWorkload

type private Envelope = { Epoch: string; Revision: uint64; Workload: Workload }
type private Acquisition =
    { Generation: uint64; Id: uint64; Snapshot: Envelope; mutable Settled: bool }

type Owner =
    { Submit: Command -> unit; Independent: int -> unit
      Connect: unit -> unit; Disconnect: unit -> unit; Replace: unit -> unit
      Burst: unit -> unit; Cached: unit -> unit; Complete: unit -> unit; CompleteOldest: unit -> unit
      FailNext: unit -> unit; Observe: unit -> SvgExternalSessionHostObservation
      Describe: unit -> string * int * string * int; Dispose: unit -> unit }

// Deterministic, unauthenticated fixture gateway. No local session or simulation clock.
let create initial (apply: Workload -> unit) (report: string -> unit) =
    let mutable authority = { Epoch = "soldier-epoch-A"; Revision = uint64 initial.AuthorityRevision; Workload = initial }
    let mutable replacement = 0UL
    let mutable sequence = 0UL
    let mutable receipts: string list = []
    let acquisitions = ResizeArray<Acquisition>()
    let mutable cached: Envelope option = None
    let mutable failApply = false
    let mutable disposed = false
    let host =
        new SvgExternalSessionHost<Workload>(
            { RequestPresentation = fun generation id epoch ->
                if epoch <> authority.Epoch then failwith "Soldier gateway epoch mismatch"
                if acquisitions.Count >= 32 then
                    let settled = acquisitions |> Seq.tryFindIndex _.Settled
                    match settled with Some index -> acquisitions.RemoveAt index | None -> failwith "Soldier gateway acquisition bound"
                let captured = cached |> Option.defaultValue authority
                cached <- None
                acquisitions.Add { Generation = generation; Id = id; Snapshot = captured; Settled = false }
              ApplyPresentation = fun _ _ workload ->
                if failApply then
                    failApply <- false
                    failwith "Soldier fixture presentation failure"
                try apply workload with error ->
                    report error.Message
                    reraise ()
              CancelAcquisition = fun generation id ->
                acquisitions |> Seq.tryFind (fun request -> request.Generation = generation && request.Id = id)
                |> Option.iter (fun request -> request.Settled <- true)
              EpochBound = fun _ _ _ -> (); Disconnected = ignore
              Dispose = fun () -> acquisitions |> Seq.iter (fun request -> request.Settled <- true) })
    let admit change =
        if not disposed then
            sequence <- sequence + 1UL
            let result =
                if host.Observe().State.Status <> SvgExternalSessionStatus.Connected then Error [ "disconnected" ]
                else change authority.Workload
            let outcome =
                match result with
                | Error issues -> report (String.concat "," issues); "rejected"
                | Ok workload ->
                    authority <- { authority with Workload = workload; Revision = uint64 workload.AuthorityRevision }
                    "accepted"
            receipts <- (receipts @ [ sprintf "%d:%s" sequence outcome ]) |> List.rev |> List.truncate 128 |> List.rev
            host.DemandPresentation()
    let complete request =
        request.Settled <- true
        host.CompletePresentation(request.Generation, request.Id, request.Snapshot.Epoch, request.Snapshot.Revision, request.Snapshot.Workload)
    let presentation = { Revision = 0; Camera = SvgAffine.identity; Selected = None; Focused = None }
    { Submit = fun command -> admit (fun workload ->
        let next, issues = tryApply command { Workload = workload; Presentation = presentation }
        match issues with Some issues -> Error issues | None -> Ok next.Workload)
      Independent = fun percentage -> admit (updatedSoldiers percentage)
      Connect = fun () -> if not disposed then host.BindEpoch authority.Epoch; host.DemandPresentation()
      Disconnect = host.Disconnect
      Replace = fun () ->
        if not disposed then
            replacement <- replacement + 1UL
            authority <- { Epoch = sprintf "soldier-epoch-replacement:%d" replacement; Revision = uint64 initial.AuthorityRevision; Workload = initial }
            host.BindEpoch authority.Epoch
            host.DemandPresentation()
      Burst = fun () -> host.DemandPresentation(); host.DemandPresentation(); host.DemandPresentation()
      Cached = fun () ->
        cached <- acquisitions |> Seq.tryFind (fun request -> request.Snapshot.Epoch = authority.Epoch) |> Option.map _.Snapshot
        host.DemandPresentation()
      Complete = fun () -> acquisitions |> Seq.tryFindBack (fun request -> not request.Settled) |> Option.iter complete
      CompleteOldest = fun () -> acquisitions |> Seq.tryHead |> Option.iter complete
      FailNext = fun () -> failApply <- true
      Observe = host.Observe
      Describe = fun () -> authority.Epoch, authority.Workload.AuthorityRevision, String.concat "," receipts, (acquisitions |> Seq.filter (fun request -> not request.Settled) |> Seq.length)
      Dispose = fun () -> if not disposed then disposed <- true; (host :> IDisposable).Dispose() }
