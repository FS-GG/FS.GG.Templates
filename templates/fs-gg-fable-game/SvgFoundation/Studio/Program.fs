module FableGameWorkspaceNamespace.SvgFoundation.Studio.Program

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema

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
  "Create asset revision",reviseAsset
  "Resolve asset conflicts",resolveConflicts
  "Save and reload scene",saveReload
  "Verify Noto text",verifyFont
  "Run Boolean union",booleanGeometry
  "Migrate legacy content",migrateLegacy
  "Undo scene change",fun()->host.Undo()|>Result.iter(fun()->state<-host.State;announce "Undo completed")
  "Redo scene change",fun()->host.Redo()|>Result.iter(fun()->state<-host.State;announce "Redo completed") ]
|>List.iter(fun(name,action)->addControl name action)

let private snapshot () =
    createObj [ "revision" ==> state.Revision; "assets" ==> state.Catalog.Assets.Length
                "instances" ==> state.Instances.Length; "entities" ==> state.Metadata.Entities.Length
                "conflicts" ==> state.Conflicts.Length; "schema" ==> SvgScene.schema ]

[<Emit("window.svgGeneratedStudio = $0")>]
let private expose (_value:obj) : unit = jsNative

expose (createObj [ "snapshot" ==> snapshot; "descriptorsValid" ==> (fun () -> SvgScene.validateDescriptors descriptors state.Metadata |> List.isEmpty) ])
window.addEventListener("beforeunload",fun _->(host:>IDisposable).Dispose())
