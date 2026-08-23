module FableGameWorkspaceNamespace.Protocol.Tests.CodecTests

open Xunit
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime

[<Fact>]
let ``BootstrapV1 request round-trips through JSON`` () =
    let value: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }
    let decoded = value |> BootstrapV1.encodeRequest |> BootstrapV1.requestFromJson
    Assert.Equal(Ok value, decoded)

[<Fact>]
let ``BootstrapV1 response round-trips through JSON`` () =
    let value: BootstrapV1.Response =
        { Version = 1
          PlayerId = "p-1"
          SessionCapability = "opaque-capability"
          RoomId = "room-1"
          SpawnCol = 3
          SpawnRow = 4
          ArenaWidth = 20
          ArenaHeight = 12 }
    let decoded = value |> BootstrapV1.encodeResponse |> BootstrapV1.responseFromJson
    Assert.Equal(Ok value, decoded)

[<Fact>]
let ``BootstrapV1 rejects a request missing a required field`` () =
    let decoded = BootstrapV1.requestFromJson """{"version":1}"""
    Assert.True(Result.isError decoded)

[<Theory>]
[<InlineData(0)>]
[<InlineData(1)>]
[<InlineData(2)>]
[<InlineData(3)>]
[<InlineData(4)>]
[<InlineData(5)>]
let ``RealtimeV1 message round-trips through JSON for every case`` (caseIndex: int) =
    let value: RealtimeV1.Message =
        match caseIndex with
        | 0 -> RealtimeV1.InputMessage { Version = 1; Sequence = 7; TargetCol = 5; TargetRow = 2 }
        | 1 -> RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = "opaque-capability" }
        | 2 -> RealtimeV1.SnapshotMessage { Version = 1; Tick = 42; Players = [ { PlayerId = "p-1"; Col = 1; Row = 1 }; { PlayerId = "p-2"; Col = 2; Row = 3 } ] }
        | 3 -> RealtimeV1.PresenceMessage { Version = 1; PlayerId = "p-1"; Joined = true }
        | 4 -> RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = 10 }
        | _ -> RealtimeV1.ResyncSnapshotMessage { Version = 1; Tick = 42; Players = [] }
    let decoded = value |> RealtimeV1.encodeMessage |> RealtimeV1.messageFromJson
    Assert.Equal(Ok value, decoded)

/// ADR-0073's "not optional" acceptance criterion: an arbitrary-DU boundary case that
/// is *expected to be rejected*, not merely one that happens to succeed. Two distinct
/// rejection shapes are exercised: an unrecognised discriminator, and a well-known
/// discriminator whose payload fails its own field decoders.
[<Fact>]
let ``RealtimeV1 rejects an unrecognised message kind`` () =
    let decoded = RealtimeV1.messageFromJson """{"kind":"teleport","payload":{}}"""
    match decoded with
    | Error message -> Assert.Contains("teleport", message)
    | Ok _ -> Assert.Fail "an unrecognised discriminator must not decode"

[<Fact>]
let ``RealtimeV1 rejects an input payload with the wrong field types`` () =
    let decoded = RealtimeV1.messageFromJson """{"kind":"input","payload":{"version":1,"sequence":"not-a-number","targetCol":1,"targetRow":1}}"""
    Assert.True(Result.isError decoded)

[<Fact>]
let ``RealtimeV1 rejects a session hello without its opaque capability`` () =
    let decoded = RealtimeV1.messageFromJson """{"kind":"sessionHello","payload":{"version":1}}"""
    Assert.True(Result.isError decoded)
