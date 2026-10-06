module SddOwnerSkills

open System
open System.IO
open System.Reflection
open System.Security.Cryptography
open System.Text
open System.Text.Json.Nodes
open System.Text.RegularExpressions

let text (node: JsonNode) (key: string) = node.[key].GetValue<string>()
let sha (bytes: byte array) = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant()
let canonicalHash (bytes: byte array) =
    let body = Encoding.UTF8.GetString(bytes).TrimStart('\uFEFF').Replace("\r\n", "\n")
    sha (Encoding.UTF8.GetBytes(body))
let require condition message = if not condition then failwith ("SDD co-producer: " + message)
let safeRelative (value: string) =
    not (String.IsNullOrWhiteSpace value) && not (value.Contains '\\') && not (value.Contains ':') &&
    (value.Split('/') |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

// Evaluate only the declared producer grammar, never substring membership or a hopeful negative.
let selects template profile bundle (predicate: string) =
    let atom (value: string) =
        let value = value.Trim()
        if value = "always" then true
        else
            let equals = Regex.Match(value, "^(template|profile|bundle) == ([a-zA-Z0-9-]+)$")
            let choices = Regex.Match(value, "^(template|profile|bundle) in \\[([a-zA-Z0-9, -]+)\\]$")
            let actual field = if field = "template" then template elif field = "profile" then profile else bundle
            if equals.Success then actual equals.Groups.[1].Value = equals.Groups.[2].Value
            elif choices.Success then
                choices.Groups.[2].Value.Split(',') |> Array.map (fun x -> x.Trim())
                |> Array.contains (actual choices.Groups.[1].Value)
            else failwith ("SDD co-producer: unsupported predicate " + value)
    // Evaluate every arm, even if an earlier one matches: unsupported syntax always refuses.
    predicate.Split(" or ") |> Array.map (fun arm -> arm.Split(" and ") |> Array.map atom |> Array.forall id) |> Array.exists id

let admitResources (resource: string -> byte array) (names: string array) (productDir: string) (templateId: string) (expectedGeneratorVersion: string) =
    let provenance = JsonNode.Parse(File.ReadAllText(Path.Combine(productDir, ".fsgg/scaffold-provenance.json")))
    require (text provenance.["generator"] "id" = "FS.GG.SDD.Artifacts") "wrong generator identity"
    require (text provenance.["generator"] "version" = expectedGeneratorVersion) "unexpected producer version"
    require (text provenance "templateRef" = templateId) "wrong selected template provenance"
    let parameters = provenance.["effectiveParameters"].AsArray()
    let profile = parameters |> Seq.tryFind (fun row -> text row "key" = "profile") |> Option.map (fun row -> text row "value") |> Option.defaultValue ""
    let bundle = parameters |> Seq.tryFind (fun row -> text row "key" = "bundle") |> Option.map (fun row -> text row "value") |> Option.defaultValue ""
    let template = templateId.Replace("fs-gg-", "")
    let product = JsonNode.Parse(File.ReadAllText(Path.Combine(productDir, ".agents/skills/skill-manifest.json")))
    require ([1; 2] |> List.contains (product.["schemaVersion"].GetValue<int>())) "unsupported product manifest schema"
    let rows = product.["skills"].AsArray() |> Seq.map (fun row -> text row "id", row) |> Seq.toList
    require (rows |> List.map fst |> List.distinct |> List.length = rows.Length) "duplicate product id"
    let productRows = rows |> Map.ofList
    let mutable admitted = Set.empty
    // This is the producer's actual precedence: Game wins a colliding Rendering id, then Audio.
    for channel, owner in ["GameSkill", "gameSkill"; "RenderingSkill", "renderingSkill"; "AudioSkill", "audioSkill"] do
        let manifest = JsonNode.Parse(Encoding.UTF8.GetString(resource (channel + ".manifest")))
        require (manifest.["schemaVersion"].GetValue<int>() = 2) "unsupported owner manifest schema"
        let sourceRows = manifest.["skills"].AsArray() |> Seq.toList
        require (sourceRows |> List.map (fun row -> text row "id") |> List.distinct |> List.length = sourceRows.Length) "duplicate owner id"
        for source in sourceRows do
            let id = text source "id"
            if text source "scope" = "product" && selects template profile bundle (text source "materializes-when") && not (admitted.Contains id) then
                require (safeRelative id && not (id.Contains '/')) "unsafe owner id"
                let declaredFiles = source.["files"].AsArray() |> Seq.map (fun file -> text file "path", text file "sha256") |> Seq.toList
                require (declaredFiles |> List.map fst |> List.distinct |> List.length = declaredFiles.Length) "duplicate owner file"
                require (declaredFiles |> List.exists (fun (path, _) -> path = "SKILL.md")) "missing owner body"
                let prefix = channel + ".skill/" + id + "/"
                let transported = names |> Array.map (fun name -> name.Replace('\\','/')) |> Array.filter (fun name -> name.StartsWith(prefix)) |> Array.map (fun name -> name.Substring(prefix.Length)) |> Set.ofArray
                require (transported = (declaredFiles |> List.map fst |> Set.ofList)) ("unclosed resource file set " + id)
                let actualFiles = declaredFiles |> List.sortBy fst |> List.map (fun (relative, expected) ->
                    require (safeRelative relative) "unsafe owner file"
                    let bytes = resource (prefix + relative)
                    require (sha bytes = expected) ("forged resource digest " + id + "/" + relative)
                    let canonical = canonicalHash bytes
                    for root in [".agents/skills"; ".claude/skills"] do
                        let file = Path.Combine(productDir, root, id, relative)
                        require (File.Exists file && canonicalHash (File.ReadAllBytes file) = canonical) ("delivered digest drift " + file)
                    let prov = ["gameSkillPaths"; "renderingSkillPaths"] |> Seq.collect (fun field -> provenance.[field].AsArray()) |> Seq.filter (fun row -> text row "path" = ".agents/skills/" + id + "/" + relative) |> Seq.toList
                    require (prov.Length = 1 && text prov.Head "owner" = owner && text prov.Head "sha256" = canonical) ("wrong provenance owner/digest " + id)
                    relative, canonical)
                for root in [".agents/skills"; ".claude/skills"] do
                    let dir = Path.Combine(productDir, root, id)
                    let files = Directory.GetFiles(dir, "*", SearchOption.AllDirectories) |> Array.map (fun file -> Path.GetRelativePath(dir,file).Replace('\\','/')) |> Set.ofArray
                    require (files = (actualFiles |> List.map fst |> Set.ofList)) ("extra delivered file " + id)
                let expected = JsonObject()
                expected.["id"] <- JsonValue.Create(id)
                expected.["scope"] <- JsonValue.Create("product")
                expected.["sha256"] <- JsonValue.Create(actualFiles |> List.find (fun (path, _) -> path = "SKILL.md") |> snd)
                expected.["resolvablePath"] <- JsonValue.Create(".agents/skills/" + id + "/SKILL.md")
                expected.["materializes-when"] <- JsonValue.Create(if channel = "GameSkill" then "always" else text source "materializes-when")
                if channel <> "GameSkill" then expected.["supplied-by"] <- source.["supplied-by"].DeepClone()
                let files = JsonArray()
                for relative, hash in actualFiles do
                    let file = JsonObject()
                    file.["path"] <- JsonValue.Create(relative)
                    file.["sha256"] <- JsonValue.Create(hash)
                    files.Add(file)
                if product.["schemaVersion"].GetValue<int>() = 2 then expected.["files"] <- files
                require (productRows.ContainsKey id && JsonNode.DeepEquals(expected,productRows.[id])) ("foreign row fields differ from embedded owner " + id)
                admitted <- admitted.Add id
    require (not admitted.IsEmpty) "no selected embedded owner rows"
    admitted

let assemblyResources (commandsPath: string) =
    let commandsPath = Path.GetFullPath(commandsPath)
    let artifactsPath = Path.Combine(Path.GetDirectoryName(commandsPath), "FS.GG.SDD.Artifacts.dll")
    for path in [commandsPath; artifactsPath] do
        require (File.Exists path && (File.GetAttributes path &&& FileAttributes.ReparsePoint) <> FileAttributes.ReparsePoint) "producer assembly custody refused"
    let artifacts = Assembly.LoadFile artifactsPath
    require (artifacts.GetName().Name = "FS.GG.SDD.Artifacts") "wrong generator assembly"
    let informational = artifacts.GetCustomAttributes(typeof<AssemblyInformationalVersionAttribute>, false)
    require (informational.Length = 1) "missing or duplicate generator informational version"
    let raw = (informational.[0] :?> AssemblyInformationalVersionAttribute).InformationalVersion
    require (not (String.IsNullOrWhiteSpace raw)) "empty generator informational version"
    // The producer itself strips only the source-control suffix from this exact attribute.
    let core = raw.Trim().Split('+').[0]
    require (Regex.IsMatch(core, "^[0-9]+\\.[0-9]+\\.[0-9]+$", RegexOptions.CultureInvariant)) "generator version shape refused"
    let assembly = Assembly.LoadFile commandsPath
    require (assembly.GetName().Name = "FS.GG.SDD.Commands") "wrong producer assembly"
    let names = assembly.GetManifestResourceNames()
    let resource (name: string) =
        let matches = names |> Array.filter (fun candidate -> candidate.Replace('\\','/') = name)
        require (matches.Length = 1) ("missing or duplicate resource " + name)
        use stream = assembly.GetManifestResourceStream(matches.[0])
        use buffer = new MemoryStream()
        stream.CopyTo(buffer)
        buffer.ToArray()
    resource, names, core

let admit (commandsPath: string) (productDir: string) (templateId: string) =
    let resource, names, generatorVersion = assemblyResources commandsPath
    let admitted = admitResources resource names productDir templateId generatorVersion
    printfn "SDD co-producer: %d exact selected rows, Commands sha256 %s" admitted.Count (sha (File.ReadAllBytes(commandsPath)))
    admitted
