module FsGgTemplates.ProviderPayloadComparison

open System
open System.Collections.Generic
open System.IO
open System.Text
open System.Text.Json
open System.Text.RegularExpressions

type Member = { Name: string; Digest: string; Mode: int }
type Snapshot = { Members: Map<string, Member>; Configs: Map<string, Member> }

let private prefix = "content/templates/"
let private configSuffix = "/.template.config/template.json"
let private regular0644 = 0o100644
let private maxInputBytes = 4 * 1024 * 1024
let private fail message = raise (InvalidDataException message)

let private uniqueObject (where: string) (allowed: Set<string>) (value: JsonElement) =
    if value.ValueKind <> JsonValueKind.Object then fail $"{where} must be an object"
    let names = HashSet<string>(StringComparer.Ordinal)
    for property in value.EnumerateObject() do
        if not (names.Add property.Name) then fail $"{where} repeats {property.Name}"
        if not (allowed.Contains property.Name) then fail $"{where} has unsupported field {property.Name}"
    if Set.ofSeq names <> allowed then fail $"{where} is missing required fields"

let private stringField (where: string) (name: string) (value: JsonElement) =
    let field = value.GetProperty name
    if field.ValueKind <> JsonValueKind.String then fail $"{where}.{name} must be a string"
    field.GetString()

let private modeField (where: string) (value: JsonElement) =
    let field = value.GetProperty "mode"
    let mutable mode = 0
    if field.ValueKind <> JsonValueKind.Number || not (field.TryGetInt32(&mode)) then
        fail $"{where}.mode must be an integer"
    mode

let private rootOf (name: string) =
    if not (name.StartsWith(prefix, StringComparison.Ordinal)) then fail $"member {name} is outside templates"
    if not (name.IsNormalized(NormalizationForm.FormC)) then
        fail $"member {name} has a noncanonical Unicode path"
    if name.EndsWith("/", StringComparison.Ordinal) || name.Contains('\\')
       || name.Contains(':') || name.Contains('\000') then fail $"member {name} has an unsafe path"
    let parts = name.Split('/')
    if parts |> Array.exists (fun part -> part = "" || part = "." || part = "..") then
        fail $"member {name} has an unsafe path"
    if parts.Length < 4 then fail $"member {name} has no template payload path"
    parts.[2]

let private parseSnapshot (where: string) (value: JsonElement) =
    if value.ValueKind <> JsonValueKind.Array then fail $"{where} must be an array"
    if value.GetArrayLength() = 0 || value.GetArrayLength() > 4096 then
        fail $"{where} has an invalid member count"
    let aliases = HashSet<string>(StringComparer.OrdinalIgnoreCase)
    let members =
        value.EnumerateArray()
        |> Seq.mapi (fun index row ->
            let label = $"{where}[{index}]"
            uniqueObject label (Set.ofList [ "name"; "sha256"; "mode" ]) row
            let name = stringField label "name" row
            let digest = stringField label "sha256" row
            let mode = modeField label row
            let templateRoot = rootOf name
            if name.EndsWith(configSuffix, StringComparison.Ordinal)
               && name <> prefix + templateRoot + configSuffix then
                fail $"{where} has a non-root template config {name}"
            if not (aliases.Add name) then fail $"{where} repeats or aliases member {name}"
            if not (Regex.IsMatch(digest, "^[0-9a-f]{64}$", RegexOptions.CultureInvariant)) then
                fail $"{label}.sha256 is invalid"
            if mode <> regular0644 then fail $"{label}.mode differs from selected contract"
            name, { Name = name; Digest = digest; Mode = mode })
        |> Map.ofSeq
    for name in members |> Map.toSeq |> Seq.map fst do
        let mutable separator = name.IndexOf('/')
        while separator >= 0 do
            let ancestor = name.Substring(0, separator)
            if aliases.Contains ancestor then fail $"{where} member {name} has file ancestor {ancestor}"
            separator <- name.IndexOf('/', separator + 1)
    let roots = members |> Map.toSeq |> Seq.map (fst >> rootOf) |> Set.ofSeq
    for root in roots do
        let config = prefix + root + configSuffix
        if not (members.ContainsKey config) then fail $"{where} is missing template config for {root}"
        let assets = members |> Map.toSeq |> Seq.filter (fun (name, _) -> rootOf name = root && name <> config) |> Seq.length
        if assets = 0 then fail $"{where} has no payload asset for {root}"
    { Members = members
      Configs = members |> Map.filter (fun name _ -> name.EndsWith(configSuffix, StringComparison.Ordinal)) }

let private compare (left: Snapshot) (right: Snapshot) =
    let before = left.Members |> Map.toSeq |> Seq.map fst |> Set.ofSeq
    let after = right.Members |> Map.toSeq |> Seq.map fst |> Set.ofSeq
    let common = Set.intersect before after
    let missing = Set.difference before after |> Set.count
    let extra = Set.difference after before |> Set.count
    let bodyDrift = common |> Seq.filter (fun name -> left.Members.[name].Digest <> right.Members.[name].Digest) |> Seq.length
    let modeDrift = common |> Seq.filter (fun name -> left.Members.[name].Mode <> right.Members.[name].Mode) |> Seq.length
    {| status = if missing + extra + bodyDrift + modeDrift = 0 then "TEMPLATE_PAYLOAD_MATCH_ONLY" else "NO_VERDICT"
       configOnlyMatch = left.Configs = right.Configs
       missing = missing
       extra = extra
       bodyDrift = bodyDrift
       modeDrift = modeDrift |}

let private readInput () =
    use source = Console.OpenStandardInput()
    use buffer = new MemoryStream()
    let chunk = Array.zeroCreate<byte> 8192
    let mutable count = source.Read(chunk, 0, chunk.Length)
    while count > 0 do
        if buffer.Length + int64 count > int64 maxInputBytes then fail "comparison input exceeds bound"
        buffer.Write(chunk, 0, count)
        count <- source.Read(chunk, 0, chunk.Length)
    buffer.ToArray()

[<EntryPoint>]
let main _ =
    try
        use document = JsonDocument.Parse(readInput ())
        let root = document.RootElement
        uniqueObject "comparison" (Set.ofList [ "left"; "right" ]) root
        let left = parseSnapshot "left" (root.GetProperty "left")
        let right = parseSnapshot "right" (root.GetProperty "right")
        compare left right |> JsonSerializer.Serialize |> Console.Out.WriteLine
    with error ->
        JsonSerializer.Serialize({| status = "NO_VERDICT"; reason = error.Message |})
        |> Console.Out.WriteLine
    0
