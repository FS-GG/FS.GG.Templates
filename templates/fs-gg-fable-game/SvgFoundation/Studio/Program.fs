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

[<Emit("(function(text){const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='arena-content.v2.json';a.click();URL.revokeObjectURL(url);})($0)")>]
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
let mutable private authoredContent = compileArenaContent state.Document |> Result.defaultWith failwith
let mutable private playState = ArenaRules.create () |> ArenaRules.join "studio-player" ({ Col = 0; Row = 0 }: Cell)
let mutable private playCollision = false
let mutable private exportedContentJson = ""
let private playTransactionId = "studio-play-runtime"
let mutable private playFrozenDocument: SvgDocument option = None

#if SVG_REPLAY_CANDIDATE
let private replayStudio = ReplayStudio.mount announce
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

let private movePlayableHazard label target =
    let next = ArenaContent.withHazardCell target authoredContent
    let dx = next.Hazard.X - authoredContent.Hazard.X
    let dy = next.Hazard.Y - authoredContent.Hazard.Y
    commit label [ SvgAuthoringOperation.TransformElements([ "hazard" ], SvgAffine.translate dx dy) ]
    authoredContent <- compileArenaContent state.Document |> Result.defaultWith failwith
    playState <- ArenaRules.withDefinition authoredContent playState

let private scaleAndRotatePlayableHazard () =
    let pivotX = authoredContent.Hazard.X + authoredContent.Hazard.Width / 2.0
    let pivotY = authoredContent.Hazard.Y + authoredContent.Hazard.Height / 2.0
    let transform =
        SvgAffine.compose
            (SvgAffine.translate pivotX pivotY)
            (SvgAffine.compose
                (SvgAffine.rotateDegrees 12.0)
                (SvgAffine.compose (SvgAffine.scale 1.25 0.8) (SvgAffine.translate -pivotX -pivotY)))
    commit "Playable hazard scaled and rotated" [ SvgAuthoringOperation.TransformElements([ "hazard" ], transform) ]
    authoredContent <- compileArenaContent state.Document |> Result.defaultWith failwith
    playState <- ArenaRules.withDefinition authoredContent playState

let private playEditedArenaStep () =
    setMode SvgWorkspaceMode.Play
    let frozenDocument =
        match playFrozenDocument with
        | Some document -> document
        | None ->
            let frozen = SvgAuthoring.takePlaySnapshot state.Revision state |> Result.defaultWith (fun error -> failwithf "%A" error)
            let document = SvgDocument.deserialize frozen.PlaySnapshot.Value.SerializedDocument |> Result.defaultWith (fun issues -> failwithf "%A" issues)
            playFrozenDocument <- Some document
            document
    let frozenContent = compileArenaContent frozenDocument |> Result.defaultWith failwith
    playState <- ArenaRules.withDefinition frozenContent playState
    playSourceHash <- hash frozenDocument
    let current = playState.Room.Players.["studio-player"].Cell
    let target: ArenaContent.ArenaCell = { Col = min (ArenaContent.arenaColumns - 1) (current.Col + 1); Row = current.Row }
    let beforeHealth = playState.Status.Health
    playState <- ArenaRules.applyIntent "studio-player" (ArenaRules.Intent.Move target) playState
    playState <- ArenaRules.advance playState
    playCollision <- playState.Status.Health < beforeHealth
    host.CancelGesture playTransactionId |> ignore
    let current = ArenaRules.currentContent playState
    let player = playState.Room.Players.["studio-player"].Cell
    let runtimeDocument =
        { frozenDocument with
            Children =
                frozenDocument.Children
                |> List.map (fun element ->
                    match element.Id with
                    | "player" -> { element with Transform = SvgAffine.translate (ArenaContent.cellX { Col = player.Col; Row = player.Row }) (ArenaContent.cellY { Col = player.Col; Row = player.Row }) }
                    | "hazard" ->
                        let delta = SvgAffine.translate (current.Hazard.X - frozenContent.Hazard.X) (current.Hazard.Y - frozenContent.Hazard.Y)
                        { element with Transform = SvgAffine.compose delta element.Transform }
                    | _ -> element) }
    host.Preview { Schema = SvgAuthoring.transactionSchema; Id = playTransactionId; Operations = [ SvgAuthoringOperation.ReplaceDocument runtimeDocument ] }
    |> Result.defaultWith (fun error -> failwithf "%A" error)
    announce "Edited arena play step"

let private validateRoundTrip () =
    let envelope={Schema=SvgScene.schema;Metadata=state.Metadata;Document=state.Document;Catalog=state.Catalog;Instances=state.Instances;Fonts=[]}
    match SvgScene.serialize envelope |> Result.bind SvgScene.deserialize with
    | Ok restored when
        restored.Metadata = state.Metadata && restored.Catalog = state.Catalog && restored.Instances = state.Instances &&
        hash restored.Document = hash state.Document ->
        announce "Scene round-trip validated"
    | Ok _ -> announce "Validation error: scene reload changed accepted content"
    | Error issues -> announce(sprintf "Validation error: %A" issues)

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

let private exportArenaContent () =
    let content = authoredContent
    exportedContentJson <-
        JS.JSON.stringify(
            createObj
                [ "schemaVersion" ==> content.SchemaVersion
                  "contentId" ==> content.ContentId
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
            authoredContent <- compileArenaContent state.Document |> Result.defaultWith failwith
            playState <- ArenaRules.withDefinition authoredContent playState
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

[ "Save asset",saveAsset
  "Place two instances",placeInstances
  "Edit scene properties",editProperties
  "Author grid and freeform",authorGridAndFreeform
  "Move playable hazard far away",fun () -> movePlayableHazard "Playable hazard moved far away" { Col = 18; Row = 10 }
  "Scale and rotate playable hazard",scaleAndRotatePlayableHazard
  "Move playable hazard into next step",fun () ->
      let current = playState.Room.Players.["studio-player"].Cell
      movePlayableHazard "Playable hazard moved into next step" { Col = current.Col + 1; Row = current.Row }
  "Play edited arena step",playEditedArenaStep
  "Create asset revision",reviseAsset
  "Resolve asset conflicts",resolveConflicts
  "Validate scene round-trip",validateRoundTrip
  "Save scene in browser",saveScene
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
                "viewBox" ==> $"{state.Document.ViewBox.X},{state.Document.ViewBox.Y},{state.Document.ViewBox.Width},{state.Document.ViewBox.Height}"
                "playHealth" ==> playState.Status.Health; "playCollision" ==> playCollision
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
