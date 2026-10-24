namespace FS.GG.Templates.PolyglotProviderTool

open System
open System.Text
open System.Text.Json.Nodes
open Fsgg
open FS.GG.SDD.Artifacts
open FS.GG.SDD.Commands

/// Concrete producer declarations; public SDD contracts own validation and digest semantics.
module Catalog =
    let private require = function Ok value -> value | Error errors -> failwithf "Public SDD contract refused: %A" errors
    let providerIds = [ "typescript-cli"; "javascript-cli"; "rust-cli"; "go-cli" ]
    let operations = [ "build"; "lint"; "test"; "public-surface"; "package"; "security"; "evidence"; "release" ]
    let private parameter key help : ProviderCatalog.Parameter =
        { Key = key; Kind = ProviderCatalog.String; Required = true; Prompt = help; Help = help
          Default = None; Values = []; Validation = { NonEmpty = true; MinLength = 1; MaxLength = 256; AllowedValues = [] } }
    let private tool id version : ProviderCatalog.ToolRequirement =
        { Id = id; Version = version; Platforms = [ "linux-x64" ] }
    let private tools = function
        | "typescript-cli" | "javascript-cli" -> [ tool "python" "3.14.8"; tool "node" "24.20.0"; tool "npm" "11.19.0"; tool "typescript" "5.9.2" ]
        | "rust-cli" -> [ tool "python" "3.14.8"; tool "rustc" "1.98.1"; tool "cargo" "1.98.1"; tool "cargo-audit" "0.22.2" ]
        | "go-cli" -> [ tool "python" "3.14.8"; tool "go" "1.27.1"; tool "govulncheck" "1.9.0" ]
        | value -> invalidArg "provider" value
    let private skills = function
        | "typescript-cli" -> [ "node-workspace"; "typescript-project"; "node-testing" ]
        | "javascript-cli" -> [ "node-workspace"; "javascript-project"; "node-testing" ]
        | "rust-cli" -> [ "rust-workspace"; "rust-safety" ]
        | "go-cli" -> [ "go-workspace"; "go-testing" ]
        | value -> invalidArg "provider" value
    let private descriptor version revision id : ProviderCatalog.Descriptor =
        let selectedTools = tools id
        let evidence : ProviderCatalog.EvidenceDeclaration list =
            operations |> List.map (fun operation ->
                { Id = operation + "-handoff"; Format = "fsgg.governance-handoff@2.0.0"
                  Path = "artifacts/" + operation + "-handoff.json"; Required = true })
        let capabilities : ProviderCatalog.CapabilityDeclaration list =
            operations |> List.map (fun operation ->
                { Id = operation + ":" + operation; Required = true; Platforms = [ "linux-x64" ]
                  ToolIds = selectedTools |> List.map (fun value -> value.Id)
                  EvidenceIds = [ operation + "-handoff" ]
                  Binding = ProviderCatalog.Command(
                      { Executable = "/bin/sh"; Arguments = [ "scripts/operations.sh"; operation ] },
                      { WorkingDirectory = "."; TimeoutSeconds = (if operation = "security" then 300 else 180)
                        CostClass = "product"; EnvironmentIds = [ "polyglot-local" ] }) })
        let declaration : ProviderCatalog.Descriptor =
            { Id = id; DisplayName = id; Help = "Explicit " + id + " workspace; product and code identities are independent."
              Language = (match id with "typescript-cli" -> "TypeScript" | "javascript-cli" -> "JavaScript" | "rust-cli" -> "Rust" | _ -> "Go"); ProductShape = "executable-cli"
              DescriptorId = "fs-gg-" + id; DescriptorRevision = revision
              DescriptorDigest = ProviderCatalogIntegrity.digest [||]; ContractVersion = "3.0.0"
              TemplateSource = "FS.GG.Workspace.Template::" + version; TemplateId = "fs-gg-" + id
              Platforms = [ "linux-x64" ]
              Parameters = [ parameter "rawName" "Human display name"
                             parameter "packageIdentity" (if id = "go-cli" then "Required explicit Go module path" else "Explicit ecosystem package identity")
                             parameter "codeIdentifier" "Explicit language-valid function identifier" ]
              Identities = { RawName = "rawName"; PackageIdentity = "packageIdentity"; CodeIdentifier = "codeIdentifier" }
              Tools = selectedTools; Capabilities = capabilities; Evidence = evidence; Skills = skills id }
        { declaration with DescriptorDigest = ProviderCatalogIntegrity.digest (ProviderCatalogIntegrity.descriptorBytes declaration) }

    let bytes (version: string) =
        // Catalog revisions are opaque producer versions; actual Git is joined through the archive nuspec/receipt.
        let revision = version
        if not (ProviderCatalog.isExactVersion version) then invalidArg "version" "Exact package version required."
        let catalog : ProviderCatalog.Catalog =
            { SchemaVersion = 2; Id = "fs-gg-polyglot-cli"; Revision = revision
              Digest = ProviderCatalogIntegrity.digest [||]; Providers = providerIds |> List.map (descriptor version revision) }
        match ProviderCatalog.validate catalog with
        | [] -> ()
        | errors -> failwithf "Invalid producer catalog: %A" errors
        let canonical = ProviderCatalogIntegrity.catalogBytes catalog
        let node = JsonNode.Parse(Encoding.UTF8.GetString canonical)
        if isNull node then failwith "Public canonical catalog is absent."
        node["digest"] <- JsonValue.Create(ProviderCatalogIntegrity.digest canonical)
        let result = Encoding.UTF8.GetBytes(node.ToJsonString())
        ProviderCatalogIntegrity.verify (ProviderCatalogIntegrity.digest result) result |> require |> ignore
        // Use the actual production prepare route, including all original required parameters.
        for id in providerIds do
            CatalogScaffoldWorkflow.prepare
                { CatalogBytes = result; ExpectedRawDigest = ProviderCatalogIntegrity.digest result; Provider = Some id
                  Overrides = [ "rawName", "42 awkward display!? $(literal);&"
                                "packageIdentity", (if id = "go-cli" then "example.org/explicit/product" else "explicit-product")
                                "codeIdentifier", "explicit_greet" ] }
            |> require |> ignore
        result

    /// Actual public API controls; these are authoring/codec tests, never provider runtime acceptance.
    let controls () =
        let raw = bytes "0.20.0"
        let digest = ProviderCatalogIntegrity.digest raw
        let catalog = ProviderCatalogIntegrity.verify digest raw |> require
        let mutable count = 0
        let expectRefusal result =
            match result with
            | Error _ -> count <- count + 1
            | Ok _ -> failwith "Expected production contract refusal."
        ProviderCatalogIntegrity.verify (ProviderCatalogIntegrity.digest [| 0uy |]) raw |> expectRefusal
        ProviderCatalogIntegrity.verify digest (Array.append raw [| 0uy |]) |> expectRefusal
        for id in providerIds do
            ProviderCatalog.resolve catalog id [ "rawName", "Awkward name!?"; "codeIdentifier", "greet" ] |> expectRefusal
            ProviderCatalog.resolve catalog id [ "rawName", "x"; "rawName", "y"; "packageIdentity", "valid"; "codeIdentifier", "greet" ] |> expectRefusal
            ProviderCatalog.resolve catalog id [ "rawName", "x"; "packageIdentity", "valid"; "codeIdentifier", "greet"; "unknown", "value" ] |> expectRefusal
        ProviderCatalog.resolve catalog "not-a-provider" [] |> expectRefusal
        if bytes "0.20.0" <> raw then failwith "Typed emission is nondeterministic."
        count + 1
