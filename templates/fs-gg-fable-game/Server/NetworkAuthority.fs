namespace FableGameWorkspaceNamespace.Server

open FS.GG.Game.Core
open FS.GG.Net.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace

/// Game owns admission and complete replay semantics; Net owns bounded delivery and
/// reconnect state. Every recorded event carries the digest of the same ArenaRules
/// state used by production, including content, health, score, outcome, and contacts.
[<RequireQualifiedAccess>]
module NetworkAuthority =

    type AdmittedIntent =
        {
            Action: string
            TargetCol: int
            TargetRow: int
        }

    type ReplayCommand = ArenaRules.Command

    type Snapshot = ArenaRules.State

    let private sessionId = "arena-1"

    let private snapshotEnvelope revision value : SessionSnapshot<Snapshot> =
        {
            SessionId = sessionId
            Revision = revision
            Compatibility = ArenaRules.compatibility
            Value = value
        }

    let private encodeSnapshot = ArenaRules.canonicalState

    let private encodeIntent =
        function
        | ArenaRules.Intent.Move cell -> $"move|{cell.Col}|{cell.Row}"
        | ArenaRules.Intent.LegacyMove cell -> $"legacy-move|{cell.Col}|{cell.Row}"
        | ArenaRules.Intent.Interact -> "interact"
        | ArenaRules.Intent.Restart -> "restart"

    let private encodeCommand =
        function
        | ArenaRules.Command.Join(playerId, cell) -> $"join|{playerId}|{cell.Col}|{cell.Row}"
        | ArenaRules.Command.Leave playerId -> $"leave|{playerId}"
        | ArenaRules.Command.Apply(playerId, intent) -> $"intent|{playerId}|{encodeIntent intent}"

    let private digest = encodeSnapshot

    let mutable private admission: NetworkAdmissionState<AdmittedIntent> =
        NetworkAdmission.create sessionId []
        |> Result.defaultWith (fun issues -> invalidOp $"network admission: {issues}")

    let mutable private deliveries: Map<string, DeliveryState<Snapshot, Snapshot>> =
        Map.empty

    let mutable private replay: ReplayRecording<ReplayCommand, Snapshot> =
        let initial = ArenaRules.create ()

        ReplayRecorder.create (snapshotEnvelope 0UL initial) (digest initial)
        |> Result.defaultWith (fun issues -> invalidOp $"replay initialization: {issues}")

    let mutable private replaySequence = 0UL

    let private append command snapshot =
        replaySequence <- replaySequence + 1UL

        let input: SessionInput<ReplayCommand> =
            {
                SessionId = sessionId
                InputId = "fsgg.generated.arena.v2"
                Sequence = replaySequence
                Value = command
            }

        replay <-
            ReplayRecorder.appendInput input (digest snapshot) replay
            |> Result.defaultWith (fun issues -> invalidOp $"replay append: {issues}")

    let reset (snapshot: Snapshot) =
        admission <-
            NetworkAdmission.create sessionId []
            |> Result.defaultWith (fun issues -> invalidOp $"network admission: {issues}")

        deliveries <- Map.empty
        replaySequence <- 0UL

        replay <-
            ReplayRecorder.create (snapshotEnvelope 0UL snapshot) (digest snapshot)
            |> Result.defaultWith (fun issues -> invalidOp $"replay initialization: {issues}")

    let bind playerId token revision (snapshot: Snapshot) =
        let binding: NetworkClientBinding =
            {
                SessionId = sessionId
                ClientId = playerId
                ReconnectToken = token
            }

        admission <-
            NetworkAdmission.bind binding admission
            |> Result.defaultWith (fun issues -> invalidOp $"network bind: {issues}")

        let ticket: ReconnectTicket =
            {
                SessionId = sessionId
                ClientId = playerId
                Token = token
            }

        let config =
            {
                MaxQueuedDeltas = 4
                ReconnectLifetimeMilliseconds = 120000UL
            }

        let delivery: DeliveryState<Snapshot, Snapshot> =
            Delivery.create config ticket revision
            |> Result.defaultWith (fun issues -> invalidOp $"delivery create: {issues}")

        deliveries <- Map.add playerId delivery deliveries
        let cell = snapshot.Room.Players.[playerId].Cell
        append (ArenaRules.Command.Join(playerId, cell)) snapshot

    let unbind playerId (snapshot: Snapshot) =
        admission <- NetworkAdmission.unbind playerId admission

        deliveries <-
            match Map.tryFind playerId deliveries with
            | Some delivery -> let _, _ = Delivery.dispose delivery in Map.remove playerId deliveries
            | None -> deliveries

        append (ArenaRules.Command.Leave playerId) snapshot

    let admit playerId token sequence action targetCol targetRow =
        let binding: NetworkClientBinding =
            {
                SessionId = sessionId
                ClientId = playerId
                ReconnectToken = token
            }

        let candidate: NetworkInput<AdmittedIntent> =
            {
                Binding = binding
                Input =
                    {
                        SessionId = sessionId
                        InputId = "fsgg.generated.arena.v2"
                        Sequence = sequence
                        Value =
                            {
                                Action = action
                                TargetCol = targetCol
                                TargetRow = targetRow
                            }
                    }
            }

        let validate intent =
            if not (Set.contains intent.Action (Set.ofList [ "move"; "legacy-move"; "interact"; "restart" ])) then
                Error "intent.unknown-action"
            elif
                intent.TargetCol < 0
                || intent.TargetCol >= ArenaContent.arenaColumns
                || intent.TargetRow < 0
                || intent.TargetRow >= ArenaContent.arenaRows
            then
                Error "intent.out-of-bounds"
            else
                Ok()

        match NetworkAdmission.admit validate candidate admission with
        | Error issue -> Error $"{issue}"
        | Ok(next, accepted) ->
            admission <- next
            Ok accepted.AcceptedOrder

    let recordIntent playerId intent snapshot =
        append (ArenaRules.Command.Apply(playerId, intent)) snapshot

    let recordAdvance revision snapshot =
        replay <-
            ReplayRecorder.appendAdvance 1UL (digest snapshot) replay
            |> Result.defaultWith (fun issues -> invalidOp $"replay advance: {issues}")

        if revision % 16UL = 0UL then
            replay <-
                ReplayRecorder.addCheckpoint (snapshotEnvelope revision snapshot) (digest snapshot) replay
                |> Result.defaultWith (fun issues -> invalidOp $"replay checkpoint: {issues}")

    let publish revision snapshot =
        deliveries <-
            deliveries
            |> Map.map (fun _ delivery ->
                Delivery.publish revision snapshot snapshot delivery
                |> Result.map fst
                |> Result.defaultValue delivery)

    let acknowledge playerId revision =
        match Map.tryFind playerId deliveries with
        | None -> Error "client delivery is not bound"
        | Some delivery ->
            match Delivery.acknowledge revision delivery with
            | Error issue -> Error $"{issue}"
            | Ok(next, _) ->
                deliveries <- Map.add playerId next deliveries
                Ok()

    let disconnect playerId now =
        match Map.tryFind playerId deliveries with
        | None -> ()
        | Some delivery ->
            match Delivery.disconnect now delivery with
            | Ok(next, _) -> deliveries <- Map.add playerId next deliveries
            | Error _ -> ()

    let reconnect playerId token now =
        match Map.tryFind playerId deliveries with
        | None -> Error "client delivery is not bound"
        | Some delivery ->
            let ticket =
                {
                    SessionId = sessionId
                    ClientId = playerId
                    Token = token
                }

            match Delivery.reconnect ticket now delivery with
            | Error issue -> Error $"{issue}"
            | Ok(next, DeliveryEffect.Reconnected pending) ->
                deliveries <- Map.add playerId next deliveries
                Ok pending
            | Ok(next, _) ->
                deliveries <- Map.add playerId next deliveries
                Ok []

    let resync clientRevision currentRevision =
        NetworkAdmission.resync None clientRevision currentRevision

    let verifyReplay () =
        Replay.seek
            (ArenaRules.contractForDefinition replay.InitialSnapshot.Value.Definition)
            digest
            (fun _ -> false)
            (uint64 replay.Events.Length)
            replay

    let review () =
        let accepted =
            NetworkAdmission.canonicalText
                (fun intent -> $"{intent.Action}:{intent.TargetCol},{intent.TargetRow}")
                admission

        let replayText =
            ReplayExport.canonicalText encodeCommand encodeSnapshot replay
            |> Result.defaultWith (fun issues -> invalidOp $"replay export: {issues}")

        accepted, replayText, replay.Events.Length
