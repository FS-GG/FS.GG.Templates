open System
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text
open System.Text.Json
open FS.GG.Templates.SvgWorkspacePolicy
open FS.GG.Templates.SvgWorkspaceArchive

let utf8 = UTF8Encoding(false)
let bytes (value: string) = utf8.GetBytes value
let sha (value: byte[]) = SHA256.HashData value |> Convert.ToHexString |> fun digest -> digest.ToLowerInvariant()
let assertEqual expected actual = if expected <> actual then failwithf "expected %A, got %A" expected actual
let assertError (fragment: string) (result: Result<'a, string>) =
    match result with
    | Error value when value.Contains(fragment, StringComparison.Ordinal) -> ()
    | other -> failwithf "expected error %s, got %A" fragment other

let prefix = "content/templates/fs-gg-fable-game/"
let regular = 0o100644
let rows =
    [ prefix + "FableGameWorkspace.slnx", bytes "<Solution/>\n", regular
      prefix + "Domain/Room.fs", bytes "namespace FableGameWorkspaceNamespace.Domain\n", regular
      prefix + "Asset.txt", bytes "HELLO FableGameWorkspaceNamespace FableGameWorkspace fablegameworkspace\r\n", 0o100755
      prefix + "Asset.bin", [| 0xffuy; 0uy; 0x80uy |], regular
      prefix + ".agents/skills/example/SKILL.md", bytes "# FableGameWorkspace\n", regular ]
let managed =
    [ ".agents/skills/example/SKILL.md"; ".claude/skills/example/SKILL.md"
      "Asset.bin"; "Asset.txt"; "FableGameWorkspace.slnx" ]
let retired = [ "Retired.txt" ]
let createArchive path entries =
    use output = File.Create path
    use archive = new ZipArchive(output, ZipArchiveMode.Create)
    for name, body, mode in entries do
        let entry = archive.CreateEntry name
        entry.ExternalAttributes <- mode <<< 16
        use stream = entry.Open()
        stream.Write(body, 0, body.Length)
let archiveSha path = File.ReadAllBytes path |> sha
let inspect path expectedSha mirror =
    Observer.inspectArchive path expectedSha "FableGameWorkspace" "FableGameWorkspaceNamespace" mirror managed retired

let root = Path.Combine(Path.GetTempPath(), "fsc05-archive-" + Guid.NewGuid().ToString("N"))
Directory.CreateDirectory root |> ignore
try
    let archivePath = Path.Combine(root, "selected.nupkg")
    createArchive archivePath rows
    let digest = archiveSha archivePath
    let observed =
        match inspect archivePath digest MirrorDirectory with
        | Ok value -> value
        | Error reason -> failwith reason
    assertEqual 5 observed.Puts.Length
    assertEqual 6 observed.Intents.Length
    let asset = observed.Puts |> List.find (fun row -> row.LogicalPath = "Asset.txt")
    assertEqual (prefix + "Asset.txt") asset.MemberName
    assertEqual 0o100755 asset.UnixMode
    assertEqual (bytes "HELLO FableGameWorkspaceNamespace FableGameWorkspace fablegameworkspace\r\n") asset.RawBytes
    let binary = observed.Puts |> List.find (fun row -> row.LogicalPath = "Asset.bin")
    assertEqual [| 0xffuy; 0uy; 0x80uy |] binary.RawBytes
    let mirror = observed.Puts |> List.find (fun row -> row.LogicalPath = ".claude/skills/example/SKILL.md")
    assertEqual (prefix + ".agents/skills/example/SKILL.md") mirror.MemberName
    match inspect archivePath digest MirrorAbsent with
    | Ok value -> assertEqual 4 value.Puts.Length
    | Error reason -> failwith reason
    assertError "archive-sha256-mismatch" (inspect archivePath (String.replicate 64 "0") MirrorDirectory)
    let archiveLink = Path.Combine(root, "archive-link.nupkg")
    File.CreateSymbolicLink(archiveLink, archivePath) |> ignore
    assertError "archive-path-unavailable-or-link" (inspect archiveLink digest MirrorDirectory)

    let reject label entries expected =
        let path = Path.Combine(root, label + ".nupkg")
        createArchive path entries
        assertError expected (inspect path (archiveSha path) MirrorDirectory)
    reject "dot-alias" (rows @ [ prefix + "Asset/./alias.txt", bytes "x", regular ]) "archive-member-unsafe"
    reject "duplicate" (rows @ [ prefix + "Asset.txt", bytes "changed", regular ]) "archive-member-duplicate-or-alias"
    reject "case-alias" (rows @ [ prefix + "asset.txt", bytes "changed", regular ]) "archive-member-duplicate-or-alias"
    reject "symlink" (rows |> List.map (fun (name, body, mode) ->
        if name = prefix + "Asset.txt" then name, body, 0o120777 else name, body, mode)) "archive-member-nonregular-or-link"
    reject "signature-symlink" (rows @ [ ".signature.p7s", bytes "outside", 0o120777 ]) "archive-member-nonregular-or-link"
    reject "identity" (rows |> List.map (fun (name, body, mode) ->
        if name = prefix + "Domain/Room.fs" then name, bytes "namespace Other.Domain\n", mode else name, body, mode)) "source-namespace-identity-mismatch"
    assertError "source-product-identity-mismatch"
        (Observer.inspectArchive archivePath digest "Wrong" "FableGameWorkspaceNamespace" MirrorDirectory managed retired)
    let changedMode = Path.Combine(root, "mode-only.nupkg")
    createArchive changedMode (rows |> List.map (fun (name, body, mode) ->
        if name = prefix + "Asset.txt" then name, body, regular else name, body, mode))
    assertError "archive-sha256-mismatch" (inspect changedMode digest MirrorDirectory)
    match inspect changedMode (archiveSha changedMode) MirrorDirectory with
    | Ok value -> assertEqual regular (value.Puts |> List.find (fun row -> row.LogicalPath = "Asset.txt")).UnixMode
    | Error reason -> failwith reason

    let workspace = Path.Combine(root, "receiver")
    Directory.CreateDirectory(Path.Combine(workspace, "Domain")) |> ignore
    File.WriteAllText(Path.Combine(workspace, "Receiver.slnx"), "old", utf8)
    File.WriteAllText(Path.Combine(workspace, "Domain/Room.fs"), "namespace Receiver.Domain\n", utf8)
    let oldAsset = bytes "BASE Receiver\n"
    let oldRetired = bytes "RETIRE Receiver\n"
    File.WriteAllBytes(Path.Combine(workspace, "Asset.txt"), oldAsset)
    File.WriteAllBytes(Path.Combine(workspace, "Retired.txt"), oldRetired)
    let authored = Path.Combine(workspace, "authored.txt")
    File.WriteAllText(authored, "authored sentinel", utf8)
    let allowed = Map.ofList [ "Asset.txt", Set.singleton (sha oldAsset)
                               "FableGameWorkspace.slnx", Set.singleton (sha (bytes "old"))
                               "Retired.txt", Set.singleton (sha oldRetired) ]
    let outputs =
        match Observer.inspectOutputs observed workspace "Receiver" "Receiver" allowed with
        | Ok value -> value
        | Error reason -> failwith reason
    let assetOutput = outputs |> List.find (fun row -> row.LogicalPath = "Asset.txt")
    assertEqual "replace" assetOutput.State
    assertEqual (Some (bytes "HELLO Receiver Receiver receiver\r\n" |> sha)) assetOutput.ProposedSha256
    assertEqual "Receiver.slnx" (outputs |> List.find (fun row -> row.LogicalPath = "FableGameWorkspace.slnx")).DestinationPath
    assertEqual "retire" (outputs |> List.find (fun row -> row.LogicalPath = "Retired.txt")).State
    let alias =
        Observer.inspectArchive archivePath digest "FableGameWorkspace" "FableGameWorkspaceNamespace"
            MirrorDirectory managed [ "Receiver.slnx" ]
    match alias with
    | Error reason -> failwith reason
    | Ok observation ->
        assertError "output-path-alias:Receiver.slnx"
            (Observer.inspectOutputs observation workspace "Receiver" "Receiver" allowed)
    File.WriteAllText(Path.Combine(workspace, "Asset.txt"), "authored", utf8)
    assertError "output-owner-mismatch:Asset.txt" (Observer.inspectOutputs observed workspace "Receiver" "Receiver" allowed)
    File.Delete(Path.Combine(workspace, "Asset.txt"))
    File.CreateSymbolicLink(Path.Combine(workspace, "Asset.txt"), authored) |> ignore
    assertError "output-symlink:Asset.txt" (Observer.inspectOutputs observed workspace "Receiver" "Receiver" allowed)
    File.Delete(Path.Combine(workspace, "Asset.txt"))
    File.WriteAllBytes(Path.Combine(workspace, "Asset.txt"), oldAsset)
    let skillDirectory = Path.Combine(workspace, ".agents")
    Directory.CreateSymbolicLink(skillDirectory, Path.Combine(workspace, "Domain")) |> ignore
    assertError "output-symlink:.agents/skills/example/SKILL.md"
        (Observer.inspectOutputs observed workspace "Receiver" "Receiver" allowed)
    Directory.Delete(skillDirectory)
    File.WriteAllText(Path.Combine(workspace, "Domain/Room.fs"), "namespace Wrong.Domain\n", utf8)
    assertError "destination-identity-mismatch" (Observer.inspectOutputs observed workspace "Receiver" "Receiver" allowed)
    assertEqual "authored sentinel" (File.ReadAllText authored)
    printfn "synthetic archive and receiver controls passed"
finally
    Directory.Delete(root, true)

if Environment.GetCommandLineArgs().Length = 3 then
    let args = Environment.GetCommandLineArgs()
    let baselinePath = Path.GetFullPath("scripts/svg-complete-workspace-baselines.json")
    use baseline = JsonDocument.Parse(File.ReadAllBytes baselinePath)
    let property = baseline.RootElement
    let paths (name: string) = property.GetProperty(name).EnumerateArray() |> Seq.map (fun item -> item.GetString()) |> Seq.toList
    match Observer.inspectArchive args[1] args[2] "FableGameWorkspace" "FableGameWorkspaceNamespace"
            MirrorAbsent (paths "managedPaths") (paths "retiredPaths") with
    | Error reason -> failwithf "selected archive failed: %s" reason
    | Ok result ->
        printfn "selected archive %s; puts %d; intents %d; merge-deferred %d" result.ArchiveSha256
            result.Puts.Length result.Intents.Length (result.Puts |> List.filter _.RequiresMerge |> List.length)
