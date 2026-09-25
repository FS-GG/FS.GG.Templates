namespace FS.GG.Templates.SvgWorkspaceArchive

open System
open System.Collections.Generic
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text
open System.Text.RegularExpressions
open FS.GG.Templates.SvgWorkspacePolicy

type CapturedPut = {
    LogicalPath: string
    MemberName: string
    RawBytes: byte[]
    RawSha256: string
    UnixMode: int
    RequiresMerge: bool
}

type ArchiveObservation = {
    ArchiveSha256: string
    SourceProduct: string
    SourceNamespace: string
    Intents: WriteIntent list
    Puts: CapturedPut list
}

type OutputObservation = {
    LogicalPath: string
    DestinationPath: string
    State: string
    ProposedSha256: string option
    SourceUnixMode: int option
    CurrentUnixMode: int option
}

/// Source-only observation. The selected archive hash and ownership digests are
/// caller facts, not provenance or receiver authority.
module Observer =
    let private prefix = "content/templates/fs-gg-fable-game/"
    let private maxArchiveBytes = 30_000_000L
    let private maxMemberBytes = 4_000_000L
    let private maxExpandedBytes = 64_000_000L
    let private utf8 = UTF8Encoding(false, true)
    let private identityPattern = Regex(@"^(?:module|namespace) ([A-Za-z_][A-Za-z0-9_.]*?)\.Domain(?:\s|$)", RegexOptions.Multiline)
    let private fail message = raise (InvalidDataException message)
    let private sha (bytes: byte[]) = SHA256.HashData bytes |> Convert.ToHexString |> fun value -> value.ToLowerInvariant()

    let private safeMember (name: string) =
        not (String.IsNullOrEmpty name)
        && not (name.Contains '\\' || name.Contains ':' || name.Contains(char 0))
        && not (name.StartsWith "/")
        && (name.Split '/' |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

    let private readBounded (entry: ZipArchiveEntry) =
        if entry.Length > maxMemberBytes then fail $"archive-member-too-large:{entry.FullName}"
        use input = entry.Open()
        use output = new MemoryStream()
        let buffer = Array.zeroCreate<byte> 8192
        let mutable count = input.Read(buffer, 0, buffer.Length)
        while count > 0 do
            if output.Length + int64 count > maxMemberBytes then fail $"archive-member-too-large:{entry.FullName}"
            output.Write(buffer, 0, count)
            count <- input.Read(buffer, 0, buffer.Length)
        output.ToArray()

    let private namespaceFrom (bytes: byte[]) =
        let text = utf8.GetString bytes
        let matched = identityPattern.Match text
        if not matched.Success then fail "source-namespace-unreadable"
        matched.Groups[1].Value

    let private mergedManifest logical =
        logical = ".agents/skills/skill-manifest.json"
        || logical = ".claude/skills/skill-manifest.json"

    let private memberFor (logical: string) =
        let sourceLogical =
            if logical.StartsWith(".claude/skills/", StringComparison.Ordinal) then
                ".agents/skills/" + logical.Substring(".claude/skills/".Length)
            else logical
        prefix + sourceLogical

    /// Bind every admitted Put intent to exact selected ZIP bytes, mode and
    /// member name. The archive remains in memory after the supplied SHA check.
    let inspectArchive path expectedArchiveSha expectedSourceProduct expectedSourceNamespace
                       mirrorState managed retired : Result<ArchiveObservation, string> =
        try
            let file = FileInfo path
            if not (isNull file.LinkTarget) || not file.Exists then fail "archive-path-unavailable-or-link"
            if file.Length > maxArchiveBytes then fail "archive-too-large"
            let archiveBytes = File.ReadAllBytes path
            if int64 archiveBytes.Length > maxArchiveBytes then fail "archive-too-large"
            let archiveSha = sha archiveBytes
            if archiveSha <> expectedArchiveSha then fail "archive-sha256-mismatch"
            let intents =
                match Policy.plan mirrorState managed retired with
                | Ok value -> value
                | Error reason -> fail $"intent-policy:{reason}"
            use memory = new MemoryStream(archiveBytes, false)
            use archive = new ZipArchive(memory, ZipArchiveMode.Read)
            let seen = HashSet<string>(StringComparer.OrdinalIgnoreCase)
            let rows = Dictionary<string, byte[] * int>(StringComparer.Ordinal)
            let mutable expanded = 0L
            for entry in archive.Entries do
                if not (safeMember entry.FullName) then fail $"archive-member-unsafe:{entry.FullName}"
                if not (seen.Add entry.FullName) then fail $"archive-member-duplicate-or-alias:{entry.FullName}"
                let mode = (entry.ExternalAttributes >>> 16) &&& 0xffff
                if not (entry.FullName = ".signature.p7s" && mode = 0)
                   && mode &&& 0o170000 <> 0o100000 then
                    fail $"archive-member-nonregular-or-link:{entry.FullName}"
                let bytes = readBounded entry
                expanded <- expanded + int64 bytes.Length
                if expanded > maxExpandedBytes then fail "archive-expanded-limit"
                rows.Add(entry.FullName, (bytes, mode))
            let solutions =
                rows.Keys
                |> Seq.filter (fun name ->
                    if name.StartsWith(prefix, StringComparison.Ordinal) then
                        let relative = name.Substring(prefix.Length)
                        not (relative.Contains '/') && relative.EndsWith(".slnx", StringComparison.Ordinal)
                    else false)
                |> Seq.toList
            let sourceProduct =
                match solutions with
                | [ name ] -> Path.GetFileNameWithoutExtension name
                | _ -> fail "source-solution-not-unique"
            if sourceProduct <> expectedSourceProduct then fail "source-product-identity-mismatch"
            let room = prefix + "Domain/Room.fs"
            if not (rows.ContainsKey room) then fail "source-room-missing"
            let sourceNamespace = namespaceFrom (fst rows[room])
            if sourceNamespace <> expectedSourceNamespace then fail "source-namespace-identity-mismatch"
            let puts =
                [ for intent in intents do
                    match intent with
                    | Retire _ -> ()
                    | Put logical ->
                        let memberName = memberFor logical
                        match rows.TryGetValue memberName with
                        | false, _ -> fail $"managed-archive-member-missing:{logical}"
                        | true, (bytes, mode) ->
                            yield { LogicalPath = logical; MemberName = memberName
                                    RawBytes = Array.copy bytes; RawSha256 = sha bytes
                                    UnixMode = mode; RequiresMerge = mergedManifest logical } ]
            Ok { ArchiveSha256 = archiveSha; SourceProduct = sourceProduct
                 SourceNamespace = sourceNamespace; Intents = intents; Puts = puts }
        with
        | :? InvalidDataException as error -> Error error.Message
        | :? IOException -> Error "archive-io"
        | :? UnauthorizedAccessException -> Error "archive-access-denied"
        | :? DecoderFallbackException -> Error "archive-identity-utf8-invalid"
        | :? ArgumentException -> Error "archive-argument-invalid"

    let private isLink (path: string) =
        let info = FileInfo path
        not (isNull info.LinkTarget)
        || ((File.Exists path || Directory.Exists path) && File.GetAttributes(path).HasFlag FileAttributes.ReparsePoint)

    let private checkTargetChain (root: string) (relative: string) =
        if isLink root || not (Directory.Exists root) then fail "workspace-root-unsafe"
        let mutable current = root
        let parts = relative.Split '/'
        for index in 0 .. parts.Length - 1 do
            current <- Path.Combine(current, parts[index])
            if isLink current then fail $"output-symlink:{relative}"
            if index < parts.Length - 1 && File.Exists current then fail $"output-parent-nondirectory:{relative}"
        current

    let private transformed (sourceProduct: string) (sourceNamespace: string)
                            (destinationProduct: string) (destinationNamespace: string) (raw: byte[]) =
        try
            let mutable text = utf8.GetString raw
            let replacements =
                [ sourceNamespace, destinationNamespace
                  sourceProduct, destinationProduct
                  sourceProduct.ToLowerInvariant(), destinationProduct.ToLowerInvariant() ]
                |> List.sortByDescending (fun (oldValue, _) -> oldValue.Length)
            for oldValue, newValue in replacements do
                if oldValue <> "" then text <- text.Replace(oldValue, newValue, StringComparison.Ordinal)
            utf8.GetBytes text
        with :? DecoderFallbackException -> Array.copy raw

    /// Read receiver identity and touched paths only. Existing bytes must equal
    /// proposed bytes or an explicitly supplied allowed digest; merged skill
    /// manifests remain deferred because their owner rows need separate proof.
    let inspectOutputs (observation: ArchiveObservation) workspaceRoot
                       expectedProduct expectedNamespace (allowedExisting: Map<string, Set<string>>)
                       : Result<OutputObservation list, string> =
        try
            let root = Path.GetFullPath workspaceRoot
            if isLink root || not (Directory.Exists root) then fail "workspace-root-unsafe"
            let solutions = Directory.GetFiles(root, "*.slnx", SearchOption.TopDirectoryOnly)
            let solution =
                match solutions with
                | [| only |] when not (isLink only) -> only
                | _ -> fail "workspace-solution-not-unique"
            let destinationProduct = Path.GetFileNameWithoutExtension solution
            let room = checkTargetChain root "Domain/Room.fs"
            if not (File.Exists room) then fail "workspace-room-missing"
            let destinationNamespace = namespaceFrom (File.ReadAllBytes room)
            if destinationProduct <> expectedProduct || destinationNamespace <> expectedNamespace then
                fail "destination-identity-mismatch"
            let puts = observation.Puts |> List.map (fun row -> row.LogicalPath, row) |> Map.ofList
            let actual = HashSet<string>(StringComparer.OrdinalIgnoreCase)
            [ for intent in observation.Intents do
                let logical = match intent with Put value | Retire value -> value
                let destination =
                    if logical = observation.SourceProduct + ".slnx" then Path.GetFileName solution
                    else logical
                if not (actual.Add destination) then fail $"output-path-alias:{destination}"
                let path = checkTargetChain root destination
                if (Directory.Exists path && not (File.Exists path)) then fail $"output-nonregular:{logical}"
                let current = if File.Exists path then Some(File.ReadAllBytes path) else None
                let currentMode =
                    if File.Exists path && OperatingSystem.IsLinux() then Some(int (File.GetUnixFileMode path))
                    else None
                match intent with
                | Put _ ->
                    let source = puts[logical]
                    if source.RequiresMerge then
                        yield { LogicalPath = logical; DestinationPath = destination
                                State = "deferred-merged-manifest"; ProposedSha256 = None
                                SourceUnixMode = Some source.UnixMode; CurrentUnixMode = currentMode }
                    else
                        let proposed = transformed observation.SourceProduct observation.SourceNamespace
                                        destinationProduct destinationNamespace source.RawBytes
                        let proposedSha = sha proposed
                        let state =
                            match current with
                            | None -> "add"
                            | Some bytes when bytes = proposed && currentMode = Some(source.UnixMode &&& 0o7777) -> "unchanged"
                            | Some bytes when bytes = proposed -> "replace"
                            | Some bytes when allowedExisting |> Map.tryFind logical |> Option.defaultValue Set.empty |> Set.contains (sha bytes) -> "replace"
                            | Some _ -> fail $"output-owner-mismatch:{logical}"
                        yield { LogicalPath = logical; DestinationPath = destination
                                State = state; ProposedSha256 = Some proposedSha
                                SourceUnixMode = Some source.UnixMode; CurrentUnixMode = currentMode }
                | Retire _ ->
                    let state =
                        match current with
                        | None -> "retired-absent"
                        | Some bytes when allowedExisting |> Map.tryFind logical |> Option.defaultValue Set.empty |> Set.contains (sha bytes) -> "retire"
                        | Some _ -> fail $"output-owner-mismatch:{logical}"
                    yield { LogicalPath = logical; DestinationPath = destination
                            State = state; ProposedSha256 = None; SourceUnixMode = None
                            CurrentUnixMode = currentMode } ]
            |> Ok
        with
        | :? InvalidDataException as error -> Error error.Message
        | :? IOException -> Error "workspace-io"
        | :? UnauthorizedAccessException -> Error "workspace-access-denied"
        | :? DecoderFallbackException -> Error "workspace-identity-utf8-invalid"
        | :? ArgumentException -> Error "workspace-argument-invalid"
