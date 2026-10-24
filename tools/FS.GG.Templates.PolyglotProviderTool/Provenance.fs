namespace FS.GG.Templates.PolyglotProviderTool

open System.IO
open System.Text.Json
open Fsgg
open FS.GG.SDD.Artifacts

/// Mechanical readback of the public schema, not an execution acceptance claim.
module Provenance =
    let private require = function Ok value -> value | Error errors -> failwithf "Public provenance refused: %A" errors
    let check (provenancePath: string) (summaryPath: string) =
        let record =
            CatalogScaffoldProvenance.parse (File.ReadAllText provenancePath) |> require

        let descriptor = record.Declaration.Descriptor

        let commands =
            descriptor.Capabilities
            |> List.choose (fun capability ->
                match capability.Binding with
                | ProviderCatalog.SemanticOnly -> None
                | ProviderCatalog.Command(command, limits) ->
                    Some
                        {|
                            capabilityId = capability.Id
                            executable = command.Executable
                            arguments = List.toArray command.Arguments
                            workingDirectory = limits.WorkingDirectory
                        |})
            |> List.toArray

        let evidence =
            descriptor.Evidence
            |> List.map (fun entry ->
                {|
                    id = entry.Id
                    format = entry.Format
                    path = entry.Path
                |})
            |> List.toArray

        let paths entries =
            entries
            |> List.map (fun (entry: ScaffoldProvenance.ScaffoldProducedPath) -> entry.Path)
            |> List.toArray

        let summary =
            {|
                declaredCommands = commands
                declaredEvidence = evidence
                effectiveParameters =
                    record.Declaration.EffectiveParameters
                    |> List.map (fun (a, b) -> [| a; b |])
                    |> List.toArray
                invocations =
                    record.Observation.Invocations
                    |> List.map (fun invocation ->
                        {|
                            executable = invocation.Executable
                            arguments = List.toArray invocation.Arguments
                            exitCode = invocation.ExitCode
                        |})
                    |> List.toArray
                rawCatalogDigest = record.Declaration.RawCatalogDigest
                policyDigest = record.Declaration.Policy.Digest
                archiveDigest = record.Declaration.Archive.Digest
                schemaVersion = record.SchemaVersion
                platform = record.Observation.Platform
                result = record.Observation.Result
                producedPaths = paths record.Ownership.ProducedPaths
                mirroredPaths = paths record.Ownership.MirroredPaths
                sddOwnedPaths = paths record.Ownership.SddOwnedPaths
                tools =
                    record.Observation.Tools
                    |> List.map (fun tool ->
                        {|
                            id = tool.Id
                            version = tool.Version
                            executable = tool.Executable
                        |})
                    |> List.toArray
                invocationCount = record.Observation.Invocations.Length
            |}

        use output =
            new FileStream(summaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None)

        let bytes =
            JsonSerializer.SerializeToUtf8Bytes(summary, JsonSerializerOptions(WriteIndented = true))

        output.Write(bytes, 0, bytes.Length)
