open FS.GG.Templates.SvgWorkspacePolicy

let mutable count = 0

let expect label expected actual =
    count <- count + 1
    if actual <> expected then failwithf "%s: expected %A, got %A" label expected actual

let refuses label managed retired =
    count <- count + 1
    match Policy.plan true managed retired with
    | Error _ -> ()
    | Ok writes -> failwithf "%s: accepted %A" label writes

expect "managed and retired write set" (Ok [Put "a/b"; Put "b"; Retire "old"])
    (Policy.plan true ["a/b"; "b"] ["old"])
expect "unconfigured mirror is omitted" (Ok [Put "a/b"; Retire "old"])
    (Policy.plan false [".claude/skills/x/SKILL.md"; "a/b"] [".claude/skills/y/SKILL.md"; "old"])
expect "configured mirror is included" (Ok [Put ".claude/skills/x/SKILL.md"])
    (Policy.plan true [".claude/skills/x/SKILL.md"] [])

refuses "missing managed paths" [] []
refuses "duplicate managed path" ["a/b"; "a/b"] []
refuses "unsorted managed paths" ["b"; "a"] []
refuses "duplicate retired path" ["a"] ["b"; "b"]
refuses "cross-list alias" ["a/b"] ["a/b"]
refuses "dot alias" ["a/./b"; "a/b"] []
refuses "parent traversal" ["a/../b"] []
refuses "repeated separator" ["a//b"] []
refuses "trailing separator" ["a/"] []
refuses "absolute path" ["/a"] []
refuses "drive path" ["C:/outside"] []
refuses "backslash path" ["a\\b"] []
refuses "NUL path" ["a\000b"] []
refuses "invalid retired path even if mirror omitted" ["safe"] [".claude/skills/../escape"]

printfn "svg workspace F# policy controls: %d passed" count
