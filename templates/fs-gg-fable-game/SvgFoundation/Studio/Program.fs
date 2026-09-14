module FableGameWorkspaceNamespace.SvgFoundation.Studio.Program

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema
open FableGameWorkspaceNamespace.Domain
module ArenaContent = FableGameWorkspaceNamespace.ArenaContent
module ArenaRules = FableGameWorkspaceNamespace.ArenaRules
#if SVG_INPUT_CANDIDATE
open FS.GG.UI.KeyboardInput
module WorkspaceCommands = FableGameWorkspaceNamespace.SvgFoundation.Studio.WorkspaceInput
#endif

[<ImportDefault("./vendor/noto-sans-latin-400-normal.woff2.base64?raw")>]
let private notoBase64: string = jsNative

[<Emit("new Worker(new URL('../SvgGeometryWorkerEntry.js', import.meta.url), { type:'module' })")>]
let private workerFactory () : obj = jsNative

[<Emit("(function(text){const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='arena-content.v3.json';a.click();URL.revokeObjectURL(url);})($0)")>]
let private downloadArenaContent (_text: string) : unit = jsNative

let private container: HTMLElement = document.getElementById("svg-authoring-studio")
let mutable private state = initialState ()

let private host =
    SvgStudio.mount container
        { MountNamespace = "generated-authoring-studio"
          AccessibleLabel = "Generated SVG scene studio"
          WorkerFactory = Some workerFactory }
        state (fun accepted -> state <- accepted)
    |> Result.defaultWith (fun error -> failwithf "Generated SVG studio mount refused: %A" error)

let private status: HTMLElement = document.getElementById("generated-scene-status")
let private announce text = status.textContent <- text
let private retainedCamera = SvgAffine.translate 4.0 3.0
do host.SetSelection [ "hazard" ] |> Result.defaultWith (fun error -> failwithf "%A" error)
do host.SetCamera retainedCamera |> Result.defaultWith (fun error -> failwithf "%A" error)
let mutable private playSourceHash = ""
let mutable private authoredContent = compileArenaContent state.Metadata state.Document |> Result.defaultWith failwith
let mutable private playState = ArenaRules.create () |> ArenaRules.join "studio-player" ({ Col = 0; Row = 0 }: Cell)
let mutable private playCollision = false
let mutable private exportedContentJson = ""
let mutable private crossContentRestoreRefused = false
let private playTransactionId = "studio-play-runtime"
let mutable private playFrozenDocument: SvgDocument option = None
let mutable private playFrozenMetadata: SvgSceneMetadata option = None

#if SVG_REPLAY_CANDIDATE
let private replayStudio = ReplayStudio.mount announce (fun () -> playState)
#endif

#if SVG_INPUT_CANDIDATE
container.setAttribute("tabindex", "-1")
let mutable private inputProfile = WorkspaceCommands.profile
let mutable private inputAdapter: SvgInputHost option = None

let private updateInput observation =
    inputAdapter |> Option.iter (fun adapter -> adapter.Update observation |> ignore)

let private workspaceMode = function
    | SvgWorkspaceMode.Create -> "create"
    | SvgWorkspaceMode.Arrange -> "arrange"
    | SvgWorkspaceMode.Play -> "play"
    | SvgWorkspaceMode.Review -> "review"

let private renderWorkspace () =
    container.setAttribute("data-workspace-mode", workspaceMode host.WorkspaceState.Mode)

let private updateWorkspace message =
    let effects = host.UpdateWorkspace message
    effects
    |> List.iter (function
        | SvgWorkspaceEffect.ActiveContextsChanged contexts -> updateInput (CommandResolverObservation.ContextsChanged contexts)
        | _ -> ())
    renderWorkspace ()

let private setMode mode =
    if mode <> SvgWorkspaceMode.Play && playFrozenDocument.IsSome then
        host.CancelGesture playTransactionId |> ignore
        state <- host.State
        playFrozenDocument <- None
        playFrozenMetadata <- None
    updateWorkspace (SvgWorkspaceMessage.SetMode mode)
    announce ("Workspace mode: " + workspaceMode mode)

let private acceptCaptured gesture =
    let adapter = inputAdapter.Value
    let selected = "workspace.palette"
    let displaced =
        adapter.State.Profile.Bindings
        |> List.filter (fun binding -> binding.Gesture = gesture && binding.Command <> selected)
        |> List.map _.Command
        |> List.distinct
    let displacementOverrides =
        displaced
        |> List.map (fun command ->
            let remaining = adapter.State.Profile.Bindings |> List.filter (fun binding -> binding.Command = command && binding.Gesture <> gesture)
            if remaining.IsEmpty then InputBindingOverride.UnbindCommand command
            else InputBindingOverride.ReplaceCommand(command, remaining))
    let replacement =
        InputBindingOverride.ReplaceCommand(selected, [ { Gesture = gesture; Command = selected; Context = "workspace" } ])
    let candidate = { inputProfile with Overrides = inputProfile.Overrides @ displacementOverrides @ [ replacement ] }
    match WorkspaceCommands.compile candidate with
    | Error issues -> announce (sprintf "Input conflict refused: %A" issues)
    | Ok effective ->
        match host.Root.querySelector("[data-fsgg-workspace-overlay='rebind']") with
        | null -> ()
        | element -> element.textContent <- $"Rebind command accepted. Conflict feedback: displaced {displaced.Length} command(s)."
        inputProfile <- candidate
        updateInput (CommandResolverObservation.ProfileChanged effective)
        updateWorkspace SvgWorkspaceMessage.CloseOverlay
        announce ($"Input rebound; displaced commands: {displaced.Length}")

let private handleInputEffect effect =
    match effect with
    | CommandResolverEffect.InvokeCommand invocation ->
        container.setAttribute("data-last-workspace-command", invocation.Command)
        match invocation.Command with
        | "workspace.mode.create" -> setMode SvgWorkspaceMode.Create
        | "workspace.mode.arrange" -> setMode SvgWorkspaceMode.Arrange
        | "workspace.mode.play" -> setMode SvgWorkspaceMode.Play
        | "workspace.mode.review" -> setMode SvgWorkspaceMode.Review
        | "workspace.palette" ->
            updateWorkspace (SvgWorkspaceMessage.OpenPalette "generated-authoring-studio--scene")
            updateInput (CommandResolverObservation.PushModal { Context = "workspace.palette"; RestoreFocus = "generated-authoring-studio--scene" })
            announce "Command palette opened"
        | "workspace.help" ->
            updateWorkspace (SvgWorkspaceMessage.OpenHelp "generated-authoring-studio--scene")
            updateInput (CommandResolverObservation.PushModal { Context = "workspace.help"; RestoreFocus = "generated-authoring-studio--scene" })
            announce "Possible input help opened"
        | "workspace.rebind" ->
            updateWorkspace (SvgWorkspaceMessage.BeginRebind("workspace.palette", "generated-authoring-studio--scene"))
            updateInput (CommandResolverObservation.BeginCapture "generated-authoring-studio--scene")
            announce "Rebind capture waiting for raw input"
        | "workspace.pointer" -> setMode SvgWorkspaceMode.Arrange
        | "workspace.touch" -> setMode SvgWorkspaceMode.Arrange
        | "workspace.gamepad" -> setMode SvgWorkspaceMode.Play
        | _ -> ()
    | CommandResolverEffect.CapturedGesture gesture -> acceptCaptured gesture
    | CommandResolverEffect.RequestFocus _ ->
        if host.WorkspaceState.Overlay.IsSome then updateWorkspace SvgWorkspaceMessage.CloseOverlay
        else updateInput (CommandResolverObservation.ContextsChanged (SvgWorkspace.activeContexts host.WorkspaceState))
    | _ -> ()

do
    let effective = WorkspaceCommands.compile inputProfile |> Result.defaultWith (fun issues -> failwithf "%A" issues)
    document.getElementById("generated-authoring-studio--scene").setAttribute("data-fsgg-input-action", "primary")
    inputAdapter <-
        Some(new SvgInputHost(
            container,
            WorkspaceCommands.catalog,
            CommandResolver.init (SvgWorkspace.activeContexts host.WorkspaceState) effective,
            (fun () -> WorkspaceCommands.catalog.Commands |> List.map _.Id),
            handleInputEffect,
            SvgInputHost.defaultOptions))
    renderWorkspace ()
    for selector in
        [ "#generated-authoring-studio--workspace-mode-0"
          "#generated-authoring-studio--workspace-mode-1"
          "#generated-authoring-studio--workspace-mode-2"
          "#generated-authoring-studio--workspace-mode-3"
          "#generated-authoring-studio--workspace-palette"
          "#generated-authoring-studio--workspace-help"
          "#generated-authoring-studio--workspace-rebind" ] do
        match host.Root.querySelector(selector) with
        | null -> ()
        | element ->
            element.addEventListener("click", fun _ ->
                if host.WorkspaceState.Mode <> SvgWorkspaceMode.Play && playFrozenDocument.IsSome then
                    host.CancelGesture playTransactionId |> ignore
                    state <- host.State
                    playFrozenDocument <- None
                    playFrozenMetadata <- None
                updateInput (CommandResolverObservation.ContextsChanged (SvgWorkspace.activeContexts host.WorkspaceState))
                match host.WorkspaceState.Overlay with
                | Some(SvgWorkspaceOverlay.CommandPalette restore) -> updateInput (CommandResolverObservation.PushModal { Context="workspace.palette"; RestoreFocus=restore })
                | Some(SvgWorkspaceOverlay.PossibleInputHelp restore) -> updateInput (CommandResolverObservation.PushModal { Context="workspace.help"; RestoreFocus=restore })
                | Some(SvgWorkspaceOverlay.RebindCommand(_, restore)) -> updateInput (CommandResolverObservation.BeginCapture restore)
                | None -> ()
                renderWorkspace ())
#endif

let private hash (document: SvgDocument) = SvgAsset.contentHash document |> Result.defaultWith (fun issues -> failwithf "%A" issues)
let private transaction id operations = { Schema = SvgAuthoring.transactionSchema; Id = id; Operations = operations }
let private commit id operations =
    let candidate=transaction id operations
    match host.Preview candidate |> Result.bind(fun()->host.CommitGesture candidate.Id) with
    | Ok () -> state <- host.State; announce id
    | Error error -> announce (sprintf "Validation error: %A" error)

let private replaceScene label document metadata =
    commit label
        [ SvgAuthoringOperation.ReplaceDocument document
          SvgAuthoringOperation.ReplaceSceneMetadata metadata ]

let private startBlankGame () =
    setMode SvgWorkspaceMode.Create
    replaceScene "Blank playable game started" emptyDocument
        { SceneId = emptyDocument.Id; Layers = []; Entities = []; Grid = None; ResourceReferences = [] }

let private openStarterGame () =
    replaceScene "Starter playable game opened" arenaDocument
        (gameplayMetadata arenaDocument.Id [| "arena"; "collectible"; "hazard"; "goal"; "thin-wall"; "player" |])
    match host.SetSelection [ "hazard" ] with
    | Ok () -> ()
    | Error error -> announce (sprintf "Validation error: %A" error)
    match compileArenaContent state.Metadata state.Document with
    | Ok content -> authoredContent <- content; playState <- ArenaRules.createWith content |> ArenaRules.join "studio-player" ({ Col = content.Spawn.Col; Row = content.Spawn.Row }: Cell)
    | Error issue -> announce ("Validation error: " + issue)

let private drawPlayableShapes () =
    replaceScene "Playable vector shapes drawn" authoredArenaDocument
        { SceneId = authoredArenaDocument.Id; Layers = []; Entities = []; Grid = None; ResourceReferences = [] }
    setMode SvgWorkspaceMode.Arrange

let private assignGameplayRoles () =
    let ids = [| for index in 1 .. 6 -> $"authored-shape-{index}" |]
    commit "Gameplay roles assigned" [ SvgAuthoringOperation.ReplaceSceneMetadata(gameplayRoleMetadata authoredArenaDocument.Id ids) ]

let private defineGameplayRules () =
    let ids = [| for index in 1 .. 6 -> $"authored-shape-{index}" |]
    commit "Interaction and win rules defined" [ SvgAuthoringOperation.ReplaceSceneMetadata(gameplayMetadata authoredArenaDocument.Id ids) ]
    match compileArenaContent state.Metadata state.Document with
    | Ok content -> authoredContent <- content; playState <- ArenaRules.createWith content |> ArenaRules.join "studio-player" ({ Col = content.Spawn.Col; Row = content.Spawn.Row }: Cell)
    | Error issue -> announce ("Validation error: " + issue)

let private rebindHazardAndGoalRoles () =
    match compileArenaContent state.Metadata state.Document with
    | Error issue -> announce ("Validation error: " + issue)
    | Ok previousContent ->
        let previousState = ArenaRules.createWith previousContent
        let saved = (ArenaRules.contractForDefinition previousContent).Snapshot previousState
        let roleOf (entity: SvgSceneEntity) =
            entity.Properties
            |> List.tryPick (fun property ->
                match property.Key, property.Value with
                | "role", SvgScenePropertyValue.Text value -> Some value
                | _ -> None)
        let hazardVisual = state.Metadata.Entities |> List.tryFind (roleOf >> (=) (Some "hazard")) |> Option.bind _.VisualElementId
        let goalVisual = state.Metadata.Entities |> List.tryFind (roleOf >> (=) (Some "goal")) |> Option.bind _.VisualElementId
        match hazardVisual, goalVisual with
        | Some hazardId, Some goalId ->
            let rebound =
                { state.Metadata with
                    Entities =
                        state.Metadata.Entities
                        |> List.map (fun entity ->
                            match roleOf entity with
                            | Some "hazard" -> { entity with VisualElementId = Some goalId }
                            | Some "goal" -> { entity with VisualElementId = Some hazardId }
                            | _ -> entity) }
            commit "Hazard and goal gameplay roles rebound" [ SvgAuthoringOperation.ReplaceSceneMetadata rebound ]
            match compileArenaContent state.Metadata state.Document with
            | Ok currentContent ->
                crossContentRestoreRefused <-
                    currentContent.ContentId <> previousContent.ContentId
                    && ((ArenaRules.contractForDefinition currentContent).Restore saved |> Result.isError)
                authoredContent <- currentContent
                playState <- ArenaRules.createWith currentContent |> ArenaRules.join "studio-player" ({ Col = currentContent.Spawn.Col; Row = currentContent.Spawn.Row }: Cell)
                announce "Hazard and goal gameplay roles rebound with stale snapshot refusal"
            | Error issue -> announce ("Validation error: " + issue)
        | _ -> announce "Validation error: hazard and goal roles require visuals"

let private saveAsset () =
    let asset =
        { Schema = SvgAsset.schema
          AssetId = "sample-object"
          Revision = 1
          ContentHash = hash state.Document
          Rights = { License = "CC0-1.0"; Attribution = None; Source = Some "generated neutral sample" }
          Dependencies = []
          Document = state.Document }
    commit "Asset revision 1 saved" [ SvgAuthoringOperation.UpsertAsset asset ]

let private placeInstances () =
    match state.Catalog.Assets |> List.tryFind (fun asset -> asset.AssetId = "sample-object" && asset.Revision = 1) with
    | None -> announce "Validation error: save the sample asset first"
    | Some asset ->
        let target = asset.Document.Children |> List.tryHead |> Option.map _.Id
        let overrides =
            target
            |> Option.map (fun id -> [ { ElementId=id; Property=SvgPrefabProperty.Visibility; Value=SvgPrefabOverrideValue.Visibility true } ])
            |> Option.defaultValue []
        let first = { InstanceId="sample-instance-a";AssetId=asset.AssetId;AcceptedRevision=1;Overrides=overrides }
        let second = { InstanceId="sample-instance-b";AssetId=asset.AssetId;AcceptedRevision=1;Overrides=[] }
        let entities =
            [ { EntityId="sample-object-a";KindId="sample.object";VisualElementId=None;PrefabInstanceId=Some first.InstanceId;Properties=[{Key="position";Value=SvgScenePropertyValue.Coordinate {X=24.5;Y=30.25}}] }
              { EntityId="sample-object-b";KindId="sample.object";VisualElementId=None;PrefabInstanceId=Some second.InstanceId;Properties=[{Key="position";Value=SvgScenePropertyValue.Coordinate {X=72.75;Y=30.25}}] } ]
        commit "Two pinned instances placed"
            [ SvgAuthoringOperation.PutInstance first
              SvgAuthoringOperation.PutInstance second
              SvgAuthoringOperation.ReplaceSceneMetadata { state.Metadata with Entities=entities } ]

let private reviseAsset () =
    match state.Catalog.Assets |> List.tryFind (fun asset -> asset.AssetId="sample-object" && asset.Revision=1) with
    | None -> announce "Validation error: no asset revision to update"
    | Some previous ->
        let changed={previous.Document with Children=previous.Document.Children |> List.skip (min 1 previous.Document.Children.Length)}
        let next={previous with Revision=2;Document=changed;ContentHash=hash changed}
        commit "Asset revision conflict exposed"
            [ SvgAuthoringOperation.UpsertAsset next
              SvgAuthoringOperation.UpdateInstances(previous.AssetId,1,2) ]

let private resolveConflicts () =
    let operations = state.Instances |> List.map(fun instance->SvgAuthoringOperation.PutInstance {instance with Overrides=[]})
    if operations.IsEmpty then announce "Validation error: no instances"
    else commit "Asset conflicts resolved" operations

let private editProperties () =
    let metadata =
        { state.Metadata with
            Grid=Some {Origin={X=3.0;Y=5.0};Step={X=8.0;Y=8.0}}
            Entities=state.Metadata.Entities |> List.map(fun entity->{entity with Properties=entity.Properties@[{Key="label";Value=SvgScenePropertyValue.Text "edited"}]}) }
    commit "Scene properties and grid edited" [SvgAuthoringOperation.ReplaceSceneMetadata metadata]

let private authorGridAndFreeform () =
    state.Metadata
    |> gridAdapter
    |> continuousAdapter
    |> fun metadata -> commit "Grid and freeform adapters authored" [ SvgAuthoringOperation.ReplaceSceneMetadata metadata ]

let private refreshPlayableContent () =
    match compileArenaContent state.Metadata state.Document with
    | Ok content -> authoredContent <- content; playState <- ArenaRules.withDefinition content playState
    | Error issue -> announce ("Validation error: " + issue)

let private movePlayerSpawn () =
    match visualIdForRole "player" state.Metadata state.Document with
    | Error issue -> announce ("Validation error: " + issue)
    | Ok playerId ->
        commit "Player spawn moved to authored grid cell 2,1"
            [ SvgAuthoringOperation.TransformElements([ playerId ], SvgAffine.translate (ArenaContent.cellX { Col = 2; Row = 1 }) (ArenaContent.cellY { Col = 2; Row = 1 })) ]
        refreshPlayableContent ()

let private translateArenaUnsupported () =
    match visualIdForRole "arena" state.Metadata state.Document with
    | Error issue -> announce ("Validation error: " + issue)
    | Ok arenaId -> commit "Arena translated for validation" [ SvgAuthoringOperation.TransformElements([ arenaId ], SvgAffine.translate 11.0 0.0) ]

let private movePlayableHazard label target =
    match compileArenaContent state.Metadata state.Document, visualIdForRole "hazard" state.Metadata state.Document with
    | Error issue, _ | _, Error issue -> announce ("Validation error: " + issue)
    | Ok currentContent, Ok hazardId ->
        let next = ArenaContent.withHazardCell target currentContent
        let dx = next.Hazard.X - currentContent.Hazard.X
        let dy = next.Hazard.Y - currentContent.Hazard.Y
        commit label [ SvgAuthoringOperation.TransformElements([ hazardId ], SvgAffine.translate dx dy) ]
        refreshPlayableContent ()

let private scaleAndRotatePlayableHazard () =
    match compileArenaContent state.Metadata state.Document, visualIdForRole "hazard" state.Metadata state.Document with
    | Error issue, _ | _, Error issue -> announce ("Validation error: " + issue)
    | Ok currentContent, Ok hazardId ->
        let pivotX = currentContent.Hazard.X + currentContent.Hazard.Width / 2.0
        let pivotY = currentContent.Hazard.Y + currentContent.Hazard.Height / 2.0
        let transform =
            SvgAffine.compose
                (SvgAffine.translate pivotX pivotY)
                (SvgAffine.compose
                    (SvgAffine.rotateDegrees 12.0)
                    (SvgAffine.compose (SvgAffine.scale 1.25 0.8) (SvgAffine.translate -pivotX -pivotY)))
        commit "Playable hazard scaled and rotated" [ SvgAuthoringOperation.TransformElements([ hazardId ], transform) ]
        refreshPlayableContent ()

let private playEditedArenaStep () =
    let frozen =
        match playFrozenDocument, playFrozenMetadata with
        | Some document, Some metadata -> Ok(document, metadata)
        | _ ->
            SvgAuthoring.takePlaySnapshot state.Revision state
            |> Result.mapError (sprintf "%A")
            |> Result.bind (fun snapshot ->
                SvgDocument.deserialize snapshot.PlaySnapshot.Value.SerializedDocument
                |> Result.mapError (sprintf "%A")
                |> Result.map (fun document -> document, state.Metadata))
    match frozen |> Result.bind (fun (document, metadata) -> compileArenaContent metadata document |> Result.map (fun content -> document, metadata, content)) with
    | Error issue -> announce ("Play refused before effects: " + issue)
    | Ok(frozenDocument, frozenMetadata, frozenContent) ->
        setMode SvgWorkspaceMode.Play
        playFrozenDocument <- Some frozenDocument
        playFrozenMetadata <- Some frozenMetadata
        playState <- ArenaRules.withDefinition frozenContent playState
        playSourceHash <- hash frozenDocument
        let currentCell = playState.Room.Players.["studio-player"].Cell
        let target: ArenaContent.ArenaCell = { Col = min (ArenaContent.arenaColumns - 1) (currentCell.Col + 1); Row = currentCell.Row }
        let beforeHealth = playState.Status.Health
        let beforeMove = playState
        let moveCommand = ArenaRules.Command.Apply("studio-player", ArenaRules.Intent.Move target)
        playState <- ArenaRules.applyIntent "studio-player" (ArenaRules.Intent.Move target) playState
#if SVG_REPLAY_CANDIDATE
        replayStudio.ObserveInput(beforeMove, moveCommand, playState)
#endif
        let beforeAdvance = playState
        playState <- ArenaRules.advance playState
#if SVG_REPLAY_CANDIDATE
        replayStudio.ObserveAdvance(beforeAdvance, 1UL, playState)
#endif
        playCollision <- playState.Status.Health < beforeHealth
        host.CancelGesture playTransactionId |> ignore
        let currentContent = ArenaRules.currentContent playState
        let player = playState.Room.Players.["studio-player"].Cell
        let roleId role =
            frozenMetadata.Entities
            |> List.find (fun entity -> entity.Properties |> List.exists (fun property -> property.Key = "role" && property.Value = SvgScenePropertyValue.Text role))
            |> fun entity -> entity.VisualElementId.Value
        let playerId, hazardId = roleId "player", roleId "hazard"
        let runtimeDocument =
            { frozenDocument with
                Children =
                    frozenDocument.Children
                    |> List.map (fun element ->
                        if element.Id = playerId then
                            { element with Transform = SvgAffine.translate (ArenaContent.cellX { Col = player.Col; Row = player.Row }) (ArenaContent.cellY { Col = player.Col; Row = player.Row }) }
                        elif element.Id = hazardId then
                            let delta = SvgAffine.translate (currentContent.Hazard.X - frozenContent.Hazard.X) (currentContent.Hazard.Y - frozenContent.Hazard.Y)
                            { element with Transform = SvgAffine.compose delta element.Transform }
                        else element) }
        host.Preview { Schema = SvgAuthoring.transactionSchema; Id = playTransactionId; Operations = [ SvgAuthoringOperation.ReplaceDocument runtimeDocument ] }
        |> Result.defaultWith (fun error -> failwithf "%A" error)
        announce "Edited arena play step"

let private interactWithEditedArena () =
    let before = playState
    let command = ArenaRules.Command.Apply("studio-player", ArenaRules.Intent.Interact)
    playState <- ArenaRules.applyIntent "studio-player" ArenaRules.Intent.Interact playState
#if SVG_REPLAY_CANDIDATE
    replayStudio.ObserveInput(before, command, playState)
#endif
    announce $"Edited arena interaction accepted; score {playState.Status.Score}; outcome {playState.Status.Outcome}"

let private moveEditedPlayer deltaCol deltaRow =
    let current = playState.Room.Players.["studio-player"].Cell
    let target: ArenaContent.ArenaCell =
        { Col = max 0 (min (ArenaContent.arenaColumns - 1) (current.Col + deltaCol))
          Row = max 0 (min (ArenaContent.arenaRows - 1) (current.Row + deltaRow)) }
    let before = playState
    let command = ArenaRules.Command.Apply("studio-player", ArenaRules.Intent.Move target)
    playState <- ArenaRules.applyIntent "studio-player" (ArenaRules.Intent.Move target) playState
#if SVG_REPLAY_CANDIDATE
    replayStudio.ObserveInput(before, command, playState)
#endif
    let accepted = playState.Room.Players.["studio-player"].Cell
    announce $"Edited player moved to {accepted.Col},{accepted.Row}; outcome {playState.Status.Outcome}"

let private restartEditedArena () =
    let before = playState
    let command = ArenaRules.Command.Apply("studio-player", ArenaRules.Intent.Restart)
    playState <- ArenaRules.applyIntent "studio-player" ArenaRules.Intent.Restart playState
#if SVG_REPLAY_CANDIDATE
    replayStudio.ObserveInput(before, command, playState)
#endif
    announce $"Edited arena restarted at round {playState.Round}"

let private validateRoundTrip () =
    let envelope={Schema=SvgScene.schema;Metadata=state.Metadata;Document=state.Document;Catalog=state.Catalog;Instances=state.Instances;Fonts=[]}
    match SvgScene.serialize envelope |> Result.bind SvgScene.deserialize with
    | Ok restored when
        restored.Metadata = state.Metadata && restored.Catalog = state.Catalog && restored.Instances = state.Instances &&
        hash restored.Document = hash state.Document ->
        announce "Scene round-trip validated"
    | Ok _ -> announce "Validation error: scene reload changed accepted content"
    | Error issues -> announce(sprintf "Validation error: %A" issues)

let private invalidImportPayload kind =
    let envelope document =
        { Schema = SvgScene.schema; Metadata = state.Metadata; Document = document
          Catalog = state.Catalog; Instances = state.Instances; Fonts = [] }
    match kind with
    | "malformed" -> "{not-a-scene"
    | "over-complex" ->
        let serialized = SvgScene.serialize (envelope state.Document) |> Result.defaultWith (fun issues -> failwithf "%A" issues)
        let sceneToken = $"{state.Metadata.SceneId.Length}:{state.Metadata.SceneId}"
        let count = string state.Metadata.Layers.Length
        let marker = sceneToken + $"{count.Length}:{count}"
        serialized.Replace(marker, sceneToken + "3:513")
    | "missing-reference" ->
        let definitionId = "known-ref"
        let missingId = "ghost-ref"
        let definition =
            { Id = definitionId
              Content = SvgDefinitionContent.Clip(SvgCoordinateUnits.UserSpaceOnUse, [ SvgClipShape.Rectangle { X = 0.0; Y = 0.0; Width = 8.0; Height = 8.0 } ]) }
        let document =
            match state.Document.Children with
            | first :: remaining ->
                { state.Document with Definitions = definition :: state.Document.Definitions
                                      Children = { first with ClipId = Some definitionId } :: remaining }
            | [] -> failwith "missing-reference fixture requires accepted scene geometry"
        let serialized = SvgScene.serialize (envelope document) |> Result.defaultWith (fun issues -> failwithf "%A" issues)
        let marker = $"{definitionId.Length}:{definitionId}"
        let at = serialized.LastIndexOf(marker, StringComparison.Ordinal)
        if at < 0 then failwith "missing-reference fixture was not encoded"
        serialized.Substring(0, at) + $"{missingId.Length}:{missingId}" + serialized.Substring(at + marker.Length)
    | other -> invalidArg (nameof kind) $"unknown import failure fixture: {other}"

let mutable private persistenceOperation = 0UL
let mutable private handlePersistence: BrowserPersistenceEvent -> unit = ignore
let private persistence =
    new BrowserPersistenceHost(
        { DatabaseName = "FableGameWorkspaceNamespace-svg-studio"
          MaxPayloadCharacters = 262144
          MaxArchiveCharacters = 524288 },
        fun event -> handlePersistence event)

let private storageKey = { Family = BrowserStorageFamily.ProjectDocument; Slot = "continuous-arena" }

let private saveScene () =
    let envelope={Schema=SvgScene.schema;Metadata=state.Metadata;Document=state.Document;Catalog=state.Catalog;Instances=state.Instances;Fonts=[]}
    match SvgScene.serialize envelope with
    | Ok serialized ->
        persistenceOperation <- persistenceOperation + 1UL
        persistence.Persist(
            { Generation = 1UL; Operation = persistenceOperation },
            { Key = storageKey; SchemaVersion = 1; PayloadHash = hash state.Document; Payload = serialized })
    | Error issues -> announce(sprintf "Validation error: %A" issues)

let private loadScene () = persistence.Load storageKey

let private exerciseStorageFailure () =
    persistenceOperation <- persistenceOperation + 1UL
    persistence.Persist(
        { Generation = 1UL; Operation = persistenceOperation },
        { Key = storageKey; SchemaVersion = 1; PayloadHash = hash state.Document; Payload = String.replicate 262145 "x" })

let private exportArenaContent () =
    match compileArenaContent state.Metadata state.Document with
    | Error issue ->
        exportedContentJson <- ""
        announce ("Validation error: playable export refused before download: " + issue)
    | Ok content ->
        authoredContent <- content
        exportedContentJson <-
            JS.JSON.stringify(
                createObj
                    [ "schemaVersion" ==> content.SchemaVersion
                      "contentId" ==> content.ContentId
                      "boundaryX" ==> content.Boundary.X; "boundaryY" ==> content.Boundary.Y
                      "boundaryWidth" ==> content.Boundary.Width; "boundaryHeight" ==> content.Boundary.Height
                      "spawnCol" ==> content.Spawn.Col; "spawnRow" ==> content.Spawn.Row
                      "collectibleX" ==> content.CollectibleX; "collectibleY" ==> content.CollectibleY
                      "hazardX" ==> content.Hazard.X; "hazardY" ==> content.Hazard.Y
                      "hazardWidth" ==> content.Hazard.Width; "hazardHeight" ==> content.Hazard.Height
                      "goalX" ==> content.Goal.X; "goalY" ==> content.Goal.Y
                      "goalWidth" ==> content.Goal.Width; "goalHeight" ==> content.Goal.Height
                      "thinWallX" ==> content.ThinWall.X; "thinWallY" ==> content.ThinWall.Y
                      "thinWallWidth" ==> content.ThinWall.Width; "thinWallHeight" ==> content.ThinWall.Height ])
        downloadArenaContent exportedContentJson
        announce "Playable arena content exported for authority startup"

handlePersistence <- function
    | BrowserPersistenceEvent.Ready -> persistence.Load storageKey
    | BrowserPersistenceEvent.Persisted _ -> announce "Scene persisted in browser storage"
    | BrowserPersistenceEvent.Loaded(_, Some stored) ->
        match SvgScene.deserialize stored.Payload with
        | Ok envelope when stored.SchemaVersion = 1 && stored.PayloadHash = hash envelope.Document ->
            let operations =
                [ SvgAuthoringOperation.ReplaceDocument envelope.Document
                  SvgAuthoringOperation.ReplaceSceneMetadata envelope.Metadata
                  for asset in envelope.Catalog.Assets do SvgAuthoringOperation.UpsertAsset asset
                  for instance in envelope.Instances do SvgAuthoringOperation.PutInstance instance ]
            commit "Persisted scene loaded" operations
            match compileArenaContent state.Metadata state.Document with
            | Ok content ->
                authoredContent <- content
                playState <- ArenaRules.createWith content |> ArenaRules.join "studio-player" ({ Col = content.Spawn.Col; Row = content.Spawn.Row }: Cell)
                announce "Persisted scene loaded"
            | Error issue -> announce ("Persisted scene loaded; gameplay unavailable: " + issue)
        | Ok _ -> announce "Validation error: persisted scene identity mismatch"
        | Error issues -> announce(sprintf "Validation error: persisted scene refused: %A" issues)
    | BrowserPersistenceEvent.Loaded(_, None) -> announce "No persisted scene"
    | BrowserPersistenceEvent.Failed(_, failure) -> announce($"Persistence refused: {failure}")
    | _ -> ()

do persistence.Load storageKey

let private verifyFont () =
    match SvgResourceInterchange.notoSansLatin400(notoBase64.Trim()) with
    | Ok resource ->
        let paint={Fill=Some{Red=15uy;Green=23uy;Blue=42uy;Alpha=255uy};Stroke=None;Opacity=1.0;Antialias=true;BlendMode=BlendMode.SrcOver;Shader=None;ColorFilter=ColorFilter.NoColorFilter;MaskFilter=MaskFilter.NoMaskFilter;ImageFilter=ImageFilter.NoImageFilter;PathEffect=PathEffect.NoPathEffect}
        let text={Id="verified-text";SemanticId=Some "verified-text";Visible=true;Transform=SvgAffine.identity;ClipId=None;MaskId=None;Presentation=None;Content=SvgElementContent.SceneLeaf{Nodes=[SceneNode.TextRun{Text="Offline Noto";Position={X=8.0;Y=24.0};Font={Family=Some resource.Family;Size=16.0;Weight=Some 400};Paint=paint}]}}
        let font={Id=resource.DefinitionId;Content=SvgDefinitionContent.Font{Family=resource.Family;Source=resource.FileName;Sha256=resource.Sha256;License=resource.License}}
        let document={state.Document with Definitions=font::state.Document.Definitions;Children=state.Document.Children@[text]}
        match SvgResourceInterchange.exportSvg "generated-offline" {Document=document;Fonts=[resource]} |> Result.bind(SvgResourceInterchange.importXml {AssetNamespace="generated-offline";DocumentId="generated-offline";Limits=SvgDocument.defaultLimits}) with
        | Error issues -> announce(sprintf "Validation error: %A" issues)
        | Ok restored when restored.Fonts=[resource] && restored.Document.Children.Length=document.Children.Length ->
            match SvgStudio.activateFont resource with
            | Ok activated -> announce "Verified Noto text exported and reopened offline"; (activated :> IDisposable).Dispose()
            | Error issues -> announce(sprintf "Validation error: %A" issues)
        | Ok _ -> announce "Validation error: verified resource roundtrip drifted"
    | Error issues -> announce(sprintf "Validation error: %A" issues)

let private booleanGeometry () =
    let path x = {Commands=[PathCommand.MoveTo {X=x;Y=8.0};PathCommand.LineTo {X=x+18.0;Y=8.0};PathCommand.LineTo {X=x+18.0;Y=26.0};PathCommand.LineTo {X=x;Y=26.0};PathCommand.Close];FillType=PathFillType.Winding}
    match SvgGeometry.prepare ("generated-boolean-"+string state.Revision) state.Revision PathOperation.Union [path 8.0] [path 16.0] SvgGeometry.defaultMaximumDeviation, host.GeometryWorker with
    | Ok prepared,Some worker ->
        match worker.Start(prepared,(fun result->match host.CommitGeometry(prepared,result) with Ok()->state<-host.State;announce "Boolean geometry committed once"|Error error->announce(sprintf "Validation error: %A" error)),(fun error->announce("Validation error: "+error))) with
        | Ok()->announce "Boolean geometry running"
        | Error error->announce("Validation error: "+error)
    | Error error,_->announce(sprintf "Validation error: %A" error)
    | _,None->announce "Validation error: geometry worker unavailable"

let private migrateLegacy () =
    match SvgScene.migrateLegacy state.Document state.Catalog state.Instances [] with
    | Ok migrated when migrated.Metadata.Entities.IsEmpty -> announce "Legacy document and catalog migrated additively"
    | Ok _ -> announce "Validation error: migration invented entity meaning"
    | Error issues -> announce(sprintf "Validation error: %A" issues)

let private addControl name action =
    let button: HTMLElement=document.createElement("button")
    button.setAttribute("type","button")
    button.setAttribute("aria-label",name)
    button.textContent<-name
    button.addEventListener("click",fun _->action())
    document.getElementById("generated-scene-actions").appendChild(button)|>ignore

[ "Start blank game",startBlankGame
  "Open starter game",openStarterGame
  "Draw playable vector shapes",drawPlayableShapes
  "Assign gameplay roles",assignGameplayRoles
  "Define interaction and win rules",defineGameplayRules
  "Rebind hazard and goal gameplay roles",rebindHazardAndGoalRoles
  "Save asset",saveAsset
  "Place two instances",placeInstances
  "Edit scene properties",editProperties
  "Author grid and freeform",authorGridAndFreeform
  "Move playable hazard far away",fun () -> movePlayableHazard "Playable hazard moved far away" { Col = 18; Row = 10 }
  "Move player spawn",movePlayerSpawn
  "Translate arena boundary",translateArenaUnsupported
  "Scale and rotate playable hazard",scaleAndRotatePlayableHazard
  "Move playable hazard into next step",fun () ->
      let current = playState.Room.Players.["studio-player"].Cell
      movePlayableHazard "Playable hazard moved into next step" { Col = current.Col + 1; Row = current.Row }
  "Play edited arena step",playEditedArenaStep
  "Move edited player left",fun () -> moveEditedPlayer -1 0
  "Move edited player right",fun () -> moveEditedPlayer 1 0
  "Move edited player up",fun () -> moveEditedPlayer 0 -1
  "Move edited player down",fun () -> moveEditedPlayer 0 1
  "Interact with edited arena",interactWithEditedArena
  "Restart edited arena",restartEditedArena
  "Create asset revision",reviseAsset
  "Resolve asset conflicts",resolveConflicts
  "Validate scene round-trip",validateRoundTrip
  "Save scene in browser",saveScene
  "Load scene from browser",loadScene
  "Export playable arena content",exportArenaContent
  "Verify Noto text",verifyFont
  "Run Boolean union",booleanGeometry
  "Migrate legacy content",migrateLegacy
  "Undo scene change",fun()->host.Undo()|>Result.iter(fun()->state<-host.State;announce "Undo completed")
  "Redo scene change",fun()->host.Redo()|>Result.iter(fun()->state<-host.State;announce "Redo completed") ]
|>List.iter(fun(name,action)->addControl name action)

#if SVG_INPUT_CANDIDATE
[ "Command palette", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-palette"; Source="pointer:control"; Command="workspace.palette" })
  "Possible input help", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-help"; Source="pointer:control"; Command="workspace.help" })
  "Rebind command", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-rebind"; Source="pointer:control"; Command="workspace.rebind" })
  "Close workspace overlay", fun () -> updateInput CommandResolverObservation.PopModal; updateWorkspace SvgWorkspaceMessage.CloseOverlay
  "Pointer workspace action", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-pointer"; Source="pointer:control"; Command="workspace.pointer" })
  "Touch workspace action", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-touch"; Source="pointer:control"; Command="workspace.touch" })
  "Gamepad workspace action", fun () -> handleInputEffect (CommandResolverEffect.InvokeCommand { EventId="accessible-gamepad"; Source="gamepad:accessible"; Command="workspace.gamepad" })
  "Collapse side docks", fun () -> updateWorkspace (SvgWorkspaceMessage.SetViewportWidth 640.0)
  "Restore side docks", fun () -> updateWorkspace (SvgWorkspaceMessage.SetViewportWidth 1200.0) ]
|> List.iter (fun (name, action) -> addControl name action)
#endif

let private snapshot () =
    createObj [ "revision" ==> state.Revision; "assets" ==> state.Catalog.Assets.Length
                "instances" ==> state.Instances.Length; "entities" ==> state.Metadata.Entities.Length
                "conflicts" ==> state.Conflicts.Length; "schema" ==> SvgScene.schema
                "sceneId" ==> state.Metadata.SceneId; "documentId" ==> state.Document.Id
                "contentHash" ==> hash state.Document; "playSourceHash" ==> playSourceHash; "exportedContentJson" ==> exportedContentJson
                "gameplayContentId" ==> (compileArenaContent state.Metadata state.Document |> Result.map _.ContentId |> Result.defaultValue ""); "crossContentRestoreRefused" ==> crossContentRestoreRefused
                "viewBox" ==> $"{state.Document.ViewBox.X},{state.Document.ViewBox.Y},{state.Document.ViewBox.Width},{state.Document.ViewBox.Height}"
                "playHealth" ==> playState.Status.Health; "playCollision" ==> playCollision
                "playScore" ==> playState.Status.Score; "playCollected" ==> playState.Status.Collected; "playOutcome" ==> playState.Status.Outcome
                "playPlayerCell" ==> (let cell = playState.Room.Players.["studio-player"].Cell in $"{cell.Col},{cell.Row}")
                "playCanonicalState" ==> ArenaRules.canonicalState playState
                "selectionCount" ==> host.Observe().SelectionCount; "activePlayPreview" ==> (host.Observe().ActiveGesture = Some playTransactionId)
                "camera" ==> $"{retainedCamera.E},{retainedCamera.F}"
#if SVG_INPUT_CANDIDATE
                "workspaceMode" ==> workspaceMode host.WorkspaceState.Mode
                "workspaceOverlay" ==> (host.WorkspaceState.Overlay |> Option.map string |> Option.defaultValue "")
                "collapsedPanelCount" ==> (host.WorkspaceState.Layout.Panels |> List.filter (fun panel -> panel.Effective = SvgPanelPlacement.Collapsed) |> List.length)
                "inputBindingCount" ==> inputAdapter.Value.State.Profile.Bindings.Length
                "inputLifecycle" ==> inputAdapter.Value.Observe()
#endif
#if SVG_REPLAY_CANDIDATE
                "replay" ==> replayStudio.Snapshot()
#endif
              ]

[<Emit("window.svgGeneratedStudio = $0")>]
let private expose (_value:obj) : unit = jsNative

expose (createObj [ "snapshot" ==> snapshot
                    "descriptorsValid" ==> (fun () -> SvgScene.validateDescriptors descriptors state.Metadata |> List.isEmpty)
                    "exerciseStorageFailure" ==> exerciseStorageFailure
                    "invalidImportPayload" ==> invalidImportPayload
#if SVG_INPUT_CANDIDATE
                    "pollGamepads" ==> (fun () -> inputAdapter.Value.PollGamepadsOnce())
                    "disposeInput" ==> (fun () -> (inputAdapter.Value :> IDisposable).Dispose())
#endif
                  ])
window.addEventListener("beforeunload",fun _->
#if SVG_INPUT_CANDIDATE
    inputAdapter |> Option.iter (fun value -> (value :> IDisposable).Dispose())
#endif
    (persistence :> IDisposable).Dispose()
    (host:>IDisposable).Dispose())
