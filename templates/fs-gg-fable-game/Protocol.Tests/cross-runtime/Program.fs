module FableGameWorkspaceNamespace.Protocol.Tests.CrossRuntime.Program

open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace.ArenaContent
open FableGameWorkspaceNamespace.ArenaRules

/// A tiny CLI, compiled *twice* -- once as an ordinary .NET console app
/// (`CodecProbe.Net.fsproj`, against `Thoth.Json.Net`) and once via `dotnet fable`
/// (`CodecProbe.Fable.fsproj`, against `Thoth.Json`, run under Node) -- that exists
/// only to make ADR-0073's "not optional" acceptance criterion executable: every
/// request/response DTO is tested by encoding from .NET and decoding in the browser
/// runtime (and the reverse), including a case expected to be *rejected*, so
/// serializer compatibility is demonstrated per DTO rather than assumed for the type
/// system as a whole. `../run-cross-runtime.sh` drives both builds of this same
/// source file against each other's output.
///
/// The two `#if FABLE_COMPILER` blocks below are the only target-specific code in
/// this file; every codec call is the same named function from `Protocol/Http.fs` /
/// `Protocol/Realtime.fs` on both sides.

#if FABLE_COMPILER
open Fable.Core

[<Emit("process.argv.slice(2)")>]
let private commandLineArgs () : string[] = jsNative

[<Import("readFileSync", "node:fs")>]
let private readFileSyncNative (path: string, encoding: string) : string = jsNative

[<Import("writeFileSync", "node:fs")>]
let private writeFileSyncNative (path: string, contents: string) : unit = jsNative

let private readFile (path: string) : string = readFileSyncNative (path, "utf8")
let private writeFile (path: string) (contents: string) : unit = writeFileSyncNative (path, contents)
#else
let private commandLineArgs () : string[] =
    System.Environment.GetCommandLineArgs() |> Array.skip 1

let private readFile (path: string) : string = System.IO.File.ReadAllText path
let private writeFile (path: string) (contents: string) : unit = System.IO.File.WriteAllText(path, contents)
#endif

let private canonicalBootstrapRequest: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }

let private canonicalBootstrapResponse: BootstrapV1.Response =
    { Version = 1
      PlayerId = "cross-runtime-player"
      SessionCapability = "cross-runtime-capability"
      RoomId = "cross-runtime-room"
      SpawnCol = 3
      SpawnRow = 4
      ArenaWidth = 20
      ArenaHeight = 12 }

let private canonicalRealtimeCase (name: string) : RealtimeV1.Message option =
    match name with
    | "input" -> Some(RealtimeV1.InputMessage { Version = 1; Sequence = 7; TargetCol = 5; TargetRow = 2 })
    | "sessionHello" -> Some(RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = "cross-runtime-capability" })
    | "snapshot" ->
        Some(
            RealtimeV1.SnapshotMessage
                { Version = 1
                  Tick = 42
                  Players = [ { PlayerId = "p-1"; Col = 1; Row = 1 }; { PlayerId = "p-2"; Col = 2; Row = 3 } ] }
        )
    | "presence" -> Some(RealtimeV1.PresenceMessage { Version = 1; PlayerId = "p-1"; Joined = true })
    | "resyncRequest" -> Some(RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = 10 })
    | "resyncSnapshot" -> Some(RealtimeV1.ResyncSnapshotMessage { Version = 1; Tick = 42; Players = [] })
    | _ -> None

let private canonicalRealtimeV2Case (name: string) : RealtimeV2.Message option =
    let snapshot: RealtimeV2.Snapshot =
        { Version = 2; Tick = 42; Round = 3
          Players = [ { PlayerId = "p-1"; Col = 5; Row = 2 } ]
          Health = 2; Score = 100; Collected = true; Outcome = "playing"
          ContentId = "continuous-arena/cross-runtime"; ContentSchema = 2
          CollectibleX = 60.0; CollectibleY = 25.0
          HazardX = 88.0; HazardY = 80.0; HazardWidth = 11.0; HazardHeight = 10.0
          GoalX = 176.0; GoalY = 50.0; GoalWidth = 11.0; GoalHeight = 10.0
          ThinWallX = 112.0; ThinWallY = 0.0; ThinWallWidth = 2.0; ThinWallHeight = 48.0
          HazardCol = 8; HazardRow = 8 }
    match name with
    | "input" -> Some(RealtimeV2.InputMessage { Version = 2; Sequence = 8; Action = "interact"; TargetCol = 5; TargetRow = 2 })
    | "sessionHello" -> Some(RealtimeV2.SessionHelloMessage { Version = 2; SessionCapability = "cross-runtime-capability" })
    | "snapshot" -> Some(RealtimeV2.SnapshotMessage snapshot)
    | "presence" -> Some(RealtimeV2.PresenceMessage { Version = 2; PlayerId = "p-1"; Joined = true })
    | "resyncRequest" -> Some(RealtimeV2.ResyncRequestMessage { Version = 2; LastKnownTick = 10 })
    | "resyncSnapshot" -> Some(RealtimeV2.ResyncSnapshotMessage snapshot)
    | _ -> None

/// The two deliberately-rejected cases: an unrecognised discriminator, and a
/// well-known discriminator whose payload fails its own field decoders. Baked in
/// (not read from a file) so both runtimes independently attempt the *same* literal
/// bytes -- proving both decoders are equally strict, not merely that one runtime's
/// encoder never produces something the other rejects.
let private rejectedCases =
    [ "unrecognised-kind", """{"kind":"teleport","payload":{}}"""
      "wrong-field-type", """{"kind":"input","payload":{"version":1,"sequence":"not-a-number","targetCol":1,"targetRow":1}}""" ]

let private encodeArenaIntent = function
    | Intent.Move cell -> $"move:{cell.Col}:{cell.Row}"
    | Intent.LegacyMove cell -> $"legacy:{cell.Col}:{cell.Row}"
    | Intent.Interact -> "interact"
    | Intent.Restart -> "restart"

let private encodeArenaCommand = function
    | Command.Join(playerId, cell) -> $"join:{playerId}:{cell.Col}:{cell.Row}"
    | Command.Leave playerId -> $"leave:{playerId}"
    | Command.Apply(playerId, intent) -> $"apply:{playerId}:{encodeArenaIntent intent}"

let private interactionBoundaryProof () =
    let baseline = contentAt 0UL
    let stateBefore collectibleX =
        let content =
            { baseline with
                ContentId = "continuous-arena/interaction-boundary"
                CollectibleX = collectibleX
                CollectibleY = 5.0 }
        createWith content
        |> join "boundary-player" { Col = 0; Row = 0 }
    let atBoundaryBefore = stateBefore 15.0
    let justInsideBefore = stateBefore 14.9999999999
    let atBoundaryBytes = canonicalState atBoundaryBefore
    let justInsideBytes = canonicalState justInsideBefore
    if atBoundaryBytes = justInsideBytes then
        failwith "canonical state merged bounds with different interaction outcomes"
    let atBoundary = applyIntent "boundary-player" Intent.Interact atBoundaryBefore
    let justInside = applyIntent "boundary-player" Intent.Interact justInsideBefore
    if atBoundary.Status.Collected || not justInside.Status.Collected then
        failwith "interaction boundary no longer distinguishes touching from overlap"
    atBoundaryBytes + "\n" + justInsideBytes

/// Execute the product's complete portable contract and Replay implementation from
/// the same source on .NET and Fable. The exported bytes include every post-operation
/// digest, so matching final state alone cannot hide a dropped Interact or Restart.
let private arenaProof () =
    let boundaryProof = interactionBoundaryProof ()
    let baseline = contentAt 0UL
    let content =
        { baseline with
            ContentId = "continuous-arena/cross-runtime-rules"
            CollectibleX = 5.25
            CollectibleY = 5.75
            // Fractional AABBs model the bounds compiled from a rotated/scaled
            // Studio element and force portable numeric canonicalization.
            Hazard = { X = 9.625; Y = -1.25; Width = 13.75; Height = 12.5 }
            Goal = { baseline.Goal with X = 21.75; Y = -0.5; Width = 13.5; Height = 11.25 }
            ThinWall = { baseline.ThinWall with X = arenaWidth - 2.125; Y = 0.375 } }
    let contract = contractFor content.ContentId
    let mutable state =
        contract.Initialize { SessionId = "arena-1"; Compatibility = compatibility; Configuration = createWith content }
        |> Result.defaultWith (fun failure -> failwith failure.Code)
    let mutable recording =
        ReplayRecorder.create (contract.Snapshot state) (canonicalState state)
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    let mutable sequence = 0UL
    let apply command =
        sequence <- sequence + 1UL
        let input = { SessionId = "arena-1"; InputId = "cross-runtime-arena"; Sequence = sequence; Value = command }
        state <- contract.AdmitInput input state |> Result.defaultWith (fun failure -> failwith failure.Code)
        recording <- ReplayRecorder.appendInput input (canonicalState state) recording |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    apply (Command.Join("p", { Col = 0; Row = 0 }))
    apply (Command.Apply("p", Intent.Move { Col = 1; Row = 0 }))
    if state.Status.Health <> 2 then failwith "cross-runtime contact was not applied"
    apply (Command.Apply("p", Intent.Move { Col = 0; Row = 0 }))
    apply (Command.Apply("p", Intent.Interact))
    if not state.Status.Collected || state.Status.Score <> 100 then failwith "cross-runtime collectible was not applied"
    apply (Command.Apply("p", Intent.Move { Col = 1; Row = 0 }))
    apply (Command.Apply("p", Intent.Move { Col = 2; Row = 0 }))
    apply (Command.Apply("p", Intent.Interact))
    if state.Status.Outcome <> "won" then failwith "cross-runtime win was not applied"
    apply (Command.Apply("p", Intent.Restart))
    if state.Status <> initialStatus || state.Round <> 2 || state.Room.Players.["p"].Cell <> { Col = 0; Row = 0 } then
        failwith "cross-runtime restart was incomplete"
    state <- contract.Advance { SessionId = "arena-1"; StepCount = 20UL } state |> Result.defaultWith (fun failure -> failwith failure.Code)
    recording <- ReplayRecorder.appendAdvance 20UL (canonicalState state) recording |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    match Replay.seek contract canonicalState (fun _ -> false) (uint64 recording.Events.Length) recording with
    | Ok(ReplayRunOutcome.Completed(_, replayed)) when canonicalState replayed = canonicalState state ->
        ReplayExport.canonicalText encodeArenaCommand canonicalState recording
        |> Result.map (fun replay -> canonicalState state + "\n---BOUNDARY---\n" + boundaryProof + "\n---REPLAY---\n" + replay)
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    | outcome -> failwithf "cross-runtime replay failed: %A" outcome

[<EntryPoint>]
let main _ =
    match commandLineArgs () |> Array.toList with
    | [ "encode-bootstrap-request"; outFile ] ->
        writeFile outFile (BootstrapV1.encodeRequest canonicalBootstrapRequest)
        printfn "WROTE"
        0
    | [ "decode-bootstrap-request"; inFile ] ->
        match readFile inFile |> BootstrapV1.requestFromJson with
        | Ok value when value = canonicalBootstrapRequest -> printfn "OK"; 0
        | Ok value -> printfn "MISMATCH %A" value; 1
        | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-bootstrap-response"; outFile ] ->
        writeFile outFile (BootstrapV1.encodeResponse canonicalBootstrapResponse)
        printfn "WROTE"
        0
    | [ "decode-bootstrap-response"; inFile ] ->
        match readFile inFile |> BootstrapV1.responseFromJson with
        | Ok value when value = canonicalBootstrapResponse -> printfn "OK"; 0
        | Ok value -> printfn "MISMATCH %A" value; 1
        | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-realtime"; caseName; outFile ] ->
        match canonicalRealtimeCase caseName with
        | Some message ->
            writeFile outFile (RealtimeV1.encodeMessage message)
            printfn "WROTE"
            0
        | None ->
            printfn "UNKNOWN-CASE %s" caseName
            2
    | [ "decode-realtime"; caseName; inFile ] ->
        match canonicalRealtimeCase caseName with
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
        | Some expected ->
            match readFile inFile |> RealtimeV1.messageFromJson with
            | Ok value when value = expected -> printfn "OK"; 0
            | Ok value -> printfn "MISMATCH %A" value; 1
            | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-realtime-v2"; caseName; outFile ] ->
        match canonicalRealtimeV2Case caseName with
        | Some message -> writeFile outFile (RealtimeV2.encodeMessage message); printfn "WROTE"; 0
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
    | [ "decode-realtime-v2"; caseName; inFile ] ->
        match canonicalRealtimeV2Case caseName with
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
        | Some expected ->
            match readFile inFile |> RealtimeV2.messageFromJson with
            | Ok value when value = expected -> printfn "OK"; 0
            | Ok value -> printfn "MISMATCH %A" value; 1
            | Error message -> printfn "REJECTED %s" message; 1
    | [ "decode-rejected-cases" ] ->
        let results =
            rejectedCases
            |> List.map (fun (name, json) ->
                match RealtimeV1.messageFromJson json with
                | Error _ -> name, true
                | Ok value -> printfn "UNEXPECTEDLY-ACCEPTED %s -> %A" name value; name, false)
        if results |> List.forall snd then
            printfn "ALL-REJECTED-AS-EXPECTED"
            0
        else
            1
    | [ "write-arena-proof"; outFile ] ->
        writeFile outFile (arenaProof ())
        printfn "WROTE"
        0
#if !FABLE_COMPILER
    | [ "write-arena-proof-de"; outFile ] ->
        System.Globalization.CultureInfo.CurrentCulture <- System.Globalization.CultureInfo.GetCultureInfo("de-DE")
        writeFile outFile (arenaProof ())
        printfn "WROTE"
        0
#endif
    | args ->
        printfn "USAGE: unrecognised arguments %A" args
        2
