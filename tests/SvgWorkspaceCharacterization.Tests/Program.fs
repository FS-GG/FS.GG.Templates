open System
open System.IO
open System.Text.Json
open FS.GG.Templates.SvgWorkspacePolicy

if Environment.GetCommandLineArgs().Length <> 2 then failwith "characterization JSON path required"

let data = JsonDocument.Parse(File.ReadAllBytes(Environment.GetCommandLineArgs()[1]))
let root = data.RootElement
let strings (name: string) =
    root.GetProperty(name).EnumerateArray()
    |> Seq.map (fun (item: JsonElement) -> item.GetString())
    |> Seq.toList
let managed, retired = strings "managed", strings "retired"
let expectedPaths = strings "journalPaths"
let expectedStates = strings "journalStates"

match Policy.plan false managed retired with
| Error message -> failwithf "Python-admitted archive paths refused by F# policy: %s" message
| Ok intents ->
    let paths = intents |> List.map (function Put path | Retire path -> path)
    let states = intents |> List.map (function Put _ -> "present" | Retire _ -> "absent")
    if paths <> expectedPaths || states <> expectedStates then
        failwithf "F# logical intents differ from Python journal: %A/%A vs %A/%A"
            paths states expectedPaths expectedStates
    printfn "F# logical intents match %d archive-backed Python journal rows" intents.Length
