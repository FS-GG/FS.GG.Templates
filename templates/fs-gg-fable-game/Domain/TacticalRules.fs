module FableGameWorkspaceNamespace.TacticalRules

open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain

type Content =
    {
        Id: string
        ContentIdentity: string
        Columns: int
        Rows: int
        FirstId: string
        First: Cell
        SecondId: string
        Second: Cell
        Target: Cell
    }

type State =
    {
        Definition: Content
        Room: Room.State
        Route: Cell list
        Planning: PlanningSession<string, Room.State, Cell> option
        Recording: ReplayRecording<Cell, Room.State>
        Sequence: uint64
        LastOperation: string
    }

let digest (definition: Content) (state: Room.State) =
    let players =
        state.Players
        |> Map.toList
        |> List.map (fun (id, player) -> $"{id}:{player.PlayerId}:{player.Cell.Col}:{player.Cell.Row}")
        |> String.concat ";"

    $"tactical/v1|{definition.ContentIdentity}|definition:{definition.Columns}x{definition.Rows}|first:{definition.FirstId}:{definition.First.Col},{definition.First.Row}|second:{definition.SecondId}:{definition.Second.Col},{definition.Second.Row}|target:{definition.Target.Col},{definition.Target.Row}|room:{state.Width}x{state.Height}|tick:{state.Tick}|{players}"

let private validCell width height (cell: Cell) =
    cell.Col >= 0 && cell.Col < width && cell.Row >= 0 && cell.Row < height

let private validateRoom (definition: Content) (room: Room.State) =
    let players = room.Players |> Map.toList

    if definition.Columns <= 0 || definition.Rows <= 0 then
        Some "authored grid dimensions must be positive"
    elif room.Width <> definition.Columns || room.Height <> definition.Rows then
        Some "room dimensions do not match authored content"
    elif room.Tick < 0 then
        Some "room tick must not be negative"
    elif
        not (validCell definition.Columns definition.Rows definition.First)
        || not (validCell definition.Columns definition.Rows definition.Second)
        || not (validCell definition.Columns definition.Rows definition.Target)
    then
        Some "authored cells must remain in bounds"
    elif definition.FirstId = definition.SecondId || definition.First = definition.Second then
        Some "authored units must be distinct"
    elif
        players |> List.map fst |> Set.ofList
        <> Set.ofList [ definition.FirstId; definition.SecondId ]
    then
        Some "room unit set does not match authored content"
    elif
        players
        |> List.exists (fun (id, player) -> id <> player.PlayerId || not (validCell room.Width room.Height player.Cell))
    then
        Some "room unit identity or position is invalid"
    elif
        players
        |> List.map (fun (_, player) -> player.Cell)
        |> List.distinct
        |> List.length
        <> players.Length
    then
        Some "room units must occupy distinct cells"
    else
        None

let private compatibility definition =
    {
        ContractVersion = 1
        EngineId = "fsgg.generated.tactical"
        EngineVersion = "1"
        ProfileId = definition.ContentIdentity
        SchemaId = "tactical-room"
        SchemaVersion = 1
    }

let contract definition : SessionContract<Room.State, Room.State, Cell, Room.State, Room.State> =
    let expected = compatibility definition

    {
        Initialize =
            fun initialization ->
                match validateRoom definition initialization.Configuration with
                | None -> Ok initialization.Configuration
                | Some message ->
                    Error
                        {
                            Code = "tactical.initialization.content"
                            Message = message
                        }
        AdmitInput = fun input state -> Ok(Room.applyStep definition.FirstId input.Value state)
        Advance = fun _ state -> Ok state
        Project =
            fun state ->
                {
                    SessionId = definition.Id
                    Revision = uint64 state.Tick
                    Value = state
                }
        Snapshot =
            fun state ->
                {
                    SessionId = definition.Id
                    Revision = uint64 state.Tick
                    Compatibility = expected
                    Value = state
                }
        Restore =
            fun snapshot ->
                if snapshot.SessionId <> definition.Id then
                    Error
                        {
                            Code = "tactical.snapshot.session"
                            Message = "tactical snapshot session mismatch"
                        }
                elif snapshot.Compatibility <> expected then
                    Error
                        {
                            Code = "tactical.snapshot.compatibility"
                            Message = "tactical snapshot compatibility mismatch"
                        }
                else
                    match validateRoom definition snapshot.Value with
                    | None -> Ok snapshot.Value
                    | Some message ->
                        Error
                            {
                                Code = "tactical.snapshot.content"
                                Message = message
                            }
    }

let private accepted (definition: Content) (room: Room.State) : AcceptedState<Room.State> =
    {
        SessionId = definition.Id
        Revision = uint64 room.Tick
        StateDigest = digest definition room
        Value = room
    }

let create definition =
    let room =
        Room.create definition.Columns definition.Rows
        |> Room.join definition.FirstId definition.First
        |> Room.join definition.SecondId definition.Second

    match validateRoom definition room with
    | Some issue -> invalidArg (nameof definition) issue
    | None -> ()

    let runtime = contract definition

    let recording =
        ReplayRecorder.create (runtime.Snapshot room) (digest definition room)
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)

    {
        Definition = definition
        Room = room
        Route = []
        Planning = None
        Recording = recording
        Sequence = 0UL
        LastOperation = "ready"
    }

let plan state =
    match Room.planMove state.Definition.FirstId state.Definition.Target state.Room with
    | None -> Error "route-blocked"
    | Some route ->
        let authored =
            {
                ContentId = state.Definition.ContentIdentity
                Revision = 0UL
                Value = state.Definition.ContentIdentity
            }

        let adapter: ScenarioAdapter<Room.State, Cell> =
            {
                Apply = fun cell room -> Ok(Room.applyStep state.Definition.FirstId cell room)
                StateDigest = digest state.Definition
            }

        let planned: Result<PlanningSession<string, Room.State, Cell>, string> =
            Planning.create authored (accepted state.Definition state.Room)
            |> Result.mapError (sprintf "%A")
            |> Result.bind (fun session ->
                Planning.beginScenario "selected-route" session
                |> Result.mapError (sprintf "%A"))
            |> Result.bind (fun session ->
                (Ok session, route |> List.skip (min 1 route.Length))
                ||> List.fold (fun current cell ->
                    current
                    |> Result.bind (fun value ->
                        Planning.apply adapter "selected-route" cell value
                        |> Result.mapError (sprintf "%A"))))

        planned
        |> Result.map (fun planning ->
            { state with
                Route = route
                Planning = Some planning
                LastOperation = "planned"
            })

let compare state =
    match state.Planning with
    | None -> Error "scenario-missing"
    | Some planning ->
        Planning.compare "selected-route" planning
        |> Result.mapError (sprintf "%A")
        |> Result.map (fun comparison ->
            comparison,
            { state with
                LastOperation = "compared"
            })

let cancel state =
    match state.Planning with
    | None -> Error "scenario-missing"
    | Some planning ->
        Planning.cancel "selected-route" planning
        |> Result.mapError (sprintf "%A")
        |> Result.map (fun cancelled ->
            { state with
                Route = []
                Planning = Some cancelled
                LastOperation = "cancelled"
            })

let private record cell room sequence recording definition =
    let nextSequence = sequence + 1UL

    let input =
        {
            SessionId = definition.Id
            InputId = "tactical.accepted"
            Sequence = nextSequence
            Value = cell
        }

    let nextRecording =
        ReplayRecorder.appendInput input (digest definition room) recording
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)

    nextSequence, nextRecording

let commit state =
    match state.Planning with
    | None -> Error "scenario-missing"
    | Some planning ->
        Planning.proposeCommit "selected-route" planning
        |> Result.mapError (sprintf "%A")
        |> Result.map (fun proposed ->
            let room, sequence, recording =
                ((state.Room, state.Sequence, state.Recording), proposed.Intents)
                ||> List.fold (fun (room, sequence, recording) cell ->
                    let nextRoom = Room.applyStep state.Definition.FirstId cell room

                    let nextSequence, nextRecording =
                        record cell nextRoom sequence recording state.Definition

                    nextRoom, nextSequence, nextRecording)

            { state with
                Room = room
                Route = []
                Planning = None
                Sequence = sequence
                Recording = recording
                LastOperation = "committed"
            })

let simulate state =
    match state.Route with
    | _ :: next :: remaining ->
        let room = Room.applyStep state.Definition.FirstId next state.Room

        let sequence, recording =
            record next room state.Sequence state.Recording state.Definition

        Ok
            { state with
                Room = room
                Route = next :: remaining
                Planning = None
                Sequence = sequence
                Recording = recording
                LastOperation = "simulated"
            }
    | _ -> Error "route-missing"

let review state =
    if state.Recording.Events.IsEmpty then
        Error "recording-empty"
    else
        Replay.seek
            (contract state.Definition)
            (digest state.Definition)
            (fun _ -> false)
            (uint64 state.Recording.Events.Length)
            state.Recording
        |> Result.mapError (sprintf "%A")
        |> Result.bind (function
            | ReplayRunOutcome.Completed(_, room) when digest state.Definition room = digest state.Definition state.Room ->
                Ok
                    { state with
                        LastOperation = "reviewed"
                    }
            | outcome -> Error(sprintf "%A" outcome))

let projection state =
    let acceptedCol = state.Room.Players.[state.Definition.FirstId].Cell.Col

    let predictedCol =
        state.Planning
        |> Option.bind (fun planning -> planning.Scenarios |> List.tryHead)
        |> Option.bind (fun scenario ->
            match scenario.Status with
            | PlanningScenarioStatus.Draft ->
                Some scenario.Prediction.Value.Players.[state.Definition.FirstId].Cell.Col
            | _ -> None)
        |> Option.orElseWith (fun () -> state.Route |> List.tryLast |> Option.map (fun cell -> cell.Col))
        |> Option.defaultValue acceptedCol

    state.LastOperation, acceptedCol, predictedCol, not state.Recording.Events.IsEmpty

let canonicalProjection state =
    let operation, acceptedCol, predictedCol, recorded = projection state
    let recordedText = if recorded then "true" else "false"
    $"phase:{operation}|acceptedCol:{acceptedCol}|predictedCol:{predictedCol}|committedCol:{acceptedCol}|recorded:{recordedText}"
