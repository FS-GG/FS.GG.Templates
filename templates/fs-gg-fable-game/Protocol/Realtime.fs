namespace FableGameWorkspaceNamespace.Protocol.Realtime

#if FABLE_COMPILER
open Thoth.Json
#else
open Thoth.Json.Net
#endif

/// The SignalR wire boundary (unchanged by ADR-0073): connection/session-oriented
/// traffic -- input, snapshots, presence, and resync -- carried over the narrow
/// template-owned binding on `@microsoft/signalr` (see ../Client/SignalR.fs and
/// ../Server/GameHub.fs). Every message is one case of the `Message` envelope DU below,
/// mapped to/from an explicit tagged-record wire shape -- never assumed
/// serializer-compatible and never sent as the raw domain type.
[<RequireQualifiedAccess>]
module RealtimeV1 =

    /// One input intent, client -> server. `Sequence` is a monotonic per-connection
    /// counter; `Room/InputRouter.fs` (server) drops any input whose sequence does not
    /// strictly increase, which is the stale-input handling this DTO exists to carry.
    type InputCommand = { Version: int; Sequence: int; TargetCol: int; TargetRow: int }

    /// The capability issued by the HTTP bootstrap. This is deliberately a message,
    /// rather than query identity: the hub accepts no player or credential in its URL.
    type SessionHello = { Version: int; SessionCapability: string }

    type PlayerSnapshot = { PlayerId: string; Col: int; Row: int }

    /// The authoritative world snapshot, server -> client, sent after every committed
    /// tick and again in full on `ResyncSnapshotMessage` after a reconnect.
    type Snapshot = { Version: int; Tick: int; Players: PlayerSnapshot list }

    type Presence = { Version: int; PlayerId: string; Joined: bool }

    /// Sent by a reconnecting client so the server can validate its deterministic
    /// frontier. This template rejects negative/future cursors and answers every
    /// reached frontier with one full `ResyncSnapshotMessage` (a bounded resync,
    /// never an unbounded delta log) per #348's acceptance.
    type ResyncRequest = { Version: int; LastKnownTick: int }

    /// The hub message envelope. This is the deliberate "arbitrary DU" boundary case
    /// ADR-0073 requires round-trip proof for (see ../Protocol.Tests): a discriminated
    /// union mapped to a `{ kind; payload }` wire shape by the explicit code below, not
    /// by automatic union encoding.
    type Message =
        | InputMessage of InputCommand
        | SessionHelloMessage of SessionHello
        | SnapshotMessage of Snapshot
        | PresenceMessage of Presence
        | ResyncRequestMessage of ResyncRequest
        | ResyncSnapshotMessage of Snapshot

    let private encodeInput (v: InputCommand) =
        Encode.object [ "version", Encode.int v.Version; "sequence", Encode.int v.Sequence; "targetCol", Encode.int v.TargetCol; "targetRow", Encode.int v.TargetRow ]

    let private decodeInput: Decoder<InputCommand> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              Sequence = get.Required.Field "sequence" Decode.int
              TargetCol = get.Required.Field "targetCol" Decode.int
              TargetRow = get.Required.Field "targetRow" Decode.int })

    let private encodeSessionHello (v: SessionHello) =
        Encode.object [ "version", Encode.int v.Version; "sessionCapability", Encode.string v.SessionCapability ]

    let private decodeSessionHello: Decoder<SessionHello> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              SessionCapability = get.Required.Field "sessionCapability" Decode.string })

    let private encodePlayerSnapshot (v: PlayerSnapshot) =
        Encode.object [ "playerId", Encode.string v.PlayerId; "col", Encode.int v.Col; "row", Encode.int v.Row ]

    let private decodePlayerSnapshot: Decoder<PlayerSnapshot> =
        Decode.object (fun get ->
            { PlayerId = get.Required.Field "playerId" Decode.string
              Col = get.Required.Field "col" Decode.int
              Row = get.Required.Field "row" Decode.int })

    let private encodeSnapshot (v: Snapshot) =
        Encode.object
            [ "version", Encode.int v.Version
              "tick", Encode.int v.Tick
              "players", Encode.list (v.Players |> List.map encodePlayerSnapshot) ]

    let private decodeSnapshot: Decoder<Snapshot> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              Tick = get.Required.Field "tick" Decode.int
              Players = get.Required.Field "players" (Decode.list decodePlayerSnapshot) })

    let private encodePresence (v: Presence) =
        Encode.object [ "version", Encode.int v.Version; "playerId", Encode.string v.PlayerId; "joined", Encode.bool v.Joined ]

    let private decodePresence: Decoder<Presence> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              PlayerId = get.Required.Field "playerId" Decode.string
              Joined = get.Required.Field "joined" Decode.bool })

    let private encodeResyncRequest (v: ResyncRequest) =
        Encode.object [ "version", Encode.int v.Version; "lastKnownTick", Encode.int v.LastKnownTick ]

    let private decodeResyncRequest: Decoder<ResyncRequest> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              LastKnownTick = get.Required.Field "lastKnownTick" Decode.int })

    let encodeMessage (value: Message) : string =
        let kind, payload =
            match value with
            | InputMessage v -> "input", encodeInput v
            | SessionHelloMessage v -> "sessionHello", encodeSessionHello v
            | SnapshotMessage v -> "snapshot", encodeSnapshot v
            | PresenceMessage v -> "presence", encodePresence v
            | ResyncRequestMessage v -> "resyncRequest", encodeResyncRequest v
            | ResyncSnapshotMessage v -> "resyncSnapshot", encodeSnapshot v
        Encode.object [ "kind", Encode.string kind; "payload", payload ] |> Encode.toString 0

    /// Rejects an unrecognised `kind` and any payload whose fields don't match --
    /// exactly the "explicit rejected arbitrary-DU case" ADR-0073 requires evidence
    /// for (`Protocol.Tests` / `cross-runtime` exercises this from both runtimes).
    let decodeMessage: Decoder<Message> =
        Decode.field "kind" Decode.string
        |> Decode.andThen (fun kind ->
            match kind with
            | "input" -> Decode.field "payload" decodeInput |> Decode.map InputMessage
            | "sessionHello" -> Decode.field "payload" decodeSessionHello |> Decode.map SessionHelloMessage
            | "snapshot" -> Decode.field "payload" decodeSnapshot |> Decode.map SnapshotMessage
            | "presence" -> Decode.field "payload" decodePresence |> Decode.map PresenceMessage
            | "resyncRequest" -> Decode.field "payload" decodeResyncRequest |> Decode.map ResyncRequestMessage
            | "resyncSnapshot" -> Decode.field "payload" decodeSnapshot |> Decode.map ResyncSnapshotMessage
            | other -> Decode.fail (sprintf "unknown realtime message kind '%s'" other))

    let messageFromJson (json: string) : Result<Message, string> = Decode.fromString decodeMessage json
