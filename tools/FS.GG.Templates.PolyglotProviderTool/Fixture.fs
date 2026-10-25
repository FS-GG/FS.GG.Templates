namespace FS.GG.Templates.PolyglotProviderTool

open System
open System.IO
open System.IO.Compression
open System.Text.Json
open Fsgg
open FS.GG.SDD.Artifacts
open FS.GG.SDD.Commands

/// Feed one actual once-packed archive into the maintained catalog CLI driver.
/// Caller policy and native/runtime qualification remain independent inputs.
module Fixture =
    let private require = function Ok value -> value | Error errors -> failwithf "Public fixture contract refused: %A" errors
    let emit (provider: string) (catalogPath: string) (policyPath: string) (archivePath: string) (output: string) =
        if not (List.contains provider Catalog.providerIds) then invalidArg "provider" "Closed four-provider selection required."
        let read (path: string) =
            if not (Path.IsPathFullyQualified path) || File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint) then
                invalidArg "path" "Absolute regular input required."
            let info = FileInfo(path)
            if info.Length > 64L * 1048576L then invalidArg "path" "Input exceeds archive bound."
            File.ReadAllBytes path
        let raw = read catalogPath
        if raw <> Catalog.bytes "0.20.0" then failwith "Catalog differs from actual current typed producer."
        let catalog = ProviderCatalogIntegrity.verify (ProviderCatalogIntegrity.digest raw) raw |> require
        let policyBytes = read policyPath
        let policy = CatalogScaffoldPolicy.parse (ProviderCatalogIntegrity.digest policyBytes) policyBytes |> require
        let overrides =
            [ "rawName", "42 awkward display!? $(literal);&"
              "packageIdentity", (if provider = "go-cli" then "example.org/explicit/product" else "explicit-product")
              "codeIdentifier", "explicit_greet" ]
        let selected = ProviderCatalog.resolve catalog provider overrides |> require
        ProviderCapabilityAdmission.resolve policy "linux-x64" selected.Descriptor |> require |> ignore
        let archiveBytes = read archivePath
        use archiveStream = new MemoryStream(archiveBytes, false)
        use archive = new ZipArchive(archiveStream, ZipArchiveMode.Read)
        let entries = archive.Entries |> Seq.filter (fun entry -> entry.FullName = "content/providers/polyglot.catalog.json") |> Seq.toList
        match entries with
        | [entry] when entry.Length <= 1048576L ->
            use stream = entry.Open()
            use copy = new MemoryStream()
            stream.CopyTo(copy)
            if copy.ToArray() <> raw then failwith "Once-packed archive catalog differs."
        | _ -> failwith "Once-packed archive requires one bounded typed catalog member."
        let toolId, toolVersion =
            match provider with
            | "typescript-cli" | "javascript-cli" -> "node", "24.20.0"
            | "rust-cli" -> "rustc", "1.98.1"
            | _ -> "go", "1.27.3"
        let fixture =
            {| generatorAssemblySha256 = ProviderCatalogIntegrity.digest (File.ReadAllBytes(System.Reflection.Assembly.GetExecutingAssembly().Location)) |> fun value -> value.Substring(7)
               catalog = catalogPath; catalogDigest = ProviderCatalogIntegrity.digest raw
               policy = policyPath; policyDigest = ProviderCatalogIntegrity.digest policyBytes
               archive = archivePath; archiveDigest = ProviderCatalogIntegrity.digest archiveBytes
               provider = provider; platform = "linux-x64"; preflightSeconds = 60; scaffoldSeconds = 120
               overrides = overrides |> List.map (fun (key,value) -> [|key;value|]) |> List.toArray
               toolId = toolId; toolVersion = toolVersion; templateId = "fs-gg-" + provider
               fixtureExpectations =
                   {| files = [| {| path = "display-name.txt"; text = "42 awkward display!? $(literal);&\n" |} |]
                      absentPaths = [| "artifacts/build-handoff.json"; "artifacts/release-handoff.json" |]
                      producedSkillPaths = selected.Descriptor.Skills |> List.map (fun id -> ".agents/skills/" + id + "/SKILL.md") |> List.toArray |} |}
        use destination = new FileStream(output, FileMode.CreateNew, FileAccess.Write, FileShare.None)
        let bytes = JsonSerializer.SerializeToUtf8Bytes(fixture, JsonSerializerOptions(WriteIndented = true))
        destination.Write(bytes, 0, bytes.Length)
        destination.Flush(true)
