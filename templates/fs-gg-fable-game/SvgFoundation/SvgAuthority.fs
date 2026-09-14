module FableGameWorkspaceNamespace.SvgAuthority

open Fable.Core
open FableGameWorkspaceNamespace.Client
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime
open FS.GG.Game.Core
module ArenaContent = FableGameWorkspaceNamespace.ArenaContent

[<Emit("$0.then($1, $2)")>]
let private thenBoth (promise: JS.Promise<'T>) (onOk: 'T -> unit) (onError: obj -> unit) : unit = jsNative

type Player = { Id: string; Col: int; Row: int; IsSelf: bool }

type private QueuedIntent =
    | RelativeMove of deltaCol: int * deltaRow: int
    | Action of string

type private InFlightIntent =
    { Sequence: int
      Intent: QueuedIntent
      AdmittedAfterTick: int option }

type private State =
    { PlayerId: string option
      Capability: string option
      Players: Player list
      Tick: int
      Sequence: int
      Connection: SignalR.HubConnection option }

let mutable private state =
    { PlayerId = None; Capability = None; Players = []; Tick = 0; Sequence = 1; Connection = None }

let mutable private publish: string -> Player list -> int -> int -> int -> int -> bool -> string -> string -> int -> ArenaContent.ArenaContent -> int -> int -> unit = fun _ _ _ _ _ _ _ _ _ _ _ _ _ -> ()
let mutable private game = 3, 0, false, "playing", 7, 8
let mutable private identity = 1, "continuous-arena/default-v2", 2
let mutable private content = ArenaContent.contentAt 0UL
let mutable private queuedIntents: QueuedIntent list = []
let mutable private inFlightIntent: InFlightIntent option = None
let mutable private dispatchNext: unit -> unit = ignore
let private maximumQueuedIntents = 32

let private notify status =
    let health, score, collected, outcome, hazardCol, hazardRow = game
    let round, contentId, contentSchema = identity
    publish status state.Players state.Tick round health score collected outcome contentId contentSchema content hazardCol hazardRow

let private sendHello capability (connection: SignalR.HubConnection) =
    let json = RealtimeV3.encodeMessage (RealtimeV3.SessionHelloMessage { Version = 3; SessionCapability = capability })
    thenBoth (connection.invoke("SendMessage", json)) ignore (fun error -> notify ("authority error: " + string error))

let private accept message =
    match message with
    | RealtimeV3.SnapshotMessage snapshot
    | RealtimeV3.ResyncSnapshotMessage snapshot when snapshot.Version = 3 && (snapshot.ContentSchema = 2 || snapshot.ContentSchema = 3) && snapshot.ContentId.StartsWith("continuous-arena/") && snapshot.Tick >= state.Tick ->
        let self = state.PlayerId
        state <-
            { state with
                Tick = snapshot.Tick
                Players = snapshot.Players |> List.map (fun player ->
                    { Id = player.PlayerId; Col = player.Col; Row = player.Row; IsSelf = self = Some player.PlayerId }) }
        game <- snapshot.Health, snapshot.Score, snapshot.Collected, snapshot.Outcome, snapshot.HazardCol, snapshot.HazardRow
        identity <- snapshot.Round, snapshot.ContentId, snapshot.ContentSchema
        content <-
            { SchemaVersion = snapshot.ContentSchema; ContentId = snapshot.ContentId
              Boundary = { X = snapshot.BoundaryX; Y = snapshot.BoundaryY; Width = snapshot.BoundaryWidth; Height = snapshot.BoundaryHeight }
              Spawn = { Col = snapshot.SpawnCol; Row = snapshot.SpawnRow }
              CollectibleX = snapshot.CollectibleX; CollectibleY = snapshot.CollectibleY
              Hazard = { X = snapshot.HazardX; Y = snapshot.HazardY; Width = snapshot.HazardWidth; Height = snapshot.HazardHeight }
              Goal = { X = snapshot.GoalX; Y = snapshot.GoalY; Width = snapshot.GoalWidth; Height = snapshot.GoalHeight }
              ThinWall = { X = snapshot.ThinWallX; Y = snapshot.ThinWallY; Width = snapshot.ThinWallWidth; Height = snapshot.ThinWallHeight } }
        // Invocation success proves admission into a particular authority frontier.
        // Wait for a later frontier before deriving the next relative target. This
        // serializes edge-triggered input without guessing through collisions.
        match inFlightIntent with
        | Some pending when pending.AdmittedAfterTick |> Option.exists (fun tick -> snapshot.Tick > tick) ->
            inFlightIntent <- None
            dispatchNext ()
        | _ -> ()
        notify "synchronized"
    | RealtimeV3.PresenceMessage _ -> notify "presence changed"
    | _ -> ()

let private connect capability =
    let connection = SignalR.build "/hub/game"
    connection.on("Message", fun json -> RealtimeV3.messageFromJson json |> Result.iter accept)
    connection.onreconnecting(fun _ -> notify "reconnecting")
    connection.onreconnected(fun _ ->
        queuedIntents <- []
        inFlightIntent <- None
        sendHello capability connection)
    connection.onclose(fun _ ->
        queuedIntents <- []
        inFlightIntent <- None
        state <- { state with Connection = None }
        notify "closed")
    state <- { state with Connection = Some connection }
    thenBoth (connection.start()) (fun () -> sendHello capability connection) (fun error -> notify ("authority error: " + string error))

let start onSnapshot =
    publish <- onSnapshot
    let request: BootstrapV1.Request = { Version = 1; PlayerName = "SVG player" }
    Async.StartImmediate(async {
        try
            let! response = Api.bootstrap request
            state <- { state with PlayerId = Some response.PlayerId; Capability = Some response.SessionCapability }
            notify "connecting"
            connect response.SessionCapability
        with error -> notify ("bootstrap failed: " + error.Message) })

let private pump () =
    match inFlightIntent, queuedIntents, state.PlayerId, state.Connection, state.Players |> List.tryFind _.IsSelf with
    | None, intent :: remaining, Some _, Some connection, Some self ->
        queuedIntents <- remaining
        let sequence = state.Sequence
        let action, targetCol, targetRow =
            match intent with
            | RelativeMove(deltaCol, deltaRow) -> "move", self.Col + deltaCol, self.Row + deltaRow
            | Action action -> action, self.Col, self.Row
        let json =
            RealtimeV3.encodeMessage (
                RealtimeV3.InputMessage
                    { Version = 3
                      Sequence = sequence
                      Action = action
                      TargetCol = targetCol
                      TargetRow = targetRow })
        state <- { state with Sequence = sequence + 1 }
        inFlightIntent <- Some { Sequence = sequence; Intent = intent; AdmittedAfterTick = None }
        thenBoth (connection.invoke("SendMessage", json))
            (fun _ ->
                match inFlightIntent with
                | Some pending when pending.Sequence = sequence ->
                    inFlightIntent <- Some { pending with AdmittedAfterTick = Some state.Tick }
                | _ -> ())
            (fun error ->
                match inFlightIntent with
                | Some pending when pending.Sequence = sequence ->
                    inFlightIntent <- None
                    notify ("authority error: " + string error)
                    dispatchNext ()
                | _ -> ())
    | _ -> ()

dispatchNext <- pump

let private enqueue intent =
    match state.PlayerId, state.Connection, state.Players |> List.tryFind _.IsSelf with
    | Some _, Some _, Some _ when queuedIntents.Length < maximumQueuedIntents ->
        queuedIntents <- queuedIntents @ [ intent ]
        dispatchNext ()
    | Some _, Some _, Some _ -> notify "input queue full"
    | _ -> notify "authority unavailable"

let move deltaCol deltaRow = enqueue (RelativeMove(deltaCol, deltaRow))

let command action =
    enqueue (Action action)

/// Redacted disclosure assertion used by product adapters when they emit derived
/// presentation, audio, or persistence bytes. The capability itself stays private.
let excludesCapability (value: string) =
    state.Capability
    |> Option.forall (fun capability -> not (value.Contains(capability, System.StringComparison.Ordinal)))

let dispose () =
    queuedIntents <- []
    inFlightIntent <- None
    state.Connection |> Option.iter (fun connection -> thenBoth (connection.stop()) ignore ignore)
