module FableGameWorkspaceNamespace.SvgFoundation.Studio.Program

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema
#if SVG_INPUT_CANDIDATE
open FS.GG.UI.KeyboardInput
module WorkspaceCommands = FableGameWorkspaceNamespace.SvgFoundation.Studio.WorkspaceInput
#endif

[<ImportDefault("./vendor/noto-sans-latin-400-normal.woff2.base64?raw")>]
let private notoBase64: string = jsNative

[<Emit("new Worker(new URL('../SvgGeometryWorkerEntry.js', import.meta.url), { type:'module' })")>]
let private workerFactory () : obj = jsNative

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
let mutable private playSourceHash = ""
let mutable private playHealth = 3
let mutable private playCollision = false

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
                updateInput (CommandResolverObservation.ContextsChanged (SvgWorkspace.activeContexts host.WorkspaceState))
                match host.WorkspaceState.Overlay with
                | Some(SvgWorkspaceOverlay.CommandPalette restore) -> updateInput (CommandResolverObservation.PushModal { Context="workspace.palette"; RestoreFocus=restore })
                | Some(SvgWorkspaceOverlay.PossibleInputHelp restore) -> updateInput (CommandResolverObservation.PushModal { Context="workspace.help"; RestoreFocus=restore })
                | Some(SvgWorkspaceOverlay.RebindCommand(_, restore)) -> updateInput (CommandResolverObservation.BeginCapture restore)
                | None -> ()
                renderWorkspace ())
#endif

let private hash document = SvgAsset.contentHash document |> Result.defaultWith (fun issues -> failwithf "%A" issues)
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

let private movePlayableHazard () =
    commit "Playable hazard moved" [ SvgAuthoringOperation.TransformElements([ "hazard" ], SvgAffine.translate 8.0 -4.0) ]

let private playEditedArenaStep () =
    setMode SvgWorkspaceMode.Play
    playSourceHash <- hash state.Document
    playCollision <-
        state.Document.Children
        |> List.tryFind (fun element -> element.Id = "hazard")
        |> Option.exists (fun hazard -> hazard.Transform <> SvgAffine.identity)
    if playCollision then playHealth <- max 0 (playHealth - 1)
    commit "Edited arena play step" [ SvgAuthoringOperation.TransformElements([ "player" ], SvgAffine.translate 11.0 0.0) ]

let private saveReload () =
    let envelope={Schema=SvgScene.schema;Metadata=state.Metadata;Document=state.Document;Catalog=state.Catalog;Instances=state.Instances;Fonts=[]}
    match SvgScene.serialize envelope |> Result.bind SvgScene.deserialize with
    | Ok restored when restored.Metadata=state.Metadata && restored.Document=state.Document && restored.Catalog=state.Catalog && restored.Instances=state.Instances -> announce "Scene saved and reloaded"
    | Ok _ -> announce "Validation error: scene reload changed accepted content"
    | Error issues -> announce(sprintf "Validation error: %A" issues)

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
  "Move playable hazard",movePlayableHazard
  "Play edited arena step",playEditedArenaStep
  "Create asset revision",reviseAsset
  "Resolve asset conflicts",resolveConflicts
  "Save and reload scene",saveReload
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
                "contentHash" ==> hash state.Document; "playSourceHash" ==> playSourceHash
                "viewBox" ==> $"{state.Document.ViewBox.X},{state.Document.ViewBox.Y},{state.Document.ViewBox.Width},{state.Document.ViewBox.Height}"
                "playHealth" ==> playHealth; "playCollision" ==> playCollision
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
    (host:>IDisposable).Dispose())
