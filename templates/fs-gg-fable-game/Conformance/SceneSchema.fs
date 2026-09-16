module FableGameWorkspaceNamespace.SvgFoundation.Studio.SceneSchema

open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.ArenaContent

let descriptors =
    [
        {
            KindId = "gameplay.role"
            DisplayName = "Playable game role"
            Properties =
                [
                    {
                        Key = "role"
                        Kind = SvgScenePropertyKind.Text
                        Required = true
                    }
                    {
                        Key = "interaction"
                        Kind = SvgScenePropertyKind.Text
                        Required = true
                    }
                ]
        }
        {
            KindId = "sample.terrain"
            DisplayName = "Terrain region"
            Properties =
                [
                    {
                        Key = "terrain"
                        Kind = SvgScenePropertyKind.Text
                        Required = true
                    }
                    {
                        Key = "cost"
                        Kind = SvgScenePropertyKind.Number
                        Required = true
                    }
                ]
        }
        {
            KindId = "sample.boundary"
            DisplayName = "Boundary"
            Properties =
                [
                    {
                        Key = "closed"
                        Kind = SvgScenePropertyKind.Flag
                        Required = true
                    }
                ]
        }
        {
            KindId = "sample.object"
            DisplayName = "Object"
            Properties =
                [
                    {
                        Key = "position"
                        Kind = SvgScenePropertyKind.Coordinate
                        Required = true
                    }
                    {
                        Key = "label"
                        Kind = SvgScenePropertyKind.Text
                        Required = false
                    }
                ]
        }
    ]

/// Product-owned grid adapter: region and boundary meaning stays outside Rendering.
let gridAdapter existing =
    { existing with
        Grid =
            Some
                {
                    Origin = { X = 3.0; Y = 5.0 }
                    Step = { X = 8.0; Y = 8.0 }
                }
        Entities =
            existing.Entities
            @ [
                {
                    EntityId = "sample-grid-region"
                    KindId = "sample.terrain"
                    VisualElementId = None
                    PrefabInstanceId = Some "sample-instance-a"
                    Properties =
                        [
                            {
                                Key = "terrain"
                                Value = SvgScenePropertyValue.Text "walkable"
                            }
                            {
                                Key = "cost"
                                Value = SvgScenePropertyValue.Number 1.0
                            }
                        ]
                }
                {
                    EntityId = "sample-grid-boundary"
                    KindId = "sample.boundary"
                    VisualElementId = None
                    PrefabInstanceId = Some "sample-instance-a"
                    Properties =
                        [
                            {
                                Key = "closed"
                                Value = SvgScenePropertyValue.Flag true
                            }
                        ]
                }
            ]
    }

/// Product-owned continuous adapter: fractional placement remains exact scene metadata.
let continuousAdapter existing =
    { existing with
        Entities =
            existing.Entities
            @ [
                {
                    EntityId = "sample-freeform-object"
                    KindId = "sample.object"
                    VisualElementId = None
                    PrefabInstanceId = Some "sample-instance-b"
                    Properties =
                        [
                            {
                                Key = "position"
                                Value = SvgScenePropertyValue.Coordinate { X = 121.375; Y = 66.625 }
                            }
                            {
                                Key = "label"
                                Value = SvgScenePropertyValue.Text "freeform"
                            }
                        ]
                }
            ]
    }

let private color red green blue =
    {
        Red = red
        Green = green
        Blue = blue
        Alpha = 255uy
    }

let private leaf id nodes =
    {
        Id = id
        SemanticId = Some("arena:" + id)
        Visible = true
        Transform = SvgAffine.identity
        ClipId = None
        MaskId = None
        Presentation = None
        Content = SvgElementContent.SceneLeaf { Nodes = nodes }
    }

/// The Studio opens the same editable arena content used by the production player.
let arenaDocument =
    let content = contentAt 1UL

    {
        Schema = SvgDocument.schema
        Id = "continuous-arena"
        ViewBox =
            {
                X = 0.0
                Y = 0.0
                Width = arenaWidth
                Height = arenaHeight
            }
        Definitions = []
        Children =
            [
                leaf
                    "arena"
                    [
                        SceneNode.Rectangle((0.0, 0.0, arenaWidth, arenaHeight), color 241uy 245uy 249uy)
                    ]
                leaf
                    "collectible"
                    [
                        SceneNode.Circle(
                            {
                                X = content.CollectibleX
                                Y = content.CollectibleY
                            },
                            5.0,
                            color 245uy 158uy 11uy
                        )
                    ]
                leaf
                    "hazard"
                    [
                        SceneNode.Rectangle(
                            (content.Hazard.X, content.Hazard.Y, content.Hazard.Width, content.Hazard.Height),
                            color 220uy 38uy 38uy
                        )
                    ]
                leaf
                    "goal"
                    [
                        SceneNode.Rectangle(
                            (content.Goal.X, content.Goal.Y, content.Goal.Width, content.Goal.Height),
                            color 22uy 163uy 74uy
                        )
                    ]
                leaf
                    "thin-wall"
                    [
                        SceneNode.Rectangle(
                            (content.ThinWall.X, content.ThinWall.Y, content.ThinWall.Width, content.ThinWall.Height),
                            color 71uy 85uy 105uy
                        )
                    ]
                leaf
                    "player"
                    [
                        SceneNode.Rectangle((playerStartX, playerStartY, 10.0, 10.0), color 37uy 99uy 235uy)
                    ]
            ]
    }

let gameplayMetadata sceneId (visualIds: string array) =
    let entity role interaction visualId =
        {
            EntityId = "gameplay:" + role
            KindId = "gameplay.role"
            VisualElementId = Some visualId
            PrefabInstanceId = None
            Properties =
                [
                    {
                        Key = "role"
                        Value = SvgScenePropertyValue.Text role
                    }
                    {
                        Key = "interaction"
                        Value = SvgScenePropertyValue.Text interaction
                    }
                ]
        }

    {
        SceneId = sceneId
        Layers = []
        Entities =
            [
                entity "arena" "boundary" visualIds.[0]
                entity "collectible" "collect:100" visualIds.[1]
                entity "hazard" "damage:1" visualIds.[2]
                entity "goal" "win:requires-collectible" visualIds.[3]
                entity "barrier" "solid" visualIds.[4]
                entity "player" "spawn" visualIds.[5]
            ]
        Grid = None
        ResourceReferences = []
    }

let gameplayRoleMetadata sceneId visualIds =
    gameplayMetadata sceneId visualIds
    |> fun metadata ->
        { metadata with
            Entities =
                metadata.Entities
                |> List.map (fun entity ->
                    { entity with
                        Properties =
                            entity.Properties
                            |> List.map (fun property ->
                                if property.Key = "interaction" then
                                    { property with
                                        Value = SvgScenePropertyValue.Text "unconfigured"
                                    }
                                else
                                    property)
                    })
        }

let emptyDocument =
    {
        Schema = SvgDocument.schema
        Id = "authored-arena"
        ViewBox =
            {
                X = 0.0
                Y = 0.0
                Width = arenaWidth
                Height = arenaHeight
            }
        Definitions = []
        Children = []
    }

let authoredArenaDocument =
    { arenaDocument with
        Id = "authored-arena"
        Children =
            arenaDocument.Children
            |> List.mapi (fun index element ->
                { element with
                    Id = $"authored-shape-{index + 1}"
                    SemanticId = Some $"authored:shape:{index + 1}"
                })
    }

let initialState () =
    let metadata =
        gameplayMetadata "continuous-arena" [| "arena"; "collectible"; "hazard"; "goal"; "thin-wall"; "player" |]

    SvgAuthoring.tryCreateScene
        0
        metadata
        arenaDocument
        {
            Schema = SvgAsset.catalogSchema
            Assets = []
        }
        []
    |> Result.defaultWith (fun error -> failwithf "Initial generated SVG scene refused: %A" error)

let private gameplayElement role (metadata: SvgSceneMetadata) (document: SvgDocument) =
    let bindings =
        metadata.Entities
        |> List.filter (fun entity ->
            entity.KindId = "gameplay.role"
            && (entity.Properties
                |> List.exists (fun property ->
                    property.Key = "role" && property.Value = SvgScenePropertyValue.Text role)))

    match bindings with
    | [] -> Error($"missing gameplay role {role}")
    | _ :: _ :: _ -> Error($"gameplay role {role} is ambiguous")
    | [ binding ] ->
        match binding.VisualElementId with
        | None -> Error($"gameplay role {role} has no visual")
        | Some id ->
            match document.Children |> List.tryFind (fun element -> element.Id = id) with
            | None -> Error($"gameplay role {role} references missing visual {id}")
            | Some element when not (SvgAffine.isFinite element.Transform) ->
                Error($"gameplay role {role} has a non-finite transform")
            | Some element -> Ok element

let visualIdForRole role metadata document =
    gameplayElement role metadata document |> Result.map _.Id

let private transformedCircle role metadata document =
    gameplayElement role metadata document
    |> Result.bind (fun element ->
        match element.Content with
        | SvgElementContent.SceneLeaf leaf ->
            match
                leaf.Nodes
                |> List.choose (function
                    | SceneNode.Circle(center, radius, _) -> Some(center, radius)
                    | _ -> None)
            with
            | [ center, radius ] when radius > 0.0 -> Ok(SvgAffine.transformPoint element.Transform center)
            | [ _ ] -> Error($"gameplay role {role} has an invalid circle")
            | _ -> Error($"gameplay role {role} must contain exactly one circle")
        | _ -> Error($"gameplay role {role} must be a scene leaf"))

let private validateGameplayRules (metadata: SvgSceneMetadata) =
    [
        "arena", "boundary"
        "collectible", "collect:100"
        "hazard", "damage:1"
        "goal", "win:requires-collectible"
        "barrier", "solid"
        "player", "spawn"
    ]
    |> List.tryPick (fun (role, expected) ->
        let actual =
            metadata.Entities
            |> List.tryFind (fun entity ->
                entity.KindId = "gameplay.role"
                && entity.Properties
                   |> List.exists (fun property ->
                       property.Key = "role" && property.Value = SvgScenePropertyValue.Text role))
            |> Option.bind (fun entity ->
                entity.Properties |> List.tryFind (fun property -> property.Key = "interaction"))
            |> Option.bind (fun property ->
                match property.Value with
                | SvgScenePropertyValue.Text value -> Some value
                | _ -> None)

        if actual = Some expected then
            None
        else
            Some($"gameplay role {role} requires interaction {expected}"))
    |> Option.map Error
    |> Option.defaultValue (Ok())

let private framed (value: string) = $"{value.Length}:{value}"

let private canonicalPropertyValue =
    function
    | SvgScenePropertyValue.Text value -> "text:" + framed value
    | SvgScenePropertyValue.Number value -> "number:" + canonicalFloat value
    | SvgScenePropertyValue.Flag value -> if value then "flag:true" else "flag:false"
    | SvgScenePropertyValue.Coordinate value -> "coordinate:" + canonicalFloat value.X + "," + canonicalFloat value.Y

/// Bind compiled gameplay identity to the complete accepted scene metadata as
/// well as the SVG bytes. Invisible, node-free markers let Rendering's public
/// canonical SHA-256 remain the sole hashing implementation.
let gameplayContentHash (metadata: SvgSceneMetadata) (document: SvgDocument) =
    let optionValue (value: string option) =
        value |> Option.defaultValue "" |> framed

    let marker (id: string) (semanticId: string) =
        {
            Id = $"__gameplay-identity-{id}"
            SemanticId = Some semanticId
            Visible = false
            Transform = SvgAffine.identity
            ClipId = None
            MaskId = None
            Presentation = None
            Content = SvgElementContent.SceneLeaf { Nodes = [] }
        }

    let entityMarkers =
        metadata.Entities
        |> List.sortBy _.EntityId
        |> List.mapi (fun index entity ->
            let properties =
                entity.Properties
                |> List.sortBy _.Key
                |> List.map (fun property -> framed property.Key + framed (canonicalPropertyValue property.Value))
                |> String.concat ""

            marker
                $"entity-{index}"
                ("entity:"
                 + framed entity.EntityId
                 + framed entity.KindId
                 + optionValue entity.VisualElementId
                 + optionValue entity.PrefabInstanceId
                 + framed properties))

    let grid =
        metadata.Grid
        |> Option.map (fun value ->
            String.concat
                ","
                [
                    canonicalFloat value.Origin.X
                    canonicalFloat value.Origin.Y
                    canonicalFloat value.Step.X
                    canonicalFloat value.Step.Y
                ])
        |> Option.defaultValue "none"

    let header =
        "scene:"
        + framed metadata.SceneId
        + "|layers:"
        + (metadata.Layers |> List.sort |> List.map framed |> String.concat "")
        + "|grid:"
        + framed grid
        + "|resources:"
        + (metadata.ResourceReferences |> List.sort |> List.map framed |> String.concat "")

    { document with
        Children = document.Children @ (marker "header" header :: entityMarkers)
    }
    |> SvgAsset.contentHash

let private transformedRect role metadata document =
    gameplayElement role metadata document
    |> Result.bind (fun element ->
        match element.Content with
        | SvgElementContent.SceneLeaf leaf ->
            match
                leaf.Nodes
                |> List.choose (function
                    | SceneNode.Rectangle((x, y, width, height), _) -> Some(x, y, width, height)
                    | _ -> None)
            with
            | [ x, y, width, height ] ->
                let points =
                    [
                        { X = x; Y = y }
                        { X = x + width; Y = y }
                        { X = x; Y = y + height }
                        { X = x + width; Y = y + height }
                    ]
                    |> List.map (SvgAffine.transformPoint element.Transform)

                let xs = points |> List.map _.X
                let ys = points |> List.map _.Y
                let left, right = List.min xs, List.max xs
                let top, bottom = List.min ys, List.max ys

                if right <= left || bottom <= top then
                    Error($"gameplay role {role} has empty transformed bounds")
                else
                    let bounds: FS.GG.Game.Core.Rect =
                        {
                            X = left
                            Y = top
                            Width = right - left
                            Height = bottom - top
                        }

                    Ok bounds
            | _ -> Error($"gameplay role {role} must contain exactly one rectangle")
        | _ -> Error($"gameplay role {role} must be a scene leaf"))

/// Compile accepted authoring geometry into the product rules model. Gameplay
/// rectangles use their transformed axis-aligned bounds; decorative SVG remains
/// under Rendering without invented rules.
let compileArenaContent (metadata: SvgSceneMetadata) (document: SvgDocument) =
    let baseline = contentAt 1UL
    let exact left right = abs (left - right) <= 0.000001

    match
        validateGameplayRules metadata,
        transformedCircle "collectible" metadata document,
        transformedRect "hazard" metadata document,
        transformedRect "goal" metadata document,
        transformedRect "arena" metadata document,
        transformedRect "barrier" metadata document,
        transformedRect "player" metadata document
    with
    | Ok(), Ok _, Ok _, Ok _, Ok arena, Ok _, Ok _ when
        not (
            exact arena.X 0.0
            && exact arena.Y 0.0
            && exact arena.Width arenaWidth
            && exact arena.Height arenaHeight
        )
        ->
        Error "gameplay arena boundary must use the supported 220x120 world at origin 0,0"
    | Ok(), Ok _, Ok _, Ok _, Ok _, Ok _, Ok player when
        not (
            exact player.Width playerWidth
            && exact player.Height playerHeight
            && exact (player.X / cellWidth) (round (player.X / cellWidth))
            && exact (player.Y / cellHeight) (round (player.Y / cellHeight))
        )
        ->
        Error "gameplay player spawn must be an unscaled 10x10 rectangle aligned to the 11x10 arena grid"
    | Ok(), Ok collectible, Ok hazard, Ok goal, Ok arena, Ok barrier, Ok player when
        player.X >= arena.X
        && player.Y >= arena.Y
        && player.X + player.Width <= arena.X + arena.Width
        && player.Y + player.Height <= arena.Y + arena.Height
        ->
        gameplayContentHash metadata document
        |> Result.mapError (fun issues -> $"gameplay identity could not be hashed: {issues}")
        |> Result.map (fun contentHash ->
            { baseline with
                SchemaVersion = 3
                ContentId = "continuous-arena/" + contentHash
                Boundary = arena
                Spawn =
                    {
                        Col = int (round (player.X / cellWidth))
                        Row = int (round (player.Y / cellHeight))
                    }
                CollectibleX = collectible.X
                CollectibleY = collectible.Y
                Hazard = hazard
                Goal = goal
                ThinWall = barrier
            })
    | Ok _, Ok _, Ok _, Ok _, Ok _, Ok _, Ok _ ->
        Error "gameplay player spawn lies outside the supported arena boundary"
    | Error issue, _, _, _, _, _, _
    | _, Error issue, _, _, _, _, _
    | _, _, Error issue, _, _, _, _
    | _, _, _, Error issue, _, _, _
    | _, _, _, _, Error issue, _, _
    | _, _, _, _, _, Error issue, _
    | _, _, _, _, _, _, Error issue -> Error issue
