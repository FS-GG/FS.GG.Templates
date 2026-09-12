module FableGameWorkspaceNamespace.TacticalCompatibilityTests

open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.TacticalCompatibility

let private require condition message = if not condition then failwith message

let run () =
    // This value represents undisclosed source truth. The adapter cannot receive it because its input
    // contract contains disclosed presentation values only.
    let undisclosedFact = "undisclosed-contact-at-grid-9"
    let baselineInput = characterizedProjection 41 "shared-scene:41"
    let baseline = baselineInput |> project
    let revised = characterizedProjection 42 "shared-scene:42" |> project
    let rejectedSelection =
        { baselineInput with
            Selection = { SelectedObjectId = Some undisclosedFact; FocusedObjectId = Some undisclosedFact } }
        |> project

    require (baseline.RevisionIdentity = "shared-scene:41" && baseline.Scene.Revision = 41) "revision identity changed"
    require (baseline.Scene.Layers |> List.map _.Id = [ "terrain"; "units"; "commands" ]) "layer order changed"
    require
        (baseline.Layers =
            [ { Id = "terrain"; Order = 10; Visible = true; Locked = true }
              { Id = "units"; Order = 20; Visible = true; Locked = false }
              { Id = "commands"; Order = 30; Visible = false; Locked = false } ])
        "layer visibility or lock characterization changed"
    require (baseline.Scene.Camera = { PanX = 13.5; PanY = -4.25; Zoom = 1.75 }) "camera changed"
    require (baseline.Interaction.SelectedObjectId = Some "unit:7") "selection changed"
    require (baseline.Interaction.FocusedObjectId = Some "unit:11") "focus changed"
    require
        (rejectedSelection.Interaction.SelectedObjectId.IsNone && rejectedSelection.Interaction.FocusedObjectId.IsNone)
        "an identity absent from disclosed visible objects entered selection or focus"
    let baselineIds = baseline.Scene.Layers |> List.collect _.Objects |> List.map _.Id
    let revisedIds = revised.Scene.Layers |> List.collect _.Objects |> List.map _.Id
    require (baselineIds = revisedIds) "semantic identities changed across revision"

    let replacement = SvgRetained.update (RetainedInteractionMessage.ReplaceScene revised.Scene) baseline.Interaction
    require replacement.Error.IsNone "supported revision replacement failed"
    require (replacement.State.SelectedObjectId = Some "unit:7") "selection was not retained across revision"
    require (replacement.State.FocusedObjectId = Some "unit:11") "focus was not retained across revision"

    let accessible = accessibleProjection baseline
    require (accessible |> List.map fst = [ "unit:7"; "unit:11" ]) "accessible disclosed identities changed"
    require
        (accessible |> List.forall (fun (id, label) -> id <> undisclosedFact && not (label.Contains undisclosedFact)))
        "undisclosed fact entered the accessible projection"
    require
        (baseline.Scene.Layers
         |> List.collect _.Objects
         |> List.forall (fun value -> value.Id <> undisclosedFact && not (value.AccessibleLabel.Contains undisclosedFact)))
        "undisclosed fact entered the retained scene"

    let serialized, exported, previewState = PreviewDocument.verifyPortable ()
    require (serialized.Contains SvgDocument.schema) "Preview-A canonical serialization lost its schema"
    require (previewState.SelectedSemanticId = Some "semantic:fractional-route") "Preview-A semantic selection changed"
    require (PreviewDocument.document.Definitions.Length = 7) "Preview-A definition surface changed"
    for token in [ "linearGradient"; "clipPath"; "mask-type:alpha"; "mask-type:luminance"; "symbol"; "font-face" ] do
        require (exported.Contains token) $"Preview-A export omitted {token}"

    baseline

[<EntryPoint>]
let main _ =
    run () |> ignore
    printfn "tactical-compatibility: identities=passed layers=passed camera=passed selection-focus=passed disclosure=passed revisions=passed preview-document=passed"
    0
