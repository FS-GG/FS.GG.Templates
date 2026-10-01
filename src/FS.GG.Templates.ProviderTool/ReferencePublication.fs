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
    ExpectedRevision: string
    ExpectedTagRevision: string
    ExpectedDescriptorSha256: string
    Provider: Provider
}

let private packageId = "FS.GG.Workspace.Template"
let private version = "0.17.0"
let private source = packageId + "::" + version
let private hex64 = Regex("^[0-9a-f]{64}$", RegexOptions.CultureInvariant)
let private hex40 = Regex("^[0-9a-f]{40}$", RegexOptions.CultureInvariant)
let private required =
    [ "content/templates/fs-gg-fable-game/.template.config/template.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj"
      "content/templates/fs-gg-fable-game/SvgFoundation/Program.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/build.sh"
      "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]

let private refuse message = Error message
let private sha256 path =
    use stream = File.OpenRead path
    Convert.ToHexString(SHA256.HashData stream).ToLowerInvariant()

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

let validateReceiver (archive: string) (receiver: string) (route: string) (expectedLifecycle: string) (expectedGeneratorVersion: string) =
    if not (File.Exists archive) || not (Directory.Exists receiver) then refuse "receiver-input-missing"
    elif not ([ "direct"; "provider"; "wizard" ] |> List.contains route) then refuse "receiver-route-refused"
    elif not ([ "none"; "typed-sdd" ] |> List.contains expectedLifecycle) then refuse "receiver-lifecycle-refused"
    elif route = "direct" && expectedLifecycle <> "none" then refuse "receiver-lifecycle-refused"
    else
        try
            use package = ZipFile.OpenRead archive
            let prefix = "content/templates/fs-gg-fable-game/"
            let receiverExact =
                [ "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
                  "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
                  "content/templates/fs-gg-fable-game/SvgFoundation/build.sh"
                  "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]
            let mismatched =
                receiverExact
                |> List.exists (fun name ->
                    let entry = package.GetEntry name
                    let relative = name.Substring(prefix.Length)
                    let output = Path.Combine(receiver, relative.Replace('/', Path.DirectorySeparatorChar))
                    if isNull entry || not (File.Exists output) then true
                    else
                        use sourceStream = entry.Open()
                        use targetStream = File.OpenRead output
                        not (SHA256.HashData(sourceStream).AsSpan().SequenceEqual(SHA256.HashData(targetStream))) )
            if mismatched then refuse "receiver-source-closure-refused"
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
                            if not generatorOk || generatorId.GetString() <> "FS.GG.SDD.Artifacts" || generatorVersion.GetString() <> expectedGeneratorVersion then refuse "receiver-generator-refused"
                            elif providerName.GetString() <> "fable-game" || templateRef.GetString() <> source then refuse "receiver-provider-source-refused"
                            elif lifecycle <> [ expectedLifecycle ] then refuse "receiver-lifecycle-refused"
                            else Ok ()
        with
        | :? JsonException -> refuse "receiver-provenance-json-refused"
        | :? InvalidDataException -> refuse "archive-format-refused"

let private descriptorCheck (provider: Provider) =
    let lifecycle = provider.Parameters |> List.filter (fun p -> p.Key = "lifecycle")
    if provider.Name <> "fable-game" then refuse "descriptor-provider-identity-refused"
    elif provider.ContractVersion <> "1.1.0" then refuse "descriptor-contract-refused"
    elif provider.TemplateId <> "fs-gg-fable-game" then refuse "descriptor-template-refused"
    elif provider.Source <> source then refuse "descriptor-source-refused"
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
    elif request.ExpectedRevision <> request.ExpectedTagRevision then refuse "immutable-tag-revision-refused"
    elif sha256 request.Archive <> request.ExpectedSha256 then refuse "archive-sha256-refused"
    elif sha256 request.Descriptor <> request.ExpectedDescriptorSha256 then refuse "descriptor-sha256-refused"
    else
        match descriptorCheck request.Provider with
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
                    elif required |> List.exists (fun name -> archive.GetEntry(name) |> Option.ofObj |> Option.forall (fun e -> e.Length = 0L)) then refuse "reference-member-missing"
                    else
                        let nuspecs = archive.Entries |> Seq.filter (fun e -> e.FullName.EndsWith(".nuspec", StringComparison.OrdinalIgnoreCase)) |> Seq.toList
                        match nuspecs with
                        | [ nuspec ] ->
                            use stream = nuspec.Open()
                            let doc = XDocument.Load stream
                            let values name = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = name) |> Seq.map _.Value |> Seq.toList
                            let one name expected = values name = [ expected ]
                            let repository = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = "repository") |> Seq.toList
                            if not (one "id" packageId && one "version" version) then refuse "package-identity-refused"
                            elif repository.Length <> 1 || isNull (repository.Head.Attribute(XName.Get "commit")) || repository.Head.Attribute(XName.Get "commit").Value <> request.ExpectedRevision then refuse "package-source-revision-refused"
                            else Ok names.Length
                        | _ -> refuse "package-nuspec-census-refused"
            with :? InvalidDataException -> refuse "archive-format-refused"
