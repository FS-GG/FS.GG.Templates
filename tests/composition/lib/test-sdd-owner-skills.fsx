#load "../../../scripts/sdd-owner-skills.fsx"
open System
open System.IO
open System.Text
open System.Text.Json.Nodes

let product = fsi.CommandLineArgs.[1]
let load, names = SddOwnerSkills.assemblyResources fsi.CommandLineArgs.[2]
let manifest = Path.Combine(product,".agents/skills/skill-manifest.json")
let original = File.ReadAllBytes manifest
let mutable controls = 0
let refuses name action =
    let mutable refused = false
    try action() with _ -> refused <- true
    if not refused then failwith ("Unexpected acceptance: " + name)
    controls <- controls + 1
    printfn "PASS refusal: %s" name
let admit resource = SddOwnerSkills.admitResources resource names product "fs-gg-fable-game" |> ignore
try
    let selected = SddOwnerSkills.admitResources load names product "fs-gg-fable-game"
    if selected.Count <> 12 then failwith "Wrong actual selected cardinality"
    controls <- controls + 1
    for field,value in ["supplied-by","template/forged/"; "sha256",String.replicate 64 "0"; "materializes-when","always"] do
        let doc = JsonNode.Parse(Encoding.UTF8.GetString(original))
        let row = doc.["skills"].AsArray() |> Seq.find (fun row -> row.["id"].GetValue<string>() = "fs-gg-browser-audio")
        row.[field] <- JsonValue.Create(value)
        File.WriteAllText(manifest,doc.ToJsonString())
        refuses ("foreign " + field) (fun () -> admit load)
        File.WriteAllBytes(manifest,original)
    refuses "forged resource body" (fun () -> admit (fun name -> if name = "AudioSkill.skill/fs-gg-browser-audio/SKILL.md" then Encoding.UTF8.GetBytes("forged") else load name))
    refuses "unsupported owner predicate even when another arm matches" (fun () -> admit (fun name ->
        if name = "AudioSkill.manifest" then
            let doc = JsonNode.Parse(Encoding.UTF8.GetString(load name))
            doc.["skills"].[0].["materializes-when"] <- JsonValue.Create("template == fable-game or unknown(feature)")
            Encoding.UTF8.GetBytes(doc.ToJsonString())
        else load name))
    let body = Path.Combine(product,".agents/skills/fs-gg-browser-audio/SKILL.md")
    let saved = File.ReadAllBytes body
    try File.WriteAllText(body,"swapped"); refuses "changed delivered body" (fun () -> admit load)
    finally File.WriteAllBytes(body,saved)
    let sidecar = Path.Combine(product,".agents/skills/fs-gg-browser-audio/extra.txt")
    try File.WriteAllText(sidecar,"extra"); refuses "extra delivered file" (fun () -> admit load)
    finally File.Delete sidecar
    let prov = Path.Combine(product,".fsgg/scaffold-provenance.json")
    let saved = File.ReadAllBytes prov
    try
        let doc = JsonNode.Parse(Encoding.UTF8.GetString(saved))
        for row in doc.["renderingSkillPaths"].AsArray() do
            if row.["path"].GetValue<string>() = ".agents/skills/fs-gg-browser-audio/SKILL.md" then row.["owner"] <- JsonValue.Create("gameSkill")
        File.WriteAllText(prov,doc.ToJsonString())
        refuses "forged provenance owner" (fun () -> admit load)
    finally File.WriteAllBytes(prov,saved)
    // Same-id unverified bytes cannot hide behind an otherwise legitimate supplier.
    if not (SddOwnerSkills.selects "fable-game" "" "" "profile in [game, sample-pack] or template == fable-game") then failwith "Predicate positive failed"
    if SddOwnerSkills.selects "fable-game" "" "" "template == fable-game and bundle in [tactical, complete]" then failwith "Unselected bundle accepted"
    controls <- controls + 2
    printfn "PASS %d co-producer causal controls" controls
finally File.WriteAllBytes(manifest,original)
