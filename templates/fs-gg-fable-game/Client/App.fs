namespace FableGameWorkspaceNamespace.Client

open Fable.Core
open Elmish
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime

/// The Elmish + direct-DOM client (the spike report's "smallest viable view layer":
/// Elmish plus direct DOM bindings, no UI framework contract). `SignalR` and `Api`
/// carry the two wire adapters ADR-0073 keeps separate; this module owns only the
/// game-facing decisions: bootstrap once, then treat every `SnapshotMessage` /
/// `ResyncSnapshotMessage` from the server as the *entire* truth about player
/// positions -- `Movement.previewPath` never writes into `Model.Players` directly,
/// which is what "client prediction is limited to qualified shared logic" means here.
module App =

    [<Emit("$0.then($1, $2)")>]
    let private thenBoth (promise: JS.Promise<'T>) (onOk: 'T -> unit) (onError: obj -> unit) : unit = jsNative

    type Model =
        { PlayerId: string option
          SessionCapability: string option
          RoomId: string
          ArenaWidth: int
          ArenaHeight: int
          Players: Map<string, Cell>
          Tick: int
          NextSequence: int
          PreviewPath: Cell list
          Status: string }

    type Msg =
        | Bootstrapped of BootstrapV1.Response
        | BootstrapFailed of exn
        | Connected
        | Reconnecting
        | Reconnected
        | ConnectionClosed
        | ConnectionFailed of string
        | ReceivedRealtime of RealtimeV1.Message
        | CellClicked of Cell

    /// The one live `SignalR.HubConnection`, outside `Model` because it is not data:
    /// Elmish models are compared/replaced by value, and a connection is an external
    /// resource with its own lifecycle. This is the same reason `RoomAuthority` on the
    /// server side is its own module rather than something threaded through every
    /// function signature -- documented here, not hidden.
    let mutable private connection: SignalR.HubConnection option = None

    let private sendHello (capability: string) (dispatch: Msg -> unit) (conn: SignalR.HubConnection) : unit =
        let hello = RealtimeV1.encodeMessage (RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = capability })
        thenBoth (conn.invoke ("SendMessage", hello)) ignore (fun err -> dispatch (ConnectionFailed(string err)))

    let private connectSub (capability: string) (dispatch: Msg -> unit) : unit =
        // The URL contains neither player identity nor capability. The latter is sent
        // only after the transport opens, in a versioned protocol message.
        let conn = SignalR.build "/hub/game"
        conn.on (
            "Message",
            fun json ->
                match RealtimeV1.messageFromJson json with
                | Ok message -> dispatch (ReceivedRealtime message)
                | Error err -> dispatch (ConnectionFailed err)
        )
        conn.onreconnecting(fun _ -> dispatch Reconnecting)
        conn.onreconnected(fun _ -> dispatch Reconnected)
        conn.onclose(fun _ -> connection <- None; dispatch ConnectionClosed)
        connection <- Some conn
        thenBoth (conn.start ()) (fun () -> dispatch Connected) (fun err -> dispatch (ConnectionFailed(string err)))

    let init () : Model * Cmd<Msg> =
        let model =
            { PlayerId = None
              SessionCapability = None
              RoomId = ""
              ArenaWidth = 0
              ArenaHeight = 0
              Players = Map.empty
              Tick = 0
              NextSequence = 1
              PreviewPath = []
              Status = "bootstrapping" }
        let request: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }
        model, Cmd.OfAsync.either Api.bootstrap request Bootstrapped BootstrapFailed

    let update (msg: Msg) (model: Model) : Model * Cmd<Msg> =
        match msg with
        | Bootstrapped response ->
            let self: Cell = { Col = response.SpawnCol; Row = response.SpawnRow }
            { model with
                PlayerId = Some response.PlayerId
                SessionCapability = Some response.SessionCapability
                RoomId = response.RoomId
                ArenaWidth = response.ArenaWidth
                ArenaHeight = response.ArenaHeight
                Players = Map.ofList [ response.PlayerId, self ]
                Status = "connecting" },
            Cmd.ofEffect (connectSub response.SessionCapability)
        | BootstrapFailed exn -> { model with Status = $"bootstrap failed: {exn.Message}" }, Cmd.none
        | Connected ->
            match model.SessionCapability, connection with
            | Some capability, Some conn ->
                { model with Status = "connected; authorizing session" }, Cmd.ofEffect (fun dispatch -> sendHello capability dispatch conn)
            | _ -> { model with Status = "connection closed before session authorization" }, Cmd.none
        | Reconnecting -> { model with Status = "reconnecting" }, Cmd.none
        | Reconnected ->
            match model.SessionCapability, connection with
            | Some capability, Some conn ->
                { model with Status = "reconnected; requesting bounded resync" }, Cmd.ofEffect (fun dispatch -> sendHello capability dispatch conn)
            | _ -> { model with Status = "reconnect closed before session authorization" }, Cmd.none
        | ConnectionClosed -> { model with Status = "closed" }, Cmd.none
        | ConnectionFailed message -> { model with Status = $"connection failed: {message}" }, Cmd.none
        | ReceivedRealtime message ->
            match message with
            | RealtimeV1.SnapshotMessage snapshot
            | RealtimeV1.ResyncSnapshotMessage snapshot ->
                let players = snapshot.Players |> List.map (fun p -> p.PlayerId, ({ Col = p.Col; Row = p.Row }: Cell)) |> Map.ofList
                if snapshot.Version <> 1 then
                    { model with Status = $"unsupported realtime version {snapshot.Version}" }, Cmd.none
                elif snapshot.Tick < model.Tick then
                    // A delayed hub callback cannot rewind the view after a newer tick.
                    model, Cmd.none
                else
                    { model with Players = players; Tick = snapshot.Tick; PreviewPath = []; Status = "synchronized" }, Cmd.none
            | RealtimeV1.PresenceMessage presence ->
                let verb = if presence.Joined then "joined" else "left"
                { model with Status = $"{presence.PlayerId} {verb}" }, Cmd.none
            | RealtimeV1.InputMessage _
            | RealtimeV1.SessionHelloMessage _
            | RealtimeV1.ResyncRequestMessage _ ->
                // The server never sends these two kinds; GameHub.SendMessage rejects a
                // client that does. Receiving one here would mean this client is talking
                // to something other than this template's own server.
                model, Cmd.none
        | CellClicked target ->
            match model.PlayerId with
            | None -> model, Cmd.none
            | Some playerId ->
                match model.Players |> Map.tryFind playerId with
                | None -> model, Cmd.none
                | Some selfCell ->
                    let occupied =
                        model.Players
                        |> Map.toSeq
                        |> Seq.filter (fun (id, _) -> id <> playerId)
                        |> Seq.map snd
                        |> Set.ofSeq
                    let preview =
                        Movement.previewPath model.ArenaWidth model.ArenaHeight occupied selfCell target
                        |> Option.defaultValue []
                    match connection with
                    | Some conn ->
                        let json =
                            RealtimeV1.encodeMessage (
                                RealtimeV1.InputMessage { Version = 1; Sequence = model.NextSequence; TargetCol = target.Col; TargetRow = target.Row }
                            )
                        thenBoth (conn.invoke ("SendMessage", json)) ignore ignore
                        { model with PreviewPath = preview; NextSequence = model.NextSequence + 1 }, Cmd.none
                    | None -> { model with PreviewPath = preview }, Cmd.none

    /// The grid's DOM nodes, built exactly once (the arena's dimensions never change
    /// after bootstrap) and thereafter only *updated* in place (class list and
    /// `data-occupant`), never torn down and recreated. An earlier version rebuilt the
    /// whole grid via `innerHTML <- ""` on every message, including the frequent
    /// periodic tick snapshots -- which could detach the very cell element a real
    /// click was in flight against, silently dropping the input. Reusing nodes removes
    /// that race entirely rather than papering over it with a delay.
    let mutable private cellElements: Map<Cell, Browser.Types.HTMLElement> = Map.empty
    let mutable private gridBuildCount = 0

    let private focusCell (current: Browser.Types.HTMLElement) (target: Cell) : unit =
        match Map.tryFind target cellElements with
        | None -> ()
        | Some next ->
            current.tabIndex <- -1
            next.tabIndex <- 0
            next.focus ()

    let private handleCellKey (cell: Cell) (el: Browser.Types.HTMLElement) (dispatch: Msg -> unit) (event: Browser.Types.Event) : unit =
        let keyEvent: Browser.Types.KeyboardEvent = unbox event
        let target =
            match keyEvent.key with
            | "ArrowLeft" -> Some { cell with Col = cell.Col - 1 }
            | "ArrowRight" -> Some { cell with Col = cell.Col + 1 }
            | "ArrowUp" -> Some { cell with Row = cell.Row - 1 }
            | "ArrowDown" -> Some { cell with Row = cell.Row + 1 }
            | _ -> None
        match target with
        | Some next ->
            keyEvent.preventDefault ()
            focusCell el next
        | None when keyEvent.key = "Enter" || keyEvent.key = " " ->
            keyEvent.preventDefault ()
            dispatch (CellClicked cell)
        | None -> ()

    let private buildGrid (container: Browser.Types.HTMLElement) (model: Model) (dispatch: Msg -> unit) : unit =
        container.innerHTML <- ""
        gridBuildCount <- gridBuildCount + 1
        container.setAttribute ("data-grid-build-count", string gridBuildCount)
        container.setAttribute ("data-grid-cell-count", string (model.ArenaWidth * model.ArenaHeight))
        let grid = Browser.Dom.document.createElement "div"
        grid.setAttribute ("role", "grid")
        grid.setAttribute ("aria-label", "Game board")
        grid.setAttribute ("aria-rowcount", string model.ArenaHeight)
        grid.setAttribute ("aria-colcount", string model.ArenaWidth)
        grid.setAttribute ("style", $"display:grid;grid-template-columns:repeat({model.ArenaWidth},24px)")
        let mutable built = Map.empty
        for row in 0 .. model.ArenaHeight - 1 do
            for col in 0 .. model.ArenaWidth - 1 do
                let cell: Cell = { Col = col; Row = row }
                let el = Browser.Dom.document.createElement "div"
                el.setAttribute ("data-cell", $"{col}-{row}")
                el.setAttribute ("role", "gridcell")
                el.setAttribute ("aria-rowindex", string (row + 1))
                el.setAttribute ("aria-colindex", string (col + 1))
                el.tabIndex <- if row = 0 && col = 0 then 0 else -1
                el.addEventListener ("click", (fun _ -> dispatch (CellClicked cell)))
                el.addEventListener ("keydown", handleCellKey cell el dispatch)
                el.addEventListener ("focus", (fun _ ->
                    for KeyValue(_, other) in cellElements do
                        other.tabIndex <- if obj.ReferenceEquals(other, el) then 0 else -1))
                grid.appendChild el |> ignore
                built <- built |> Map.add cell el
        container.appendChild grid |> ignore
        cellElements <- built

    let view (model: Model) (dispatch: Msg -> unit) : unit =
        match Browser.Dom.document.getElementById "arena" with
        | null -> ()
        | container ->
            if model.ArenaWidth > 0 && model.ArenaHeight > 0 then
                if Map.isEmpty cellElements then
                    buildGrid container model dispatch
                container.setAttribute ("aria-busy", "false")
                for KeyValue(cell, el) in cellElements do
                    let occupant = model.Players |> Map.toSeq |> Seq.tryFind (fun (_, c) -> c = cell) |> Option.map fst
                    let classes =
                        [ "cell"
                          if occupant = model.PlayerId && Option.isSome occupant then "self"
                          elif Option.isSome occupant then "other"
                          if List.contains cell model.PreviewPath then "preview" ]
                    el.className <- String.concat " " classes
                    match occupant with
                    | Some playerId ->
                        el.setAttribute ("data-occupant", playerId)
                        let identity = if Some playerId = model.PlayerId then "you" else "another player"
                        let selection = if List.contains cell model.PreviewPath then ", selected path" else ""
                        el.setAttribute ("aria-label", $"Column {cell.Col + 1}, row {cell.Row + 1}: {identity}{selection}")
                    | None ->
                        el.removeAttribute "data-occupant"
                        let selection = if List.contains cell model.PreviewPath then ", selected path" else ""
                        el.setAttribute ("aria-label", $"Column {cell.Col + 1}, row {cell.Row + 1}: empty{selection}")
                    el.setAttribute ("aria-selected", (string (List.contains cell model.PreviewPath)).ToLowerInvariant())
                    if occupant = model.PlayerId && Option.isSome occupant then el.setAttribute ("aria-current", "true")
                    else el.removeAttribute "aria-current"
            match Browser.Dom.document.getElementById "status" with
            | null -> ()
            | status -> status.textContent <- $"room {model.RoomId} - {model.Status}"
            match Browser.Dom.document.getElementById "tick" with
            | null -> ()
            | tick -> tick.textContent <- $"Tick {model.Tick}"
            match Browser.Dom.document.getElementById "presence" with
            | null -> ()
            | presence ->
                let others = max 0 (model.Players.Count - (if Option.isSome model.PlayerId then 1 else 0))
                presence.textContent <- $"Players present: {model.Players.Count}. You plus {others} other player(s)."
            // A minimal, explicit test hook: the assigned player id, otherwise invisible
            // in the DOM. Browser.Tests reads this to know which rendered cell is "this"
            // browser context's own player without depending on class-name heuristics.
            match Browser.Dom.document.getElementById "player-id" with
            | null -> ()
            | el -> el.textContent <- (model.PlayerId |> Option.defaultValue "")
