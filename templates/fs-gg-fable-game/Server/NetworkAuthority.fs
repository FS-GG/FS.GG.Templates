namespace FableGameWorkspaceNamespace.Server

open FS.GG.Game.Core
open FS.GG.Net.Core
open FableGameWorkspaceNamespace.Domain

/// The candidate networking composition. Game owns admission and replay semantics;
/// Net owns bounded delivery and reconnect state; this generated server supplies the
/// product move validation and the only state-changing transition function.
[<RequireQualifiedAccess>]
module NetworkAuthority =

    type MoveIntent = { TargetCol: int; TargetRow: int }

    type ReplayCommand =
        | Joined of playerId: string * cell: Cell
        | Left of playerId: string
        | Moved of playerId: string * target: Cell

    type Snapshot = int * (string * int * int) list

    let private sessionId = "arena-1"

    let private compatibility =
        { ContractVersion = 1
          EngineId = "fsgg.generated.arena"
          EngineVersion = "1"
          ProfileId = "authoritative-room"
          SchemaId = "fsgg.generated.arena.snapshot"
          SchemaVersion = 1 }

    let private snapshotEnvelope revision value : SessionSnapshot<Snapshot> =
        { SessionId = sessionId
          Revision = revision
          Compatibility = compatibility
          Value = value }

    let private encodeSnapshot (tick, players) =
        let encodedPlayers =
            players
            |> List.map (fun (playerId, col, row) -> $"{playerId}:{col}:{row}")
            |> String.concat ";"
        $"{tick}|{encodedPlayers}"

    let private encodeCommand = function
        | Joined(playerId, cell) -> $"join|{playerId}|{cell.Col}|{cell.Row}"
        | Left playerId -> $"leave|{playerId}"
        | Moved(playerId, cell) -> $"move|{playerId}|{cell.Col}|{cell.Row}"

    let private digest snapshot = encodeSnapshot snapshot

    let mutable private admission : NetworkAdmissionState<MoveIntent> =
        NetworkAdmission.create sessionId [] |> Result.defaultWith (fun issues -> invalidOp $"network admission: {issues}")

    let mutable private deliveries : Map<string, DeliveryState<Snapshot, Snapshot>> = Map.empty
    let mutable private replay : ReplayRecording<ReplayCommand, Snapshot> =
        let initial = (0, [])
        ReplayRecorder.create (snapshotEnvelope 0UL initial) (digest initial)
        |> Result.defaultWith (fun issues -> invalidOp $"replay initialization: {issues}")
    let mutable private replaySequence = 0UL

    let private append command snapshot =
        replaySequence <- replaySequence + 1UL
        let input : SessionInput<ReplayCommand> =
            { SessionId = sessionId
              InputId = "fsgg.generated.network"
              Sequence = replaySequence
              Value = command }
        replay <-
            ReplayRecorder.appendInput input (digest snapshot) replay
            |> Result.defaultWith (fun issues -> invalidOp $"replay append: {issues}")

    let reset snapshot =
        admission <- NetworkAdmission.create sessionId [] |> Result.defaultWith (fun issues -> invalidOp $"network admission: {issues}")
        deliveries <- Map.empty
        replaySequence <- 0UL
        replay <-
            ReplayRecorder.create (snapshotEnvelope 0UL snapshot) (digest snapshot)
            |> Result.defaultWith (fun issues -> invalidOp $"replay initialization: {issues}")

    let bind playerId token revision snapshot =
        let binding : NetworkClientBinding =
            { SessionId = sessionId; ClientId = playerId; ReconnectToken = token }
        admission <-
            NetworkAdmission.bind binding admission
            |> Result.defaultWith (fun issues -> invalidOp $"network bind: {issues}")
        let ticket : ReconnectTicket =
            { SessionId = sessionId; ClientId = playerId; Token = token }
        let config = { MaxQueuedDeltas = 4; ReconnectLifetimeMilliseconds = 120000UL }
        let delivery : DeliveryState<Snapshot, Snapshot> =
            Delivery.create config ticket revision
            |> Result.defaultWith (fun issues -> invalidOp $"delivery create: {issues}")
        deliveries <- Map.add playerId delivery deliveries
        append (Joined(playerId, snd snapshot |> List.find (fun (id, _, _) -> id = playerId) |> fun (_, col, row) -> { Col = col; Row = row })) snapshot

    let unbind playerId snapshot =
        admission <- NetworkAdmission.unbind playerId admission
        deliveries <-
            match Map.tryFind playerId deliveries with
            | Some delivery ->
                let _, _ = Delivery.dispose delivery
                Map.remove playerId deliveries
            | None -> deliveries
        append (Left playerId) snapshot

    let admit playerId token sequence targetCol targetRow =
        let binding : NetworkClientBinding =
            { SessionId = sessionId; ClientId = playerId; ReconnectToken = token }
        let candidate : NetworkInput<MoveIntent> =
            { Binding = binding
              Input =
                { SessionId = sessionId
                  InputId = "fsgg.generated.move"
                  Sequence = sequence
                  Value = { TargetCol = targetCol; TargetRow = targetRow } } }
        let validate intent =
            if intent.TargetCol < 0 || intent.TargetCol >= 20
               || intent.TargetRow < 0 || intent.TargetRow >= 12 then
                Error "move.out-of-bounds"
            else Ok()
        match NetworkAdmission.admit validate candidate admission with
        | Error issue -> Error $"{issue}"
        | Ok(next, accepted) ->
            admission <- next
            Ok accepted.AcceptedOrder

    let recordMove playerId target snapshot = append (Moved(playerId, target)) snapshot

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
            | Ok(next, _) -> deliveries <- Map.add playerId next deliveries; Ok()

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
            let ticket = { SessionId = sessionId; ClientId = playerId; Token = token }
            match Delivery.reconnect ticket now delivery with
            | Error issue -> Error $"{issue}"
            | Ok(next, DeliveryEffect.Reconnected pending) ->
                deliveries <- Map.add playerId next deliveries
                Ok pending
            | Ok(next, _) -> deliveries <- Map.add playerId next deliveries; Ok []

    let resync clientRevision currentRevision =
        NetworkAdmission.resync None clientRevision currentRevision

    let review () =
        let accepted = NetworkAdmission.canonicalText (fun move -> $"{move.TargetCol},{move.TargetRow}") admission
        let replayText =
            ReplayExport.canonicalText encodeCommand encodeSnapshot replay
            |> Result.defaultWith (fun issues -> invalidOp $"replay export: {issues}")
        accepted, replayText, replay.Events.Length
