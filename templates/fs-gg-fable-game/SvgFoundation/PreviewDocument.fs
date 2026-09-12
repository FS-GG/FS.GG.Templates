module FableGameWorkspaceNamespace.PreviewDocument

open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.PreviewFont

let private color red green blue alpha =
    { Red = red; Green = green; Blue = blue; Alpha = alpha }

let private point x y = { X = x; Y = y }
let private rect x y width height = { X = x; Y = y; Width = width; Height = height }

let private paint value =
    { Fill = Some value
      Stroke = None
      Opacity = 1.0
      Antialias = true
      BlendMode = BlendMode.SrcOver
      Shader = None
      ColorFilter = ColorFilter.NoColorFilter
      MaskFilter = MaskFilter.NoMaskFilter
      ImageFilter = ImageFilter.NoImageFilter
      PathEffect = PathEffect.NoPathEffect }

let private leaf id semanticId scene =
    { Id = id
      SemanticId = semanticId
      Visible = true
      Transform = SvgAffine.identity
      ClipId = None
      MaskId = None
      Presentation = None
      Content = SvgElementContent.SceneLeaf scene }

let private maskChild id value =
    leaf id None { Nodes = [ SceneNode.Rectangle((0.0, 0.0, 1.0, 1.0), value) ] }

let private gradient =
    { Geometry = SvgGradientGeometry.Linear(point 0.0 0.0, point 1.0 1.0)
      Units = SvgCoordinateUnits.ObjectBoundingBox
      Transform = SvgAffine.compose (SvgAffine.rotateDegrees 18.0) (SvgAffine.skewXDegrees 7.0)
      Spread = SvgSpreadMethod.Reflect
      Stops =
        [ { Offset = 0.0; Color = color 29uy 78uy 216uy 255uy; StopOpacity = 1.0 }
          { Offset = 0.5; Color = color 20uy 184uy 166uy 255uy; StopOpacity = 0.85 }
          { Offset = 1.0; Color = color 249uy 115uy 22uy 255uy; StopOpacity = 1.0 } ]
      InheritFrom = None }

let private hole =
    { Commands =
        [ PathCommand.MoveTo(point 0.0 0.0)
          PathCommand.LineTo(point 38.0 0.0)
          PathCommand.LineTo(point 38.0 28.0)
          PathCommand.LineTo(point 0.0 28.0)
          PathCommand.Close
          PathCommand.MoveTo(point 10.0 8.0)
          PathCommand.LineTo(point 28.0 8.0)
          PathCommand.LineTo(point 28.0 20.0)
          PathCommand.LineTo(point 10.0 20.0)
          PathCommand.Close ]
      FillType = PathFillType.EvenOdd }

let private presentation =
    { FillSource = Some(SvgPaintSource.Definition "preview-gradient")
      StrokeStyle =
        Some
            { Source = SvgPaintSource.Solid(color 15uy 23uy 42uy 255uy)
              Width = 1.5
              Cap = StrokeCap.Round
              Join = StrokeJoin.RoundJoin
              Miter = 4.0
              Dash = [ 3.0; 2.0 ]
              DashOffset = 0.5 }
      OverallOpacity = 1.0
      FillRule = PathFillType.EvenOdd }

let document =
    let symbolChild =
        leaf "preview-symbol-shape" None
            { Nodes = [ SceneNode.Circle(point 6.0 6.0, 5.5, color 250uy 204uy 21uy 255uy) ] }
    let gridCells =
        [ for row in 0 .. 1 do
              for column in 0 .. 2 do
                  let id = $"preview-grid-{column}-{row}"
                  yield
                      leaf id (Some $"semantic:grid:{column}:{row}")
                          { Nodes =
                              [ SceneNode.Rectangle(
                                  (float column * 19.0, float row * 19.0, 17.0, 17.0),
                                  color 226uy 232uy 240uy 255uy) ] } ]
    let gridGroup =
        { leaf "preview-grid" None { Nodes = [] } with
            Transform = SvgAffine.translate 7.0 7.0
            Content = SvgElementContent.Group gridCells }
    let fractionalPath =
        { leaf "preview-fractional-route" (Some "semantic:fractional-route")
            { Nodes = [ SceneNode.Path(hole, paint (color 29uy 78uy 216uy 255uy)) ] } with
            Transform =
                SvgAffine.compose
                    (SvgAffine.translate 72.5 10.25)
                    (SvgAffine.compose (SvgAffine.rotateDegrees 4.0) (SvgAffine.scale 1.15 1.1))
            ClipId = Some "preview-nested-clip"
            MaskId = Some "preview-alpha-mask"
            Presentation = Some presentation }
    let luminance =
        { leaf "preview-luminance" (Some "semantic:luminance")
            { Nodes = [ SceneNode.Circle(point 139.25 25.5, 13.25, color 124uy 58uy 237uy 255uy) ] } with
            MaskId = Some "preview-luminance-mask" }
    let symbol =
        { leaf "preview-symbol-instance" (Some "semantic:symbol") { Nodes = [] } with
            Transform = SvgAffine.translate 151.5 11.75
            Content = SvgElementContent.SymbolInstance("preview-symbol", Some(rect 0.0 0.0 28.0 28.0)) }
    let label =
        leaf "preview-label" (Some "semantic:label")
            { Nodes =
                [ SceneNode.TextRun
                    { Text = "Grid + fractional SVG"
                      Position = point 7.25 72.5
                      Font = { Family = Some family; Size = 12.0; Weight = Some 400 }
                      Paint = paint (color 15uy 23uy 42uy 255uy) } ] }
    { Schema = SvgDocument.schema
      Id = "preview-a-generated-consumer"
      ViewBox = rect 0.0 0.0 190.0 84.0
      Definitions =
        [ { Id = "preview-gradient"; Content = SvgDefinitionContent.Gradient gradient }
          { Id = "preview-symbol"; Content = SvgDefinitionContent.Symbol(Some(rect 0.0 0.0 12.0 12.0), [ symbolChild ]) }
          { Id = "preview-base-clip"
            Content = SvgDefinitionContent.Clip(SvgCoordinateUnits.UserSpaceOnUse, [ SvgClipShape.Rectangle(rect 0.0 0.0 40.0 30.0) ]) }
          { Id = "preview-nested-clip"
            Content =
                SvgDefinitionContent.Clip(
                    SvgCoordinateUnits.UserSpaceOnUse,
                    [ SvgClipShape.Intersection [ "preview-base-clip" ]; SvgClipShape.Path hole ]) }
          { Id = "preview-alpha-mask"
            Content =
                SvgDefinitionContent.Mask(
                    SvgCoordinateUnits.ObjectBoundingBox,
                    rect 0.0 0.0 1.0 1.0,
                    SvgMaskKind.Alpha,
                    [ maskChild "preview-alpha-mask-shape" (color 255uy 255uy 255uy 210uy) ]) }
          { Id = "preview-luminance-mask"
            Content =
                SvgDefinitionContent.Mask(
                    SvgCoordinateUnits.ObjectBoundingBox,
                    rect 0.0 0.0 1.0 1.0,
                    SvgMaskKind.Luminance,
                    [ maskChild "preview-luminance-mask-shape" (color 190uy 190uy 190uy 255uy) ]) }
          { Id = "preview-font"
            Content = SvgDefinitionContent.Font { Family = family; Source = source; Sha256 = sha256; License = "OFL-1.1" } } ]
      Children = [ gridGroup; fractionalPath; luminance; symbol; label ] }

let selectedState () =
    match SvgDocumentInteraction.tryCreate 0 SvgAffine.identity document with
    | Error error -> failwithf "Preview-A document state failed: %A" error
    | Ok initial ->
        let result =
            SvgDocumentInteraction.update
                (SvgDocumentInteractionMessage.SelectSemantic(0, "semantic:fractional-route"))
                initial
        match result.Error with
        | Some error -> failwithf "Preview-A semantic selection failed: %A" error
        | None -> result.State

let verifyPortable () =
    let serialized =
        match SvgDocument.serialize document with
        | Ok value -> value
        | Error issues -> failwithf "Preview-A document serialization failed: %A" issues
    let restored =
        match SvgDocument.deserialize serialized with
        | Ok value -> value
        | Error issues -> failwithf "Preview-A document round trip failed: %A" issues
    if SvgDocument.serialize restored <> Ok serialized then failwith "Preview-A canonical document round trip drifted"
    let exported =
        match SvgDocument.exportSvg "generated-preview" restored with
        | Ok value -> value
        | Error issues -> failwithf "Preview-A SVG export failed: %A" issues
    for token in [ "<linearGradient"; "<clipPath"; "<mask"; "<symbol"; "<use"; "<text"; "matrix(" ] do
        if not (exported.Contains token) then failwithf "Preview-A SVG export omitted %s" token
    let state = selectedState ()
    if state.SelectedSemanticId <> Some "semantic:fractional-route" then failwith "Preview-A selection drifted"
    serialized, exported, state
