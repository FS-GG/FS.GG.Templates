module FableGameWorkspaceNamespace.ArenaRules

open System
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace.ArenaContent

[<RequireQualifiedAccess>]
type Intent =
    | Move of ArenaCell
    | LegacyMove of ArenaCell
    | Interact
    | Restart

type State =
    {
        Definition: ArenaContent
        Room: Room.State
        Round: int
        Status: ArenaStatus
        HazardContacts: Set<string>
        LegacyPlayers: Set<string>
    }

[<RequireQualifiedAccess>]
type Command =
    | Join of playerId: string * cell: Cell
    | Leave of playerId: string
    | Apply of playerId: string * intent: Intent

let createWith definition =
    {
        Definition = definition
        Room = Room.create arenaColumns arenaRows
        Round = 1
        Status = initialStatus
        HazardContacts = Set.empty
        LegacyPlayers = Set.empty
    }

let create () = createWith (contentAt 0UL)
let withDefinition definition state = { state with Definition = definition }

let currentContent state =
    atTick (uint64 state.Room.Tick) state.Definition

let join playerId spawn state =
    { state with
        Room = Room.join playerId spawn state.Room
    }

let leave playerId state =
    { state with
        Room = Room.leave playerId state.Room
        HazardContacts = state.HazardContacts.Remove playerId
        LegacyPlayers = state.LegacyPlayers.Remove playerId
    }

let private applyContacts contacts state =
    if state.Status.Outcome <> "playing" then
        { state with HazardContacts = contacts }
    else
        let entered = Set.difference contacts state.HazardContacts
        let health = max 0 (state.Status.Health - entered.Count)

        { state with
            Status =
                { state.Status with
                    Health = health
                    Outcome = if health = 0 then "lost" else state.Status.Outcome
                }
            HazardContacts = contacts
        }

let applyIntent playerId intent state =
    let content = currentContent state

    match intent with
    | Intent.Restart ->
        let players =
            state.Room.Players
            |> Map.toList
            |> List.sortBy fst
            |> List.mapi (fun index (id, player) ->
                let spawnOffset =
                    state.Definition.Spawn.Row * arenaColumns + state.Definition.Spawn.Col

                let bounded = (spawnOffset + index) % (arenaColumns * arenaRows)

                let cell: Cell =
                    {
                        Col = bounded % arenaColumns
                        Row = bounded / arenaColumns
                    }

                id, { player with Cell = cell })
            |> Map.ofList

        { state with
            Room = { state.Room with Players = players }
            Round = state.Round + 1
            Status = initialStatus
            HazardContacts = Set.empty
        }
    | Intent.Interact ->
        match state.Room.Players |> Map.tryFind playerId with
        | Some player ->
            { state with
                Status =
                    interact
                        content
                        {
                            Col = player.Cell.Col
                            Row = player.Cell.Row
                        }
                        state.Status
            }
        | None -> state
    | Intent.LegacyMove target ->
        match Room.planMove playerId { Col = target.Col; Row = target.Row } state.Room with
        | Some(_ :: next :: _) ->
            { state with
                Room = Room.applyStep playerId next state.Room
                LegacyPlayers = state.LegacyPlayers.Add playerId
            }
        | _ ->
            { state with
                LegacyPlayers = state.LegacyPlayers.Add playerId
            }
    | Intent.Move target ->
        match
            state.Room.Players |> Map.tryFind playerId,
            Room.planMove playerId { Col = target.Col; Row = target.Row } state.Room
        with
        | Some player, Some(_ :: next :: _) ->
            let accepted, _, hits =
                resolveMove
                    content
                    {
                        Col = player.Cell.Col
                        Row = player.Cell.Row
                    }
                    { Col = next.Col; Row = next.Row }
                    state.Status

            let room =
                if accepted.Col = player.Cell.Col && accepted.Row = player.Cell.Row then
                    state.Room
                else
                    Room.applyStep
                        playerId
                        {
                            Col = accepted.Col
                            Row = accepted.Row
                        }
                        state.Room

            let contacts =
                if Set.contains "hazard" hits then
                    state.HazardContacts.Add playerId
                else
                    state.HazardContacts.Remove playerId

            applyContacts contacts { state with Room = room }
        | _ -> state

/// Time advances independently of input. Moving content can therefore contact a
/// stationary player; damage is charged once on contact entry, not once per tick.
let advance state =
    let room = Room.advanceTick state.Room
    let content = atTick (uint64 room.Tick) state.Definition

    let contacts =
        room.Players
        |> Map.toSeq
        |> Seq.choose (fun (id, player) ->
            if
                not (state.LegacyPlayers.Contains id)
                && hazardContact
                    content
                    {
                        Col = player.Cell.Col
                        Row = player.Cell.Row
                    }
            then
                Some id
            else
                None)
        |> Set.ofSeq

    applyContacts contacts { state with Room = room }

let snapshot state =
    state.Room.Tick, Room.toSnapshotPairs state.Room, state.Status, state.HazardContacts

let compatibility =
    {
        ContractVersion = 1
        EngineId = "fsgg.generated.arena"
        EngineVersion = "2"
        ProfileId = "authoritative-room"
        SchemaId = "fsgg.generated.arena.snapshot"
        SchemaVersion = 2
    }

let compatibilityFor (definition: ArenaContent) =
    if definition.SchemaVersion = 2 then
        compatibility
    else
        { compatibility with
            EngineVersion = string definition.SchemaVersion
            SchemaVersion = definition.SchemaVersion
        }

let canonicalState state =
    let content = state.Definition
    let boolean value = if value then "true" else "false"
    // Encode the exact IEEE-754 payload in network byte order. Decimal formatting
    // differs by locale and runtime, while quantization can merge two bounds that
    // produce different collision or interaction outcomes.
    let number = canonicalFloat

    let players =
        Room.toSnapshotPairs state.Room
        |> List.map (fun (id, col, row) -> $"{id}:{col}:{row}")
        |> String.concat ";"

    let contacts = state.HazardContacts |> Set.toList |> String.concat ","
    let legacy = state.LegacyPlayers |> Set.toList |> String.concat ","

    let gameplay =
        $"{number content.CollectibleX},{number content.CollectibleY}|{number content.Hazard.X},{number content.Hazard.Y},{number content.Hazard.Width},{number content.Hazard.Height}|{number content.Goal.X},{number content.Goal.Y},{number content.Goal.Width},{number content.Goal.Height}|{number content.ThinWall.X},{number content.ThinWall.Y},{number content.ThinWall.Width},{number content.ThinWall.Height}|{state.Room.Tick}|{state.Round}|{players}|{state.Status.Health}|{state.Status.Score}|{boolean state.Status.Collected}|{state.Status.Outcome}|{contacts}|{legacy}"

    if content.SchemaVersion = 2 then
        // Frozen .3 identity: schema-2 readers and retained recordings must observe
        // byte-for-byte the original canonical state shape.
        $"v2|2|{content.ContentId}|{gameplay}"
    else
        $"v3|{content.SchemaVersion}|{content.ContentId}|{number content.Boundary.X},{number content.Boundary.Y},{number content.Boundary.Width},{number content.Boundary.Height}|{content.Spawn.Col},{content.Spawn.Row}|{gameplay}"

/// The same pure contract factory is compiled by the .NET authority and Fable Studio.
/// Restore is bound to the session's selected authored content identity.
let contractForDefinition (expectedDefinition: ArenaContent) : SessionContract<State, State, Command, State, State> =
    let expectedCompatibility = compatibilityFor expectedDefinition

    {
        Initialize = fun initialization -> Ok initialization.Configuration
        AdmitInput =
            fun input state ->
                match input.Value with
                | Command.Join(playerId, cell) -> Ok(join playerId cell state)
                | Command.Leave playerId -> Ok(leave playerId state)
                | Command.Apply(playerId, intent) -> Ok(applyIntent playerId intent state)
        Advance =
            fun value state ->
                let mutable next = state

                for _ in 1UL .. value.StepCount do
                    next <- advance next

                Ok next
        Project =
            fun state ->
                {
                    SessionId = "arena-1"
                    Revision = uint64 state.Room.Tick
                    Value = state
                }
        Snapshot =
            fun state ->
                {
                    SessionId = "arena-1"
                    Revision = uint64 state.Room.Tick
                    Compatibility = expectedCompatibility
                    Value = state
                }
        Restore =
            fun saved ->
                if saved.Compatibility <> expectedCompatibility then
                    Error
                        {
                            Code = "arena.snapshot.compatibility"
                            Message = "arena snapshot compatibility mismatch"
                        }
                elif
                    saved.Value.Definition.SchemaVersion <> expectedDefinition.SchemaVersion
                    || saved.Value.Definition.ContentId <> expectedDefinition.ContentId
                then
                    Error
                        {
                            Code = "arena.snapshot.content"
                            Message = "arena snapshot content identity mismatch"
                        }
                else
                    Ok saved.Value
    }

let contractFor expectedContentId =
    let baseline = contentAt 0UL

    contractForDefinition
        { baseline with
            ContentId = expectedContentId
        }

let contract = contractForDefinition (contentAt 0UL)
