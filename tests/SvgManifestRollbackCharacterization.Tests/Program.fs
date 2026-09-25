open System
open System.IO
open System.Text.Json
open FS.GG.Templates.SvgWorkspacePolicy
open FS.GG.Templates.SvgWorkspaceArchive

let args = Environment.GetCommandLineArgs()
if args.Length <> 2 then failwith "characterization observation JSON path required"
let observationJson = JsonDocument.Parse(File.ReadAllBytes args[1])
let observation = observationJson.RootElement
let strings (element: JsonElement) (name: string) =
    element.GetProperty(name).EnumerateArray()
    |> Seq.map (fun item -> item.GetString())
    |> Seq.toList
let managed = strings observation "managed"
let retired = strings observation "retired"
let manifestPaths = [ ".agents/skills/skill-manifest.json"; ".claude/skills/skill-manifest.json" ]
let retiredPaths = [ ".agents/skills/fable-remoting/SKILL.md"; ".claude/skills/fable-remoting/SKILL.md" ]
if managed <> manifestPaths || retired <> retiredPaths then failwith "synthetic intent paths differ from selected manifest slice"

let baselineJson = JsonDocument.Parse(File.ReadAllBytes("scripts/svg-complete-workspace-baselines.json"))
let baseline = baselineJson.RootElement
let selectedManaged = strings baseline "managedPaths"
let selectedRetired = strings baseline "retiredPaths"
let selected mirror =
    match Policy.plan mirror selectedManaged selectedRetired with
    | Error reason -> failwithf "selected F# intent policy failed: %s" reason
    | Ok intents ->
        intents |> List.filter (function
            | Put path -> List.contains path manifestPaths
            | Retire path -> List.contains path retiredPaths)
let mirrorIntents = selected MirrorDirectory
let absentIntents = selected MirrorAbsent
let expected = [ Put manifestPaths[0]; Put manifestPaths[1]; Retire retiredPaths[0]; Retire retiredPaths[1] ]
if mirrorIntents <> expected then failwithf "selected mirror intents changed: %A" mirrorIntents
if absentIntents <> [ Put manifestPaths[0]; Retire retiredPaths[0] ] then
    failwithf "selected absent-mirror intents changed: %A" absentIntents

let archivePath = observation.GetProperty("archivePath").GetString()
let archiveSha = observation.GetProperty("archiveSha256").GetString()
let captured =
    match Observer.inspectArchive archivePath archiveSha "FableGameWorkspace" "FableGameWorkspaceNamespace"
            MirrorDirectory managed retired with
    | Error reason -> failwithf "synthetic archive observer refused selected slice: %s" reason
    | Ok value -> value
if captured.Intents <> mirrorIntents then failwith "#503 archive observation differs from #501 selected intents"
if captured.Puts.Length <> 2 || captured.Puts |> List.exists (fun row -> not row.RequiresMerge) then
    failwith "merged manifests were not deferred"
let rawManifestSha = observation.GetProperty("rawManifestSha256").GetString()
if captured.Puts |> List.exists (fun row -> row.RawSha256 <> rawManifestSha) then
    failwith "selected manifest intents did not bind exact archive bytes"
let journalPaths = strings observation "journalPaths"
let journalStates = strings observation "journalStates"
let intendedPaths = mirrorIntents |> List.map (function Put path | Retire path -> path)
let intendedStates = mirrorIntents |> List.map (function Put _ -> "present" | Retire _ -> "absent")
if journalPaths <> intendedPaths || journalStates <> intendedStates then
    failwithf "Python journal differs from selected F# intents: %A/%A" journalPaths journalStates
printfn "selected F# intents, #503 archive puts and Python rollback journal match %d paths" mirrorIntents.Length
observationJson.Dispose()
baselineJson.Dispose()
