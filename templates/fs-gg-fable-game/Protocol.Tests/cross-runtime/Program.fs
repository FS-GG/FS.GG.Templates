module FableGameWorkspaceNamespace.Protocol.Tests.CrossRuntime.Program

open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime

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
      RoomId = "cross-runtime-room"
      SpawnCol = 3
      SpawnRow = 4
      ArenaWidth = 20
      ArenaHeight = 12 }

let private canonicalRealtimeCase (name: string) : RealtimeV1.Message option =
    match name with
    | "input" -> Some(RealtimeV1.InputMessage { Sequence = 7; TargetCol = 5; TargetRow = 2 })
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

/// The two deliberately-rejected cases: an unrecognised discriminator, and a
/// well-known discriminator whose payload fails its own field decoders. Baked in
/// (not read from a file) so both runtimes independently attempt the *same* literal
/// bytes -- proving both decoders are equally strict, not merely that one runtime's
/// encoder never produces something the other rejects.
let private rejectedCases =
    [ "unrecognised-kind", """{"kind":"teleport","payload":{}}"""
      "wrong-field-type", """{"kind":"input","payload":{"sequence":"not-a-number","targetCol":1,"targetRow":1}}""" ]

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
    | args ->
        printfn "USAGE: unrecognised arguments %A" args
        2
