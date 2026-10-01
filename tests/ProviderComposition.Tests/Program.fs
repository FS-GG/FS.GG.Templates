open FsGgTemplates.ProviderComposition
open FsGgTemplates.ReferencePublication
open System
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text

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
        requiredEntries |> List.filter ((<>) omit) |> List.iter (fun name -> add name "fixture")
        if duplicate then add requiredEntries.Head "again"
    let archive = Path.Combine(temp, "valid.nupkg")
    makeArchive archive "" false
    let digest path = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes path)).ToLowerInvariant()
    let request path = { Archive = path; Descriptor = descriptor; ExpectedSha256 = digest path; ExpectedRevision = revision }
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
    assertEqual "changed archive hash refuses" (Error "archive-sha256-refused") (validate { request archive with ExpectedSha256 = String.replicate 64 "0" })
    File.WriteAllText(descriptor, File.ReadAllText(descriptor).Replace("::0.17.0", "::0.16.0"))
    assertEqual "stale descriptor pin refuses" (Error "descriptor-source-refused") (validate (request archive))
    Directory.Delete(temp, true)
    0
