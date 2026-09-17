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
        {
            Version = 1
            PlayerId = "p-1"
            SessionCapability = "opaque-capability"
            RoomId = "room-1"
            SpawnCol = 3
            SpawnRow = 4
            ArenaWidth = 20
            ArenaHeight = 12
        }

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
        | 0 ->
            RealtimeV1.InputMessage
                {
                    Version = 1
                    Sequence = 7
                    TargetCol = 5
                    TargetRow = 2
                }
        | 1 ->
            RealtimeV1.SessionHelloMessage
                {
                    Version = 1
                    SessionCapability = "opaque-capability"
                }
        | 2 ->
            RealtimeV1.SnapshotMessage
                {
                    Version = 1
                    Tick = 42
                    Players =
                        [
                            { PlayerId = "p-1"; Col = 1; Row = 1 }
                            { PlayerId = "p-2"; Col = 2; Row = 3 }
                        ]
                }
        | 3 ->
            RealtimeV1.PresenceMessage
                {
                    Version = 1
                    PlayerId = "p-1"
                    Joined = true
                }
        | 4 -> RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = 10 }
        | _ -> RealtimeV1.ResyncSnapshotMessage { Version = 1; Tick = 42; Players = [] }

    let decoded = value |> RealtimeV1.encodeMessage |> RealtimeV1.messageFromJson
    Assert.Equal(Ok value, decoded)

[<Theory>]
[<InlineData(0)>]
[<InlineData(1)>]
[<InlineData(2)>]
[<InlineData(3)>]
[<InlineData(4)>]
[<InlineData(5)>]
let ``RealtimeV2 complete arena message round-trips for every case`` (caseIndex: int) =
    let snapshot: RealtimeV2.Snapshot =
        {
            Version = 2
            Tick = 42
            Round = 3
            Players = [ { PlayerId = "p-1"; Col = 1; Row = 1 } ]
            Health = 3
            Score = 100
            Collected = true
            Outcome = "playing"
            ContentId = "continuous-arena/default-v2"
            ContentSchema = 2
            CollectibleX = 60.0
            CollectibleY = 25.0
            HazardX = 88.0
            HazardY = 80.0
            HazardWidth = 11.0
            HazardHeight = 10.0
            GoalX = 176.0
            GoalY = 50.0
            GoalWidth = 11.0
            GoalHeight = 10.0
            ThinWallX = 112.0
            ThinWallY = 0.0
            ThinWallWidth = 2.0
            ThinWallHeight = 48.0
            HazardCol = 8
            HazardRow = 8
        }

    let value: RealtimeV2.Message =
        match caseIndex with
        | 0 ->
            RealtimeV2.InputMessage
                {
                    Version = 2
                    Sequence = 7
                    Action = "interact"
                    TargetCol = 5
                    TargetRow = 2
                }
        | 1 ->
            RealtimeV2.SessionHelloMessage
                {
                    Version = 2
                    SessionCapability = "opaque-capability"
                }
        | 2 -> RealtimeV2.SnapshotMessage snapshot
        | 3 ->
            RealtimeV2.PresenceMessage
                {
                    Version = 2
                    PlayerId = "p-1"
                    Joined = true
                }
        | 4 -> RealtimeV2.ResyncRequestMessage { Version = 2; LastKnownTick = 10 }
        | _ -> RealtimeV2.ResyncSnapshotMessage snapshot

    Assert.Equal(Ok value, value |> RealtimeV2.encodeMessage |> RealtimeV2.messageFromJson)

[<Fact>]
let ``RealtimeV2 refuses a snapshot without complete content identity`` () =
    let incomplete =
        """{"kind":"snapshot","payload":{"version":2,"tick":1,"players":[],"health":3,"score":0,"collected":false,"outcome":"playing","hazardCol":7,"hazardRow":8}}"""

    Assert.True(RealtimeV2.messageFromJson incomplete |> Result.isError)

let private authoredV3Snapshot: RealtimeV3.Snapshot =
    {
        Version = 3
        Tick = 42
        Round = 3
        Players = [ { PlayerId = "p-1"; Col = 4; Row = 3 } ]
        Health = 2
        Score = 100
        Collected = true
        Outcome = "playing"
        ContentId = "continuous-arena/authored-v3"
        ContentSchema = 3
        BoundaryX = 0.0
        BoundaryY = 0.0
        BoundaryWidth = 220.0
        BoundaryHeight = 120.0
        SpawnCol = 4
        SpawnRow = 3
        CollectibleX = 60.5
        CollectibleY = 25.25
        HazardX = 88.0
        HazardY = 80.0
        HazardWidth = 11.0
        HazardHeight = 10.0
        GoalX = 176.0
        GoalY = 50.0
        GoalWidth = 11.0
        GoalHeight = 10.0
        ThinWallX = 112.0
        ThinWallY = 0.0
        ThinWallWidth = 2.0
        ThinWallHeight = 48.0
        HazardCol = 8
        HazardRow = 8
    }

[<Theory>]
[<InlineData(0)>]
[<InlineData(1)>]
[<InlineData(2)>]
[<InlineData(3)>]
[<InlineData(4)>]
[<InlineData(5)>]
let ``RealtimeV3 carries immutable authored content for every message case`` (caseIndex: int) =
    let value: RealtimeV3.Message =
        match caseIndex with
        | 0 ->
            RealtimeV3.InputMessage
                {
                    Version = 3
                    Sequence = 7
                    Action = "interact"
                    TargetCol = 4
                    TargetRow = 3
                }
        | 1 ->
            RealtimeV3.SessionHelloMessage
                {
                    Version = 3
                    SessionCapability = "opaque-capability"
                }
        | 2 -> RealtimeV3.SnapshotMessage authoredV3Snapshot
        | 3 ->
            RealtimeV3.PresenceMessage
                {
                    Version = 3
                    PlayerId = "p-1"
                    Joined = true
                }
        | 4 -> RealtimeV3.ResyncRequestMessage { Version = 3; LastKnownTick = 10 }
        | _ -> RealtimeV3.ResyncSnapshotMessage authoredV3Snapshot

    Assert.Equal(Ok value, value |> RealtimeV3.encodeMessage |> RealtimeV3.messageFromJson)

[<Fact>]
let ``RealtimeV3 refuses a V2 snapshot that omits immutable spawn and boundary`` () =
    let oldWire =
        RealtimeV2.SnapshotMessage
            {
                Version = 2
                Tick = authoredV3Snapshot.Tick
                Round = authoredV3Snapshot.Round
                Players = []
                Health = 3
                Score = 0
                Collected = false
                Outcome = "playing"
                ContentId = "continuous-arena/default-v2"
                ContentSchema = 2
                CollectibleX = 60.
                CollectibleY = 25.
                HazardX = 88.
                HazardY = 80.
                HazardWidth = 11.
                HazardHeight = 10.
                GoalX = 176.
                GoalY = 50.
                GoalWidth = 11.
                GoalHeight = 10.
                ThinWallX = 112.
                ThinWallY = 0.
                ThinWallWidth = 2.
                ThinWallHeight = 48.
                HazardCol = 8
                HazardRow = 8
            }

    Assert.True(
        oldWire
        |> RealtimeV2.encodeMessage
        |> RealtimeV3.messageFromJson
        |> Result.isError
    )

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
    let decoded =
        RealtimeV1.messageFromJson
            """{"kind":"input","payload":{"version":1,"sequence":"not-a-number","targetCol":1,"targetRow":1}}"""

    Assert.True(Result.isError decoded)

[<Fact>]
let ``RealtimeV1 rejects a session hello without its opaque capability`` () =
    let decoded =
        RealtimeV1.messageFromJson """{"kind":"sessionHello","payload":{"version":1}}"""

    Assert.True(Result.isError decoded)
