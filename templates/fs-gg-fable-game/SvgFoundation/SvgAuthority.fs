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

let private notify status =
    let health, score, collected, outcome, hazardCol, hazardRow = game
    let round, contentId, contentSchema = identity
    publish status state.Players state.Tick round health score collected outcome contentId contentSchema content hazardCol hazardRow

let private sendHello capability (connection: SignalR.HubConnection) =
    let json = RealtimeV2.encodeMessage (RealtimeV2.SessionHelloMessage { Version = 2; SessionCapability = capability })
    thenBoth (connection.invoke("SendMessage", json)) ignore (fun error -> notify ("authority error: " + string error))

let private accept message =
    match message with
    | RealtimeV2.SnapshotMessage snapshot
    | RealtimeV2.ResyncSnapshotMessage snapshot when snapshot.Version = 2 && snapshot.ContentSchema = 2 && snapshot.ContentId.StartsWith("continuous-arena/") && snapshot.Tick >= state.Tick ->
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
              CollectibleX = snapshot.CollectibleX; CollectibleY = snapshot.CollectibleY
              Hazard = { X = snapshot.HazardX; Y = snapshot.HazardY; Width = snapshot.HazardWidth; Height = snapshot.HazardHeight }
              Goal = { X = snapshot.GoalX; Y = snapshot.GoalY; Width = snapshot.GoalWidth; Height = snapshot.GoalHeight }
              ThinWall = { X = snapshot.ThinWallX; Y = snapshot.ThinWallY; Width = snapshot.ThinWallWidth; Height = snapshot.ThinWallHeight } }
        notify "synchronized"
    | RealtimeV2.PresenceMessage _ -> notify "presence changed"
    | _ -> ()

let private connect capability =
    let connection = SignalR.build "/hub/game"
    connection.on("Message", fun json -> RealtimeV2.messageFromJson json |> Result.iter accept)
    connection.onreconnecting(fun _ -> notify "reconnecting")
    connection.onreconnected(fun _ -> sendHello capability connection)
    connection.onclose(fun _ -> state <- { state with Connection = None }; notify "closed")
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

let move deltaCol deltaRow =
    match state.PlayerId, state.Connection, state.Players |> List.tryFind _.IsSelf with
    | Some _, Some connection, Some self ->
        let json =
            RealtimeV2.encodeMessage (
                RealtimeV2.InputMessage
                    { Version = 2
                      Sequence = state.Sequence
                      Action = "move"
                      TargetCol = self.Col + deltaCol
                      TargetRow = self.Row + deltaRow })
        state <- { state with Sequence = state.Sequence + 1 }
        thenBoth (connection.invoke("SendMessage", json)) ignore (fun error -> notify ("authority error: " + string error))
    | _ -> notify "authority unavailable"

let command action =
    match state.Connection, state.Players |> List.tryFind _.IsSelf with
    | Some connection, Some self ->
        let json =
            RealtimeV2.encodeMessage (
                RealtimeV2.InputMessage
                    { Version = 2; Sequence = state.Sequence; Action = action; TargetCol = self.Col; TargetRow = self.Row })
        state <- { state with Sequence = state.Sequence + 1 }
        thenBoth (connection.invoke("SendMessage", json)) ignore (fun error -> notify ("authority error: " + string error))
    | _ -> notify "authority unavailable"

let dispose () =
    state.Connection |> Option.iter (fun connection -> thenBoth (connection.stop()) ignore ignore)
