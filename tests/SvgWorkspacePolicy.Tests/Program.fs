open FS.GG.Templates.SvgWorkspacePolicy
open System.IO
open System.Text.Json

let mutable count = 0

let expect label expected actual =
    count <- count + 1
    if actual <> expected then failwithf "%s: expected %A, got %A" label expected actual

let refuses label managed retired =
    count <- count + 1
    match Policy.plan MirrorDirectory managed retired with
    | Error _ -> ()
    | Ok writes -> failwithf "%s: accepted %A" label writes

expect "managed and retired write set" (Ok [Put "a/b"; Put "b"; Retire "old"])
    (Policy.plan MirrorDirectory ["a/b"; "b"] ["old"])
expect "unconfigured mirror is omitted" (Ok [Put "a/b"; Retire "old"])
    (Policy.plan MirrorAbsent [".claude/skills/x/SKILL.md"; "a/b"] [".claude/skills/y/SKILL.md"; "old"])
expect "configured mirror is included" (Ok [Put ".claude/skills/x/SKILL.md"])
    (Policy.plan MirrorDirectory [".claude/skills/x/SKILL.md"] [])
expect "symlinked mirror refuses before filtering" (Error "configured skill mirror is not a regular directory")
    (Policy.plan MirrorSymlink [".claude/skills/x/SKILL.md"; "a/b"] [])
expect "non-directory mirror refuses before filtering" (Error "configured skill mirror is not a regular directory")
    (Policy.plan MirrorNonDirectory ["a/b"] [])
expect "Python Unicode codepoint path order" (Ok [Put "\uE000"; Put "😀"])
    (Policy.plan MirrorAbsent ["\uE000"; "😀"] [])
expect "only ASCII drive letters are reserved" (Ok [Put "É:/asset"])
    (Policy.plan MirrorAbsent ["É:/asset"] [])

refuses "missing managed paths" [] []
refuses "duplicate managed path" ["a/b"; "a/b"] []
refuses "unsorted managed paths" ["b"; "a"] []
refuses "duplicate retired path" ["a"] ["b"; "b"]
refuses "cross-list alias" ["a/b"] ["a/b"]
refuses "managed ancestor cannot also be a file" ["a"; "a/b"] []
refuses "separated ancestor collision" ["a"; "a-"; "a/b"] []
refuses "retired ancestor collides with managed child" ["a/b"] ["a"]
refuses "dot alias" ["a/./b"; "a/b"] []
refuses "parent traversal" ["a/../b"] []
refuses "repeated separator" ["a//b"] []
refuses "trailing separator" ["a/"] []
refuses "absolute path" ["/a"] []
refuses "drive path" ["C:/outside"] []
refuses "backslash path" ["a\\b"] []
refuses "NUL path" ["a\000b"] []
refuses "invalid UTF-16 surrogate" [System.String([| char 0xD800 |])] []
refuses "invalid retired path even if mirror omitted" ["safe"] [".claude/skills/../escape"]

let root = Path.GetFullPath(Path.Combine(__SOURCE_DIRECTORY__, "../.."))
let manifest = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "scripts/svg-complete-workspace-baselines.json")))
let paths (name: string) =
    manifest.RootElement.GetProperty(name).EnumerateArray()
    |> Seq.map (fun (row: JsonElement) -> row.GetString())
    |> Seq.toList
let checkedInManaged, checkedInRetired = paths "managedPaths", paths "retiredPaths"
match Policy.plan MirrorDirectory checkedInManaged checkedInRetired with
| Ok intents -> expect "checked-in manifest logical write-set size" 128 intents.Length
| Error reason -> failwithf "checked-in manifest rejected: %s" reason
manifest.Dispose()

printfn "svg workspace F# policy controls: %d passed" count
