open System
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text
open System.Text.Json
open FS.GG.Templates.SvgSkillManifestMerge

let args = Environment.GetCommandLineArgs()
if args.Length <> 2 then failwith "Python expected-byte JSON path required"
let data = JsonDocument.Parse(File.ReadAllBytes args[1])
let root = data.RootElement
let decode (element: JsonElement) = Convert.FromBase64String(element.GetString())
let utf8 = UTF8Encoding(false, true)
let candidate = decode (root.GetProperty "candidateManifestBase64")
let bodies =
    root.GetProperty("candidateBodiesBase64").EnumerateObject()
    |> Seq.map (fun row -> row.Name, decode row.Value)
    |> Map.ofSeq
let provenance = decode (root.GetProperty "candidateProvenanceBase64")
let archivePath = root.GetProperty("sourceArchivePath").GetString()
let archiveSha = root.GetProperty("sourceArchiveSha256").GetString()
let actualArchiveSha =
    SHA256.HashData(File.ReadAllBytes archivePath)
    |> Convert.ToHexString |> fun value -> value.ToLowerInvariant()
if actualArchiveSha <> archiveSha then failwith "Python expected bytes are not bound to selected synthetic archive"
let archive = ZipFile.OpenRead archivePath
let archiveMember logical =
    let entry = archive.GetEntry("content/templates/fs-gg-fable-game/" + logical)
    if isNull entry then failwithf "archive member missing: %s" logical
    use stream = entry.Open()
    use output = new MemoryStream()
    stream.CopyTo output
    output.ToArray()
if candidate <> archiveMember ".agents/skills/skill-manifest.json" then
    failwith "candidate manifest bytes differ from selected synthetic archive"
if provenance <> archiveMember ".fsgg/scaffold-provenance.json" then
    failwith "candidate provenance differs from selected synthetic archive"
for KeyValue(path, body) in bodies do
    if body <> archiveMember path then failwithf "candidate body differs from selected synthetic archive: %s" path
archive.Dispose()
let project source bodyMap sourceProvenance current =
    Merge.bytes source bodyMap sourceProvenance current
        "FableGameWorkspace" "FableGameWorkspaceNamespace" "Receiver" "Receiver"
let expectError (fragment: string) (result: Result<byte[], string>) =
    match result with
    | Error reason when reason.Contains(fragment, StringComparison.Ordinal) -> ()
    | other -> failwithf "expected %s error, got %A" fragment other

let cases = root.GetProperty("cases").EnumerateArray() |> Seq.toList
if cases.Length <> 4 then failwith "Python expected-byte cases changed"
for case in cases do
    let name = case.GetProperty("name").GetString()
    let current =
        match case.GetProperty("currentBase64").ValueKind with
        | JsonValueKind.Null -> None
        | _ -> Some(decode (case.GetProperty "currentBase64"))
    let caseProvenance =
        match case.GetProperty("provenanceBase64").ValueKind with
        | JsonValueKind.Null -> None
        | _ -> Some(decode (case.GetProperty "provenanceBase64"))
    let expected = decode (case.GetProperty "expectedBase64")
    match project candidate bodies caseProvenance current with
    | Error reason -> failwithf "%s F# merge failed: %s" name reason
    | Ok actual when actual = expected -> ()
    | Ok actual -> failwithf "%s output bytes differ: expected %d bytes, got %d" name expected.Length actual.Length

let simpleCurrent = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[{\"id\":\"other\",\"scope\":\"workspace\"}]}"
let duplicateTop = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[],\"skills\":[{\"id\":\"other\"}]}"
let duplicateNested = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[{\"id\":\"forged\",\"id\":\"other\"}]}"
let duplicateForeign = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[{\"id\":\"other\"},{\"id\":\"other\"}]}"
let floatForeign = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[{\"id\":\"other\",\"score\":1.0}]}"
let surrogateForeign = utf8.GetBytes "{\"schemaVersion\":1,\"skills\":[{\"id\":\"\\ud800\"}]}"
expectError "duplicate-json-key:skills" (project candidate bodies (Some provenance) (Some duplicateTop))
expectError "duplicate-json-key:id" (project candidate bodies (Some provenance) (Some duplicateNested))
expectError "merged-skill-id-duplicate:other" (project candidate bodies (Some provenance) (Some duplicateForeign))
expectError "floating-number-unsupported" (project candidate bodies (Some provenance) (Some floatForeign))
expectError "escaped-surrogate-unsupported" (project candidate bodies (Some provenance) (Some surrogateForeign))
expectError "json-utf8-invalid" (project candidate bodies (Some provenance) (Some [| 0xffuy |]))
expectError "workspace-schema-invalid" (project candidate bodies (Some provenance)
    (Some(utf8.GetBytes "{\"schemaVersion\":2,\"skills\":[]}")))

let firstBodyPath = bodies |> Map.toList |> List.head |> fst
let forgedBodies = bodies |> Map.add firstBodyPath (utf8.GetBytes "forged body")
expectError "candidate-skill-body-mismatch" (project candidate forgedBodies (Some provenance) (Some simpleCurrent))
let badProvenance = utf8.GetBytes "{\"producedPaths\":[{\"owner\":\"generatedProduct\",\"path\":\".agents/skills/other/SKILL.md\"}]}"
expectError "candidate-provenance-skill-mismatch" (project candidate bodies (Some badProvenance) (Some simpleCurrent))
let sourceText = utf8.GetString candidate
let unsafeSource = sourceText.Replace(".agents/skills/fable-example/SKILL.md", ".agents/skills/../escape/SKILL.md", StringComparison.Ordinal)
expectError "candidate-skill-path-invalid" (project (utf8.GetBytes unsafeSource) bodies (Some provenance) (Some simpleCurrent))
let duplicatedSource = sourceText.Replace("\"id\": \"fable-second\"", "\"id\": \"fable-example\"", StringComparison.Ordinal)
expectError "candidate-skill-id-duplicate" (project (utf8.GetBytes duplicatedSource) bodies (Some provenance) (Some simpleCurrent))
data.Dispose()
printfn "F# merged-manifest bytes match Python in %d cases; malformed and foreign-row controls passed" cases.Length
