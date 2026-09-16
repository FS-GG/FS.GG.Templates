module PresentationPlayer

open System
open FS.GG.Game.Core
open FS.GG.UI.Scene

module Player = FableGameWorkspaceNamespace.SvgFoundation.ContinuousPlayer

let private number (value: float) = string value

let encode (state: Player.PlayerState) =
    let outcome =
        match state.Outcome with
        | Player.PlayerOutcome.Playing -> "playing"
        | Player.PlayerOutcome.Won -> "won"
        | Player.PlayerOutcome.Lost -> "lost"

    String.concat
        "|"
        [
            number state.Player.X
            number state.Player.Y
            number state.Player.Width
            number state.Player.Height
            number state.Velocity.X
            number state.Velocity.Y
            string state.Health
            string state.Score
            string state.Collected
            outcome
            string state.Revision
        ]

let decode (payload: string) =
    let parts = payload.Split('|')
    let parseFloat index = Double.Parse(parts[index])
    let parseInt index = Int32.Parse(parts[index])
    let parseRevision index = UInt64.Parse(parts[index])

    if parts.Length <> 11 then
        Error "save payload field count"
    else
        try
            let outcome =
                match parts[9] with
                | "playing" -> Player.PlayerOutcome.Playing
                | "won" -> Player.PlayerOutcome.Won
                | "lost" -> Player.PlayerOutcome.Lost
                | _ -> invalidArg "payload" "unknown outcome"

            let state: Player.PlayerState =
                {
                    Player =
                        {
                            X = parseFloat 0
                            Y = parseFloat 1
                            Width = parseFloat 2
                            Height = parseFloat 3
                        }
                    Velocity = { X = parseFloat 4; Y = parseFloat 5 }
                    Health = parseInt 6
                    Score = parseInt 7
                    Collected = parseInt 8
                    Outcome = outcome
                    HazardCol = 7
                    HazardRow = 8
                    Content = FableGameWorkspaceNamespace.ArenaContent.contentAt 0UL
                    Revision = parseRevision 10
                }

            Ok state
        with error ->
            Error error.Message

let hashPayload (payload: string) =
    let mutable hash = 2166136261u

    for character in payload do
        hash <- (hash ^^^ uint32 character) * 16777619u

    let digits = "0123456789abcdef"

    [| for shift in 28..-4..0 -> digits[int ((hash >>> shift) &&& 15u)] |]
    |> System.String

let identity schemaVersion payloadHash =
    {
        Family = SaveFamily.GameSave
        EngineId = "fs-gg.svg-continuous-player"
        EngineVersion = "1"
        ProfileId = "generated-player"
        SchemaId = "continuous-arena"
        SchemaVersion = schemaVersion
        ContentHash = "generated-arena-v1"
        AssetHash = "generated-vector-assets-v1"
    },
    payloadHash

let acceptEnvelope schemaVersion payloadHash payload =
    let expectedIdentity, _ = identity 1 payloadHash
    let candidateIdentity, _ = identity schemaVersion payloadHash

    let candidate =
        {
            Identity = candidateIdentity
            PayloadHash = payloadHash
            Payload = payload
        }

    match SaveMigration.initialize expectedIdentity with
    | Error refusal -> Error refusal
    | Ok initial ->
        let _, effects =
            SaveMigration.update hashPayload [] (SaveMigrationObservation.Begin candidate) initial

        effects
        |> List.tryPick (function
            | SaveMigrationEffect.Accepted value -> Some(Ok value.Payload)
            | SaveMigrationEffect.Refused refusal -> Some(Error refusal)
            | _ -> None)
        |> Option.defaultValue (Error(SaveRefusal.OperationFailed "save acceptance produced no terminal effect"))

let movementClip =
    {
        Id = "generated-player-movement"
        Duration = TimeSpan.FromMilliseconds 120.0
        Tracks =
            [
                PositionX,
                [
                    {
                        Time = TimeSpan.Zero
                        Value = ScalarValue -2.0
                        EasingToNext = EaseOut
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 120.0
                        Value = ScalarValue 0.0
                        EasingToNext = Linear
                    }
                ]
                Opacity,
                [
                    {
                        Time = TimeSpan.Zero
                        Value = ScalarValue 0.72
                        EasingToNext = Linear
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 120.0
                        Value = ScalarValue 1.0
                        EasingToNext = Linear
                    }
                ]
            ]
        Cues =
            [
                {
                    Id = "movement-confirmed"
                    Time = TimeSpan.FromMilliseconds 20.0
                    Payload = "audio.move"
                }
            ]
        Loop = Once
    }
    |> AnimationClip.validate
    |> Result.defaultWith (fun issues -> failwithf "generated movement clip rejected: %A" issues)

let outcomeClip =
    {
        Id = "generated-player-outcome"
        Duration = TimeSpan.FromMilliseconds 180.0
        Tracks =
            [
                ScaleX,
                [
                    {
                        Time = TimeSpan.Zero
                        Value = ScalarValue 1.0
                        EasingToNext = EaseOut
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 90.0
                        Value = ScalarValue 1.18
                        EasingToNext = EaseIn
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 180.0
                        Value = ScalarValue 1.0
                        EasingToNext = Linear
                    }
                ]
                ScaleY,
                [
                    {
                        Time = TimeSpan.Zero
                        Value = ScalarValue 1.0
                        EasingToNext = EaseOut
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 90.0
                        Value = ScalarValue 1.18
                        EasingToNext = EaseIn
                    }
                    {
                        Time = TimeSpan.FromMilliseconds 180.0
                        Value = ScalarValue 1.0
                        EasingToNext = Linear
                    }
                ]
            ]
        Cues =
            [
                {
                    Id = "outcome-confirmed"
                    Time = TimeSpan.FromMilliseconds 30.0
                    Payload = "audio.outcome"
                }
            ]
        Loop = Once
    }
    |> AnimationClip.validate
    |> Result.defaultWith (fun issues -> failwithf "generated outcome clip rejected: %A" issues)
