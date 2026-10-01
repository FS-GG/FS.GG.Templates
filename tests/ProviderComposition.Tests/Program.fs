open FsGgTemplates.ProviderComposition
open FsGgTemplates.ReferencePublication
open FsGgTemplates.FeedOccupancy
open System
open System.IO
open System.IO.Compression
open System.Diagnostics
open System.Net
open System.Net.Http
open System.Net.Http.Headers
open System.Security.Cryptography
open System.Text
open System.Threading
open System.Threading.Tasks
open FsGgTemplates.ProviderTool

type private StallingStream(cancelled: TaskCompletionSource<bool>) =
    inherit Stream()
    override _.CanRead = true
    override _.CanSeek = false
    override _.CanWrite = false
    override _.Length = raise (NotSupportedException())
    override _.Position with get () = raise (NotSupportedException()) and set _ = raise (NotSupportedException())
    override _.Flush() = ()
    override _.Read(_, _, _) = Thread.Sleep(600); 0
    override _.ReadAsync(buffer: Memory<byte>, cancellationToken: CancellationToken) =
        ValueTask<int>(task {
            try
                do! Task.Delay(Timeout.Infinite, cancellationToken)
                return 0
            with :? OperationCanceledException as ex ->
                cancelled.TrySetResult(true) |> ignore
                return raise ex
        })
    override _.Seek(_, _) = raise (NotSupportedException())
    override _.SetLength(_) = raise (NotSupportedException())
    override _.Write(_, _, _) = raise (NotSupportedException())

let productName: Parameter = { Key = "productName"; Required = true; Default = None }
let lifecycle: Parameter = { Key = "lifecycle"; Required = false; Default = Some "sdd" }

let alpha: Provider = {
    Name = "alpha"
    ContractVersion = "1.1.0"
    TemplateId = "fs-gg-alpha"
    Source = "Alpha.Template::1.0.0"
    NameParameter = Some "productName"
    IdentifierParameter = Some "rootNamespace"
    Floor = Some "1.4.0-preview.1"
    Parameters = [ productName; lifecycle ]
    File = "alpha.providers.yml"
    Line = 3
}
let beta = { alpha with Name = "beta"; TemplateId = "fs-gg-beta"; Source = "Beta.Template::2.0.0" }
let known = [ alpha; beta ]
let assertEqual name expected actual =
    if expected <> actual then failwithf "%s: expected %A, got %A" name expected actual
    printfn "PASS %s" name

[<EntryPoint>]
let main _ =
    assertEqual "closed CLI options accept each known option exactly once"
        (Map.ofList [ "--archive", "a"; "--sha256", "b" ])
        (parseClosedOptions [ "--archive"; "--sha256" ] [ "--archive"; "a"; "--sha256"; "b" ])
    let refuses name action =
        try action (); failwithf "%s: expected refusal" name
        with :? InvalidDataException -> printfn "PASS %s" name
    refuses "closed CLI options refuse duplicates" (fun () -> parseClosedOptions [ "--archive" ] [ "--archive"; "a"; "--archive"; "b" ] |> ignore)
    refuses "closed CLI options refuse unknowns" (fun () -> parseClosedOptions [ "--archive" ] [ "--archive"; "a"; "--extra"; "b" ] |> ignore)
    refuses "feed occupancy CLI refuses duplicate version option" (fun () -> parseClosedOptions [ "--version" ] [ "--version"; "0.17.0"; "--version"; "0.18.0" ] |> ignore)
    refuses "feed occupancy CLI refuses unknown option" (fun () -> parseClosedOptions [ "--version" ] [ "--candidate"; "0.17.0" ] |> ignore)
    let selected = select known known
    assertEqual "two known providers compose" (Ok known) selected
    assertEqual "subset keeps requested identity" (Ok [ beta ]) (select known [ beta ])
    assertEqual "owner files may enumerate in filename order" (Ok known) (select [ beta; alpha ] known)
    assertEqual "empty request refuses" (Error EmptySelection) (select known [])
    assertEqual "unknown provider refuses" (Error(UnknownProvider "gamma")) (select known [ { alpha with Name = "gamma" } ])
    assertEqual "duplicate request refuses" (Error(DuplicateProvider "alpha")) (select known [ alpha; alpha ])
    assertEqual "duplicate owner source refuses" (Error(DuplicateProvider "alpha")) (select [ alpha; alpha ] [ alpha ])
    assertEqual "unordered request refuses" (Error UnorderedProviders) (select known [ beta; alpha ])
    assertEqual "invalid name refuses" (Error(InvalidProvider "../alpha")) (select known [ { alpha with Name = "../alpha" } ])
    assertEqual "empty package source refuses" (Error(InvalidProvider "alpha")) (select known [ { alpha with Source = "" } ])
    assertEqual "missing owner floor refuses" (Error(MissingFloor "alpha")) (select [ { alpha with Floor = None }; beta ] [ alpha ])
    assertEqual "missing request floor refuses" (Error(MissingFloor "alpha")) (select known [ { alpha with Floor = None } ])
    assertEqual "invalid floor refuses" (Error(InvalidFloor "alpha")) (select known [ { alpha with Floor = Some "not-a-version" } ])
    assertEqual "source drift refuses" (Error(DifferentProvider "alpha")) (select known [ { alpha with Source = "Alpha.Template::9.9.9" } ])
    assertEqual "name route drift refuses" (Error(DifferentProvider "alpha"))
        (select known [ { alpha with NameParameter = Some "otherName" } ])
    assertEqual "identifier route drift refuses" (Error(DifferentProvider "alpha"))
        (select known [ { alpha with IdentifierParameter = Some "otherNamespace" } ])
    assertEqual "malformed route refuses" (Error(InvalidProvider "alpha"))
        (select known [ { alpha with NameParameter = Some "../outside" } ])
    assertEqual "registry pin admits coherent owner and request"
        (Ok [ beta ]) (selectAtRegistryFloor "1.4.0-preview.1" known [ beta ])
    assertEqual "unselected owner floor drift refuses"
        (Error(RegistryFloorMismatch("alpha", "1.4.0-preview.2", "1.4.0-preview.1")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ { alpha with Floor = Some "1.4.0-preview.2" }; beta ] [ beta ])
    assertEqual "malformed registry pin refuses"
        (Error(InvalidRegistryFloor "1.4.0 garbage"))
        (selectAtRegistryFloor "1.4.0 garbage" known [ beta ])
    assertEqual "unknown request still refuses with a coherent pin"
        (Error(UnknownProvider "gamma"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "gamma" } ])
    assertEqual "malformed request still refuses with a coherent pin"
        (Error(InvalidProvider "../alpha"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "../alpha" } ])
    assertEqual "parameter declaration drift refuses"
        (Error(DifferentProvider "alpha"))
        (selectAtRegistryFloor "1.4.0-preview.1" known
            [ { alpha with Parameters = [ productName ] } ])
    let staleAlpha = { alpha with Floor = Some "1.4.0-preview.2" }
    assertEqual "selected owner floor drift refuses"
        (Error(RegistryFloorMismatch("alpha", "1.4.0-preview.2", "1.4.0-preview.1")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ staleAlpha; beta ] [ staleAlpha ])
    assertEqual "malformed declared parameter key refuses"
        (Error(InvalidParameter("alpha", "../name")))
        (selectAtRegistryFloor "1.4.0-preview.1"
            [ { alpha with Parameters = [ { productName with Key = "../name" } ] }; beta ] [ beta ])
    assertEqual "duplicate declared parameter refuses"
        (Error(DuplicateParameter("alpha", "productName")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ { alpha with Parameters = [ productName; productName ] }; beta ] [ beta ])
    assertEqual "unknown requested parameter refuses"
        (Error(UnknownParameter("alpha", "surprise")))
        (resolveParameters alpha [ "productName", "Demo"; "surprise", "yes" ])
    assertEqual "duplicate requested parameter refuses"
        (Error(DuplicateParameter("alpha", "productName")))
        (resolveParameters alpha [ "productName", "Demo"; "productName", "Again" ])
    assertEqual "missing required parameter refuses"
        (Error(MissingRequiredParameter("alpha", "productName")))
        (resolveParameters alpha [])
    assertEqual "defaults and declared order resolve deterministically"
        (Ok [ "productName", "Demo"; "lifecycle", "sdd" ])
        (resolveParameters alpha [ "productName", "Demo" ])
    assertEqual "exact UTF-8 summary bytes match Python fixture"
        "02dff0dfdd49d147f2ec933426d6bc9910848d568fda85fc0e730678435f6b7b"
        (Convert.ToHexString(SHA256.HashData(renderEffectiveBytes true known)).ToLowerInvariant())
    assertEqual "exact UTF-8 summary without final newline matches Python fixture"
        "3f2694267343ae48149ab7b082f96727590c73a3b6b5d921566c9f0de8b033b3"
        (Convert.ToHexString(SHA256.HashData(renderEffectiveBytes false known)).ToLowerInvariant())
    let rendered =
        match selected with
        | Ok value -> renderEffective value
        | Error issue -> failwithf "valid selection refused: %A" issue
    assertEqual "summary output deterministic"
        [ "# Effective providers — generated; ordered by unique provider name."
          "# Review this block for the current selection; the release narrative remains in PIN HISTORY."
          "# effective[1]: name=alpha | template=fs-gg-alpha | source=Alpha.Template::1.0.0 | contract=1.1.0"
          "# effective[2]: name=beta | template=fs-gg-beta | source=Beta.Template::2.0.0 | contract=1.1.0" ] rendered
    let temp = Path.Combine(Path.GetTempPath(), "fsgg-reference-publication-" + Guid.NewGuid().ToString("N"))
    Directory.CreateDirectory temp |> ignore
    let descriptor = Path.Combine(temp, "fable-game.providers.yml")
    File.WriteAllText(descriptor, "schemaVersion: 1\nproviders:\n  - name: fable-game\n    contractVersion: \"1.1.0\"\n    templateId: fs-gg-fable-game\n    source: FS.GG.Workspace.Template::0.17.0\n    nameParameter: productName\n    minimumFsggSdd:\n      version: \"1.4.0-preview.1\"\n    parameters:\n      - key: lifecycle\n        required: false\n        default: typed-sdd\n", UTF8Encoding(false))
    let revision = String.replicate 40 "a"
    let requiredEntries =
        [ "content/templates/fs-gg-fable-game/.template.config/template.json"
          "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
          "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
          "content/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj"
          "content/templates/fs-gg-fable-game/SvgFoundation/Program.fs"
          "content/templates/fs-gg-fable-game/SvgFoundation/build.sh"
          "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]
    let makeArchive path omit duplicate =
        use zip = ZipFile.Open(path, ZipArchiveMode.Create)
        let add (name: string) (body: string) =
            let entry = zip.CreateEntry(name)
            use writer = new StreamWriter(entry.Open(), UTF8Encoding(false))
            writer.Write(body)
        add "FS.GG.Workspace.Template.nuspec" $"<package><metadata><id>FS.GG.Workspace.Template</id><version>0.17.0</version><repository commit=\"{revision}\" /></metadata></package>"
        requiredEntries |> List.filter ((<>) omit) |> List.iter (fun name ->
            let body =
                if name.EndsWith("template.json") then """{"symbols":{"effectiveName":{"replaces":"FableGameWorkspace","fileRename":"FableGameWorkspace","parameters":{"sourceVariableName":"productNameTrimmed","fallbackVariableName":"name"}},"effectiveIdentifier":{"replaces":"FableGameWorkspaceNamespace","parameters":{"sourceVariableName":"rootNamespaceTrimmed","fallbackVariableName":"effectiveName"}}}}"""
                elif name.EndsWith("FourDReference.fs") then "module FableGameWorkspaceNamespace.SvgFoundation.FourDReference"
                elif name.EndsWith("two-client.spec.ts") then "const db = 'FableGameWorkspaceNamespace-svg-studio';"
                else "fixture"
            add name body)
        if duplicate then add requiredEntries.Head "again"
    let archive = Path.Combine(temp, "valid.nupkg")
    makeArchive archive "" false
    let digest path = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes path)).ToLowerInvariant()
    let parsedProvider: Provider = {
        Name = "fable-game"; ContractVersion = "1.1.0"; TemplateId = "fs-gg-fable-game"
        Source = "FS.GG.Workspace.Template::0.17.0"; NameParameter = Some "productName"
        IdentifierParameter = None; Floor = Some "1.4.0-preview.1"
        Parameters = [ { Key = "lifecycle"; Required = false; Default = Some "typed-sdd" } ]
        File = descriptor; Line = 3 }
    let request path = {
        Archive = path; Descriptor = descriptor; ExpectedSha256 = digest path
        ExpectedRevision = revision; ExpectedTagRevision = revision
        ExpectedDescriptorSha256 = digest descriptor; Provider = parsedProvider }
    match validate (request archive) with | Ok _ -> printfn "PASS exact reference publication archive" | Error x -> failwith x
    let missing = Path.Combine(temp, "missing.nupkg")
    makeArchive missing requiredEntries.Head false
    assertEqual "missing reference member refuses" (Error "reference-member-missing") (validate (request missing))
    let duplicate = Path.Combine(temp, "duplicate.nupkg")
    makeArchive duplicate "" true
    assertEqual "duplicate archive entry refuses" (Error "archive-duplicate-entry-refused") (validate (request duplicate))
    let traversal = Path.Combine(temp, "traversal.nupkg")
    makeArchive traversal "" false
    use append = ZipFile.Open(traversal, ZipArchiveMode.Update)
    append.CreateEntry("../escape") |> ignore
    append.Dispose()
    assertEqual "traversal archive entry refuses" (Error "archive-path-refused") (validate (request traversal))
    let alias = Path.Combine(temp, "alias.nupkg")
    makeArchive alias "" false
    use aliasAppend = ZipFile.Open(alias, ZipArchiveMode.Update)
    aliasAppend.CreateEntry("content/templates/fs-gg-fable-game/SvgFoundation/./FourDReference.fs") |> ignore
    aliasAppend.Dispose()
    assertEqual "lexical dot alias refuses" (Error "archive-path-refused") (validate (request alias))
    let collision = Path.Combine(temp, "collision.nupkg")
    makeArchive collision "" false
    use collisionAppend = ZipFile.Open(collision, ZipArchiveMode.Update)
    collisionAppend.CreateEntry("collision") |> ignore
    collisionAppend.CreateEntry("collision/") |> ignore
    collisionAppend.Dispose()
    assertEqual "file and directory collision refuses" (Error "archive-duplicate-entry-refused") (validate (request collision))
    assertEqual "changed archive hash refuses" (Error "archive-sha256-refused") (validate { request archive with ExpectedSha256 = String.replicate 64 "0" })
    assertEqual "tag revision mismatch refuses" (Error "immutable-tag-revision-refused")
        (validate { request archive with ExpectedTagRevision = String.replicate 40 "b" })
    assertEqual "wrong lifecycle parameter refuses" (Error "descriptor-lifecycle-refused")
        (validate { request archive with Provider = { parsedProvider with Parameters = [ { Key = "different_parameter"; Required = false; Default = Some "typed-sdd" } ] } })
    assertEqual "stale descriptor pin refuses" (Error "descriptor-source-refused")
        (validate { request archive with Provider = { parsedProvider with Source = "FS.GG.Workspace.Template::0.16.0" } })
    let receiver = Path.Combine(temp, "receiver")
    use receiverArchive = ZipFile.OpenRead archive
    for name in requiredEntries.Tail do
        let relative = name.Substring("content/templates/fs-gg-fable-game/".Length)
        let target = Path.Combine(receiver, relative.Replace('/', Path.DirectorySeparatorChar))
        Directory.CreateDirectory(Path.GetDirectoryName target) |> ignore
        let entry = receiverArchive.GetEntry name
        use reader = new StreamReader(entry.Open(), UTF8Encoding(false, true))
        File.WriteAllText(target, reader.ReadToEnd().Replace("FableGameWorkspaceNamespace", "ReferenceDirect"))
    receiverArchive.Dispose()
    File.WriteAllText(Path.Combine(receiver, "ReferenceDirect.slnx"), "fixture")
    assertEqual "direct namespace transform closes exact package source" (Ok ()) (validateReceiver archive receiver "direct" "none" "1.2.3" "ReferenceDirect")
    let fourDOutput = Path.Combine(receiver, "SvgFoundation", "FourDReference.fs")
    let fourDBytes = File.ReadAllBytes fourDOutput
    File.AppendAllText(fourDOutput, "x")
    assertEqual "one-byte transformed source mutation refuses" (Error "receiver-source-closure-refused") (validateReceiver archive receiver "direct" "none" "1.2.3" "ReferenceDirect")
    File.WriteAllBytes(fourDOutput, fourDBytes)
    assertEqual "wrong trusted product name refuses" (Error "receiver-product-name-refused") (validateReceiver archive receiver "direct" "none" "1.2.3" "OtherName")
    assertEqual "direct route cannot claim an unobserved lifecycle default" (Error "receiver-lifecycle-refused") (validateReceiver archive receiver "direct" "typed-sdd" "1.2.3" "ReferenceDirect")
    let provenance = Path.Combine(receiver, ".fsgg", "scaffold-provenance.json")
    Directory.CreateDirectory(Path.GetDirectoryName provenance) |> ignore
    File.WriteAllText(provenance, """{"generator":{"id":"FS.GG.SDD.Artifacts","version":"1.2.3"},"providerName":"fable-game","templateRef":"FS.GG.Workspace.Template::0.17.0","effectiveParameters":[{"key":"productName","value":"ReferenceDirect"},{"key":"lifecycle","value":"typed-sdd"}]}""")
    assertEqual "provider receiver binds generator provider source namespace and omitted default" (Ok ()) (validateReceiver archive receiver "provider" "typed-sdd" "1.2.3" "ReferenceDirect")
    File.WriteAllText(provenance, """{"generator":{"id":"FS.GG.SDD.Artifacts","version":"1.2.3"},"providerName":"fable-game","providerName":"other","templateRef":"FS.GG.Workspace.Template::0.17.0","effectiveParameters":[{"key":"productName","value":"ReferenceDirect"},{"key":"lifecycle","value":"typed-sdd"}]}""")
    assertEqual "duplicate receiver provenance field refuses" (Error "receiver-provenance-duplicate-field-refused") (validateReceiver archive receiver "provider" "typed-sdd" "1.2.3" "ReferenceDirect")
    let toolArchive = Path.Combine(temp, "tool.nupkg")
    use toolZip = ZipFile.Open(toolArchive, ZipArchiveMode.Create)
    let toolNuspec = toolZip.CreateEntry("FS.GG.SDD.Cli.nuspec")
    use toolWriter = new StreamWriter(toolNuspec.Open(), UTF8Encoding(false))
    toolWriter.Write($"<package><metadata><id>FS.GG.SDD.Cli</id><version>1.2.3</version><repository commit=\"{revision}\" /></metadata></package>")
    toolWriter.Dispose()
    let settings = toolZip.CreateEntry("tools/net10.0/any/DotnetToolSettings.xml")
    use settingsWriter = new StreamWriter(settings.Open(), UTF8Encoding(false))
    settingsWriter.Write("<DotNetCliTool Version=\"1\"><Commands><Command Name=\"fsgg-sdd\" EntryPoint=\"FS.GG.SDD.Cli.dll\" Runner=\"dotnet\" /></Commands></DotNetCliTool>")
    settingsWriter.Dispose()
    let core = toolZip.CreateEntry("tools/net10.0/any/FS.GG.SDD.Cli.dll")
    use coreWriter = new StreamWriter(core.Open(), UTF8Encoding(false))
    coreWriter.Write("core")
    coreWriter.Dispose(); toolZip.Dispose()
    assertEqual "published tool archive identity joins exact source" (Ok 3) (validatePackageIdentity toolArchive (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" revision)
    assertEqual "published tool wrong source refuses" (Error "package-source-revision-refused") (validatePackageIdentity toolArchive (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" (String.replicate 40 "b"))
    let toolRoot = Path.Combine(temp, "tools")
    let installedRoot = Path.Combine(toolRoot, ".store", "fs.gg.sdd.cli", "1.2.3", "fs.gg.sdd.cli", "1.2.3")
    Directory.CreateDirectory(installedRoot) |> ignore
    File.Copy(toolArchive, Path.Combine(installedRoot, "fs.gg.sdd.cli.1.2.3.nupkg"))
    let installedCore = Path.Combine(installedRoot, "tools", "net10.0", "any", "FS.GG.SDD.Cli.dll")
    Directory.CreateDirectory(Path.GetDirectoryName installedCore) |> ignore
    File.WriteAllText(installedCore, "core")
    File.WriteAllText(Path.Combine(toolRoot, "fsgg-sdd"), "launcher FS.GG.SDD.Cli.dll")
    let authorized = { EntryCount = 3; CorePath = Path.GetFullPath installedCore }
    assertEqual "installed tool authorizes the exact checked managed entrypoint" (Ok authorized)
        (validateInstalledTool toolArchive toolRoot (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" revision "fsgg-sdd")
    File.WriteAllText(installedCore, "changed")
    assertEqual "changed installed tool core refuses" (Error "installed-tool-core-refused")
        (validateInstalledTool toolArchive toolRoot (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" revision "fsgg-sdd")
    File.WriteAllText(installedCore, "core")
    File.WriteAllText(Path.Combine(toolRoot, "fsgg-sdd"), "unbound launcher")
    assertEqual "plain launcher text grants no different execution identity" (Ok authorized)
        (validateInstalledTool toolArchive toolRoot (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" revision "fsgg-sdd")
    File.AppendAllText(Path.Combine(installedRoot, "fs.gg.sdd.cli.1.2.3.nupkg"), "changed")
    assertEqual "changed installed tool archive refuses" (Error "installed-tool-archive-refused")
        (validateInstalledTool toolArchive toolRoot (digest toolArchive) "FS.GG.SDD.Cli" "1.2.3" revision "fsgg-sdd")

    let occupancyContext: Context = {
        Repository = "FS-GG/FS.GG.Templates"; Workflow = "release"
        WorkflowRef = "FS-GG/FS.GG.Templates/.github/workflows/release.yml@refs/heads/main"
        EventName = "workflow_dispatch"; RunId = "42"; RunAttempt = "1"
        CheckoutSha = revision; CheckoutTree = String.replicate 40 "c" }
    let utf8 (value: string) = Encoding.UTF8.GetBytes value
    let response status headers (body: string) = { Status = status; Headers = headers; Body = utf8 body }
    let metadata repository =
        $"{{\"name\":\"FS.GG.Workspace.Template\",\"package_type\":\"nuget\",\"owner\":{{\"login\":\"FS-GG\"}},\"repository\":{{\"full_name\":\"{repository}\"}},\"url\":\"https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template\",\"version_count\":0,\"updated_at\":\"2026-10-01T00:00:00Z\"}}"
    let versionEntry id version =
        $"{{\"id\":{id},\"name\":\"{version}\",\"url\":\"https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template/versions/{id}\"}}"
    let serviceIndex = "{\"resources\":[{\"@id\":\"https://api.nuget.org/v3-flatcontainer/\",\"@type\":\"PackageBaseAddress/3.0.0\"}]}"
    let mutable observedRequests: Request list = []
    let transportFor (active: string list) (deleted: string list) (nuget: string list) overrides : Transport =
        fun request _ ->
            observedRequests <- request :: observedRequests
            match overrides |> Map.tryFind request.Uri.AbsoluteUri with
            | Some value -> value
            | None when request.Uri.AbsoluteUri = "https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template" ->
                response 200 Map.empty (metadata "FS-GG/FS.GG.Templates")
            | None when request.Uri.Query.Contains("state=active") -> response 200 Map.empty ("[" + String.Join(",", active) + "]")
            | None when request.Uri.Query.Contains("state=deleted") -> response 200 Map.empty ("[" + String.Join(",", deleted) + "]")
            | None when request.Uri.AbsoluteUri = "https://api.nuget.org/v3/index.json" -> response 200 Map.empty serviceIndex
            | None when request.Uri.AbsoluteUri = "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/index.json" ->
                response 200 Map.empty ("{\"versions\":[" + (nuget |> List.map (sprintf "\"%s\"") |> String.concat ",") + "]}")
            | None -> response 500 Map.empty "{}"
    let inspect transport limits =
        match inspectWith limits transport occupancyContext "0.17.0" with
        | Ok value -> value
        | Error reason -> failwith reason
    observedRequests <- []
    let absent = inspect (transportFor [] [] [ "0.16.0" ] Map.empty) DefaultLimits
    assertEqual "complete feed censuses prove absence" Verdict.Absent absent.Overall
    assertEqual "public feed requests carry no GitHub credential marker" true
        (observedRequests |> List.filter (fun request -> request.Uri.Host = "api.nuget.org") |> List.forall (fun request -> not request.Authenticated))
    assertEqual "every occupancy request is GET" true (observedRequests |> List.forall (fun request -> request.Method = "GET"))
    let githubOccupied = inspect (transportFor [ versionEntry 1L "0.17.0" ] [] [] Map.empty) DefaultLimits
    assertEqual "active GitHub version occupies candidate" Verdict.Occupied githubOccupied.Overall
    let deletedOccupied = inspect (transportFor [] [ versionEntry 2L "0.17.0" ] [] Map.empty) DefaultLimits
    assertEqual "deleted GitHub version occupies candidate" Verdict.Occupied deletedOccupied.Overall
    let nugetOccupied = inspect (transportFor [] [] [ "0.17.0" ] Map.empty) DefaultLimits
    assertEqual "NuGet version occupies candidate" Verdict.Occupied nugetOccupied.Overall
    assertEqual "successful census omits failure diagnostic" None absent.GitHub.FailureDiagnostic
    assertEqual "deleted empty 200 participates in complete absence" Verdict.Absent absent.GitHub.Verdict
    assertEqual "deleted target 200 remains occupied" Verdict.Occupied deletedOccupied.GitHub.Verdict
    assertEqual "terminal LF candidate is refused absolutely" (Error "candidate-version-refused") (validateCandidate "0.17.0\n")
    assertEqual "terminal CRLF candidate is refused absolutely" (Error "candidate-version-refused") (validateCandidate "0.17.0\r\n")
    assertEqual "occupied exact version cannot be queried through newline candidate" (Error "candidate-version-refused")
        (inspectWith DefaultLimits (transportFor [] [] [ "0.17.0" ] Map.empty) occupancyContext "0.17.0\n")
    let metadataUrl = "https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template"
    let deletedPage1 = "https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template/versions?per_page=100&page=1&state=deleted"
    let activeTwelve = [ 1L .. 12L ] |> List.map (fun id -> versionEntry (100L + id) $"0.1.{id}")
    let forbiddenBody = "{\"message\":\"Resource not accessible by integration\"}"
    let deleted403 = response 403 (Map.ofList [ "X-Accepted-GitHub-Permissions", "packages=write" ]) forbiddenBody
    let observed403 = inspect (transportFor activeTwelve [] [ "0.16.0" ] (Map.ofList [ deletedPage1, deleted403 ])) DefaultLimits
    assertEqual "observed 200/200/403 remains overall unknown" Verdict.Unknown observed403.Overall
    assertEqual "observed deleted failure leaves GitHub incomplete" (Verdict.Unknown, false, [ 200; 200; 403 ], 1, 12)
        (observed403.GitHub.Verdict, observed403.GitHub.Complete, observed403.GitHub.Statuses, observed403.GitHub.Pages, observed403.GitHub.Records)
    assertEqual "independent NuGet absence survives GitHub diagnostic" Verdict.Absent observed403.NuGet.Verdict
    let observedDiagnostic =
        match observed403.GitHub.FailureDiagnostic with
        | Some value -> value
        | None -> failwith "deleted 403 omitted failureDiagnostic"
    assertEqual "deleted diagnostic binds phase page and status" ("deleted", Some 1, 403)
        (observedDiagnostic.Phase, observedDiagnostic.Page, observedDiagnostic.HttpStatus)
    assertEqual "accepted packages write is structured, not flattened"
        ("integration-permission-denied", "valid", [ [ { Name = "packages"; Level = "write" } ] ])
        (observedDiagnostic.ErrorClass, observedDiagnostic.AcceptedPermissionsState, observedDiagnostic.AcceptedPermissionSets)
    assertEqual "failure diagnostic preserves original 403 response hash"
        (Convert.ToHexString(SHA256.HashData(utf8 forbiddenBody)).ToLowerInvariant())
        observed403.GitHub.ResponseSha256.[2]
    let observedReceipt = receiptJson observed403
    assertEqual "serialized diagnostic carries closed fields and structured terms" true
        (observedReceipt.Contains("\"failureDiagnostic\"", StringComparison.Ordinal) &&
         observedReceipt.Contains("\"acceptedPermissionsState\": \"valid\"", StringComparison.Ordinal) &&
         observedReceipt.Contains("\"name\": \"packages\"", StringComparison.Ordinal) &&
         observedReceipt.Contains("\"level\": \"write\"", StringComparison.Ordinal))
    assertEqual "recognized upstream message is not serialized" false
        (observedReceipt.Contains("Resource not accessible", StringComparison.Ordinal))

    assertEqual "missing accepted-permissions header remains explicit" ("absent", []) (parseAcceptedPermissions None)
    assertEqual "accepted-permissions OR alternatives retain AND terms"
        ("valid",
         [ [ { Name = "packages"; Level = "write" } ]
           [ { Name = "packages"; Level = "read" }; { Name = "contents"; Level = "read" } ] ])
        (parseAcceptedPermissions (Some "packages=write; packages=read, contents=read"))
    for name, raw, expectedState in
        [ "unknown permission", "issues=write", "unrecognized"
          "duplicate permission", "packages=read,packages=read", "malformed"
          "conflicting permission", "packages=read,packages=write", "malformed"
          "duplicate alternatives", "packages=read,contents=read;contents=read,packages=read", "malformed"
          "invalid delimiter", "packages:read", "malformed"
          "invalid level", "packages=owner", "unrecognized"
          "control character", "packages=read\n", "malformed"
          "too many alternatives", "packages=read;contents=read;metadata=read;packages=write;contents=write", "malformed"
          "too many AND terms", "packages=read,contents=read,metadata=read,packages=write,contents=write,metadata=write,packages=admin,contents=admin,metadata=admin", "malformed"
          "oversized header", String.replicate 1025 "a", "oversized" ] do
        let state, sets = parseAcceptedPermissions (Some raw)
        assertEqual $"{name} closes accepted-permissions diagnostic" (expectedState, []) (state, sets)

    let sentinel = "CREDENTIAL_SENTINEL_7f31"
    let maliciousHeaders = Map.ofList [ "x-accepted-github-permissions", $"packages=write;{sentinel}=admin"; "cookie", sentinel ]
    let maliciousBody = $"{{\"message\":\"{sentinel}\",\"documentation_url\":\"https://evil.example/{sentinel}\"}}"
    let malicious403 = response 403 maliciousHeaders maliciousBody
    let maliciousResult = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, malicious403 ])) DefaultLimits
    let maliciousReceipt = receiptJson maliciousResult
    assertEqual "unrecognized diagnostic text never enters receipt" false (maliciousReceipt.Contains(sentinel, StringComparison.Ordinal))
    assertEqual "raw response headers never enter receipt" false (maliciousReceipt.Contains("cookie", StringComparison.OrdinalIgnoreCase))
    assertEqual "malicious 403 retains unknown classification" Verdict.Unknown maliciousResult.Overall

    let malformed403Body = "{\"message\":\"Resource not accessible by integration\",\"message\":\"changed\"}"
    let malformed403 = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 Map.empty malformed403Body ])) DefaultLimits
    let malformedDiagnostic = malformed403.GitHub.FailureDiagnostic.Value
    assertEqual "malformed error body is closed without losing status" ("malformed-error", "absent", 403)
        (malformedDiagnostic.ErrorClass, malformedDiagnostic.AcceptedPermissionsState, malformedDiagnostic.HttpStatus)
    assertEqual "malformed error body retains original response hash"
        (Convert.ToHexString(SHA256.HashData(utf8 malformed403Body)).ToLowerInvariant())
        malformed403.GitHub.ResponseSha256.[2]
    let malformedWithPermission = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 (Map.ofList [ "x-accepted-github-permissions", "packages=write" ]) "{}" ])) DefaultLimits
    assertEqual "valid permission header cannot mask malformed body" "malformed-error"
        malformedWithPermission.GitHub.FailureDiagnostic.Value.ErrorClass

    let scope403Body = "{\"message\":\"Your token has not been granted the required scopes to execute this request. The 'read:packages' scope is required.\"}"
    let scopeResult = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 Map.empty scope403Body ])) DefaultLimits
    let scopeDiagnostic = scopeResult.GitHub.FailureDiagnostic.Value
    assertEqual "fixed package scope template records only enumerated scope" ("package-scope-required", [ "read:packages" ])
        (scopeDiagnostic.ErrorClass, scopeDiagnostic.RequiredScopes)
    let adminResult = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 (Map.ofList [ "x-accepted-github-permissions", "packages=admin" ]) forbiddenBody ])) DefaultLimits
    assertEqual "accepted package admin evidence stays diagnostic only" "package-admin-required"
        adminResult.GitHub.FailureDiagnostic.Value.ErrorClass
    let rateResult = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 (Map.ofList [ "x-ratelimit-remaining", "0" ]) forbiddenBody ])) DefaultLimits
    assertEqual "validated rate-limit marker has closed class" "rate-limited"
        rateResult.GitHub.FailureDiagnostic.Value.ErrorClass
    let otherHttp = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 500 Map.empty "{\"message\":\"upstream failure\"}" ])) DefaultLimits
    assertEqual "non-forbidden HTTP failure has closed class" "other-http-error"
        otherHttp.GitHub.FailureDiagnostic.Value.ErrorClass
    let oversizedDiagnosticBody = "{\"message\":\"" + String.replicate (16 * 1024) "x" + "\"}"
    let oversizedDiagnostic = inspect (transportFor [] [] [] (Map.ofList [ deletedPage1, response 403 Map.empty oversizedDiagnosticBody ])) DefaultLimits
    assertEqual "diagnostic body cap retains unknown and original hash" (Verdict.Unknown, "malformed-error", Convert.ToHexString(SHA256.HashData(utf8 oversizedDiagnosticBody)).ToLowerInvariant())
        (oversizedDiagnostic.Overall, oversizedDiagnostic.GitHub.FailureDiagnostic.Value.ErrorClass, oversizedDiagnostic.GitHub.ResponseSha256.[2])
    for status in [ 302; 401; 403; 404 ] do
        let result = inspect (transportFor [] [] [] (Map.ofList [ metadataUrl, response status Map.empty "{}" ])) DefaultLimits
        assertEqual $"GitHub {status} remains unknown" Verdict.Unknown result.GitHub.Verdict
    let metadataFailure = inspect (transportFor [] [] [] (Map.ofList [ metadataUrl, response 403 Map.empty forbiddenBody ])) DefaultLimits
    assertEqual "metadata diagnostic omits page" ("metadata-before", None)
        (metadataFailure.GitHub.FailureDiagnostic.Value.Phase, metadataFailure.GitHub.FailureDiagnostic.Value.Page)
    let wrongRepository = inspect (transportFor [] [] [] (Map.ofList [ metadataUrl, response 200 Map.empty (metadata "FS-GG/Other") ])) DefaultLimits
    assertEqual "wrong package repository remains unknown" Verdict.Unknown wrongRepository.GitHub.Verdict
    let wrongPackageBody = (metadata "FS-GG/FS.GG.Templates").Replace("\"name\":\"FS.GG.Workspace.Template\"", "\"name\":\"FS.GG.Other\"")
    let wrongPackage = inspect (transportFor [] [] [] (Map.ofList [ metadataUrl, response 200 Map.empty wrongPackageBody ])) DefaultLimits
    assertEqual "wrong package name remains unknown" Verdict.Unknown wrongPackage.GitHub.Verdict
    let activePage1 = "https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template/versions?per_page=100&page=1&state=active"
    let activePage2 = "https://api.github.com/orgs/FS-GG/packages/nuget/FS.GG.Workspace.Template/versions?per_page=100&page=2&state=active"
    let later = transportFor [] [] [] (Map.ofList [
        activePage1, response 200 (Map.ofList [ "link", $"<{activePage2}>; rel=\"next\"" ]) "[]"
        activePage2, response 200 Map.empty ("[" + versionEntry 3L "0.17.0" + "]") ])
    assertEqual "target on later GitHub page occupies candidate" Verdict.Occupied (inspect later DefaultLimits).Overall
    let offHost = transportFor [] [] [] (Map.ofList [ activePage1, response 200 (Map.ofList [ "link", "<https://evil.example/page=2>; rel=\"next\"" ]) "[]" ])
    assertEqual "off-host pagination remains unknown" Verdict.Unknown (inspect offHost DefaultLimits).GitHub.Verdict
    let repeated = transportFor [] [] [] (Map.ofList [ activePage1, response 200 (Map.ofList [ "link", $"<{activePage1}>; rel=\"next\"" ]) "[]" ])
    assertEqual "repeated pagination remains unknown" Verdict.Unknown (inspect repeated DefaultLimits).GitHub.Verdict
    let unfinished = transportFor [] [] [] (Map.ofList [ activePage1, response 200 (Map.ofList [ "link", "malformed" ]) "[]" ])
    assertEqual "unfinished pagination remains unknown" Verdict.Unknown (inspect unfinished DefaultLimits).GitHub.Verdict
    let duplicateJson = response 200 Map.empty "{\"versions\":[],\"versions\":[]}"
    let malformed = inspect (transportFor [] [] [] (Map.ofList [ "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/index.json", duplicateJson ])) DefaultLimits
    assertEqual "duplicate authoritative JSON field remains unknown" Verdict.Unknown malformed.NuGet.Verdict
    let malformedVersion = inspect (transportFor [] [] [ "not a version" ] Map.empty) DefaultLimits
    assertEqual "malformed served version remains unknown" "malformed-version-identity" malformedVersion.NuGet.Reason
    let newlineVersion = inspect (transportFor [] [] [ "0.17.0\\n" ] Map.empty) DefaultLimits
    assertEqual "served version with terminal LF remains unknown" "malformed-version-identity" newlineVersion.NuGet.Reason
    let repeatedIdentity = inspect (transportFor [ versionEntry 9L "0.16.0" ] [ versionEntry 10L "0.16.0" ] [] Map.empty) DefaultLimits
    assertEqual "contradictory GitHub version state remains unknown" "github-version-identity-repeated" repeatedIdentity.GitHub.Reason
    let mutable metadataReads = 0
    let changedMetadata : Transport = fun request timeout ->
        if request.Uri.AbsoluteUri = metadataUrl then
            metadataReads <- metadataReads + 1
            response 200 Map.empty ((metadata "FS-GG/FS.GG.Templates").Replace("2026-10-01T00:00:00Z", if metadataReads = 1 then "2026-10-01T00:00:00Z" else "2026-10-01T00:00:01Z"))
        else (transportFor [] [] [] Map.empty) request timeout
    assertEqual "metadata change across census remains unknown" "github-metadata-changed" (inspect changedMetadata DefaultLimits).GitHub.Reason
    let timingOut : Transport = fun _ _ -> raise (TimeoutException())
    assertEqual "transport timeout remains unknown" Verdict.Unknown (inspect timingOut DefaultLimits).Overall
    let lateLimits = { DefaultLimits with RequestTimeout = TimeSpan.FromMilliseconds 100.0; AcquisitionTimeout = TimeSpan.FromMilliseconds 250.0 }
    let lateFinal : Transport = fun request timeout ->
        if request.Uri.AbsoluteUri = "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/index.json" then Thread.Sleep 350
        (transportFor [] [] [ "0.16.0" ] Map.empty) request timeout
    let lateClock = Stopwatch.StartNew()
    let lateResult = inspect lateFinal lateLimits
    assertEqual "late final response cannot classify absence" Verdict.Unknown lateResult.Overall
    assertEqual "late final response reports acquisition exhaustion" "acquisition-time-limit" lateResult.NuGet.Reason
    assertEqual "late final control actually crossed aggregate deadline" true (lateClock.Elapsed >= lateLimits.AcquisitionTimeout)
    let bodyCancelled = TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously)
    use stalledHandler =
        { new HttpMessageHandler() with
            override _.SendAsync(_, _) =
                let reply = new HttpResponseMessage(HttpStatusCode.OK)
                reply.Content <- new StreamContent(new StallingStream(bodyCancelled))
                Task.FromResult(reply) }
    let stalledTransport = httpTransportWithHandler "unused" stalledHandler
    let stalledClock = Stopwatch.StartNew()
    let stalledCancelled =
        try
            stalledTransport { Uri = Uri("https://api.nuget.org/v3/index.json"); Method = "GET"; Authenticated = false } (TimeSpan.FromMilliseconds 75.0) |> ignore
            false
        with :? OperationCanceledException -> true
    assertEqual "stalled response body observes request cancellation" true stalledCancelled
    assertEqual "cancellation reaches the response body stream" true (bodyCancelled.Task.Wait(TimeSpan.FromSeconds 1.0))
    assertEqual "stalled response body completes within bounded control window" true (stalledClock.Elapsed < TimeSpan.FromMilliseconds 500.0)
    let mutable boundaryCalls = 0
    let mutable boundaryAuthorization: AuthenticationHeaderValue option = None
    use boundaryHandler =
        { new HttpMessageHandler() with
            override _.SendAsync(request, _) =
                boundaryCalls <- boundaryCalls + 1
                boundaryAuthorization <- Option.ofObj request.Headers.Authorization
                let reply = new HttpResponseMessage(HttpStatusCode.OK)
                reply.Content <- new StringContent("{}", Encoding.UTF8, "application/json")
                Task.FromResult(reply) }
    let boundaryTransport = httpTransportWithHandler sentinel boundaryHandler
    let refusesBoundary name request =
        try boundaryTransport request (TimeSpan.FromSeconds 1.0) |> ignore; failwith $"{name}: expected refusal"
        with :? InvalidOperationException -> printfn "PASS %s" name
    refusesBoundary "production transport refuses non-GET" { Uri = Uri("https://api.github.com/"); Method = "POST"; Authenticated = true }
    refusesBoundary "production transport refuses authenticated off-host request" { Uri = Uri("https://api.nuget.org/v3/index.json"); Method = "GET"; Authenticated = true }
    assertEqual "refused requests never reach handler" 0 boundaryCalls
    boundaryTransport { Uri = Uri("https://api.nuget.org/v3/index.json"); Method = "GET"; Authenticated = false } (TimeSpan.FromSeconds 1.0) |> ignore
    assertEqual "public NuGet request carries no Authorization header" None boundaryAuthorization
    let tiny = { DefaultLimits with MaxResponseBytes = 2 }
    assertEqual "response size exhaustion remains unknown" Verdict.Unknown (inspect (transportFor [] [] [] Map.empty) tiny).Overall
    let tinyTotal = { DefaultLimits with MaxTotalBytes = 400L }
    let totalLimited = inspect (transportFor [] [] [] Map.empty) tinyTotal
    assertEqual "overall byte exhaustion remains unknown" true
        (totalLimited.GitHub.Reason = "total-size-limit" || totalLimited.NuGet.Reason = "total-size-limit")
    let onePage = { DefaultLimits with MaxGitHubPages = 1 }
    assertEqual "GitHub page bound cannot look absent" Verdict.Unknown (inspect (transportFor [] [] [] Map.empty) onePage).GitHub.Verdict
    let noItems = { DefaultLimits with MaxItemsPerPage = 0 }
    assertEqual "GitHub item bound cannot look complete" "github-page-item-limit"
        (inspect (transportFor [ versionEntry 11L "0.16.0" ] [] [] Map.empty) noItems).GitHub.Reason
    let nugetIndexUrl = "https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/index.json"
    let nugetNotFound = inspect (transportFor [] [] [] (Map.ofList [ nugetIndexUrl, response 404 Map.empty "{}" ])) DefaultLimits
    assertEqual "NuGet 404 remains unknown" Verdict.Unknown nugetNotFound.NuGet.Verdict
    let aliasOccupied = inspect (transportFor [] [] [ "0.17.0.0+repository" ] Map.empty) DefaultLimits
    assertEqual "NuGet zero-fourth/build alias occupies candidate" Verdict.Occupied aliasOccupied.Overall
    let prereleaseAbsent = inspect (transportFor [] [] [ "0.17.0-rc.1" ] Map.empty) DefaultLimits
    assertEqual "prerelease remains a different identity" Verdict.Absent prereleaseAbsent.Overall
    let ambiguousAlias = inspect (transportFor [] [] [ "0.17.0"; "0.17.0.0" ] Map.empty) DefaultLimits
    assertEqual "duplicate normalized NuGet aliases remain unknown" Verdict.Unknown ambiguousAlias.NuGet.Verdict
    assertEqual "canonical stable candidate accepted" (Ok "0.17.0") (validateCandidate "0.17.0")
    assertEqual "prerelease candidate refused" (Error "candidate-version-refused") (validateCandidate "0.17.0-rc.1")
    let sanitized = receiptJson absent
    assertEqual "receipt contains hashes rather than raw censuses" false (sanitized.Contains("0.16.0", StringComparison.Ordinal))
    assertEqual "successful receipt omits optional failureDiagnostic" false (sanitized.Contains("failureDiagnostic", StringComparison.Ordinal))
    Directory.Delete(temp, true)
    0
