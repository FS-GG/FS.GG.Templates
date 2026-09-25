namespace FS.GG.Templates.SvgSkillManifestMerge

open System
open System.Collections.Generic
open System.Globalization
open System.IO
open System.Numerics
open System.Security.Cryptography
open System.Text
open System.Text.Json
open System.Text.RegularExpressions

type private Value =
    | Object of (string * Value) list
    | Array of Value list
    | String of string
    | Integer of string
    | Boolean of bool
    | Null

/// Pure byte projection of the Python product-skill merge for JSON values
/// supported below. Candidate bytes, bodies, provenance and receiver bytes
/// are caller facts; this module does not authenticate their physical origin.
module Merge =
    let private utf8 = UTF8Encoding(false, true)
    let private fail reason = raise (InvalidDataException reason)
    let private sha (bytes: byte[]) =
        SHA256.HashData bytes |> Convert.ToHexString |> fun value -> value.ToLowerInvariant()

    let private parse (bytes: byte[]) =
        let text = utf8.GetString bytes
        // JsonElement decodes lone surrogate escapes to a replacement scalar.
        // Refuse escaped surrogates until a lossless decoder is qualified.
        if Regex.IsMatch(text, @"\\u[dD][89a-fA-F][0-9a-fA-F]{2}") then
            fail "escaped-surrogate-unsupported"
        use document = JsonDocument.Parse text
        let rec value (element: JsonElement) =
            match element.ValueKind with
            | JsonValueKind.Object ->
                let seen = HashSet<string>(StringComparer.Ordinal)
                Object [ for property in element.EnumerateObject() do
                             if not (seen.Add property.Name) then fail $"duplicate-json-key:{property.Name}"
                             yield property.Name, value property.Value ]
            | JsonValueKind.Array -> Array [ for item in element.EnumerateArray() -> value item ]
            | JsonValueKind.String -> String(element.GetString())
            | JsonValueKind.Number ->
                let raw = element.GetRawText()
                if raw.Contains('.') || raw.Contains('e') || raw.Contains('E') then
                    fail "floating-number-unsupported"
                Integer(BigInteger.Parse(raw, CultureInfo.InvariantCulture).ToString(CultureInfo.InvariantCulture))
            | JsonValueKind.True -> Boolean true
            | JsonValueKind.False -> Boolean false
            | JsonValueKind.Null -> Null
            | _ -> fail "json-value-unsupported"
        value document.RootElement

    let private field name = function
        | Object fields -> fields |> List.tryPick (fun (key, value) -> if key = name then Some value else None)
        | _ -> None

    let private stringField name value =
        match field name value with Some(String text) -> Some text | _ -> None

    let private rows label value =
        if field "schemaVersion" value <> Some(Integer "1") then fail $"{label}-schema-invalid"
        match field "skills" value with
        | Some(Array values) -> values
        | _ -> fail $"{label}-skills-invalid"

    let private safeRelative (value: string) =
        not (String.IsNullOrEmpty value)
        && not (value.StartsWith "/")
        && not (value.Contains '\\' || value.Contains(char 0))
        && not (value.Length >= 2 && Char.IsAsciiLetter value[0] && value[1] = ':')
        && (value.Split '/' |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

    let private escape (value: string) =
        let output = StringBuilder("\"")
        for letter in value do
            match letter with
            | '"' -> output.Append("\\\"") |> ignore
            | '\\' -> output.Append("\\\\") |> ignore
            | '\b' -> output.Append("\\b") |> ignore
            | '\t' -> output.Append("\\t") |> ignore
            | '\n' -> output.Append("\\n") |> ignore
            | '\f' -> output.Append("\\f") |> ignore
            | '\r' -> output.Append("\\r") |> ignore
            | _ when int letter < 32 || int letter >= 128 ->
                output.Append("\\u").Append((int letter).ToString("x4", CultureInfo.InvariantCulture)) |> ignore
            | _ -> output.Append letter |> ignore
        output.Append('"').ToString()

    let private render root =
        let rec write depth = function
            | Null -> "null"
            | Boolean true -> "true"
            | Boolean false -> "false"
            | Integer number -> number
            | String value -> escape value
            | Array [] -> "[]"
            | Array values ->
                "[\n" + (values |> List.map (fun item -> String.replicate ((depth + 1) * 2) " " + write (depth + 1) item)
                         |> String.concat ",\n") + "\n" + String.replicate (depth * 2) " " + "]"
            | Object [] -> "{}"
            | Object fields ->
                "{\n" + (fields |> List.map (fun (key, item) ->
                    String.replicate ((depth + 1) * 2) " " + escape key + ": " + write (depth + 1) item)
                         |> String.concat ",\n") + "\n" + String.replicate (depth * 2) " " + "}"
        write 0 root

    let private pythonOrder (left: string) (right: string) =
        Array.compareWith compare (utf8.GetBytes left) (utf8.GetBytes right)

    let private transform (sourceProduct: string) (sourceNamespace: string)
                          (destinationProduct: string) (destinationNamespace: string) (value: string) =
        [ sourceNamespace, destinationNamespace
          sourceProduct, destinationProduct
          sourceProduct.ToLowerInvariant(), destinationProduct.ToLowerInvariant() ]
        |> List.mapi (fun index (oldValue, newValue) -> index, oldValue, newValue)
        |> List.sortWith (fun (leftIndex, left, _) (rightIndex, right, _) ->
            let byLength = compare right.Length left.Length
            if byLength <> 0 then byLength else compare leftIndex rightIndex)
        |> List.fold (fun (text: string) (_, oldValue, newValue) ->
            if oldValue = "" then text else text.Replace(oldValue, newValue, StringComparison.Ordinal)) value

    /// Produce the exact Python candidate_bytes projection for a merged skill
    /// manifest. Float JSON values fail closed until their rendering is proved.
    let bytes (candidateManifest: byte[]) (candidateBodies: Map<string, byte[]>)
              (candidateProvenance: byte[] option) (current: byte[] option)
              sourceProduct sourceNamespace destinationProduct destinationNamespace
              : Result<byte[], string> =
        try
            let candidateRows = rows "candidate" (parse candidateManifest)
            let ownedPaths =
                candidateProvenance |> Option.map (fun raw ->
                    let provenance = parse raw
                    let produced =
                        match field "producedPaths" provenance with
                        | Some(Array values) -> values
                        | _ -> fail "candidate-provenance-paths-invalid"
                    let owned =
                        [ for row in produced do
                            match stringField "owner" row, stringField "path" row with
                            | Some "generatedProduct", Some path
                                when path.StartsWith(".agents/skills/", StringComparison.Ordinal)
                                     && path.EndsWith("/SKILL.md", StringComparison.Ordinal) ->
                                if not (safeRelative path) then fail "candidate-provenance-path-unsafe"
                                yield path
                            | _ -> () ] |> Set.ofList
                    if Set.isEmpty owned then fail "candidate-provenance-no-product-skills"
                    owned)
            let packageRows = ResizeArray<string * Value>()
            let mutable materialized = Set.empty
            let packageIds = HashSet<string>(StringComparer.Ordinal)
            for row in candidateRows do
                match stringField "scope" row, stringField "supplied-by" row with
                | Some "product", Some suppliedBy
                    when suppliedBy.StartsWith("template/product-skills/fable-", StringComparison.Ordinal) ->
                    let path = stringField "resolvablePath" row |> Option.defaultWith (fun () -> fail "candidate-skill-path-invalid")
                    if not (safeRelative path)
                       || not (path.StartsWith(".agents/skills/", StringComparison.Ordinal))
                       || not (path.EndsWith("/SKILL.md", StringComparison.Ordinal)) then
                        fail $"candidate-skill-path-invalid:{path}"
                    let id = stringField "id" row |> Option.defaultWith (fun () -> fail "candidate-skill-id-invalid")
                    if not (packageIds.Add id) then fail $"candidate-skill-id-duplicate:{id}"
                    packageRows.Add(id, row)
                    match candidateBodies |> Map.tryFind path with
                    | Some body ->
                        if stringField "sha256" row <> Some(sha body) then fail $"candidate-skill-body-mismatch:{path}"
                        materialized <- materialized.Add path
                    | None -> ()
                | _ -> ()
            if packageRows.Count = 0 || Set.isEmpty materialized then fail "candidate-no-materialized-product-skills"
            if ownedPaths |> Option.exists (fun owned -> owned <> materialized) then
                fail "candidate-provenance-skill-mismatch"

            let preserved = ResizeArray<string * Value>()
            match current with
            | None -> ()
            | Some raw ->
                for row in rows "workspace" (parse raw) do
                    let id = stringField "id" row |> Option.defaultWith (fun () -> fail "workspace-skill-row-invalid")
                    if id <> "fable-remoting" && not (packageIds.Contains id) then preserved.Add(id, row)
            let combined = Seq.append preserved packageRows |> Seq.toList
            let ids = HashSet<string>(StringComparer.Ordinal)
            for id, _ in combined do
                if not (ids.Add id) then fail $"merged-skill-id-duplicate:{id}"
            let sorted = combined |> List.sortWith (fun (left, _) (right, _) -> pythonOrder left right)
            let merged = Object [ "schemaVersion", Integer "1"; "skills", Array(sorted |> List.map snd) ]
            let serialized = render merged + "\n"
            transform sourceProduct sourceNamespace destinationProduct destinationNamespace serialized
            |> utf8.GetBytes |> Ok
        with
        | :? InvalidDataException as error -> Error error.Message
        | :? JsonException -> Error "json-invalid"
        | :? DecoderFallbackException -> Error "json-utf8-invalid"
        | :? ArgumentException -> Error "merge-argument-invalid"
