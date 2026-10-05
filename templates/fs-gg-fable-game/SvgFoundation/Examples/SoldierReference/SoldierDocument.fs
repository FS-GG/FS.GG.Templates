module FableGameWorkspaceNamespace.SoldierDocument

open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.SoldierWorkload

let assetId = "templates-original-equipped-soldier"
let assetVersion = "1.0.0"
let assetLicense = "MIT"
let glyphBounds: Rect = { X = 0.; Y = 0.; Width = 48.; Height = 64. }
let private color r g b = { Red = r; Green = g; Blue = b; Alpha = 255uy }
let private ink = color 24uy 34uy 43uy
let private skin = color 220uy 174uy 132uy
let private steel = color 91uy 108uy 119uy
let private boot = color 41uy 47uy 51uy
let private paint fill =
    { Fill = Some fill; Stroke = None; Opacity = 1.; Antialias = true
      BlendMode = BlendMode.SrcOver; Shader = None; ColorFilter = ColorFilter.NoColorFilter
      MaskFilter = MaskFilter.NoMaskFilter; ImageFilter = ImageFilter.NoImageFilter; PathEffect = PathEffect.NoPathEffect }
let private element id semantic content =
    { Id = id; SemanticId = semantic; Visible = true; Transform = SvgAffine.identity
      ClipId = None; MaskId = None; Presentation = None; Content = content }
let private leaf id nodes = element id None (SvgElementContent.SceneLeaf { Nodes = nodes })
let private polygon id fill coordinates =
    let points = coordinates |> List.map (fun (x, y) -> { X = x; Y = y })
    let commands = PathCommand.MoveTo points.Head :: ((points.Tail |> List.map PathCommand.LineTo) @ [ PathCommand.Close ])
    leaf id [ SceneNode.Path({ Commands = commands; FillType = PathFillType.Winding }, paint fill) ]
let private rectangle id fill x y w h = leaf id [ SceneNode.Rectangle((x, y, w, h), fill) ]

let definitionId revision faction pose =
    let factionName = match faction with Faction.Blue -> "blue" | Faction.Amber -> "amber"
    let poseName = match pose with Pose.Ready -> "ready" | Pose.March -> "march" | Pose.Kneel -> "kneel"
    sprintf "soldier-r%d-%s-%s" revision factionName poseName

// Original geometry authored for this reference. No traced or imported source art.
// Helmet, face/visor, backpack, shoulder pads, vest/pouches, gloves, rifle and articulated boots.
let private glyph revision faction pose =
    let prefix = definitionId revision faction pose
    let path name fill coordinates = polygon (prefix + "-" + name) fill coordinates
    let rect name fill x y w h = rectangle (prefix + "-" + name) fill x y w h
    let uniform = match faction, revision with
                  | Faction.Blue, 1 -> color 49uy 104uy 157uy
                  | Faction.Blue, _ -> color 57uy 120uy 171uy
                  | Faction.Amber, 1 -> color 177uy 121uy 42uy
                  | Faction.Amber, _ -> color 191uy 139uy 52uy
    let armour = match faction with Faction.Blue -> color 72uy 83uy 91uy | Faction.Amber -> color 98uy 86uy 64uy
    [ // Feet/legs are authored pose variants, not instance paint inheritance.
      match pose with
      | Pose.Ready ->
          yield path "left-leg" uniform [ (17.,39.);(24.,40.);(23.,56.);(16.,56.) ]
          yield path "right-leg" uniform [ (25.,40.);(31.,39.);(33.,56.);(26.,56.) ]
          yield path "left-boot" boot [ (16.,54.);(23.,54.);(23.,61.);(12.,61.);(12.,58.) ]
          yield path "right-boot" boot [ (26.,54.);(33.,54.);(37.,58.);(37.,61.);(26.,61.) ]
      | Pose.March ->
          yield path "left-leg" uniform [ (17.,39.);(24.,40.);(19.,49.);(13.,57.);(7.,54.) ]
          yield path "right-leg" uniform [ (25.,40.);(31.,39.);(35.,49.);(32.,57.);(26.,55.);(28.,49.) ]
          yield path "left-boot" boot [ (7.,53.);(14.,56.);(12.,62.);(3.,58.);(3.,55.) ]
          yield path "right-boot" boot [ (26.,53.);(33.,55.);(38.,59.);(37.,62.);(25.,59.) ]
      | Pose.Kneel ->
          yield path "left-leg" uniform [ (17.,39.);(24.,40.);(17.,48.);(23.,52.);(20.,58.);(9.,50.) ]
          yield path "right-leg" uniform [ (25.,40.);(31.,39.);(36.,47.);(33.,57.);(27.,56.);(29.,48.) ]
          yield path "left-boot" boot [ (18.,52.);(24.,54.);(23.,61.);(15.,61.);(15.,58.) ]
          yield path "right-boot" boot [ (27.,54.);(34.,54.);(40.,58.);(40.,61.);(27.,61.) ]
      yield path "backpack" ink [ (10.,20.);(17.,18.);(20.,24.);(18.,39.);(9.,37.);(7.,28.) ]
      yield rect "pack-panel" armour 9. 25. 7. 9.
      yield path "torso" uniform [ (17.,18.);(29.,18.);(34.,25.);(31.,41.);(16.,41.);(13.,25.) ]
      yield path "vest" armour [ (18.,20.);(28.,20.);(30.,38.);(17.,38.) ]
      yield rect "vest-seam" steel 22. 23. 2. 12.
      yield rect "left-pouch" ink 17. 30. 5. 7.
      yield rect "right-pouch" ink 25. 30. 5. 7.
      yield path "left-arm" uniform [ (14.,20.);(19.,24.);(14.,31.);(23.,34.);(21.,39.);(8.,34.);(8.,28.) ]
      yield path "right-arm" uniform [ (28.,20.);(34.,21.);(39.,29.);(34.,35.);(29.,32.);(32.,28.) ]
      yield path "rifle-stock" boot [ (15.,34.);(21.,30.);(25.,31.);(19.,39.);(16.,39.) ]
      yield path "rifle-body" ink [ (21.,29.);(38.,23.);(40.,27.);(26.,33.);(25.,38.);(21.,37.);(22.,33.) ]
      yield path "rifle-barrel" steel [ (37.,23.);(44.,20.);(45.,22.);(39.,26.) ]
      yield path "rifle-sight" ink [ (34.,23.);(33.,20.);(36.,19.);(38.,22.) ]
      yield path "left-glove" skin [ (19.,33.);(23.,31.);(26.,34.);(23.,38.);(20.,38.) ]
      yield path "right-glove" skin [ (33.,28.);(37.,26.);(39.,29.);(36.,33.);(32.,32.) ]
      yield rect "neck" skin 20. 15. 8. 6.
      yield path "face" skin [ (17.,7.);(29.,7.);(31.,13.);(28.,19.);(20.,19.);(16.,14.) ]
      yield path "helmet" armour [ (13.,10.);(14.,5.);(19.,2.);(28.,2.);(33.,6.);(34.,11.);(29.,13.);(15.,13.) ]
      yield rect "visor" ink 19. 10. 13. 3.
      yield rect "helmet-band" uniform 15. 7. 17. 2.
      yield rect "belt" boot 16. 38. 15. 3.
      yield rect "buckle" steel 22. 38. 3. 3. ]

let private buildDefinitions revision =
    [ for faction in [ Faction.Blue; Faction.Amber ] do
        for pose in [ Pose.Ready; Pose.March; Pose.Kneel ] do
            yield { Id = definitionId revision faction pose
                    Content = SvgDefinitionContent.Symbol(Some glyphBounds,
                        [ leaf (definitionId revision faction pose + "-geometry")
                            (glyph revision faction pose |> List.collect (fun element ->
                                match element.Content with
                                | SvgElementContent.SceneLeaf scene -> scene.Nodes
                                | _ -> failwith "Authored glyph must be Scene leaves")) ]) } ]

// Immutable definition sets are allocated once per supported asset revision.
let private revisionOne = buildDefinitions 1
let private revisionTwo = buildDefinitions 2
let definitions revision = if revision = 1 then revisionOne else revisionTwo

let assetDocumentFor revision =
    { Schema = SvgDocument.schema; Id = assetId; ViewBox = glyphBounds
      Definitions = definitions revision
      Children = [ element "asset-preview" None (SvgElementContent.SymbolInstance(definitionId revision Faction.Blue Pose.Ready, Some glyphBounds)) ] }

let assetDocument = assetDocumentFor 1

let private soldierElement revision presentation (soldier: Soldier) =
    let art =
        { element (soldier.Id + "-art") None (SvgElementContent.SymbolInstance(definitionId revision soldier.Faction soldier.Pose, Some glyphBounds)) with
            Transform = SvgAffine.compose (SvgAffine.rotateDegrees soldier.FacingDegrees) (SvgAffine.translate -24. -32.) }
    let health =
        leaf (soldier.Id + "-health")
            [ SceneNode.Rectangle((-24., -39., 48. * float soldier.Health / 100., 4.), color 81uy 190uy 112uy) ]
    let ring suffix fill =
        // Four thin bars form a bounded frame; avoid painting over the equipment.
        leaf (soldier.Id + suffix)
            [ SceneNode.Rectangle((-27., -43., 54., 2.), fill); SceneNode.Rectangle((-27., 34., 54., 2.), fill)
              SceneNode.Rectangle((-27., -41., 2., 75.), fill); SceneNode.Rectangle((25., -41., 2., 75.), fill) ]
    let children =
        [ yield art; yield health
          if presentation.Selected = Some soldier.Id then yield ring "-selected" (color 255uy 229uy 99uy)
          if presentation.Focused = Some soldier.Id then yield ring "-focused" (color 244uy 244uy 255uy) ]
    { element soldier.Id (Some soldier.Id) (SvgElementContent.Group children) with
        Transform = SvgAffine.translate soldier.Position.X soldier.Position.Y }

let project state =
    match validateState state with
    | issue :: issues -> Error (issue :: issues)
    | [] ->
        let document =
            { Schema = SvgDocument.schema; Id = "soldier-reference-v1"
              ViewBox = { X = 0.; Y = 0.; Width = 1664.; Height = 3264. }
              Definitions = definitions state.Workload.DefinitionRevision
              Children =
                [ { element "soldier-world" None
                            (SvgElementContent.Group(state.Workload.Soldiers |> List.map (soldierElement state.Workload.DefinitionRevision state.Presentation))) with
                        Transform = state.Presentation.Camera } ] }
        match SvgDocument.serialize document with
        | Error issues -> Error (issues |> List.map _.Code)
        | Ok _ -> Ok document

// View filtering preserves accepted input/draw order and pins selected/focused product IDs.
// Full content remains a separate immutable value for export.
let displaySubset visibleIds (presentation: Presentation) (document: SvgDocument) =
    let pinned = [ presentation.Selected; presentation.Focused ] |> List.choose id |> Set.ofList
    let allowed = Set.union visibleIds pinned
    let children =
        document.Children |> List.map (fun world ->
            match world.Content with
            | SvgElementContent.Group children ->
                { world with Content = SvgElementContent.Group(children |> List.filter (fun child -> Set.contains child.Id allowed)) }
            | _ -> world)
    { document with Children = children }

type AcceptedProjection = { Full: SvgDocument; Display: SvgDocument; ExportedSvg: string }

let tryAccept state visibleIds previous =
    match project state with
    | Error issues -> previous, Some issues
    | Ok document ->
        let display = displaySubset visibleIds state.Presentation document
        match SvgDocument.serialize display, SvgDocument.exportSvg "soldier-reference" document with
        | Ok _, Ok svg -> Some { Full = document; Display = display; ExportedSvg = svg }, None
        | Error issues, _ | _, Error issues -> previous, Some (issues |> List.map _.Code)
