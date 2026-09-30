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
              "manifestDigest","retainedOciManifestDigest" ]
        if requiredImageFields |> List.exists (fun (boundName,trustedName) -> boundImage.GetProperty(boundName).GetString()<>trustedImage.GetProperty(trustedName).GetString()) then
            invalidOp "binding-qualified-image-mismatch"
        let imageReference = trustedImage.GetProperty("qualifiedReference").GetString()
        let buildDigest = trustedImage.GetProperty("qualifiedBuildDigest").GetString()
        if imageReference <> "localhost/fsgg-language-route@"+buildDigest then
            invalidOp "qualified-image-reference-mismatch"
        imageReference
