module FableGameWorkspaceNamespace.Protocol.Tests.CrossRuntime.Program

open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Protocol.Realtime
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.Domain
open FableGameWorkspaceNamespace.ArenaContent
open FableGameWorkspaceNamespace.ArenaRules
open FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema
open FS.GG.UI.Scene
module Arcade = FableGameWorkspaceNamespace.ArcadeRules
module Tactical = FableGameWorkspaceNamespace.TacticalRules
#if CONTINUOUS_PLAYER
module ContinuousPlayer = FableGameWorkspaceNamespace.SvgFoundation.ContinuousPlayer
#endif

/// A tiny CLI, compiled *twice* -- once as an ordinary .NET console app
/// (`CodecProbe.Net.fsproj`, against `Thoth.Json.Net`) and once via `dotnet fable`
/// (`CodecProbe.Fable.fsproj`, against `Thoth.Json`, run under Node) -- that exists
/// only to make ADR-0073's "not optional" acceptance criterion executable: every
/// request/response DTO is tested by encoding from .NET and decoding in the browser
/// runtime (and the reverse), including a case expected to be *rejected*, so
/// serializer compatibility is demonstrated per DTO rather than assumed for the type
/// system as a whole. `../run-cross-runtime.sh` drives both builds of this same
/// source file against each other's output.
///
/// The two `#if FABLE_COMPILER` blocks below are the only target-specific code in
/// this file; every codec call is the same named function from `Protocol/Http.fs` /
/// `Protocol/Realtime.fs` on both sides.

#if FABLE_COMPILER
open Fable.Core

[<Emit("process.argv.slice(2)")>]
let private commandLineArgs () : string[] = jsNative

[<Import("readFileSync", "node:fs")>]
let private readFileSyncNative (path: string, encoding: string) : string = jsNative

[<Import("writeFileSync", "node:fs")>]
let private writeFileSyncNative (path: string, contents: string) : unit = jsNative

let private readFile (path: string) : string = readFileSyncNative (path, "utf8")
let private writeFile (path: string) (contents: string) : unit = writeFileSyncNative (path, contents)
#else
let private commandLineArgs () : string[] =
    System.Environment.GetCommandLineArgs() |> Array.skip 1

let private readFile (path: string) : string = System.IO.File.ReadAllText path
let private writeFile (path: string) (contents: string) : unit = System.IO.File.WriteAllText(path, contents)
#endif

let private canonicalBootstrapRequest: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }

let private canonicalBootstrapResponse: BootstrapV1.Response =
    { Version = 1
      PlayerId = "cross-runtime-player"
      SessionCapability = "cross-runtime-capability"
      RoomId = "cross-runtime-room"
      SpawnCol = 3
      SpawnRow = 4
      ArenaWidth = 20
      ArenaHeight = 12 }

let private canonicalRealtimeCase (name: string) : RealtimeV1.Message option =
    match name with
    | "input" -> Some(RealtimeV1.InputMessage { Version = 1; Sequence = 7; TargetCol = 5; TargetRow = 2 })
    | "sessionHello" -> Some(RealtimeV1.SessionHelloMessage { Version = 1; SessionCapability = "cross-runtime-capability" })
    | "snapshot" ->
        Some(
            RealtimeV1.SnapshotMessage
                { Version = 1
                  Tick = 42
                  Players = [ { PlayerId = "p-1"; Col = 1; Row = 1 }; { PlayerId = "p-2"; Col = 2; Row = 3 } ] }
        )
    | "presence" -> Some(RealtimeV1.PresenceMessage { Version = 1; PlayerId = "p-1"; Joined = true })
    | "resyncRequest" -> Some(RealtimeV1.ResyncRequestMessage { Version = 1; LastKnownTick = 10 })
    | "resyncSnapshot" -> Some(RealtimeV1.ResyncSnapshotMessage { Version = 1; Tick = 42; Players = [] })
    | _ -> None

let private canonicalRealtimeV2Case (name: string) : RealtimeV2.Message option =
    let snapshot: RealtimeV2.Snapshot =
        { Version = 2; Tick = 42; Round = 3
          Players = [ { PlayerId = "p-1"; Col = 5; Row = 2 } ]
          Health = 2; Score = 100; Collected = true; Outcome = "playing"
          ContentId = "continuous-arena/cross-runtime"; ContentSchema = 2
          CollectibleX = 60.0; CollectibleY = 25.0
          HazardX = 88.0; HazardY = 80.0; HazardWidth = 11.0; HazardHeight = 10.0
          GoalX = 176.0; GoalY = 50.0; GoalWidth = 11.0; GoalHeight = 10.0
          ThinWallX = 112.0; ThinWallY = 0.0; ThinWallWidth = 2.0; ThinWallHeight = 48.0
          HazardCol = 8; HazardRow = 8 }
    match name with
    | "input" -> Some(RealtimeV2.InputMessage { Version = 2; Sequence = 8; Action = "interact"; TargetCol = 5; TargetRow = 2 })
    | "sessionHello" -> Some(RealtimeV2.SessionHelloMessage { Version = 2; SessionCapability = "cross-runtime-capability" })
    | "snapshot" -> Some(RealtimeV2.SnapshotMessage snapshot)
    | "presence" -> Some(RealtimeV2.PresenceMessage { Version = 2; PlayerId = "p-1"; Joined = true })
    | "resyncRequest" -> Some(RealtimeV2.ResyncRequestMessage { Version = 2; LastKnownTick = 10 })
    | "resyncSnapshot" -> Some(RealtimeV2.ResyncSnapshotMessage snapshot)
    | _ -> None

let private canonicalRealtimeV3Case (name: string) : RealtimeV3.Message option =
    let snapshot: RealtimeV3.Snapshot =
        { Version = 3; Tick = 42; Round = 3
          Players = [ { PlayerId = "p-1"; Col = 19; Row = 11 } ]
          Health = 2; Score = 100; Collected = true; Outcome = "playing"
          ContentId = "continuous-arena/cross-runtime-authored-v3"; ContentSchema = 3
          BoundaryX = 0.0; BoundaryY = 0.0; BoundaryWidth = 220.0; BoundaryHeight = 120.0
          SpawnCol = 19; SpawnRow = 11
          CollectibleX = 60.25; CollectibleY = 25.75
          HazardX = 88.5; HazardY = 80.25; HazardWidth = 11.5; HazardHeight = 10.25
          GoalX = 176.25; GoalY = 50.5; GoalWidth = 11.25; GoalHeight = 10.5
          ThinWallX = 112.25; ThinWallY = 0.5; ThinWallWidth = 2.25; ThinWallHeight = 48.5
          HazardCol = 8; HazardRow = 8 }
    match name with
    | "input" -> Some(RealtimeV3.InputMessage { Version = 3; Sequence = 9; Action = "restart"; TargetCol = 19; TargetRow = 11 })
    | "sessionHello" -> Some(RealtimeV3.SessionHelloMessage { Version = 3; SessionCapability = "cross-runtime-capability" })
    | "snapshot" -> Some(RealtimeV3.SnapshotMessage snapshot)
    | "presence" -> Some(RealtimeV3.PresenceMessage { Version = 3; PlayerId = "p-1"; Joined = true })
    | "resyncRequest" -> Some(RealtimeV3.ResyncRequestMessage { Version = 3; LastKnownTick = 10 })
    | "resyncSnapshot" -> Some(RealtimeV3.ResyncSnapshotMessage snapshot)
    | _ -> None

/// The two deliberately-rejected cases: an unrecognised discriminator, and a
/// well-known discriminator whose payload fails its own field decoders. Baked in
/// (not read from a file) so both runtimes independently attempt the *same* literal
/// bytes -- proving both decoders are equally strict, not merely that one runtime's
/// encoder never produces something the other rejects.
let private rejectedCases =
    [ "unrecognised-kind", """{"kind":"teleport","payload":{}}"""
      "wrong-field-type", """{"kind":"input","payload":{"version":1,"sequence":"not-a-number","targetCol":1,"targetRow":1}}""" ]

let private encodeArenaIntent = function
    | Intent.Move cell -> $"move:{cell.Col}:{cell.Row}"
    | Intent.LegacyMove cell -> $"legacy:{cell.Col}:{cell.Row}"
    | Intent.Interact -> "interact"
    | Intent.Restart -> "restart"

let private encodeArenaCommand = function
    | Command.Join(playerId, cell) -> $"join:{playerId}:{cell.Col}:{cell.Row}"
    | Command.Leave playerId -> $"leave:{playerId}"
    | Command.Apply(playerId, intent) -> $"apply:{playerId}:{encodeArenaIntent intent}"

let private interactionBoundaryProof () =
    let baseline = contentAt 0UL
    let stateBefore collectibleX =
        let content =
            { baseline with
                ContentId = "continuous-arena/interaction-boundary"
                CollectibleX = collectibleX
                CollectibleY = 5.0 }
        createWith content
        |> join "boundary-player" { Col = 0; Row = 0 }
    let atBoundaryBefore = stateBefore 15.0
    let justInsideBefore = stateBefore 14.9999999999
    let atBoundaryBytes = canonicalState atBoundaryBefore
    let justInsideBytes = canonicalState justInsideBefore
    if atBoundaryBytes = justInsideBytes then
        failwith "canonical state merged bounds with different interaction outcomes"
    let atBoundary = applyIntent "boundary-player" Intent.Interact atBoundaryBefore
    let justInside = applyIntent "boundary-player" Intent.Interact justInsideBefore
    if atBoundary.Status.Collected || not justInside.Status.Collected then
        failwith "interaction boundary no longer distinguishes touching from overlap"
    atBoundaryBytes + "\n" + justInsideBytes

let private gameplayIdentityProof () =
    let visualIds = [| "arena"; "collectible"; "hazard"; "goal"; "thin-wall"; "player" |]
    let baseMetadata = gameplayMetadata arenaDocument.Id visualIds
    let diagnostic number =
        { EntityId = "gameplay:numeric-identity"
          KindId = "sample.object"
          VisualElementId = None
          PrefabInstanceId = None
          Properties =
            [ { Key = "adjacent"; Value = SvgScenePropertyValue.Number number }
              { Key = "tiny"; Value = SvgScenePropertyValue.Number 1.2345678901234567e-120 }
              { Key = "large"; Value = SvgScenePropertyValue.Coordinate { X = 1.2e100; Y = -3.4e-100 } } ] }
    let metadata number =
        { baseMetadata with
            Grid = Some { Origin = { X = 0.125; Y = -0.25 }; Step = { X = 1.0000000000000002; Y = 1.2e-100 } }
            Entities = baseMetadata.Entities @ [ diagnostic number ] }
    let hash value = gameplayContentHash value arenaDocument |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    let firstMetadata = metadata 1.0
    let adjacentMetadata = metadata 1.0000000000000002
    let reboundMetadata =
        { firstMetadata with
            Entities =
                firstMetadata.Entities
                |> List.map (fun entity ->
                    if entity.EntityId = "gameplay:hazard" then { entity with VisualElementId = Some "goal" }
                    else entity) }
    let first, adjacent, rebound = hash firstMetadata, hash adjacentMetadata, hash reboundMetadata
    if first = adjacent || first = rebound then failwith "gameplay metadata identity merged distinct accepted semantics"
    String.concat "\n" [ first; adjacent; rebound; canonicalFloat 1.0; canonicalFloat 1.0000000000000002 ]

let private arenaModelCorrespondenceProof traceFile =
    let project (state: State) =
        let boolean value = if value then "true" else "false"
        $"health:{state.Status.Health}|score:{state.Status.Score}|collected:{boolean state.Status.Collected}|outcome:{state.Status.Outcome}|round:{state.Round}|hazardContact:{boolean (not state.HazardContacts.IsEmpty)}"
    let baseline = contentAt 0UL
    let interactionContent =
        { baseline with SchemaVersion = 3; ContentId = "continuous-arena/model-interaction"
                        CollectibleX = 5.0; CollectibleY = 5.0
                        Goal = { X = 0.0; Y = 0.0; Width = 10.0; Height = 10.0 } }
    let initial = createWith interactionContent |> join "p" { Col = 0; Row = 0 }
    let staleContent = { interactionContent with ContentId = "continuous-arena/model-stale" }
    let staleState = createWith staleContent |> join "p" { Col = 0; Row = 0 }
    let staleSnapshot = (contractForDefinition staleContent).Snapshot staleState
    match (contractForDefinition interactionContent).Restore staleSnapshot with
    | Error failure when failure.Code = "arena.snapshot.content" -> ()
    | result -> failwith $"stale authored state accepted: {result}"
    let collected = applyIntent "p" Intent.Interact initial
    let won = applyIntent "p" Intent.Interact collected
    let terminalRefused = applyIntent "p" Intent.Interact won
    let restartedAfterWin = applyIntent "p" Intent.Restart terminalRefused
    let hazardContent =
        { baseline with SchemaVersion = 3; ContentId = "continuous-arena/model-hazard"
                        Hazard = { X = 0.0; Y = 0.0; Width = 10.0; Height = 10.0 } }
    let entered = restartedAfterWin |> withDefinition hazardContent |> advance
    let stayed = advance entered
    let awayContent = { hazardContent with Hazard = { hazardContent.Hazard with X = 180.0; Y = 100.0 } }
    let exited = stayed |> withDefinition awayContent |> advance
    let enteredAgain = exited |> withDefinition hazardContent |> advance
    let exitedAgain = enteredAgain |> withDefinition awayContent |> advance
    let lost = exitedAgain |> withDefinition hazardContent |> advance
    let restarted = applyIntent "p" Intent.Restart lost
    let observations =
        [ initial; collected; won; terminalRefused; restartedAfterWin; entered; stayed; exited
          enteredAgain; exitedAgain; lost; restarted ]
        |> List.map project
    let expected =
        readFile traceFile
        |> fun value -> value.Replace("\r\n", "\n").TrimEnd().Split('\n')
        |> Array.toList
    if observations <> expected then
        let actions =
            [ "init"; "collect"; "reachGoal"; "terminalGuard"; "restart"; "hazardContact"
              "stayInHazard"; "exitHazard"; "hazardContact"; "exitHazard"; "lethalHazardContact"; "restart" ]
        let index =
            [ 0 .. min expected.Length observations.Length - 1 ]
            |> List.tryFind (fun index -> expected.[index] <> observations.[index])
            |> Option.defaultValue (min expected.Length observations.Length)
        let at values = values |> List.tryItem index |> Option.defaultValue "<missing>"
        let action = at actions
        failwith $"Quint/reducer first divergence at state {index} ({action}): expected {at expected}; actual {at observations}"
    String.concat "\n" observations

let private arcadeProof traceFile =
#if CONTINUOUS_PLAYER
    let continuous = ContinuousPlayer.contract
    let continuousInitial =
        continuous.Initialize
            { SessionId = "generated-player"; Compatibility = ContinuousPlayer.compatibility; Configuration = () }
        |> Result.defaultWith (fun failure -> failwith failure.Code)
    let continuousSnapshot = continuous.Snapshot continuousInitial
    match continuous.Restore continuousSnapshot with
    | Ok restored when restored = continuousInitial -> ()
    | result -> failwith $"continuous player refused its own snapshot round trip: {result}"
    match continuous.Restore { continuousSnapshot with SessionId = "foreign-session" } with
    | Error failure when failure.Code = "continuous-player.snapshot.session" -> ()
    | result -> failwith $"continuous player accepted a foreign session snapshot: {result}"
    let priorCompatibility =
        { ContinuousPlayer.compatibility with EngineVersion = "0"; ProfileId = "generated-player/prior" }
    match continuous.Restore { continuousSnapshot with Compatibility = priorCompatibility } with
    | Error failure when failure.Code = "continuous-player.snapshot.compatibility" -> ()
    | result -> failwith $"continuous player accepted an incompatible snapshot: {result}"
#endif
    let project (state: Arcade.ArcadeState) =
        let boolean value = if value then "true" else "false"
        let outcome = match state.Outcome with Arcade.ArcadeOutcome.Playing -> "playing" | Arcade.ArcadeOutcome.Won -> "won" | Arcade.ArcadeOutcome.Lost -> "lost"
        $"health:{state.Health}|score:{state.Score}|collected:{boolean state.Collected}|outcome:{outcome}|hazardContact:{boolean state.HazardContact}"
    let omitRound (line: string) =
        let marker = "|round:"
        let start = line.IndexOf(marker)
        let finish = if start < 0 then -1 else line.IndexOf('|', start + marker.Length)
        if start < 0 || finish < 0 then failwith $"arena model observation lacks round field: {line}"
        line.Substring(0, start) + line.Substring(finish)
    let baseContent: Arcade.ArcadeContent =
        { Id = "continuous-arcade"; ContentId = "sha256:arcade-cross-runtime"
          Width = 220.0; Height = 120.0
          Spawn = { X = 12.0; Y = 54.0; Width = 10.0; Height = 10.0 }; InitialHealth = 3
          CollectibleX = 17.0; CollectibleY = 59.0; CollectibleScore = 100
          Hazard = { X = 160.0; Y = 90.0; Width = 18.0; Height = 12.0 }; HazardVelocity = 1.5; HazardDamage = 1
          Goal = { X = 12.0; Y = 54.0; Width = 16.0; Height = 18.0 } }
    let contract = Arcade.contractForDefinition baseContent
    let initial =
        contract.Initialize
            { SessionId = baseContent.Id; Compatibility = Arcade.compatibilityFor baseContent; Configuration = () }
        |> Result.defaultWith (fun failure -> failwith failure.Code)
    let collected = Arcade.applyCommand Arcade.ArcadeCommand.Interact initial
    let won = Arcade.applyCommand Arcade.ArcadeCommand.Interact collected
    let terminalRefused = Arcade.applyCommand (Arcade.ArcadeCommand.SetVelocity { X = 2.25; Y = 0.0 }) won
    let restartedAfterWin = Arcade.applyCommand Arcade.ArcadeCommand.Restart terminalRefused
    let hazardContent = { baseContent with ContentId = "sha256:arcade-hazard"; Hazard = baseContent.Spawn }
    let hazardContract = Arcade.contractForDefinition hazardContent
    let hazardInitial = Arcade.initialState hazardContent
    let entered = Arcade.advanceOnce { restartedAfterWin with Content = hazardContent; HazardX = hazardContent.Hazard.X }
    let stayed = Arcade.advanceOnce entered
    let away = { hazardContent with Hazard = { hazardContent.Hazard with X = 180.0; Y = 90.0 } }
    let exited = Arcade.advanceOnce { stayed with Content = away }
    let enteredAgain = Arcade.advanceOnce { exited with Content = hazardContent; HazardX = hazardContent.Hazard.X }
    let exitedAgain = Arcade.advanceOnce { enteredAgain with Content = away }
    let lost = Arcade.advanceOnce { exitedAgain with Content = hazardContent; HazardX = hazardContent.Hazard.X }
    if lost.Outcome <> Arcade.ArcadeOutcome.Lost then failwith "arcade lethal contact was not applied"
    let restarted = Arcade.applyCommand Arcade.ArcadeCommand.Restart lost
    let staleSnapshot = hazardContract.Snapshot hazardInitial
    match contract.Restore staleSnapshot with
    | Error failure when failure.Code = "arcade.snapshot.compatibility" -> ()
    | result -> failwith $"arcade accepted foreign content snapshot: {result}"
    let wrongSession = { contract.Snapshot initial with SessionId = "foreign-session" }
    match contract.Restore wrongSession with
    | Error failure when failure.Code = "arcade.snapshot.session" -> ()
    | result -> failwith $"arcade accepted foreign session snapshot: {result}"
    let tamperedContent = { baseContent with HazardDamage = 99 }
    let tamperedSnapshot = { contract.Snapshot initial with Value = { initial with Content = tamperedContent } }
    match contract.Restore tamperedSnapshot with
    | Error failure when failure.Code = "arcade.snapshot.content" -> ()
    | result -> failwith $"arcade accepted changed immutable content under a retained label: {result}"
    let observations =
        [ initial; collected; won; terminalRefused; restartedAfterWin; entered; stayed; exited
          enteredAgain; exitedAgain; lost; restarted ]
        |> List.map project
    let expected =
        readFile traceFile
        |> fun value -> value.Replace("\r\n", "\n").TrimEnd().Split('\n')
        |> Array.toList
        |> List.map omitRound
    if observations <> expected then
        let actions =
            [ "init"; "collect"; "reachGoal"; "terminalGuard"; "restart"; "hazardContact"
              "stayInHazard"; "exitHazard"; "hazardContact"; "exitHazard"; "lethalHazardContact"; "restart" ]
        let index =
            [ 0 .. min expected.Length observations.Length - 1 ]
            |> List.tryFind (fun index -> expected.[index] <> observations.[index])
            |> Option.defaultValue (min expected.Length observations.Length)
        let at values = values |> List.tryItem index |> Option.defaultValue "<missing>"
        failwith $"Quint/Arcade reducer first divergence at state {index} ({at actions}): expected {at expected}; actual {at observations}"
    String.concat "\n" observations

let private tacticalProof traceFile =
    let apply label operation state = operation state |> Result.defaultWith (fun issue -> failwith $"tactical {label} refused: {issue}")
    let definition: Tactical.Content =
        { Id = "tactical"; ContentIdentity = "sha256:tactical-cross-runtime"; Columns = 10; Rows = 6
          FirstId = "unit:7"; First = { Col = 1; Row = 2 }; SecondId = "unit:11"; Second = { Col = 6; Row = 3 }
          Target = { Col = 5; Row = 2 } }
    let initial = Tactical.create definition
    let planned = initial |> apply "plan" Tactical.plan
    let _, compared = planned |> apply "compare" Tactical.compare
    let cancelled = compared |> apply "cancel" Tactical.cancel
    let replanned = cancelled |> apply "replan" Tactical.plan
    let committed = replanned |> apply "commit" Tactical.commit
    let reviewedCommit = committed |> apply "review committed" Tactical.review
    let reset = Tactical.create definition
    let simulationPlan = reset |> apply "simulation plan" Tactical.plan
    let simulated = simulationPlan |> apply "simulate" Tactical.simulate
    let repeatedSimulation = simulated |> apply "repeat simulation" Tactical.simulate
    let reviewedSimulation = repeatedSimulation |> apply "review simulation" Tactical.review
    if repeatedSimulation.Room.Players.[definition.FirstId].Cell.Col <= simulated.Room.Players.[definition.FirstId].Cell.Col then
        failwith "tactical repeated simulator step did not advance the accepted room"
    let alternate = { definition with ContentIdentity = "sha256:tactical-alternate"; Target = { Col = 3; Row = 4 } }
    let alternatePlan = Tactical.create alternate |> apply "alternate row/column plan" Tactical.plan
    if alternatePlan.Route |> List.tryLast <> Some alternate.Target then failwith "tactical alternate route missed its authored target"
    let blocked = { definition with ContentIdentity = "sha256:tactical-blocked"; Target = definition.Second }
    match Tactical.create blocked |> Tactical.plan with
    | Error "route-blocked" -> ()
    | result -> failwith $"tactical occupied target was not refused: {result}"
    let tacticalContract = Tactical.contract definition
    let snapshot = tacticalContract.Snapshot initial.Room
    let alteredRoom = { initial.Room with Width = 99 }
    if Tactical.digest definition alteredRoom = Tactical.digest definition initial.Room then
        failwith "tactical canonical state merged changed room dimensions"
    match tacticalContract.Restore { snapshot with Value = alteredRoom } with
    | Error failure when failure.Code = "tactical.snapshot.content" -> ()
    | result -> failwith $"tactical accepted altered room dimensions under retained content: {result}"
    let alteredPlayer = initial.Room.Players.[definition.FirstId]
    let alteredIdentityRoom =
        { initial.Room with Players = initial.Room.Players |> Map.add definition.FirstId { alteredPlayer with PlayerId = "foreign-unit" } }
    match tacticalContract.Restore { snapshot with Value = alteredIdentityRoom } with
    | Error failure when failure.Code = "tactical.snapshot.content" -> ()
    | result -> failwith $"tactical accepted altered unit identity under retained content: {result}"
    let actual =
        [ initial; planned; compared; cancelled; replanned; committed; reviewedCommit
          reset; simulationPlan; simulated; repeatedSimulation; reviewedSimulation ]
        |> List.map Tactical.canonicalProjection
    let expected =
        readFile traceFile
        |> fun value -> value.Replace("\r\n", "\n").TrimEnd().Split('\n')
        |> Array.toList
    if actual <> expected then
        let actualText = String.concat ";" actual
        failwith $"tactical Quint/reducer trace diverged: {actualText}"
    String.concat "\n" actual

/// Execute the product's complete portable contract and Replay implementation from
/// the same source on .NET and Fable. The exported bytes include every post-operation
/// digest, so matching final state alone cannot hide a dropped Interact or Restart.
let private arenaProof () =
    let boundaryProof = interactionBoundaryProof ()
    let baseline = contentAt 0UL
    let content =
        { baseline with
            SchemaVersion = 3
            ContentId = "continuous-arena/cross-runtime-rules"
            CollectibleX = 5.25
            CollectibleY = 5.75
            // Fractional AABBs model the bounds compiled from a rotated/scaled
            // Studio element and force portable numeric canonicalization.
            Hazard = { X = 9.625; Y = -1.25; Width = 13.75; Height = 12.5 }
            Goal = { baseline.Goal with X = 21.75; Y = -0.5; Width = 13.5; Height = 11.25 }
            ThinWall = { baseline.ThinWall with X = arenaWidth - 2.125; Y = 0.375 } }
    let contract = contractForDefinition content
    let mutable state =
        contract.Initialize { SessionId = "arena-1"; Compatibility = compatibility; Configuration = createWith content }
        |> Result.defaultWith (fun failure -> failwith failure.Code)
    let mutable recording =
        ReplayRecorder.create (contract.Snapshot state) (canonicalState state)
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    let mutable sequence = 0UL
    let apply command =
        sequence <- sequence + 1UL
        let input = { SessionId = "arena-1"; InputId = "cross-runtime-arena"; Sequence = sequence; Value = command }
        state <- contract.AdmitInput input state |> Result.defaultWith (fun failure -> failwith failure.Code)
        recording <- ReplayRecorder.appendInput input (canonicalState state) recording |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    apply (Command.Join("p", { Col = 0; Row = 0 }))
    apply (Command.Apply("p", Intent.Move { Col = 1; Row = 0 }))
    if state.Status.Health <> 2 then failwith "cross-runtime contact was not applied"
    apply (Command.Apply("p", Intent.Move { Col = 0; Row = 0 }))
    apply (Command.Apply("p", Intent.Interact))
    if not state.Status.Collected || state.Status.Score <> 100 then failwith "cross-runtime collectible was not applied"
    apply (Command.Apply("p", Intent.Move { Col = 1; Row = 0 }))
    apply (Command.Apply("p", Intent.Move { Col = 2; Row = 0 }))
    apply (Command.Apply("p", Intent.Interact))
    if state.Status.Outcome <> "won" then failwith "cross-runtime win was not applied"
    apply (Command.Apply("p", Intent.Restart))
    if state.Status <> initialStatus || state.Round <> 2 || state.Room.Players.["p"].Cell <> { Col = 0; Row = 0 } then
        failwith "cross-runtime restart was incomplete"
    state <- contract.Advance { SessionId = "arena-1"; StepCount = 20UL } state |> Result.defaultWith (fun failure -> failwith failure.Code)
    recording <- ReplayRecorder.appendAdvance 20UL (canonicalState state) recording |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    match Replay.seek contract canonicalState (fun _ -> false) (uint64 recording.Events.Length) recording with
    | Ok(ReplayRunOutcome.Completed(_, replayed)) when canonicalState replayed = canonicalState state ->
        ReplayExport.canonicalText encodeArenaCommand canonicalState recording
        |> Result.map (fun replay -> canonicalState state + "\n---BOUNDARY---\n" + boundaryProof + "\n---REPLAY---\n" + replay)
        |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    | outcome -> failwithf "cross-runtime replay failed: %A" outcome

[<EntryPoint>]
let main _ =
    match commandLineArgs () |> Array.toList with
    | [ "encode-bootstrap-request"; outFile ] ->
        writeFile outFile (BootstrapV1.encodeRequest canonicalBootstrapRequest)
        printfn "WROTE"
        0
    | [ "decode-bootstrap-request"; inFile ] ->
        match readFile inFile |> BootstrapV1.requestFromJson with
        | Ok value when value = canonicalBootstrapRequest -> printfn "OK"; 0
        | Ok value -> printfn "MISMATCH %A" value; 1
        | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-bootstrap-response"; outFile ] ->
        writeFile outFile (BootstrapV1.encodeResponse canonicalBootstrapResponse)
        printfn "WROTE"
        0
    | [ "decode-bootstrap-response"; inFile ] ->
        match readFile inFile |> BootstrapV1.responseFromJson with
        | Ok value when value = canonicalBootstrapResponse -> printfn "OK"; 0
        | Ok value -> printfn "MISMATCH %A" value; 1
        | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-realtime"; caseName; outFile ] ->
        match canonicalRealtimeCase caseName with
        | Some message ->
            writeFile outFile (RealtimeV1.encodeMessage message)
            printfn "WROTE"
            0
        | None ->
            printfn "UNKNOWN-CASE %s" caseName
            2
    | [ "decode-realtime"; caseName; inFile ] ->
        match canonicalRealtimeCase caseName with
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
        | Some expected ->
            match readFile inFile |> RealtimeV1.messageFromJson with
            | Ok value when value = expected -> printfn "OK"; 0
            | Ok value -> printfn "MISMATCH %A" value; 1
            | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-realtime-v2"; caseName; outFile ] ->
        match canonicalRealtimeV2Case caseName with
        | Some message -> writeFile outFile (RealtimeV2.encodeMessage message); printfn "WROTE"; 0
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
    | [ "decode-realtime-v2"; caseName; inFile ] ->
        match canonicalRealtimeV2Case caseName with
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
        | Some expected ->
            match readFile inFile |> RealtimeV2.messageFromJson with
            | Ok value when value = expected -> printfn "OK"; 0
            | Ok value -> printfn "MISMATCH %A" value; 1
            | Error message -> printfn "REJECTED %s" message; 1
    | [ "encode-realtime-v3"; caseName; outFile ] ->
        match canonicalRealtimeV3Case caseName with
        | Some message -> writeFile outFile (RealtimeV3.encodeMessage message); printfn "WROTE"; 0
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
    | [ "decode-realtime-v3"; caseName; inFile ] ->
        match canonicalRealtimeV3Case caseName with
        | None -> printfn "UNKNOWN-CASE %s" caseName; 2
        | Some expected ->
            match readFile inFile |> RealtimeV3.messageFromJson with
            | Ok value when value = expected -> printfn "OK"; 0
            | Ok value -> printfn "MISMATCH %A" value; 1
            | Error message -> printfn "REJECTED %s" message; 1
    | [ "decode-rejected-cases" ] ->
        let results =
            rejectedCases
            |> List.map (fun (name, json) ->
                match RealtimeV1.messageFromJson json with
                | Error _ -> name, true
                | Ok value -> printfn "UNEXPECTEDLY-ACCEPTED %s -> %A" name value; name, false)
        if results |> List.forall snd then
            printfn "ALL-REJECTED-AS-EXPECTED"
            0
        else
            1
    | [ "write-arena-proof"; outFile ] ->
        writeFile outFile (arenaProof ())
        printfn "WROTE"
        0
    | [ "write-gameplay-identity-proof"; outFile ] ->
        writeFile outFile (gameplayIdentityProof ())
        printfn "WROTE"
        0
    | [ "write-arena-model-correspondence"; traceFile; outFile ] ->
        writeFile outFile (arenaModelCorrespondenceProof traceFile)
        printfn "WROTE"
        0
    | [ "write-arcade-proof"; traceFile; outFile ] ->
        writeFile outFile (arcadeProof traceFile)
        printfn "WROTE"
        0
    | [ "write-tactical-proof"; traceFile; outFile ] ->
        writeFile outFile (tacticalProof traceFile)
        printfn "WROTE"
        0
    | [ "check-arena-model-correspondence"; traceFile ] ->
        try
            arenaModelCorrespondenceProof traceFile |> ignore
            printfn "OK"
            0
        with error ->
            printfn "REJECTED %s" error.Message
            1
#if !FABLE_COMPILER
    | [ "write-arena-proof-de"; outFile ] ->
        System.Globalization.CultureInfo.CurrentCulture <- System.Globalization.CultureInfo.GetCultureInfo("de-DE")
        writeFile outFile (arenaProof ())
        printfn "WROTE"
        0
    | [ "write-gameplay-identity-proof-de"; outFile ] ->
        System.Globalization.CultureInfo.CurrentCulture <- System.Globalization.CultureInfo.GetCultureInfo("de-DE")
        writeFile outFile (gameplayIdentityProof ())
        printfn "WROTE"
        0
#endif
    | args ->
        printfn "USAGE: unrecognised arguments %A" args
        2
