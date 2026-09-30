module LanguageRouteBindingSupport =
    open System
    open System.Text.Json

    let portableNowFrom (value: DateTimeOffset) =
        DateTimeOffset(value.UtcTicks - value.UtcTicks % 10L, TimeSpan.Zero)

    let qualifiedImageReference (trustedImage: JsonElement) (boundImage: JsonElement) =
        let requiredImageFields =
            [ "archiveSha256","archiveSha256"
              "configDigest","configDigest"
              "imageId","configDigest"
              "manifestDigest","retainedOciManifestDigest"
              "importArchiveSha256","retainedImport.derived.archiveSha256"
              "importManifestDigest","retainedImport.derived.manifestDigest"
              "importConfigDigest","retainedImport.derived.configDigest"
              "importReference","retainedImport.importReference" ]
        let trustedValue (path: string) =
            path.Split('.') |> Array.fold (fun (value: JsonElement) name -> value.GetProperty(name)) trustedImage |> _.GetString()
        if requiredImageFields |> List.exists (fun (boundName,trustedName) -> boundImage.GetProperty(boundName).GetString()<>trustedValue trustedName) then
            invalidOp "binding-qualified-image-mismatch"
        let buildReference = trustedImage.GetProperty("qualifiedReference").GetString()
        let buildDigest = trustedImage.GetProperty("qualifiedBuildDigest").GetString()
        if buildReference <> "localhost/fsgg-language-route@"+buildDigest then
            invalidOp "qualified-image-reference-mismatch"
        let retained = trustedImage.GetProperty("retainedImport")
        let importName = retained.GetProperty("importName").GetString()
        let imageReference = retained.GetProperty("importReference").GetString()
        let importManifest = retained.GetProperty("derived").GetProperty("manifestDigest").GetString()
        if imageReference <> importName+"@"+importManifest || importManifest <> trustedImage.GetProperty("retainedOciManifestDigest").GetString() then
            invalidOp "retained-import-reference-mismatch"
        imageReference
