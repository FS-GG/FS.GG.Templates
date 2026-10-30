module FsGgTemplates.ReferencePublication

open System
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text
open System.Text.RegularExpressions
open System.Text.Json
open System.Xml.Linq
open FsGgTemplates.ProviderComposition

type Request = {
    Archive: string
    Descriptor: string
    ExpectedSha256: string
    ExpectedVersion: string
    ExpectedRevision: string
    ExpectedTagRevision: string
    ExpectedDescriptorSha256: string
    Provider: Provider
}

type InstalledTool = { EntryCount: int; CorePath: string }

let private packageId = "FS.GG.Workspace.Template"
let private version = "0.18.1"
// Additive WASM successors. 0.19.1 and later carry the byte-exact C guest sources that 0.19.0 Complete
// scaffolds truncated; 0.19.3 adopts FS.GG.Wasm 0.7.0 (FS-GG/FS.GG.Game#727). All keep the same
// source closure.
let private wasmSuccessors = [ "0.19.0"; "0.19.1"; "0.19.2"; "0.19.3" ]
// Current public successors (FS-GG/.github#4709). 0.19.3 becomes the newest public default that
// the public Wizard (0.22.0) resolves; 0.19.2 remains an accepted historical successor. Unlike the
// direct-only WASM successors, these are also admitted on the provider and Wizard receiver routes.
let private currentPublicSuccessors = [ "0.19.2"; "0.19.3" ]
let private supportedVersions = version :: wasmSuccessors
let private templateId = "fs-gg-fable-game"
let private hex64 = Regex("^[0-9a-f]{64}$", RegexOptions.CultureInvariant)
let private hex40 = Regex("^[0-9a-f]{40}$", RegexOptions.CultureInvariant)
let private required =
    [ "content/templates/fs-gg-fable-game/.template.config/template.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/ExternalAuthorityReference.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/Examples/ExternalAuthority/reference.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj"
      "content/templates/fs-gg-fable-game/SvgFoundation/Program.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/build.sh"
      "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]

// Additional source closure for the selected additive successor. Historical reference
// membership remains mandatory; neither this closure nor a direct receiver accepts AT.
let private wasmRelative =
    [ "SvgFoundation/SvgFoundation.fsproj"
      "SvgFoundation/Program.fs"
      "SvgFoundation/build.sh"
      "SvgFoundation/vite.config.js"
      "SvgFoundation/packages.lock.json"
      "SvgFoundation/Examples/Wasm/WasmPolicyExample.fs"
      "SvgFoundation/Examples/Wasm/WasmPolicyExample.Tests.fs"
      "SvgFoundation/Examples/Wasm/WasmPolicyBrowser.fs"
      "SvgFoundation/Examples/Wasm/README.md"
      "SvgFoundation/Examples/Wasm/materialize-assets.py"
      "SvgFoundation/Examples/Wasm/build-guests.sh"
      "SvgFoundation/Examples/Wasm/packages.lock.json"
      "SvgFoundation/Examples/Wasm/guest/policy.c"
      "SvgFoundation/Examples/Wasm/guest/rust/Cargo.toml"
      "SvgFoundation/Examples/Wasm/guest/rust/Cargo.lock"
      "SvgFoundation/Examples/Wasm/guest/rust/src/lib.rs"
      "Browser.Tests/wasm-policy.spec.ts"
      "Browser.Tests/playwright.config.ts" ]

let private refuse message = Error message
let private sha256 path =
    use stream = File.OpenRead path
    Convert.ToHexString(SHA256.HashData stream).ToLowerInvariant()
let private regularFile path =
    File.Exists path
    && not ((File.GetAttributes path &&& FileAttributes.ReparsePoint) = FileAttributes.ReparsePoint)

let validatePackageIdentity (archive: string) (expectedSha: string) (expectedId: string) (expectedVersion: string) (expectedRevision: string) =
    if not (File.Exists archive) then refuse "input-file-missing"
    elif not (hex64.IsMatch expectedSha) || not (hex40.IsMatch expectedRevision) then refuse "expected-identity-refused"
    elif sha256 archive <> expectedSha then refuse "archive-sha256-refused"
    else
        try
            use package = ZipFile.OpenRead archive
            let nuspecs = package.Entries |> Seq.filter (fun e -> e.FullName.EndsWith(".nuspec", StringComparison.OrdinalIgnoreCase)) |> Seq.toList
            match nuspecs with
            | [ nuspec ] ->
                use stream = nuspec.Open()
                let doc = XDocument.Load stream
                let values name = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = name) |> Seq.map _.Value |> Seq.toList
                let repositories = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = "repository") |> Seq.toList
                if values "id" <> [ expectedId ] || values "version" <> [ expectedVersion ] then refuse "package-identity-refused"
                elif repositories.Length <> 1 || isNull (repositories.Head.Attribute(XName.Get "commit"))
                     || repositories.Head.Attribute(XName.Get "commit").Value <> expectedRevision then refuse "package-source-revision-refused"
                else Ok package.Entries.Count
            | _ -> refuse "package-nuspec-census-refused"
        with :? InvalidDataException -> refuse "archive-format-refused"

let validateInstalledTool (archive: string) (toolRoot: string) (expectedSha: string) (expectedId: string) (expectedVersion: string) (expectedRevision: string) (commandName: string) =
    match validatePackageIdentity archive expectedSha expectedId expectedVersion expectedRevision with
    | Error reason -> Error reason
    | Ok _ ->
        let lowerId = expectedId.ToLowerInvariant()
        let lowerVersion = expectedVersion.ToLowerInvariant()
        let packageRoot = Path.Combine(toolRoot, ".store", lowerId, lowerVersion, lowerId, lowerVersion)
        let installedArchive = Path.Combine(packageRoot, lowerId + "." + lowerVersion + ".nupkg")
        if not (Directory.Exists packageRoot) || not (regularFile installedArchive) then refuse "installed-tool-custody-refused"
        elif sha256 installedArchive <> expectedSha then refuse "installed-tool-archive-refused"
        else
            match validatePackageIdentity installedArchive expectedSha expectedId expectedVersion expectedRevision with
            | Ok count ->
                use package = ZipFile.OpenRead archive
                let settings = package.Entries |> Seq.filter (fun e -> e.FullName.EndsWith("/DotnetToolSettings.xml", StringComparison.Ordinal)) |> Seq.toList
                match settings with
                | [ setting ] ->
                    use stream = setting.Open()
                    let doc = XDocument.Load stream
                    let commands = doc.Descendants() |> Seq.filter (fun e -> e.Name.LocalName = "Command") |> Seq.toList
                    match commands with
                    | [ declared ] ->
                        let attribute name = declared.Attribute(XName.Get name) |> Option.ofObj |> Option.map _.Value
                        match attribute "Name", attribute "EntryPoint", attribute "Runner" with
                        | Some declaredName, Some entryPoint, Some "dotnet" when declaredName = commandName ->
                            let entryPrefix = setting.FullName.Substring(0, setting.FullName.LastIndexOf('/') + 1)
                            let coreEntry = package.GetEntry(entryPrefix + entryPoint)
                            let corePath = Path.Combine(packageRoot, (entryPrefix + entryPoint).Replace('/', Path.DirectorySeparatorChar))
                            if isNull coreEntry || not (regularFile corePath) then refuse "installed-tool-core-refused"
                            else
                                use source = coreEntry.Open()
                                use target = File.OpenRead corePath
                                let coreMatches = SHA256.HashData(source).AsSpan().SequenceEqual(SHA256.HashData(target))
                                if coreMatches then Ok { EntryCount = count; CorePath = Path.GetFullPath corePath }
                                else refuse "installed-tool-core-refused"
                        | _ -> refuse "installed-tool-command-refused"
                    | _ -> refuse "installed-tool-command-refused"
                | _ -> refuse "installed-tool-settings-refused"
            | Error reason -> Error reason

let private uniqueObject (element: JsonElement) =
    let rec walk (value: JsonElement) =
        match value.ValueKind with
        | JsonValueKind.Object ->
            let properties = value.EnumerateObject() |> Seq.toList
            (properties |> List.map _.Name |> Set.ofList).Count = properties.Length
            && (properties |> List.forall (fun (p: JsonProperty) -> walk p.Value))
        | JsonValueKind.Array -> value.EnumerateArray() |> Seq.forall walk
        | _ -> true
    walk element

let private validateReceiverCore (currentD5: bool) (bundle: string) (archive: string) (receiver: string) (route: string) (expectedLifecycle: string) (expectedGeneratorVersion: string) (productName: string) =
    let omittedBundle = bundle = "omitted"
    let bundle = if omittedBundle then "player" else bundle
    if not (File.Exists archive) || not (Directory.Exists receiver) then refuse "receiver-input-missing"
    elif not ([ "direct"; "provider"; "wizard" ] |> List.contains route) then refuse "receiver-route-refused"
    elif not (([ "none"; "typed-sdd"; "sdd" ] @ (if currentD5 then [ "spec-kit" ] else [])) |> List.contains expectedLifecycle) then refuse "receiver-lifecycle-refused"
    elif route = "direct" && expectedLifecycle <> "none" then refuse "receiver-lifecycle-refused"
    // Only the Wizard route may claim `sdd`: Wizard 0.21.0 forwarded it as its omitted default for current
    // fable-game descriptors (0.22.0 forwards the descriptor default typed-sdd, .github#4811), and an explicit
    // --lifecycle sdd is forwarded unchanged. The recorded provenance must still equal it exactly.
    elif expectedLifecycle = "sdd" && route <> "wizard" && not currentD5 then refuse "receiver-lifecycle-refused"
    elif not (Regex.IsMatch(productName, "^[A-Za-z_][A-Za-z0-9_']*$", RegexOptions.CultureInvariant)) then refuse "receiver-product-name-refused"
    else
        try
            use package = ZipFile.OpenRead archive
            let prefix = "content/templates/fs-gg-fable-game/"
            let bytes (entry: ZipArchiveEntry) =
                use stream = entry.Open()
                use memory = new MemoryStream()
                stream.CopyTo memory
                memory.ToArray()
            let templateEntry = package.GetEntry(prefix + ".template.config/template.json")
            if isNull templateEntry then raise (InvalidDataException "template config missing")
            use templateDoc = JsonDocument.Parse(bytes templateEntry)
            let templateRoot = templateDoc.RootElement
            let mutable symbols = Unchecked.defaultof<JsonElement>
            let mutable effectiveName = Unchecked.defaultof<JsonElement>
            let mutable effectiveIdentifier = Unchecked.defaultof<JsonElement>
            let mutable nameReplaces = Unchecked.defaultof<JsonElement>
            let mutable nameFileRename = Unchecked.defaultof<JsonElement>
            let mutable nameParameters = Unchecked.defaultof<JsonElement>
            let mutable nameSource = Unchecked.defaultof<JsonElement>
            let mutable nameFallback = Unchecked.defaultof<JsonElement>
            let mutable identifierReplaces = Unchecked.defaultof<JsonElement>
            let mutable identifierParameters = Unchecked.defaultof<JsonElement>
            let mutable identifierSource = Unchecked.defaultof<JsonElement>
            let mutable identifierFallback = Unchecked.defaultof<JsonElement>
            let templateContract =
                uniqueObject templateRoot
                && templateRoot.TryGetProperty("symbols", &symbols)
                && symbols.TryGetProperty("effectiveName", &effectiveName)
                && symbols.TryGetProperty("effectiveIdentifier", &effectiveIdentifier)
                && effectiveName.TryGetProperty("replaces", &nameReplaces)
                && effectiveIdentifier.TryGetProperty("replaces", &identifierReplaces)
                && effectiveName.TryGetProperty("fileRename", &nameFileRename)
                && effectiveName.TryGetProperty("parameters", &nameParameters)
                && nameParameters.TryGetProperty("sourceVariableName", &nameSource)
                && nameParameters.TryGetProperty("fallbackVariableName", &nameFallback)
                && effectiveIdentifier.TryGetProperty("parameters", &identifierParameters)
                && identifierParameters.TryGetProperty("sourceVariableName", &identifierSource)
                && identifierParameters.TryGetProperty("fallbackVariableName", &identifierFallback)
                && nameReplaces.GetString() = "FableGameWorkspace"
                && nameFileRename.GetString() = "FableGameWorkspace"
                && nameSource.GetString() = "productNameTrimmed"
                && nameFallback.GetString() = "name"
                && identifierReplaces.GetString() = "FableGameWorkspaceNamespace"
                && identifierSource.GetString() = "rootNamespaceTrimmed"
                && identifierFallback.GetString() = "effectiveName"
            if not templateContract then raise (InvalidDataException "template transform contract refused")
            if currentD5 then
                let choices (name: string) = symbols.GetProperty(name).GetProperty("choices").EnumerateArray() |> Seq.map (fun row -> row.GetProperty("choice").GetString()) |> Seq.toList
                if choices "lifecycle" <> [ "none"; "sdd"; "typed-sdd"; "spec-kit" ]
                   || choices "bundle" <> [ "player"; "studio"; "tactical"; "arcade"; "complete" ]
                   || symbols.GetProperty("lifecycle").GetProperty("defaultValue").GetString() <> "typed-sdd"
                   || symbols.GetProperty("bundle").GetProperty("defaultValue").GetString() <> "player" then
                    raise (InvalidDataException "template transform contract refused")
            let invariant =
                if currentD5 && bundle <> "complete" then [ prefix + "SvgFoundation/build.sh" ]
                else
                    [ "content/templates/fs-gg-fable-game/SvgFoundation/Examples/ExternalAuthority/reference.json"
                      "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
                      "content/templates/fs-gg-fable-game/SvgFoundation/build.sh" ]
            let transformed =
                if currentD5 && bundle <> "complete" then [ prefix + "Browser.Tests/two-client.spec.ts" ]
                else
                    [ "content/templates/fs-gg-fable-game/SvgFoundation/ExternalAuthorityReference.fs"
                      "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
                      "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]
            let exact name expected =
                let entry = package.GetEntry name
                let relative = name.Substring(prefix.Length)
                let output = Path.Combine(receiver, relative.Replace('/', Path.DirectorySeparatorChar))
                if isNull entry || not (regularFile output) then false
                else expected (bytes entry) (File.ReadAllBytes output)
            let same (left: byte array) (right: byte array) = left.AsSpan().SequenceEqual right
            let replaced (raw: byte array) (actual: byte array) =
                let text = UTF8Encoding(false, true).GetString raw
                if not (text.Contains("FableGameWorkspaceNamespace", StringComparison.Ordinal)) then false
                else same (UTF8Encoding(false).GetBytes(text.Replace("FableGameWorkspaceNamespace", productName, StringComparison.Ordinal))) actual
            let successorWasmMismatch, successorRouteMismatch =
                let nuspecs = package.Entries |> Seq.filter (fun e -> e.FullName.EndsWith(".nuspec", StringComparison.OrdinalIgnoreCase)) |> Seq.toList
                match nuspecs with
                | [ nuspec ] ->
                    use stream = nuspec.Open()
                    let doc = XDocument.Load stream
                    let versions = doc.Descendants() |> Seq.filter (fun e -> e.Name.LocalName = "version") |> Seq.map _.Value |> Seq.toList
                    match versions with
                    | [ selected ] when List.contains selected wasmSuccessors ->
                        let templateTransform (raw: byte array) (actual: byte array) =
                            let text = UTF8Encoding(false, true).GetString raw
                            same (UTF8Encoding(false).GetBytes(text.Replace("FableGameWorkspaceNamespace", productName, StringComparison.Ordinal).Replace("FableGameWorkspace", productName, StringComparison.Ordinal))) actual
                        let selectedClosure =
                            if currentD5 then
                                (if bundle = "complete" then wasmRelative else
                                    [ "SvgFoundation/SvgFoundation.fsproj"; "SvgFoundation/Program.fs"; "SvgFoundation/build.sh"
                                      "SvgFoundation/packages.lock.json"; "SvgFoundation/vite.config.js" ])
                                @ (if bundle <> "player" then [ "SvgFoundation/Studio/Studio.fsproj"; "SvgFoundation/Studio/Program.fs" ] else [])
                                @ (if bundle = "tactical" || bundle = "complete" then [ "SvgFoundation/Examples/Tactical/scene.json" ] else [])
                                @ (if bundle = "arcade" || bundle = "complete" then [ "SvgFoundation/Examples/Arcade/scene.json" ] else [])
                            else wasmRelative
                        let mismatch = selectedClosure |> List.exists (fun name -> not (exact (prefix + name) templateTransform))
                        mismatch, (not (List.contains selected currentPublicSuccessors) && route <> "direct")
                    | _ -> false, false
                | _ -> true, false
            let mismatched =
                successorWasmMismatch
                || (invariant |> List.exists (fun name -> not (exact name same)))
                || (transformed |> List.exists (fun name -> not (exact name replaced)))
            // The WASM successors' accepted scope is direct-only. A caller cannot relabel this
            // successor as installed SDD/Wizard success through the generic checker.
            if successorRouteMismatch then refuse "receiver-successor-route-refused"
            elif not (regularFile (Path.Combine(receiver, productName + ".slnx"))) then refuse "receiver-product-name-refused"
            elif mismatched then refuse "receiver-source-closure-refused"
            elif currentD5 &&
                 ([ "SvgFoundation/Studio", bundle <> "player"
                    "SvgFoundation/Examples/Tactical", bundle = "tactical" || bundle = "complete"
                    "SvgFoundation/Examples/Arcade", bundle = "arcade" || bundle = "complete"
                    "SvgFoundation/Examples/FourD", bundle = "complete"
                    "SvgFoundation/Examples/ExternalAuthority", bundle = "complete"
                    "SvgFoundation/Examples/Wasm", bundle = "complete" ]
                  |> List.exists (fun (relative, expected) -> Directory.Exists(Path.Combine(receiver, relative)) <> expected)) then
                refuse "receiver-bundle-contents-refused"
            elif route = "direct" then Ok ()
            else
                let provenancePath = Path.Combine(receiver, ".fsgg", "scaffold-provenance.json")
                if not (File.Exists provenancePath) then refuse "receiver-provenance-missing"
                else
                    use doc = JsonDocument.Parse(File.ReadAllBytes provenancePath)
                    let root = doc.RootElement
                    if not (uniqueObject root) then refuse "receiver-provenance-duplicate-field-refused"
                    else
                        let mutable generator = Unchecked.defaultof<JsonElement>
                        let mutable providerName = Unchecked.defaultof<JsonElement>
                        let mutable templateRef = Unchecked.defaultof<JsonElement>
                        let mutable parameters = Unchecked.defaultof<JsonElement>
                        if not (root.TryGetProperty("generator", &generator) && root.TryGetProperty("providerName", &providerName)
                                && root.TryGetProperty("templateRef", &templateRef) && root.TryGetProperty("effectiveParameters", &parameters)) then
                            refuse "receiver-provenance-shape-refused"
                        else
                            let mutable generatorId = Unchecked.defaultof<JsonElement>
                            let mutable generatorVersion = Unchecked.defaultof<JsonElement>
                            let generatorOk = generator.TryGetProperty("id", &generatorId) && generator.TryGetProperty("version", &generatorVersion)
                            let lifecycle =
                                parameters.EnumerateArray()
                                |> Seq.choose (fun row ->
                                    let mutable key = Unchecked.defaultof<JsonElement>
                                    let mutable value = Unchecked.defaultof<JsonElement>
                                    if row.TryGetProperty("key", &key) && row.TryGetProperty("value", &value) && key.GetString() = "lifecycle" then Some(value.GetString()) else None)
                                |> Seq.toList
                            let parameter key =
                                parameters.EnumerateArray()
                                |> Seq.choose (fun row ->
                                    let mutable actualKey = Unchecked.defaultof<JsonElement>
                                    let mutable value = Unchecked.defaultof<JsonElement>
                                    if row.TryGetProperty("key", &actualKey) && row.TryGetProperty("value", &value) && actualKey.GetString() = key then Some(value.GetString()) else None)
                                |> Seq.toList
                            if not generatorOk || generatorId.GetString() <> "FS.GG.SDD.Artifacts" || generatorVersion.GetString() <> expectedGeneratorVersion then refuse "receiver-generator-refused"
                            elif providerName.GetString() <> "fable-game" || templateRef.GetString() <> templateId then refuse "receiver-provider-source-refused"
                            elif lifecycle <> [ expectedLifecycle ] then refuse "receiver-lifecycle-refused"
                            elif parameter "productName" <> [ productName ] then refuse "receiver-product-name-refused"
                            elif currentD5 && parameter "bundle" <> [ bundle ] && not (omittedBundle && parameter "bundle" = []) then refuse "receiver-bundle-refused"
                            else Ok ()
        with
        | :? JsonException -> refuse "receiver-provenance-json-refused"
        | :? InvalidDataException as ex when ex.Message = "template transform contract refused" -> refuse "receiver-template-contract-refused"
        | :? InvalidDataException -> refuse "archive-format-refused"


// Preserve the historical complete-only receiver contract byte-for-byte in behavior.
let validateReceiver archive receiver route lifecycle generator product =
    validateReceiverCore false "complete" archive receiver route lifecycle generator product

let currentD5Cases scope =
    if scope <> "rehearsal" && scope <> "full" then Error "current-d5-scope-refused"
    else
        let omitted = [ "provider-omitted", "provider", "omitted", "omitted"; "wizard-omitted", "wizard", "omitted", "omitted" ]
        let matrix =
            [ for route in [ "provider"; "wizard" ] do
                for lifecycle in [ "none"; "sdd"; "typed-sdd"; "spec-kit" ] do
                    for bundle in [ "player"; "studio"; "tactical"; "arcade"; "complete" ] do
                        yield route + "-" + lifecycle + "-" + bundle, route, lifecycle, bundle ]
        Ok (omitted @ (if scope = "full" then matrix else []))

let currentD5AuthorArguments root work cache bindings =
    if not (List.contains work [ "d5-default"; "d5-refused" ]) then Error "current-d5-work-refused"
    else Ok [ "typed-sdd"; "author"; "--root"; root; "--work"; work; "--title"; "Current public D5"
              "--agent"; "composition"; "--session"; "current-public"; "--cache"; cache
              "--profile"; "fsgg-quint-profile/2"; "--source"; "models/svg-arena/arena-rules.md"; "--bindings"; bindings ]

// Source/provenance seam for synthetic controls; the CLI wrapper below also pins public bytes.
let validateCurrentD5ReceiverSource archive receiver route lifecycle bundle product =
    if not (File.Exists archive) then Error "receiver-input-missing"
    elif not (List.contains bundle [ "omitted"; "player"; "studio"; "tactical"; "arcade"; "complete" ]) then Error "current-d5-bundle-refused"
    else
        match validatePackageIdentity archive (sha256 archive) packageId "0.19.3" "7be0bcf5886d39a8161b186beb8cc06e82415f1e" with
        | Error reason -> Error reason
        | Ok _ -> validateReceiverCore true bundle archive receiver route lifecycle "2.4.0" product

let validateCurrentD5Receiver archive receiver route lifecycle bundle product =
    if not (File.Exists archive) then Error "receiver-input-missing"
    elif sha256 archive <> "9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2" then
        Error "current-d5-public-archive-refused"
    else validateCurrentD5ReceiverSource archive receiver route lifecycle bundle product

let validateCurrentD5Pins (json: string) =
    try
        use doc = JsonDocument.Parse json
        let root = doc.RootElement
        let rows =
            [ "templates", [ "version", "0.19.3"; "sha256", "9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2"; "sourceCommit", "7be0bcf5886d39a8161b186beb8cc06e82415f1e"; "providerSha256", "6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006" ]
              "sdd", [ "version", "2.4.0"; "sha256", "1df2e74faebd388f90b813ed9d7497f4247f977718469c9247b37111d791921f"; "sourceCommit", "c1fee66a34ec8d222586eb708ddff4973ad5594e" ]
              "wizard", [ "version", "0.22.0"; "sha256", "caa91285e5370edc7a8a14a5a46f6cfef236d1db95f1e186357e6591b9ec7bd5"; "sourceCommit", "6e6fb9b9f7677e26f0c7d58cab1646323e81df58" ]
              "overlay", [ "version", "0.18.2"; "sha256", "496aad0e89496719bc543edc6ffbf829a82307862e630ba4e174e374ac11cc4e"; "sourceCommit", "20c009bc6728302f9ed06fdf49cb2e8bd19e417d" ] ]
        if not (uniqueObject root) || (root.EnumerateObject() |> Seq.length) <> 5
           || root.GetProperty("schema").GetString() <> "fsgg.svg-release-d5.current-public-pins/1"
           || (rows |> List.exists (fun (role, fields) ->
               let value = root.GetProperty role
               (value.EnumerateObject() |> Seq.length) <> fields.Length
               || (fields |> List.exists (fun (key, expected) -> value.GetProperty(key).GetString() <> expected)))) then
            Error "current-d5-pins-refused"
        else Ok ()
    with _ -> Error "current-d5-pins-refused"

let validateCurrentD5Backend receiver authorPath inspectPath refusedPath beforePath afterPath =
    try
        let read (path: string) = JsonDocument.Parse(File.ReadAllBytes path)
        use author = read authorPath
        use inspect = read inspectPath
        use refused = read refusedPath
        use before = read beforePath
        use after = read afterPath
        use authority = read (Path.Combine(receiver, "readiness/d5-default/typed-authority.json"))
        let succeeded (doc: JsonDocument) =
            uniqueObject doc.RootElement && doc.RootElement.GetProperty("outcome").GetString() = "succeeded"
            && doc.RootElement.GetProperty("classification").GetString() = "quint-specification-v1"
        let map (doc: JsonDocument) = doc.RootElement.EnumerateObject() |> Seq.map (fun p -> p.Name, p.Value.GetString()) |> Map.ofSeq
        let manifest = authority.RootElement
        let prefix = Path.GetFullPath(receiver).TrimEnd(Path.DirectorySeparatorChar) + string Path.DirectorySeparatorChar
        let artifactBad = manifest.GetProperty("artifacts").EnumerateArray() |> Seq.exists (fun item ->
            let path = Path.GetFullPath(Path.Combine(receiver, item.GetProperty("path").GetString()))
            not (path.StartsWith(prefix, StringComparison.Ordinal)) || not (regularFile path)
            || sha256 path <> item.GetProperty("sha256").GetString())
        let excluded = Set.ofList [ ".git"; ".nuget"; "node_modules"; "bin"; "obj" ]
        let rec observedFiles directory = seq {
            for path in Directory.EnumerateFileSystemEntries directory do
                if Directory.Exists path then
                    if not (excluded.Contains(Path.GetFileName path)) then
                        if (File.GetAttributes path &&& FileAttributes.ReparsePoint) <> enum<FileAttributes> 0 then
                            raise (InvalidDataException "receiver symlink")
                        yield! observedFiles path
                else
                    if not (regularFile path) then raise (InvalidDataException "receiver nonregular file")
                    yield Path.GetRelativePath(receiver, path).Replace('\\', '/') }
        let actualFiles = observedFiles receiver |> Set.ofSeq
        let refusal = refused.RootElement
        if not (succeeded author && succeeded inspect && uniqueObject manifest && uniqueObject refusal
                && uniqueObject before.RootElement && uniqueObject after.RootElement)
           || manifest.GetProperty("backend").GetString() <> "quint-specification-v1"
           || manifest.GetProperty("profileIdentity").GetString() <> "fsgg-quint-profile/2"
           || manifest.GetProperty("packageIdentity").GetString() <> "FS.GG.SDD.Artifacts/2.4.0"
           || manifest.GetProperty("artifacts").GetArrayLength() = 0 || artifactBad
           || refusal.GetProperty("outcome").GetString() <> "blocked" || refusal.GetProperty("changedPaths").GetArrayLength() <> 0
           || not (refusal.GetProperty("diagnostics").EnumerateArray() |> Seq.exists (fun d -> d.GetProperty("id").GetString() = "QUINT-PROFILE-IDENTITY"))
           || (map before).Count = 0
           || not ((map before).ContainsKey "readiness/d5-default/typed-authority.json")
           || not ((map before).ContainsKey ".fsgg/scaffold-provenance.json")
           || not ((map before).ContainsKey "models/svg-arena/arena-rules.md")
           || not (map before |> Map.exists (fun key _ -> key.StartsWith("readiness/d5-default/quint/", StringComparison.Ordinal)))
           || map before <> map after
           || actualFiles <> (map after |> Map.toSeq |> Seq.map fst |> Set.ofSeq)
           || (map after |> Map.exists (fun key expected ->
               let path = Path.GetFullPath(Path.Combine(receiver, key))
               not (path.StartsWith(prefix, StringComparison.Ordinal)) || not (regularFile path) || sha256 path <> expected))
           || Directory.Exists(Path.Combine(receiver, "work/d5-refused")) || File.Exists(Path.Combine(receiver, "work/d5-refused"))
           || Directory.Exists(Path.Combine(receiver, "readiness/d5-refused")) || File.Exists(Path.Combine(receiver, "readiness/d5-refused")) then
            Error "current-d5-backend-or-preservation-refused"
        else Ok ()
    with _ -> Error "current-d5-backend-or-preservation-refused"

// Typed pieces shared by the published-template selector and the source-built selector.
let private compositionSelection =
        {|
            route = "direct"
            bundle = "complete"
            lifecycle = "none"
            productName = "CurrentComposition"
            externalReference = true
            wasmPolicyExample = false
        |}

let private compositionRendering =
        {|
            version = "0.32.4"
            sourceCommit = "4ede04be66cedffc8551cd14045bab714aa358a7"
            custodySha256 = "89ea6424cae4d06969f0a60394679e9892bd2b873fb46ebd281aa10616809720"
            packages =
                [
                    {|
                        id = "FS.GG.UI.Scene"
                        sha256 = "dbc63e39782fb3f614233167aa4171f7d1a621b0348a7ddaeca323f8d27a2562"
                        lockContentHash = "h6me4Zq56jV/4cM0vrJPXiZvetZxq8IkF3ETE/KrIZsTEhqxa07Lv61W2FqPVS1FAngXAC0RkZQuFEHWv9ifzw=="
                    |};
                    {|
                        id = "FS.GG.UI.KeyboardInput"
                        sha256 = "09a9f6f04c7190111de4521daf544f8521aebe4c8f8ee96443a85049b4cf8389"
                        lockContentHash = "Q120NaTCDFJtYnRNBbdS5FvIzXwGCI7P5h8DuLNrHmEmODNC8B2SShpZ+6ELaFBuZbWGfPfU3srQwN9iInIPrg=="
                    |};
                    {|
                        id = "FS.GG.UI.Scene.SvgBrowser"
                        sha256 = "8fea42eb4a385ce2b08921c8679786e6f9d2e945bcbb54eb095cb2659b46f8d2"
                        lockContentHash = "5WPXpVlOGYEBBQWyktep6O9JbsayIVOCEnX5MlflMsv+z5pw8BLjWw0GlvLYKMu9pRNGtRnJnscRjW3lLfJcIQ=="
                    |}
                ]
        |}

let private compositionGame =
        {|
            id = "FS.GG.Game.Core"
            version = "0.16.0"
            lockContentHash = "mn66KeVyqj0kphAn8Nm11GbEUbmGcO28uRMFiuX6FdQv87Zvv4kXTV7MqwTVeH3GQtA2Nna56Okd6IaCSHH6Bg=="
        |}

let private baseCompositionCases =
    [
                            {|
                                file = "two-client.spec.ts"
                                suite = ([]: string list)
                                title = "FourD reference composes local session, normalized input, transformed hit testing and settled disposal"
                            |};
                            {|
                                file = "two-client.spec.ts"
                                suite = ([]: string list)
                                title = "external authority reference fences captured snapshots and settles commands independently"
                            |};
                            {|
                                file = "two-client.spec.ts"
                                suite = ([]: string list)
                                title = "external authority reference recovers failures and disposes owned resources terminally"
                            |};
                            {|
                                file = "two-client.spec.ts"
                                suite = ([]: string list)
                                title = "external authority reference uses production keyboard pointer editing and IME input"
                            |};
                            {|
                                file = "external-command-outcomes.spec.ts"
                                suite = [ "external authority reference command outcomes" ]
                                title = "unknown receipt survives projection and reconnect without replay"
                            |};
                            {|
                                file = "external-command-outcomes.spec.ts"
                                suite = [ "external authority reference command outcomes" ]
                                title = "explicit reconciliation and rearm retain the original and use a fresh correlation"
                            |};
                            {|
                                file = "external-command-outcomes.spec.ts"
                                suite = [ "external authority reference command outcomes" ]
                                title = "old generation completion is inert and abandonment requires explicit rearm"
                            |};
                            {|
                                file = "external-command-outcomes.spec.ts"
                                suite = [ "external authority reference command outcomes" ]
                                title = "delayed completion settles once and disposal makes retained controls inert"
                            |};
                            {|
                                file = "two-client.spec.ts"
                                suite = ([]: string list)
                                title = "Local save and replay example preserves synthetic state and settles detached controls"
                            |}
                        ]

// Cases added with the 0.20.0 template source: the broader DOM options panel and the explicit focus / native-editing
// survival across a retained update and a session replacement. They are absent from the earlier 0.19.3 archive.
let private optionsAndFocusCases =
    [
        {|
            file = "two-client.spec.ts"
            suite = ([]: string list)
            title = "FourD reference options panel keeps labelled native controls, tab order and state across retained updates and a session replacement"
        |};
        {|
            file = "two-client.spec.ts"
            suite = ([]: string list)
            title = "FourD reference focus and native editing text survive a retained update and a session replacement"
        |}
    ]

// These cases require source carrying the durable fixture codec (absent from the published 0.20.0 archive, present in 0.20.1).
let private durableLocalSaveCases =
    [
        {|
            file = "two-client.spec.ts"
            suite = ([]: string list)
            title = "Local synthetic snapshot survives page recreation with lossless uint64 order and typed refusals"
        |};
        {|
            file = "two-client.spec.ts"
            suite = ([]: string list)
            title = "Local synthetic snapshot storage failures and late loads preserve accepted state and settle disposal"
        |}
    ]

// One current public execution selector for the maintained DOM composition consumer.
// This is source data, not runtime/publication/AT/whole-Delivery acceptance.
let currentCompositionPlan () =
    {|
        schema = "fsgg.current-composition-plan/1"
        template =
            {|
                id = "FS.GG.Workspace.Template"
                version = "0.20.1"
                sha256 = "e84d5188b510937fb54218faf4cabbad93a801b58f24fd6e5bfbeba632c44a6a"
                sourceCommit = "df896c4bd587b5ef8dd990bc39c0dcb661bf2193"
                descriptorSha256 = "66dd8f066a5fd958e45b1681b934b44b68258efa4cecb2d72aa553839ee4b4a9"
                // The FS.GG.UI version the template's SvgFoundation and Studio projects default to. It must equal the
                // typed Rendering version; the former pin defaulted an older version and could not satisfy this route.
                uiDefault = "0.32.4"
            |}
        selection = compositionSelection
        rendering = compositionRendering
        game = compositionGame
        browsers =
            {|
                families = [ "chromium"; "firefox"; "webkit" ]
                retries = 0
                workers = 1
                cases = baseCompositionCases @ optionsAndFocusCases @ durableLocalSaveCases
            |}
        acceptanceScope = "thirteen maintained DOM-automation composition cases on the published 0.20.1 template only, including the explicit durable synthetic browser-storage save/load; no product-save/AT/IME/whole4818 acceptance"
    |}

// The generated-receiver conformance check for the composition plan. It is bound to the template identity the typed
// plan carries (the published 0.20.1 archive), not to the D5 current-public pin, so moving the plan to a newer
// published template never edits the D5 lane's frozen 0.19.3 selector.
let validateCurrentCompositionReceiver archive receiver route lifecycle bundle product =
    let template = (currentCompositionPlan ()).template
    if not (File.Exists archive) then Error "receiver-input-missing"
    elif sha256 archive <> template.sha256 then Error "current-composition-archive-refused"
    else
        match validatePackageIdentity archive template.sha256 packageId template.version template.sourceCommit with
        | Error reason -> Error reason
        | Ok _ -> validateReceiverCore true bundle archive receiver route lifecycle "2.4.0" product

let renderCurrentCompositionPlan () =
    JsonSerializer.Serialize(currentCompositionPlan(), JsonSerializerOptions(WriteIndented = true))

// Regression pin: the digest below is of the exact canonical output this module renders (reviewed once), not an independent source.
let private validateCompositionPlanDigest (expectedDigest: string) (json: string) =
    try
        if String.IsNullOrWhiteSpace json || Encoding.UTF8.GetByteCount(json) > 32768 then
            Error "current-composition-plan-refused"
        else
            use document = JsonDocument.Parse json
            if not (uniqueObject document.RootElement) then Error "current-composition-plan-refused"
            else
                use buffer = new MemoryStream()
                let options = JsonWriterOptions(Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping)
                use writer = new Utf8JsonWriter(buffer, options)
                let rec canonical (value: JsonElement) =
                    match value.ValueKind with
                    | JsonValueKind.Object ->
                        writer.WriteStartObject()
                        value.EnumerateObject()
                        |> Seq.sortWith (fun left right -> StringComparer.Ordinal.Compare(left.Name, right.Name))
                        |> Seq.iter (fun property -> writer.WritePropertyName(property.Name); canonical property.Value)
                        writer.WriteEndObject()
                    | JsonValueKind.Array ->
                        writer.WriteStartArray()
                        value.EnumerateArray() |> Seq.iter canonical
                        writer.WriteEndArray()
                    | JsonValueKind.String -> writer.WriteStringValue(value.GetString())
                    | _ -> value.WriteTo writer
                canonical document.RootElement
                writer.Flush()
                // Independent source-artifact canonical digest, not a hash of this builder.
                // Six immutable source citations and the selected lock entries were verified.
                let digest = Convert.ToHexString(SHA256.HashData(buffer.ToArray())).ToLowerInvariant()
                if digest = expectedDigest then Ok ()
                else Error "current-composition-plan-refused"
    with _ -> Error "current-composition-plan-refused"

// A plan whose template defaults a different FS.GG.UI version than its typed Rendering pin cannot qualify, so it is
// refused here, at plan validation, before any archive is fetched or any later step runs.
let private templateUiDefaultMatchesRendering (json: string) =
    try
        use document = JsonDocument.Parse json
        let root = document.RootElement
        let text (property: string) (element: JsonElement) =
            match element.TryGetProperty property with
            | true, value when value.ValueKind = JsonValueKind.String -> Some(value.GetString())
            | _ -> None
        match root.TryGetProperty "template", root.TryGetProperty "rendering" with
        | (true, template), (true, rendering) ->
            match text "uiDefault" template, text "version" rendering with
            | Some defaults, Some pinned when defaults = pinned -> true
            | _ -> false
        | _ -> false
    with _ -> false

let validateCurrentCompositionPlan (json: string) =
    if not (templateUiDefaultMatchesRendering json) then Error "current-composition-plan-ui-default-refused"
    else validateCompositionPlanDigest "563c7b9845a6fc637c1377170083c229b283fdf39e8d09fe56bf997d75078b49" json

// The same typed Rendering/Game/selection pins and the same maintained cases, but the template under test is
// packed from the checked-out protected Templates source instead of a published archive. Its identity is therefore
// recorded by the caller (source commit and package digest), never pinned here, and the verdict is "source-built".
let sourceBuiltCompositionPlan () =
    {|
        schema = "fsgg.current-composition-plan/1"
        template = {| origin = "source-built"; id = "FS.GG.Workspace.Template" |}
        selection = compositionSelection
        rendering = compositionRendering
        game = compositionGame
        browsers =
            {|
                families = [ "chromium"; "firefox"; "webkit" ]
                retries = 0
                workers = 1
                cases = baseCompositionCases @ optionsAndFocusCases @ durableLocalSaveCases
            |}
        acceptanceScope = "source-built DOM-automation composition cases including explicit durable synthetic save/load only; no published, installed, product-save, AT or whole4818 acceptance"
    |}

let renderSourceBuiltCompositionPlan () =
    JsonSerializer.Serialize(sourceBuiltCompositionPlan(), JsonSerializerOptions(WriteIndented = true))

let validateSourceBuiltCompositionPlan (json: string) =
    validateCompositionPlanDigest "5b426a72428ae6239a1f7481001b73bac6b20a7d57a624e530ae1447906c70d8" json

let private descriptorCheck selectedVersion (provider: Provider) =
    let lifecycle = provider.Parameters |> List.filter (fun p -> p.Key = "lifecycle")
    if provider.Name <> "fable-game" then refuse "descriptor-provider-identity-refused"
    elif provider.ContractVersion <> "2.0.0" then refuse "descriptor-contract-refused"
    elif provider.NameParameter <> Some "productName" || provider.IdentifierParameter <> Some "rootNamespace" || provider.Floor <> Some "2.1.0" then refuse "descriptor-capability-refused"
    elif provider.TemplateId <> templateId then refuse "descriptor-template-refused"
    elif provider.Source <> packageId + "::" + selectedVersion then refuse "descriptor-source-refused"
    elif lifecycle <> [ { Key = "lifecycle"; Required = false; Default = Some "typed-sdd" } ] then refuse "descriptor-lifecycle-refused"
    else Ok ()

let private canonicalName (name: string) =
    if String.IsNullOrWhiteSpace name || name.Contains('\\') || name.StartsWith("/", StringComparison.Ordinal)
       || Regex.IsMatch(name, "^[A-Za-z]:", RegexOptions.CultureInvariant) then None
    else
        let directory = name.EndsWith("/", StringComparison.Ordinal)
        let pieces = name.Split('/', StringSplitOptions.None)
        let body = if directory then pieces.[0 .. pieces.Length - 2] else pieces
        if body.Length = 0 || body |> Array.exists (fun p -> p = "" || p = "." || p = "..") then None
        else Some(String.Join("/", body) + if directory then "/" else "")

let validate request =
    if not (File.Exists request.Archive) || not (File.Exists request.Descriptor) then refuse "input-file-missing"
    elif not (hex64.IsMatch request.ExpectedSha256) || not (hex64.IsMatch request.ExpectedDescriptorSha256)
         || not (hex40.IsMatch request.ExpectedRevision) || not (hex40.IsMatch request.ExpectedTagRevision) then refuse "expected-identity-refused"
    elif not (supportedVersions |> List.contains request.ExpectedVersion) then refuse "selected-version-refused"
    elif request.ExpectedRevision <> request.ExpectedTagRevision then refuse "immutable-tag-revision-refused"
    elif sha256 request.Archive <> request.ExpectedSha256 then refuse "archive-sha256-refused"
    elif sha256 request.Descriptor <> request.ExpectedDescriptorSha256 then refuse "descriptor-sha256-refused"
    else
        match descriptorCheck request.ExpectedVersion request.Provider with
        | Error reason -> Error reason
        | Ok () ->
            try
                use archive = ZipFile.OpenRead request.Archive
                if archive.Entries.Count = 0 || archive.Entries.Count > 20000 then refuse "archive-entry-count-refused"
                else
                    let names = archive.Entries |> Seq.map (fun e -> e.FullName) |> Seq.toList
                    let canonical = names |> List.map canonicalName
                    let invalid = canonical |> List.exists Option.isNone
                    let normalized = canonical |> List.choose id
                    let duplicate = normalized |> List.countBy _.ToUpperInvariant() |> List.exists (fun (_, count) -> count <> 1)
                    let files = normalized |> List.filter (fun n -> not (n.EndsWith("/", StringComparison.Ordinal))) |> List.map _.ToUpperInvariant() |> Set.ofList
                    let directoryCollides =
                        normalized |> List.exists (fun n ->
                            let parts = n.TrimEnd('/').Split('/')
                            (n.EndsWith("/", StringComparison.Ordinal) && files.Contains(n.TrimEnd('/').ToUpperInvariant()))
                            || ([ 1 .. parts.Length - 1 ]
                                |> List.exists (fun count -> files.Contains(String.Join("/", parts.[0 .. count - 1]).ToUpperInvariant()))))
                    let oversized = archive.Entries |> Seq.exists (fun e -> e.Length < 0L || e.Length > 16L * 1024L * 1024L)
                    let total = archive.Entries |> Seq.sumBy _.Length
                    let linked = archive.Entries |> Seq.exists (fun e -> ((e.ExternalAttributes >>> 16) &&& 0xF000) = 0xA000)
                    if invalid then refuse "archive-path-refused"
                    elif duplicate || directoryCollides then refuse "archive-duplicate-entry-refused"
                    elif oversized || total > 128L * 1024L * 1024L then refuse "archive-entry-bound-refused"
                    elif linked then refuse "archive-link-refused"
                    elif (required @ (if List.contains request.ExpectedVersion wasmSuccessors then
                                          wasmRelative |> List.map (fun name -> "content/templates/fs-gg-fable-game/" + name)
                                      else []))
                         |> List.exists (fun name -> archive.GetEntry(name) |> Option.ofObj |> Option.forall (fun e -> e.Length = 0L)) then refuse "reference-member-missing"
                    else
                        let nuspecs = archive.Entries |> Seq.filter (fun e -> e.FullName.EndsWith(".nuspec", StringComparison.OrdinalIgnoreCase)) |> Seq.toList
                        match nuspecs with
                        | [ nuspec ] ->
                            use stream = nuspec.Open()
                            let doc = XDocument.Load stream
                            let values name = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = name) |> Seq.map _.Value |> Seq.toList
                            let one name expected = values name = [ expected ]
                            let repository = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = "repository") |> Seq.toList
                            if not (one "id" packageId && one "version" request.ExpectedVersion) then refuse "package-identity-refused"
                            elif repository.Length <> 1 || isNull (repository.Head.Attribute(XName.Get "commit")) || repository.Head.Attribute(XName.Get "commit").Value <> request.ExpectedRevision then refuse "package-source-revision-refused"
                            else Ok names.Length
                        | _ -> refuse "package-nuspec-census-refused"
            with :? InvalidDataException -> refuse "archive-format-refused"
