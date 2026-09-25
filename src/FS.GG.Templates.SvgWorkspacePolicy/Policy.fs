namespace FS.GG.Templates.SvgWorkspacePolicy

open System
open System.Text

type WriteIntent =
    | Put of logicalPath: string
    | Retire of logicalPath: string

type MirrorState =
    | MirrorAbsent
    | MirrorDirectory
    | MirrorSymlink
    | MirrorNonDirectory

module Policy =
    let private utf8 = UTF8Encoding(false, true)
    let private mirrorPrefix = ".claude/skills/"

    // UTF-8 byte order agrees with Python's Unicode codepoint order for valid
    // strings. .NET's ordinal comparison sorts UTF-16 surrogate units instead.
    let private pythonOrder (left: string) (right: string) =
        Array.compareWith compare (utf8.GetBytes left) (utf8.GetBytes right)

    let private validUnicode (value: string) =
        try
            utf8.GetByteCount value |> ignore
            true
        with :? EncoderFallbackException -> false

    let private asciiLetter letter =
        (letter >= 'A' && letter <= 'Z') || (letter >= 'a' && letter <= 'z')

    let private validPath (value: string) =
        not (String.IsNullOrEmpty value)
        && validUnicode value
        && not (value.Contains '\000')
        && not (value.Contains '\\')
        && not (value.StartsWith "/")
        && not (value.Length >= 2 && asciiLetter value[0] && value[1] = ':')
        && (value.Split '/' |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

    let private validatePaths label required (paths: string list) =
        if required && List.isEmpty paths then
            Error(sprintf "%s paths are empty" label)
        elif paths |> List.exists (validPath >> not) then
            Error(sprintf "%s path is unsafe or noncanonical" label)
        elif paths |> List.pairwise |> List.exists (fun (left, right) -> pythonOrder left right >= 0) then
            Error(sprintf "%s paths are not sorted and unique" label)
        else
            Ok paths

    /// Pure logical write-set only. The caller must validate the manifest schema,
    /// candidate bytes, real paths/symlinks, receiver state, and transaction journal.
    let plan mirrorState (managed: string list) (retired: string list) : Result<WriteIntent list, string> =
        match validatePaths "managed" true managed, validatePaths "retired" false retired with
        | Error message, _ | _, Error message -> Error message
        | Ok managedPaths, Ok retiredPaths ->
            let active = Set.ofList managedPaths
            if retiredPaths |> List.exists active.Contains then
                Error "managed and retired paths overlap"
            elif mirrorState = MirrorSymlink || mirrorState = MirrorNonDirectory then
                Error "configured skill mirror is not a regular directory"
            else
                let allPaths = managedPaths @ retiredPaths
                if allPaths |> List.exists (fun parent ->
                    allPaths |> List.exists (fun child -> child.StartsWith(parent + "/", StringComparison.Ordinal))) then
                    Error "logical write paths have an ancestor collision"
                else
                    let admitted (logical: string) = mirrorState = MirrorDirectory || not (logical.StartsWith(mirrorPrefix, StringComparison.Ordinal))
                    [ yield! managedPaths |> List.filter admitted |> List.map Put
                      yield! retiredPaths |> List.filter admitted |> List.map Retire ]
                    |> Ok
