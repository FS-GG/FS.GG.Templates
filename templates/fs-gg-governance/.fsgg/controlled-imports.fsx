open System
open System.IO
open System.Security.Cryptography
open System.Text
open System.Text.Json

type ImportKind =
    | RegularFile
    | DirectoryTree

type ControlledImport =
    { Kind: ImportKind
      DestinationPath: string
      UpstreamRepository: string
      UpstreamRevision: string
      UpstreamPath: string
      License: string
      ImportMethod: string
      Sha256: string }

type Finding =
    { Rule: string
      Path: string
      Message: string }

let args = fsi.CommandLineArgs |> Array.skip 1 |> Array.toList

let rec private optionValue name remaining =
    match remaining with
    | key :: value :: _ when key = name -> Some value
    | _ :: tail -> optionValue name tail
    | [] -> None

let private root =
    optionValue "--root" args
    |> Option.defaultValue (Directory.GetCurrentDirectory())
    |> Path.GetFullPath

let private manifestPath =
    optionValue "--manifest" args
    |> Option.defaultValue ".fsgg/controlled-imports.json"
    |> fun path -> if Path.IsPathRooted path then path else Path.Combine(root, path)
    |> Path.GetFullPath

let private exemptionProbe = optionValue "--check-exemption" args
let private findings = ResizeArray<Finding>()
let private verified = ResizeArray<ControlledImport * string>()

let private displayPath (path: string) =
    try Path.GetRelativePath(root, path).Replace('\\', '/')
    with _ -> path

let private add (rule: string) (path: string) (message: string) =
    findings.Add
        { Rule = rule
          Path = displayPath path
          Message = message }

let private isLowerSha256 (value: string) =
    value.Length = 64
    && value
       |> Seq.forall (fun c -> (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))

let private isPinnedRevision (value: string) =
    (value.Length = 40 || value.Length = 64)
    && value
       |> Seq.forall (fun c -> (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))

let private pathComparison =
    if OperatingSystem.IsWindows() then
        StringComparison.OrdinalIgnoreCase
    else
        StringComparison.Ordinal

let private tryRepoPath (relativePath: string) =
    if String.IsNullOrWhiteSpace relativePath || Path.IsPathRooted relativePath then
        Error "must be a non-empty repo-relative path"
    else
        let normalizedInput = relativePath.Replace('\\', '/')
        let segments = normalizedInput.Split('/', StringSplitOptions.RemoveEmptyEntries)

        if segments |> Array.exists (fun segment -> segment = "." || segment = "..") then
            Error "must not contain '.' or '..' path segments"
        else
            let full = Path.GetFullPath(Path.Combine(root, relativePath))
            let prefix = root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + string Path.DirectorySeparatorChar

            if not (full.StartsWith(prefix, pathComparison)) then
                Error "resolves outside the repository root"
            else
                Ok(normalizedInput.TrimStart('/'), full)

let private appendUInt64BigEndian (hash: IncrementalHash) (value: uint64) =
    let bytes = BitConverter.GetBytes value

    if BitConverter.IsLittleEndian then
        Array.Reverse bytes

    hash.AppendData bytes

let private rejectReparsePoint (path: string) =
    try
        if File.GetAttributes(path).HasFlag FileAttributes.ReparsePoint then
            add "GOV-IMPORT-SYMLINK" path "controlled imports may not contain symbolic links or other reparse points"
            false
        else
            true
    with ex ->
        add "GOV-IMPORT-READ" path $"cannot inspect filesystem attributes: {ex.Message}"
        false

let private rejectReparsePath (fullPath: string) =
    let relative = Path.GetRelativePath(root, fullPath)
    let segments = relative.Split([| Path.DirectorySeparatorChar; Path.AltDirectorySeparatorChar |], StringSplitOptions.RemoveEmptyEntries)
    let mutable current = root
    let mutable valid = true

    for segment in segments do
        current <- Path.Combine(current, segment)

        if (File.Exists current || Directory.Exists current) && not (rejectReparsePoint current) then
            valid <- false

    valid

let private tryDirectoryFiles (directory: string) =
    let files = ResizeArray<string * string>()
    let pending = Collections.Generic.Stack<string>()
    pending.Push directory
    let mutable valid = true

    while pending.Count > 0 do
        let current = pending.Pop()

        if rejectReparsePoint current then
            try
                for entry in Directory.EnumerateFileSystemEntries current do
                    if rejectReparsePoint entry then
                        if Directory.Exists entry then
                            pending.Push entry
                        elif File.Exists entry then
                            let relative = Path.GetRelativePath(directory, entry).Replace('\\', '/')
                            files.Add(relative, entry)
                        else
                            add "GOV-IMPORT-READ" entry "filesystem entry is neither a regular file nor a directory"
                            valid <- false
                    else
                        valid <- false
            with ex ->
                add "GOV-IMPORT-READ" current $"cannot enumerate directory: {ex.Message}"
                valid <- false
        else
            valid <- false

    if valid then
        files
        |> Seq.sortWith (fun (left, _) (right, _) -> StringComparer.Ordinal.Compare(left, right))
        |> Seq.toList
        |> Ok
    else
        Error()

// Canonical tree digest, version 1. Each ordinal-sorted file contributes an injective binary record:
//   uint64-be(path UTF-8 byte length) || path UTF-8 bytes ||
//   uint64-be(file byte length)       || raw file bytes
// The tree SHA-256 is over the concatenated records. Length prefixes keep every boundary unambiguous;
// normalized '/' paths make the same checked-out bytes hash identically on Windows and Unix.
let private tryTreeDigest (directory: string) =
    match tryDirectoryFiles directory with
    | Error _ -> Error()
    | Ok files ->
        try
            use hash = IncrementalHash.CreateHash HashAlgorithmName.SHA256

            for relative, path in files do
                let pathBytes = Encoding.UTF8.GetBytes relative
                let length = FileInfo(path).Length
                appendUInt64BigEndian hash (uint64 pathBytes.LongLength)
                hash.AppendData pathBytes
                appendUInt64BigEndian hash (uint64 length)
                use input = File.OpenRead path
                let buffer = Array.zeroCreate<byte> 81920
                let mutable read = input.Read(buffer, 0, buffer.Length)

                while read > 0 do
                    hash.AppendData(buffer, 0, read)
                    read <- input.Read(buffer, 0, buffer.Length)

            hash.GetHashAndReset()
            |> Convert.ToHexString
            |> fun text -> text.ToLowerInvariant()
            |> Ok
        with ex ->
            add "GOV-IMPORT-READ" directory $"cannot read directory tree bytes: {ex.Message}"
            Error()

let private requiredString (entry: JsonElement) (destinationPath: string) (name: string) =
    let mutable value = Unchecked.defaultof<JsonElement>

    if entry.TryGetProperty(name, &value)
       && value.ValueKind = JsonValueKind.String
       && not (String.IsNullOrWhiteSpace(value.GetString())) then
        Some(value.GetString())
    else
        add "GOV-IMPORT-MANIFEST" destinationPath $"controlled import requires non-empty '{name}'"
        None

let private parseEntry (entry: JsonElement) =
    let destinationText =
        let mutable destination = Unchecked.defaultof<JsonElement>

        if entry.TryGetProperty("destinationPath", &destination)
           && destination.ValueKind = JsonValueKind.String then
            destination.GetString()
        else
            ""

    let destinationForFinding =
        if String.IsNullOrWhiteSpace destinationText then manifestPath
        else Path.Combine(root, destinationText)

    let kind =
        match requiredString entry destinationForFinding "kind" with
        | Some "file" -> Some RegularFile
        | Some "directory" -> Some DirectoryTree
        | Some other ->
            add "GOV-IMPORT-MANIFEST" destinationForFinding $"unknown import kind '{other}'; expected 'file' or 'directory'"
            None
        | None -> None

    let destination = requiredString entry destinationForFinding "destinationPath"
    let repository = requiredString entry destinationForFinding "upstreamRepository"
    let revision = requiredString entry destinationForFinding "upstreamRevision"
    let upstreamPath = requiredString entry destinationForFinding "upstreamPath"
    let license = requiredString entry destinationForFinding "license"
    let method' = requiredString entry destinationForFinding "importMethod"
    let digest = requiredString entry destinationForFinding "sha256"

    match digest with
    | Some value when not (isLowerSha256 value) ->
        add "GOV-IMPORT-MANIFEST" destinationForFinding "'sha256' must be 64 lowercase hexadecimal characters"
    | _ -> ()

    match revision with
    | Some value when not (isPinnedRevision value) ->
        add
            "GOV-IMPORT-MANIFEST"
            destinationForFinding
            "'upstreamRevision' must be a pinned 40- or 64-character lowercase hexadecimal object id"
    | _ -> ()

    match kind, destination, repository, revision, upstreamPath, license, method', digest with
    | Some kind, Some destination, Some repository, Some revision, Some upstreamPath, Some license, Some method', Some digest
        when isLowerSha256 digest && isPinnedRevision revision ->
        Some
            { Kind = kind
              DestinationPath = destination.Replace('\\', '/')
              UpstreamRepository = repository
              UpstreamRevision = revision
              UpstreamPath = upstreamPath
              License = license
              ImportMethod = method'
              Sha256 = digest }
    | _ -> None

let private parseManifest () =
    if not (File.Exists manifestPath) then
        add "GOV-IMPORT-MANIFEST" manifestPath "controlled-import manifest is missing"
        []
    else
        try
            use document = JsonDocument.Parse(File.ReadAllBytes manifestPath)
            let rootElement = document.RootElement
            let mutable version = Unchecked.defaultof<JsonElement>
            let mutable imports = Unchecked.defaultof<JsonElement>

            if not (
                rootElement.TryGetProperty("schemaVersion", &version)
                && version.ValueKind = JsonValueKind.Number
                && version.GetInt32() = 1
            ) then
                add "GOV-IMPORT-MANIFEST" manifestPath "'schemaVersion' must be 1"

            if not (
                rootElement.TryGetProperty("imports", &imports)
                && imports.ValueKind = JsonValueKind.Array
            ) then
                add "GOV-IMPORT-MANIFEST" manifestPath "'imports' must be an array"
                []
            else
                imports.EnumerateArray() |> Seq.choose parseEntry |> Seq.toList
        with ex ->
            add "GOV-IMPORT-MANIFEST" manifestPath $"malformed JSON: {ex.Message}"
            []

let private attributesLines =
    let path = Path.Combine(root, ".gitattributes")

    if File.Exists path then
        try File.ReadAllLines(path) |> Set.ofArray
        with ex ->
            add "GOV-IMPORT-READ" path $"cannot read .gitattributes: {ex.Message}"
            Set.empty
    else
        Set.empty

let private verifyImport controlledImport =
    match tryRepoPath controlledImport.DestinationPath with
    | Error message ->
        add "GOV-IMPORT-PATH" (Path.Combine(root, controlledImport.DestinationPath)) message
    | Ok(normalized, fullPath) ->
        let expectedAttribute =
            match controlledImport.Kind with
            | RegularFile -> $"{normalized} -text"
            | DirectoryTree -> $"{normalized.TrimEnd('/')}/** -text"

        if not (attributesLines.Contains expectedAttribute) then
            add
                "GOV-IMPORT-ATTRIBUTES"
                (Path.Combine(root, ".gitattributes"))
                $"verbatim import '{normalized}' requires the exact line: {expectedAttribute}"

        if rejectReparsePath fullPath then
            match controlledImport.Kind with
            | RegularFile ->
                if not (File.Exists fullPath) || Directory.Exists fullPath then
                    add "GOV-IMPORT-DIGEST" fullPath "controlled regular-file import is missing or is not a regular file"
                else
                    try
                        use input = File.OpenRead fullPath

                        let actual =
                            SHA256.HashData input
                            |> Convert.ToHexString
                            |> fun text -> text.ToLowerInvariant()

                        if actual = controlledImport.Sha256 && attributesLines.Contains expectedAttribute then
                            verified.Add(controlledImport, fullPath)
                        else
                            add
                                "GOV-IMPORT-DIGEST"
                                fullPath
                                $"file digest mismatch: expected {controlledImport.Sha256}, got {actual}"
                    with ex ->
                        add "GOV-IMPORT-READ" fullPath $"cannot read controlled import bytes: {ex.Message}"
            | DirectoryTree ->
                if not (Directory.Exists fullPath) || File.Exists fullPath then
                    add "GOV-IMPORT-DIGEST" fullPath "controlled directory import is missing or is not a directory"
                else
                    match tryTreeDigest fullPath with
                    | Ok actual when actual = controlledImport.Sha256 && attributesLines.Contains expectedAttribute ->
                        verified.Add(controlledImport, fullPath)
                    | Ok actual ->
                        add
                            "GOV-IMPORT-DIGEST"
                            fullPath
                            $"tree digest mismatch: expected {controlledImport.Sha256}, got {actual}"
                    | Error _ -> ()

let private isSameOrDescendant parent candidate =
    String.Equals(candidate, parent, pathComparison)
    || candidate.StartsWith(
        parent.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
        + string Path.DirectorySeparatorChar,
        pathComparison
    )

let imports = parseManifest ()

if findings.Count = 0 then
    imports |> List.iter verifyImport

if findings.Count = 0 then
    for controlledImport, fullPath in verified do
        let kind =
            match controlledImport.Kind with
            | RegularFile -> "file"
            | DirectoryTree -> "directory"

        printfn "GOV-IMPORT-VERIFIED\t%s\t%s" kind (displayPath fullPath)

    match exemptionProbe with
    | None -> ()
    | Some probe ->
        match tryRepoPath probe with
        | Error message -> add "GOV-IMPORT-EXEMPTION" (Path.Combine(root, probe)) message
        | Ok(_, fullProbe) ->
            let isExempt =
                verified
                |> Seq.exists (fun (entry, fullImport) ->
                    match entry.Kind with
                    | RegularFile -> String.Equals(fullProbe, fullImport, pathComparison)
                    | DirectoryTree -> isSameOrDescendant fullImport fullProbe)

            if isExempt then
                printfn "GOV-IMPORT-EXEMPT\t%s" (displayPath fullProbe)
            else
                add
                    "GOV-IMPORT-EXEMPTION"
                    fullProbe
                    "path is not covered by a successfully verified controlled import"

if findings.Count > 0 then
    for finding in findings do
        eprintfn "%s\t%s\t%s" finding.Rule finding.Path finding.Message

    exit 1

exit 0
