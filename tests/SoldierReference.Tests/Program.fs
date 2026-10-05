module SoldierReference.Tests

open System
open System.IO
open System.Text
open System.Text.Json
open System.Security.Cryptography
open FS.GG.UI.Scene
open FableGameWorkspaceNamespace.SoldierWorkload
open FableGameWorkspaceNamespace.SoldierDocument

let mutable checks = 0
let check message condition =
    checks <- checks + 1
    if not condition then failwith message
let ok = function Ok value -> value | Error error -> failwithf "Unexpected rejection: %A" error
let apply command state =
    match tryApply command state with next, None -> next | _, Some issues -> failwithf "Unexpected command rejection: %A" issues
let initialState visible world = initial visible world |> ok
let worldChildren (document: SvgDocument) =
    match document.Children with
    | [ { Content = SvgElementContent.Group children } ] -> children
    | _ -> failwith "Expected one world group"
let childrenOf (element: SvgElement) =
    match element.Content with SvgElementContent.Group children -> children | _ -> failwith "Expected group"
let sha (value: string) = SHA256.HashData(Encoding.UTF8.GetBytes value) |> Convert.ToHexStringLower
let canonicalWorkload (workload: Workload) =
    // Test-owned portable oracle: explicit schema/order, no reflection or DU serializer assumptions.
    use stream = new MemoryStream()
    use writer = new Utf8JsonWriter(stream)
    writer.WriteStartObject()
    writer.WriteString("schema", "soldier-workload/1")
    writer.WriteNumber("version", workload.Version)
    writer.WriteNumber("seed", workload.Seed)
    writer.WriteNumber("authorityRevision", workload.AuthorityRevision)
    writer.WriteNumber("definitionRevision", workload.DefinitionRevision)
    writer.WriteStartArray("soldiers")
    for soldier in workload.Soldiers do
        writer.WriteStartObject()
        writer.WriteString("id", soldier.Id)
        writer.WriteString("faction", (match soldier.Faction with Faction.Blue -> "blue" | Faction.Amber -> "amber"))
        writer.WriteString("pose", (match soldier.Pose with Pose.Ready -> "ready" | Pose.March -> "march" | Pose.Kneel -> "kneel"))
        writer.WriteNumber("health", soldier.Health)
        writer.WriteNumber("x", soldier.Position.X)
        writer.WriteNumber("y", soldier.Position.Y)
        writer.WriteNumber("facingDegrees", soldier.FacingDegrees)
        writer.WriteEndObject()
    writer.WriteEndArray()
    writer.WriteEndObject()
    writer.Flush()
    Encoding.UTF8.GetString(stream.ToArray())

let verify () =
    let referenceRoot = Path.GetFullPath(Path.Combine(__SOURCE_DIRECTORY__, "../../templates/fs-gg-fable-game/SvgFoundation/Examples/SoldierReference"))
    use reference = JsonDocument.Parse(File.ReadAllText(Path.Combine(referenceRoot, "reference.json")))
    let data = reference.RootElement
    check "Reference schema" (data.GetProperty("schema").GetString() = "templates.soldier-reference/1")
    check "Reference seed" (data.GetProperty("seed").GetInt32() = seed)
    check "Reference visible counts" ([ for v in data.GetProperty("visibleCounts").EnumerateArray() -> v.GetInt32() ] = visibleCounts)
    check "Reference update percentages" ([ for v in data.GetProperty("updatePercentages").EnumerateArray() -> v.GetInt32() ] = updatePercentages)
    check "Reference bounded world" (data.GetProperty("control").GetProperty("worldCount").GetInt32() = maxSoldiers)
    check "Reference control visible count" (data.GetProperty("control").GetProperty("visibleCount").GetInt32() = 200)
    check "Reference asset identity" (data.GetProperty("assetId").GetString() = assetId && data.GetProperty("assetVersion").GetString() = assetVersion)
    let route = [ for point in data.GetProperty("cameraRoute").EnumerateArray() -> point[0].GetDouble(), point[1].GetDouble() ]
    check "Bounded camera route and exact values" (route.Length <= 16 && route = cameraRoute)
    let churn = data.GetProperty("churn").EnumerateArray() |> Seq.toList
    check "Bounded reference command stream" (churn.Length <= maxCommands && churn.Length = churnCommands.Length)
    for row, command in List.zip churn churnCommands do
        let kind = row.GetProperty("command").GetString()
        let id () = row.GetProperty("id").GetString()
        match command with
        | Command.Select(Some target) -> check "Select reference" (kind = "select" && id() = target)
        | Command.Focus(Some target) -> check "Focus reference" (kind = "focus" && id() = target)
        | Command.Move(target, position, facing) ->
            check "Move reference" (kind = "move" && id() = target && (row.GetProperty("position")).[0].GetDouble() = position.X && (row.GetProperty("position")).[1].GetDouble() = position.Y && row.GetProperty("facingDegrees").GetDouble() = facing)
        | Command.ChangePose(target, Pose.Kneel) -> check "Pose reference" (kind = "pose" && id() = target && row.GetProperty("pose").GetString() = "kneel")
        | Command.ChangeAppearance(target, Faction.Blue, health) -> check "Appearance reference" (kind = "appearance" && id() = target && row.GetProperty("faction").GetString() = "blue" && row.GetProperty("health").GetInt32() = health)
        | Command.Remove target -> check "Removal reference" (kind = "remove" && id() = target)
        | Command.Spawn soldier -> check "Spawn reference" (kind = "spawn" && id() = soldier.Id && (row.GetProperty("position")).[0].GetDouble() = soldier.Position.X && (row.GetProperty("position")).[1].GetDouble() = soldier.Position.Y && row.GetProperty("health").GetInt32() = soldier.Health && row.GetProperty("facingDegrees").GetDouble() = soldier.FacingDegrees && row.GetProperty("faction").GetString() = "amber" && row.GetProperty("pose").GetString() = "march")
        | Command.ReviseDefinitions revision -> check "Definition revision reference" (kind = "definitions" && row.GetProperty("revision").GetInt32() = revision)
        | _ -> failwith "Reference command contract changed"
    check "Invalid counts rejected" (initial 2 2 |> Result.isError)
    check "World limit rejected" (initial 200 2001 |> Result.isError)
    let assetBytes = SvgDocument.serialize assetDocument |> ok
    let assetSvg = SvgDocument.exportSvg "soldier-asset" assetDocument |> ok
    use provenance = JsonDocument.Parse(File.ReadAllText(Path.Combine(referenceRoot, "provenance.json")))
    check "MIT original asset provenance" (provenance.RootElement.GetProperty("license").GetString() = assetLicense && provenance.RootElement.GetProperty("assetId").GetString() = assetId)
    let frozenHash = provenance.RootElement.GetProperty("canonicalContentSha256")
    if frozenHash.ValueKind <> JsonValueKind.Null then check "Frozen canonical asset hash" (frozenHash.GetString() = sha assetBytes)
    check "Asset round trip" (assetBytes |> SvgDocument.deserialize |> ok |> SvgDocument.serialize = Ok assetBytes)
    check "Six explicit symbols" (assetDocument.Definitions.Length = 6)
    check "Explicit asset viewport" (assetDocument.Children.Head.Content = SvgElementContent.SymbolInstance("soldier-r1-blue-ready",Some glyphBounds))
    check "Definitions reused" (Object.ReferenceEquals(definitions 1, definitions 1))
    check "Revision changes definitions" (definitions 1 <> definitions 2)
    let paths, segments, nodes =
        assetDocument.Definitions |> List.map (fun definition ->
            match definition.Content with
            | SvgDefinitionContent.Symbol(Some bounds, elements) ->
                check "Normalized symbol bounds" (bounds = glyphBounds)
                check "One typed geometry leaf" (elements.Length = 1)
                for element in elements do
                    match element.Content with
                    | SvgElementContent.SceneLeaf scene ->
                        for node in scene.Nodes do
                            match node with
                            | SceneNode.Rectangle((x,y,width,height),_) -> check "Rectangle in normalized bounds" (x >= 0. && y >= 0. && x + width <= 48. && y + height <= 64.)
                            | _ -> ()
                    | _ -> failwith "Expected geometry leaf"
                let sceneNodes = elements |> List.sumBy (fun element -> match element.Content with SvgElementContent.SceneLeaf scene -> scene.Nodes.Length | _ -> 0)
                check "26 scene geometry nodes" (sceneNodes = 26)
                let pathSpecs = elements |> List.collect (fun element ->
                    match element.Content with
                    | SvgElementContent.SceneLeaf scene ->
                        scene.Nodes |> List.choose (function SceneNode.Path(spec, _) -> Some spec | _ -> None)
                    | _ -> failwith "Unexpected nested glyph")
                check "17 equipment paths" (pathSpecs.Length = 17)
                for spec in pathSpecs do
                    for command in spec.Commands do
                        match command with
                        | PathCommand.MoveTo point | PathCommand.LineTo point ->
                            check "Authored geometry in bounds" (point.X >= 0. && point.X <= 48. && point.Y >= 0. && point.Y <= 64.)
                        | PathCommand.Close -> ()
                        | _ -> failwith "Unexpected authored path command"
                pathSpecs.Length, pathSpecs |> List.sumBy (fun spec -> spec.Commands.Length), sceneNodes
            | _ -> failwith "Unexpected definition")
        |> List.fold (fun (a,b,c) (d,e,f) -> a+d,b+e,c+f) (0,0,0)
    check "Total canonical asset complexity" (paths = 102 && segments = 662 && nodes = 156)
    let cases = [ for count in visibleCounts -> count, count ] @ [200, 2000]
    let artifacts = ResizeArray<string * string>()
    artifacts.Add("asset.svg", assetSvg)
    artifacts.Add("asset.document.txt", assetBytes)
    artifacts.Add("asset-r2.document.txt", SvgDocument.serialize (assetDocumentFor 2) |> ok)
    artifacts.Add("asset-r2.svg", SvgDocument.exportSvg "soldier-asset-r2" (assetDocumentFor 2) |> ok)
    for visible, world in cases do
        let state = initialState visible world
        check "Deterministic initial workload" (state = initialState visible world)
        let full = project state |> ok
        let bytes = SvgDocument.serialize full |> ok
        check "Full count" ((worldChildren full).Length = world)
        check "Requested visible soldiers fit conservative rotated-art bounds" (state.Workload.Soldiers |> List.take visible |> List.forall (fun soldier -> soldier.Position.X - 43. >= 0. && soldier.Position.Y - 43. >= 0. && soldier.Position.X + 43. <= full.ViewBox.Width && soldier.Position.Y + 43. <= full.ViewBox.Height))
        check "Canonical round trip" (SvgDocument.serialize (SvgDocument.deserialize bytes |> ok) = Ok bytes)
        check "Shared validation accepts full scene" (SvgDocument.validate (Encoding.UTF8.GetByteCount bytes) SvgDocument.defaultLimits full = [])
        check "Stable input/draw order" (worldChildren full |> List.map _.Id = (state.Workload.Soldiers |> List.map _.Id))
        artifacts.Add(sprintf "workload-%d-%d.json" visible world, canonicalWorkload state.Workload)
        for percentage in updatePercentages do
            let moved = updatedSoldiers percentage state.Workload |> ok
            check "Deterministic independent updates" (updatedSoldiers percentage state.Workload = Ok moved)
            let beforeAfter = List.zip state.Workload.Soldiers moved.Soldiers
            check "Exact update percentage" (beforeAfter |> List.filter (fun (a,b) -> a <> b) |> List.length = world * percentage / 100)
            check "First update translates rotates and assigns pose from ready" (beforeAfter |> List.forall (fun (a,b) -> a = b || (a.Position <> b.Position && a.FacingDegrees <> b.FacingDegrees && a.Pose <> b.Pose)))
            let movedDoc = project { state with Workload = moved } |> ok
            check "Unchanged definitions after movement" (Object.ReferenceEquals(full.Definitions, movedDoc.Definitions))
            check "Stable top-level IDs after movement" (worldChildren full |> List.map _.Id = (worldChildren movedDoc |> List.map _.Id))
            for (oldSoldier,newSoldier), (oldElement,newElement) in List.zip beforeAfter (List.zip (worldChildren full) (worldChildren movedDoc)) do
                if oldSoldier = newSoldier then check "Unchanged soldier subtree" (oldElement = newElement)
            artifacts.Add(sprintf "workload-%d-%d-update-%d.json" visible world percentage, canonicalWorkload moved)
    let one = (initialState 1 1).Workload.Soldiers.Head
    check "Known initial fixture" (one = { Id = "soldier-0000"; Faction = Faction.Blue; Pose = Pose.Ready; Health = 100; Position = { X = 64.; Y = 64. }; FacingDegrees = 289. })
    let boundary = { (initialState 1 1).Workload with Soldiers = [ { one with Position = { X = 1000000.; Y = 64. } } ] }
    check "Boundary input is valid" ((validate boundary).IsEmpty)
    check "Generated movement outside coordinate bound refuses" (updatedSoldiers 100 boundary = Error [ "invalid-position" ])
    check "Rejected movement leaves input workload intact" (boundary.Soldiers.Head.Position.X = 1000000. && boundary.AuthorityRevision = 0)
    let hundred = (initialState 100 100).Workload
    let tenPercent = updatedSoldiers 10 hundred |> ok
    let actualIds = List.zip hundred.Soldiers tenPercent.Soldiers |> List.choose (fun (a,b) -> if a <> b then Some a.Id else None) |> List.sort
    check "Independent known 10-percent rank population" (actualIds = [ "soldier-0000"; "soldier-0001"; "soldier-0002"; "soldier-0003"; "soldier-0004"; "soldier-0005"; "soldier-0006"; "soldier-0007"; "soldier-0008"; "soldier-0009" ])
    let state = initialState 200 2000
    let focused = state |> apply (Command.Select(Some "soldier-0000")) |> apply (Command.Focus(Some "soldier-0000"))
    let offscreen = focused |> apply (Command.Move("soldier-0000", { X = 12000.; Y = 40. }, 90.))
    for x,y in cameraRoute do
        let panned = offscreen |> apply (Command.Camera(SvgAffine.translate (-x) (-y)))
        check "All route cameras preserve authority" (panned.Workload = offscreen.Workload)
    let camera = offscreen |> apply (Command.Camera(SvgAffine.translate -320. -240.))
    check "Camera preserves authority revision" (camera.Workload = offscreen.Workload)
    check "Camera increments presentation only" (camera.Presentation.Revision = offscreen.Presentation.Revision + 1)
    let visible = state.Workload.Soldiers |> List.take 200 |> List.map _.Id |> Set.ofList |> Set.remove "soldier-0000"
    let accepted, error = tryAccept camera visible None
    check "Accepted full and display projection" error.IsNone
    let accepted = accepted.Value
    check "Pinned offscreen selection retained" (worldChildren accepted.Display |> List.exists (fun s -> s.Id = "soldier-0000"))
    check "Display exactly 200 with pin" ((worldChildren accepted.Display).Length = 200)
    let xml = System.Xml.Linq.XDocument.Parse accepted.ExportedSvg
    let exportedUses = xml.Descendants() |> Seq.filter (fun e -> e.Name.LocalName = "use") |> Seq.toList
    check "Full export survives display filtering" (exportedUses.Length = 2000)
    check "All exported instances have normalized viewport dimensions" (exportedUses |> List.forall (fun element -> element.Attribute(System.Xml.Linq.XName.Get "width").Value = "48" && element.Attribute(System.Xml.Linq.XName.Get "height").Value = "64"))
    let changed = state |> apply (Command.ChangePose("soldier-0000", Pose.March)) |> apply (Command.ChangeAppearance("soldier-0000", Faction.Amber, 25))
    let projected = project changed |> ok |> worldChildren |> List.head |> childrenOf
    check "Explicit faction/pose symbol" (projected.Head.Content = SvgElementContent.SymbolInstance("soldier-r1-amber-march", Some glyphBounds))
    match projected[1].Content with
    | SvgElementContent.SceneLeaf { Nodes = [ SceneNode.Rectangle((_,_,width,_),_) ] } -> check "Health width" (width = 12.)
    | _ -> failwith "Health overlay missing"
    let removed = offscreen |> apply (Command.Remove "soldier-0000")
    check "Removed selection cleared" removed.Presentation.Selected.IsNone
    check "Focus moves to deterministic first survivor" (removed.Presentation.Focused = Some "soldier-0001")
    let empty = initialState 1 1 |> apply (Command.Focus(Some "soldier-0000")) |> apply (Command.Remove "soldier-0000")
    check "No survivor leaves panel focus target" empty.Presentation.Focused.IsNone
    let churned, churnError = tryApplyBatch churnCommands state
    check "Churn accepted" churnError.IsNone
    check "Churn preserves count" (churned.Workload.Soldiers.Length = 2000)
    check "Definition revision applied" (project churned |> ok |> _.Definitions |> List.forall (fun d -> d.Id.StartsWith "soldier-r2-"))
    artifacts.Add("workload-churn.json", canonicalWorkload churned.Workload)
    let invalidStates =
        [ { state with Workload = { state.Workload with Soldiers = state.Workload.Soldiers.Head :: state.Workload.Soldiers } }
          { state with Workload = { state.Workload with DefinitionRevision = 3 } }
          { state with Workload = { state.Workload with Soldiers = [ { state.Workload.Soldiers.Head with Position = { X = nan; Y = 0. } } ] } }
          { state with Presentation = { state.Presentation with Camera = SvgAffine.scale 0. 1. } } ]
    for invalid in invalidStates do
        let next, refused = tryAccept invalid visible (Some accepted)
        check "Invalid projection refuses" refused.IsSome
        check "Invalid projection retains same accepted value/export" (Object.ReferenceEquals(next.Value, accepted))
    for command in [ Command.ChangeAppearance("soldier-0000", Faction.Blue, 101); Command.Move("missing", { X = 1.; Y = 1. }, 0.); Command.Spawn state.Workload.Soldiers.Head; Command.Focus(Some "missing") ] do
        let next, refused = tryApply command state
        check "Invalid command refuses and preserves prior state" (refused.IsSome && Object.ReferenceEquals(next, state))
    let excessive, refused = tryApplyBatch (List.replicate 129 (Command.Select None)) state
    check "Bounded command batch" (refused.IsSome && Object.ReferenceEquals(excessive,state))
    let rolledBack, refused = tryApplyBatch [ Command.Remove "soldier-0000"; Command.Remove "missing" ] state
    check "Atomic batch rollback" (refused.IsSome && Object.ReferenceEquals(rolledBack,state))
    let badReference = { assetDocument with Children = [ { assetDocument.Children.Head with Content = SvgElementContent.SymbolInstance("missing",None) } ] }
    check "Shared validator refuses missing reference" (SvgDocument.serialize badReference |> Result.isError)
    printfn "PASS %d focused pure checks; canonical asset SHA-256 %s" checks (sha assetBytes)
    artifacts

[<EntryPoint>]
let main args =
    try
        let artifacts = verify ()
        match args with
        | [| "--artifacts"; directory |] ->
            Directory.CreateDirectory directory |> ignore
            for name, value in artifacts do File.WriteAllText(Path.Combine(directory,name),value,UTF8Encoding(false))
            let manifest = artifacts |> Seq.map (fun (name,value) -> name, sha value) |> dict
            File.WriteAllText(Path.Combine(directory,"hashes.json"), JsonSerializer.Serialize(manifest,JsonSerializerOptions(WriteIndented=true)),UTF8Encoding(false))
        | [||] -> ()
        | _ -> failwith "Usage: SoldierReference.Tests [--artifacts PRIVATE_DIRECTORY]"
        0
    with error -> eprintfn "%s" (error.ToString()); 1
