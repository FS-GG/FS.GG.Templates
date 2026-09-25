namespace FS.GG.Templates.SvgWorkspacePolicy

open System

type WriteIntent =
    | Put of logicalPath: string
    | Retire of logicalPath: string

module Policy =
    let private ordinal = StringComparer.Ordinal
    let private mirrorPrefix = ".claude/skills/"

    let private validPath (value: string) =
        not (String.IsNullOrEmpty value)
        && not (value.Contains '\000')
        && not (value.Contains '\\')
        && not (value.StartsWith "/")
        && not (value.Length >= 2 && Char.IsLetter value[0] && value[1] = ':')
        && (value.Split '/' |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

    let private validatePaths label required (paths: string list) =
        if required && List.isEmpty paths then
            Error(sprintf "%s paths are empty" label)
        elif paths |> List.exists (validPath >> not) then
            Error(sprintf "%s path is unsafe or noncanonical" label)
        elif paths |> List.pairwise |> List.exists (fun (left, right) -> ordinal.Compare(left, right) >= 0) then
            Error(sprintf "%s paths are not sorted and unique" label)
        else
            Ok paths

    /// Pure logical write-set only. The caller must validate the manifest schema,
    /// candidate bytes, real paths/symlinks, receiver state, and transaction journal.
    let plan configuredClaudeMirror (managed: string list) (retired: string list) : Result<WriteIntent list, string> =
        match validatePaths "managed" true managed, validatePaths "retired" false retired with
        | Error message, _ | _, Error message -> Error message
        | Ok managedPaths, Ok retiredPaths ->
            let active = Set.ofList managedPaths
            if retiredPaths |> List.exists active.Contains then
                Error "managed and retired paths overlap"
            else
                let admitted (logical: string) = configuredClaudeMirror || not (logical.StartsWith(mirrorPrefix, StringComparison.Ordinal))
                [ yield! managedPaths |> List.filter admitted |> List.map Put
                  yield! retiredPaths |> List.filter admitted |> List.map Retire ]
                |> Ok
