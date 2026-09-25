module FsGgTemplates.ProviderTool

open System
open System.IO
open System.Net.Http
open System.Text
open System.Text.RegularExpressions
open FsGgTemplates.ProviderComposition

let private fail message = raise (InvalidDataException message)
let private pattern value = Regex(value, RegexOptions.CultureInvariant)
let private providerLine = pattern "^  - name:\\s*(\\S+)\\s*(?:#.*)?$"
let private rootLine = pattern "^([A-Za-z][A-Za-z0-9]*):(?:\\s*(.*))?$"
let private schemaLine = pattern "^schemaVersion:\\s*1\\s*(?:#.*)?$"
let private fieldLine = pattern "^    ([A-Za-z][A-Za-z0-9-]*):\\s*(.*?)\\s*$"
let private floorLine = pattern "^    minimumFsggSdd:\\s*(?:#.*)?$"
let private floorFieldLine = pattern "^      ([A-Za-z][A-Za-z0-9-]*):\\s*(.*?)\\s*$"
let private versionLine = pattern "^      version:\\s*(.*?)\\s*$"
let private parameterLine = pattern "^      - key:\\s*(.*?)\\s*$"
let private parameterFieldLine = pattern "^        (required|default):\\s*(.*?)\\s*$"
let private contractLine = pattern "^  - id:\\s*(\\S+)\\s*(?:#.*)?$"
let private registryRootLine = pattern "^([A-Za-z][A-Za-z0-9-]*):(?:\\s.*)?$"
let private registryFloorLine = pattern "^    minimum-fsgg-sdd:\\s*(?:#.*)?$"
let private semver = pattern "^\\d+\\.\\d+\\.\\d+(?:[-+].*)?$"
let private beginMarker = "# BEGIN GENERATED: effective-providers"
let private endMarker = "# END GENERATED: effective-providers"
let private registryUrl = "https://raw.githubusercontent.com/FS-GG/.github/main/registry/dependencies.yml"

let private scalar where (raw: string) =
    let value = raw.Trim()
    if value = "" then fail $"{where}: expected a scalar value"
    elif value.[0] = '\'' || value.[0] = '"' then
        let closing = value.IndexOf(value.[0], 1)
        if closing < 0 then fail $"{where}: unterminated quoted value"
        let tail = value.Substring(closing + 1).Trim()
        if tail <> "" && not (tail.StartsWith("#", StringComparison.Ordinal)) then
            fail $"{where}: unsupported text after quoted value"
        let quoted = value.Substring(1, closing - 1)
        // YAML decodes escapes in double quotes; this narrow reader must not grade the raw spelling.
        if value.[0] = '"' && quoted.Contains('\\') then
            fail $"{where}: unsupported double-quoted escape"
        quoted
    else
        let beforeComment = value.Split('#').[0].Trim()
        if beforeComment = "" then fail $"{where}: expected a scalar value"
        let tokens = beforeComment.Split([| ' '; '\t' |], StringSplitOptions.RemoveEmptyEntries)
        if tokens.Length <> 1 then fail $"{where}: unsupported text after scalar value"
        let token = tokens.[0]
        if token = "~" || String.Equals(token, "null", StringComparison.OrdinalIgnoreCase) then
            fail $"{where}: implicit YAML null scalar is not a string value"
        if token.[0] = '[' || token.[0] = '{' || token.[0] = ']' || token.[0] = '}' then
            fail $"{where}: YAML flow indicator is not a string value"
        if token.[0] = '|' || token.[0] = '>' || token.[0] = '*' then
            fail $"{where}: unsupported YAML block or alias indicator"
        token

let private read path =
    try File.ReadAllText(path, UTF8Encoding(false, true))
    with :? DecoderFallbackException as ex -> fail $"{path}: is not valid UTF-8 ({ex.Message})"

let private parseDescriptor path =
    let lines = (read path).Split('\n')
    let providers = ResizeArray<Provider>()
    let mutable current: Map<string, string> option = None
    let mutable currentLine = 0
    let mutable floor: string option = None
    let mutable inFloor = false
    let mutable inProviders = false
    let mutable seenSchema = false
    let mutable seenProviders = false
    let mutable seenFloor = false
    let mutable seenFloorFields = Set.empty<string>
    let mutable inParameters = false
    let mutable seenParameters = false
    let mutable currentParameter: Map<string, string> option = None
    let parameters = ResizeArray<Parameter>()
    let finishParameter () =
        match currentParameter with
        | None -> ()
        | Some fields ->
            let key = fields.["key"]
            let required =
                match fields.TryFind "required" with
                | Some "true" -> true
                | Some "false" -> false
                | _ -> fail $"{path}: parameter '{key}' needs required: true|false"
            if parameters |> Seq.exists (fun parameter -> parameter.Key = key) then
                fail $"{path}: duplicate parameter key '{key}'"
            parameters.Add { Key = key; Required = required; Default = fields.TryFind "default" }
            currentParameter <- None
    let finish () =
        match current with
        | None -> ()
        | Some fields ->
            finishParameter ()
            let name = fields.["name"]
            if seenParameters && parameters.Count = 0 then
                fail $"{path}:{currentLine}: provider '{name}' parameters must contain an entry"
            let required key =
                match fields.TryFind key with
                | Some value -> value
                | None -> fail $"{path}:{currentLine}: provider '{name}' is missing {key}"
            providers.Add {
                Name = name
                ContractVersion = required "contractVersion"
                TemplateId = required "templateId"
                Source = required "source"
                NameParameter = fields.TryFind "nameParameter"
                IdentifierParameter = fields.TryFind "identifierParameter"
                Floor = floor
                Parameters = parameters |> Seq.toList
                File = path
                Line = currentLine
            }
    for index in 0 .. lines.Length - 1 do
        let line = lines.[index].TrimEnd('\r')
        if line.Trim() <> "" && not (line.TrimStart().StartsWith("#", StringComparison.Ordinal)) then
            let indentation = line.Substring(0, line.Length - line.TrimStart(' ', '\t').Length)
            if indentation.Contains('\t') then fail $"{path}:{index + 1}: tabs in YAML indentation are unsupported"
            let rootMatch = rootLine.Match line
            let providerMatch = providerLine.Match line
            if rootMatch.Success then
                finish ()
                current <- None
                inFloor <- false
                inParameters <- false
                inProviders <- false
                match rootMatch.Groups.[1].Value with
                | "schemaVersion" ->
                    if seenSchema || seenProviders || not (schemaLine.IsMatch line) then
                        fail $"{path}:{index + 1}: unsupported schemaVersion root"
                    seenSchema <- true
                | "providers" ->
                    if not seenSchema then fail $"{path}:{index + 1}: providers appear before schemaVersion: 1"
                    if seenProviders then fail $"{path}:{index + 1}: repeats providers"
                    seenProviders <- true
                    let inlineValue = rootMatch.Groups.[2].Value.Trim()
                    if inlineValue <> "" && not (inlineValue.StartsWith("#", StringComparison.Ordinal)) then
                        fail $"{path}:{index + 1}: providers must be a block sequence"
                    inProviders <- true
                | _ -> fail $"{path}:{index + 1}: unsupported or duplicate descriptor root key"
            elif indentation = "" then
                fail $"{path}:{index + 1}: unsupported or duplicate descriptor root key"
            elif not seenProviders then
                fail $"{path}:{index + 1}: descriptor content before providers list"
            elif inProviders && providerMatch.Success then
                finish ()
                current <- Some(Map.ofList [ "name", scalar $"{path}:{index + 1}" providerMatch.Groups.[1].Value ])
                currentLine <- index + 1
                floor <- None
                inFloor <- false
                seenFloor <- false
                seenFloorFields <- Set.empty
                inParameters <- false
                seenParameters <- false
                currentParameter <- None
                parameters.Clear()
            elif inProviders && line.StartsWith("  ", StringComparison.Ordinal) && not (line.StartsWith("    ", StringComparison.Ordinal)) then
                fail $"{path}:{index + 1}: providers must contain named block entries"
            elif inProviders && current.IsSome then
                let indent = indentation.Length
                if indent = 4 then
                    if inParameters then finishParameter ()
                    let fieldMatch = fieldLine.Match line
                    if not fieldMatch.Success then fail $"{path}:{index + 1}: malformed provider field"
                    let key = fieldMatch.Groups.[1].Value
                    if key = "minimumFsggSdd" then
                        if seenFloor then fail $"{path}:{index + 1}: repeated minimumFsggSdd"
                        if not (floorLine.IsMatch line) then fail $"{path}:{index + 1}: minimumFsggSdd must be a mapping"
                        seenFloor <- true
                        inFloor <- true
                    else
                        inFloor <- false
                    if key = "parameters" then
                        if seenParameters then fail $"{path}:{index + 1}: repeated parameters"
                        let inlineValue = fieldMatch.Groups.[2].Value.Trim()
                        if inlineValue <> "" && not (inlineValue.StartsWith("#", StringComparison.Ordinal)) then
                            fail $"{path}:{index + 1}: parameters must be a block sequence"
                        seenParameters <- true
                        inParameters <- true
                    else
                        inParameters <- false
                    if key = "contractVersion" || key = "templateId" || key = "source"
                       || key = "nameParameter" || key = "identifierParameter" then
                        let value = scalar $"{path}:{index + 1}" fieldMatch.Groups.[2].Value
                        let fields = current.Value
                        let name = fields.["name"]
                        if fields.ContainsKey key then fail $"{path}:{index + 1}: provider '{name}' repeats {key}"
                        current <- Some(fields.Add(key, value))
                    elif key <> "minimumFsggSdd" && key <> "parameters" then
                        fail $"{path}:{index + 1}: unsupported provider field '{key}'"
                elif inParameters then
                    if indent = 6 then
                        let parameterMatch = parameterLine.Match line
                        if not parameterMatch.Success then fail $"{path}:{index + 1}: malformed parameter entry"
                        finishParameter ()
                        currentParameter <- Some(Map.ofList [ "key", scalar $"{path}:{index + 1}" parameterMatch.Groups.[1].Value ])
                    elif indent = 8 && currentParameter.IsSome then
                        let parameterField = parameterFieldLine.Match line
                        if not parameterField.Success then fail $"{path}:{index + 1}: malformed parameter field"
                        let key = parameterField.Groups.[1].Value
                        let fields = currentParameter.Value
                        if fields.ContainsKey key then fail $"{path}:{index + 1}: repeated parameter field '{key}'"
                        currentParameter <- Some(fields.Add(key, scalar $"{path}:{index + 1}" parameterField.Groups.[2].Value))
                    else fail $"{path}:{index + 1}: unsupported parameter indentation"
                elif inFloor then
                    let floorField = floorFieldLine.Match line
                    if indent <> 6 || not floorField.Success then
                        fail $"{path}:{index + 1}: malformed minimumFsggSdd field"
                    let key = floorField.Groups.[1].Value
                    if key = "version" && floor.IsSome then
                        fail $"{path}:{index + 1}: repeated minimumFsggSdd.version"
                    if seenFloorFields.Contains key then
                        fail $"{path}:{index + 1}: repeated minimumFsggSdd field '{key}'"
                    seenFloorFields <- seenFloorFields.Add key
                    if key = "version" then
                        floor <- Some(scalar $"{path}:{index + 1}" floorField.Groups.[2].Value)
                else fail $"{path}:{index + 1}: unsupported provider indentation"
            elif inProviders then
                fail $"{path}:{index + 1}: unsupported content before first provider"
    finish ()
    if not seenSchema then fail $"{path}: missing schemaVersion: 1 root"
    if not seenProviders then fail $"{path}: missing providers block sequence"
    if providers.Count = 0 then fail $"{path}: declares no providers"
    let names = providers |> Seq.map _.Name |> Seq.toList
    if names <> List.sort names then fail $"{path}: providers must be ordered by name"
    if (names |> Set.ofList).Count <> names.Length then fail $"{path}: provider names must be unique"
    providers |> Seq.toList

let private registryPin (source: string) =
    let content =
        if source.StartsWith("https://", StringComparison.Ordinal) then
            use client = new HttpClient(Timeout = TimeSpan.FromSeconds 30.0)
            client.GetStringAsync(source).GetAwaiter().GetResult()
        else read source
    let lines = content.Split('\n')
    let mutable inContract = false
    let mutable inFloor = false
    let mutable found: string option = None
    let mutable selectedContractLine: int option = None
    let mutable inContracts = false
    let mutable seenContractsRoot = false
    for index in 0 .. lines.Length - 1 do
        let line = lines.[index].TrimEnd('\r')
        if line.Trim() <> "" && not (line.TrimStart().StartsWith("#", StringComparison.Ordinal)) then
            let rootMatch = registryRootLine.Match line
            let contractMatch = contractLine.Match line
            if rootMatch.Success then
                let isContracts = rootMatch.Groups.[1].Value = "contracts"
                if isContracts && seenContractsRoot then
                    fail $"{source}:{index + 1}: duplicate registry contracts root"
                if isContracts then seenContractsRoot <- true
                inContracts <- isContracts
                inContract <- false
                inFloor <- false
            elif not inContracts then ()
            elif contractMatch.Success then
                let contractId = contractMatch.Groups.[1].Value
                if contractId = "fs-gg-ui-template" then
                    match selectedContractLine with
                    | Some first ->
                        fail $"{source}:{index + 1}: duplicate selected registry contract id '{contractId}' (first at line {first})"
                    | None -> selectedContractLine <- Some(index + 1)
                inContract <- contractId = "fs-gg-ui-template"
                inFloor <- false
            elif inContract then
                if registryFloorLine.IsMatch line then inFloor <- true
                elif inFloor then
                    let versionMatch = versionLine.Match line
                    if versionMatch.Success then
                        if found.IsSome then fail $"{source}: repeated registry minimum-fsgg-sdd.version"
                        found <- Some(scalar $"{source}:{index + 1}" versionMatch.Groups.[1].Value)
                    elif line.Length - line.TrimStart(' ').Length <= 4 then inFloor <- false
    match found with
    | Some pin when semver.IsMatch pin -> pin
    | Some pin -> fail $"{source}: registry floor '{pin}' is not a version"
    | None -> fail $"{source}: missing fs-gg-ui-template.minimum-fsgg-sdd.version"

let private descriptors directory =
    // The live Python glob includes matching directories and then refuses their
    // read. GetFiles silently omitted them, which could shrink the graded set.
    let files = Directory.GetFileSystemEntries(directory, "*.providers.yml") |> Array.sort
    if files.Length = 0 then fail $"{directory}: no provider descriptors"
    for file in files do
        if not (File.Exists file) || Directory.Exists file then
            fail $"{file}: provider descriptor is not a regular file"
    let found = files |> Array.toList |> List.collect parseDescriptor
    let names = found |> List.map _.Name
    if (names |> Set.ofList).Count <> names.Length then
        fail $"{directory}: provider names must be unique across descriptors"
    found

let private grade directory registry =
    let pin = registryPin registry
    let providers = descriptors directory
    let problems =
        providers
        |> List.choose (fun provider ->
            match provider.Floor with
            | None -> Some $"{provider.File}:{provider.Line} {provider.Name}: missing minimumFsggSdd.version (registry {pin})"
            | Some floor when not (semver.IsMatch floor) -> Some $"{provider.File}:{provider.Line} {provider.Name}: invalid floor '{floor}' (registry {pin})"
            | Some floor when floor <> pin -> Some $"{provider.File}:{provider.Line} {provider.Name}: floor {floor} != registry pin {pin}"
            | Some _ -> None)
    if not problems.IsEmpty then problems |> List.iter (eprintfn "%s"); fail $"{problems.Length} provider floor(s) disagree with registry"
    // Grade the same provider metadata that workspace selection will later consume.
    // Sorting here preserves each descriptor's already-checked internal order while
    // avoiding an incidental cross-file filename order requirement.
    let ordered = providers |> List.sortBy _.Name
    match select ordered ordered with
    | Ok _ -> ()
    | Error refusal -> fail (describe refusal)
    printfn "provider floors: %d provider(s) equal registry pin %s" providers.Length pin

let private effective path =
    let original = read path
    let lines = original.Split('\n') |> Array.toList
    let indexed marker = lines |> List.indexed |> List.choose (fun (index, line) -> if line = marker then Some index else None)
    let begins = indexed beginMarker
    let ends = indexed endMarker
    if begins.Length <> 1 || ends.Length <> 1 || begins.Head >= ends.Head then
        fail $"{path}: expected exactly one ordered effective-providers marker pair"
    let parsed = parseDescriptor path
    let rendered =
        match select parsed parsed with
        | Ok selection -> renderEffective selection
        | Error refusal -> fail $"{path}: {describe refusal}"
    let expected = (lines |> List.take (begins.Head + 1)) @ rendered @ (lines |> List.skip ends.Head)
    let expectedText = String.Join("\n", expected)
    if original <> expectedText then fail $"{path}: generated summary is stale"
    printfn "effective providers: current — %d provider(s)" (parseDescriptor path).Length

let private workspaceCheck directory workspaceDescriptor registry =
    let pin = registryPin registry
    let known = descriptors directory
    let workspace = parseDescriptor workspaceDescriptor
    match selectAtRegistryFloor pin known workspace with
    | Ok _ -> ()
    | Error refusal -> fail $"{workspaceDescriptor}: {describe refusal}"
    printfn "workspace providers: %d known provider(s) match source identity and registry floor %s" workspace.Length pin

let private optionValue name args fallback =
    match args |> List.tryFindIndex ((=) name) with
    | Some index when index + 1 < args.Length -> args.[index + 1]
    | Some _ -> fail $"{name} needs a value"
    | None -> fallback

[<EntryPoint>]
let main argv =
    try
        let args = argv |> Array.toList
        let root = Directory.GetCurrentDirectory()
        let providers = optionValue "--providers" args (Path.Combine(root, "providers"))
        match args with
        | "grade" :: _ ->
            grade providers (optionValue "--registry" args registryUrl)
            0
        | "effective-check" :: _ ->
            effective (optionValue "--provider" args (Path.Combine(providers, "rendering.providers.yml")))
            0
        | "workspace-check" :: _ ->
            workspaceCheck providers (optionValue "--workspace" args "") (optionValue "--registry" args registryUrl)
            0
        | _ ->
            eprintfn "usage: ProviderTool grade [--providers DIR] [--registry PATH|URL] | effective-check [--provider FILE] | workspace-check --workspace FILE [--providers DIR]"
            2
    with ex ->
        eprintfn "provider-tool: %s" ex.Message
        1
