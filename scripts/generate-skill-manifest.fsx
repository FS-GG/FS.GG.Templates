// Generates the owner-authored product-skill manifest. Digest semantics are UTF-8 text SHA-256,
// matching Fsgg.SkillMirror: File.ReadAllText removes an optional BOM before hashing.
open System
open System.IO
open System.Security.Cryptography
open System.Text

let root =
    let rec find (dir: string) =
        if File.Exists(Path.Combine(dir, "FS.GG.Templates.csproj")) then dir
        else match Directory.GetParent dir |> Option.ofObj with Some p -> find p.FullName | None -> failwith "FS.GG.Templates root not found"
    find __SOURCE_DIRECTORY__
let path (rel: string) = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar))
let manifestRel = "template/skill-manifest/skill-manifest.json"
if Environment.GetCommandLineArgs() |> Array.contains "--list" then printfn "skill-manifest\t%s\t" manifestRel; exit 0
let catalog =
    [ "fable-project", "template/product-skills/fable-project/SKILL.md", "template in [fable-game, fable-bindings]"
      "fable-interop", "template/product-skills/fable-interop/SKILL.md", "template in [fable-game, fable-bindings]"
      "fable-remoting", "template/product-skills/fable-remoting/SKILL.md", "template in [fable-game]"
      "fable-signalr", "template/product-skills/fable-signalr/SKILL.md", "template in [fable-game]"
      "fable-testing", "template/product-skills/fable-testing/SKILL.md", "template in [fable-game, fable-bindings]"
      "fable-bindings", "template/product-skills/fable-bindings/SKILL.md", "template in [fable-bindings]" ]
let digest (text: string) = Encoding.UTF8.GetBytes text |> SHA256.HashData |> Array.map (fun b -> b.ToString "x2") |> String.concat ""
let esc (s: string) = s.Replace("\\", "\\\\").Replace("\"", "\\\"")
let rows =
    catalog |> List.sortBy (fun (id, _, _) -> id) |> List.map (fun (id, source, when_) ->
        let suppliedBy = source.Substring(0, source.LastIndexOf('/') + 1)
        sprintf "    {\n      \"id\": \"%s\",\n      \"scope\": \"product\",\n      \"sha256\": \"%s\",\n      \"resolvablePath\": \".agents/skills/%s/SKILL.md\",\n      \"materializes-when\": \"%s\",\n      \"supplied-by\": \"%s\"\n    }" id (digest (File.ReadAllText(path source))) id (esc when_) (esc suppliedBy))
    |> String.concat ",\n"
let rendered = sprintf "{\n  \"schemaVersion\": 1,\n  \"skills\": [\n%s\n  ]\n}\n" rows
let target = path manifestRel
if Environment.GetCommandLineArgs() |> Array.contains "--check" then
    if File.Exists target && File.ReadAllText target = rendered then
        printfn "skill-manifest: up to date (%d skills)" catalog.Length
    else
        eprintfn "skill-manifest: STALE — run `dotnet fsi scripts/generate-skill-manifest.fsx`"
        exit 1
else
    Directory.CreateDirectory(Path.GetDirectoryName target) |> ignore
    File.WriteAllText(target, rendered)
    printfn "skill-manifest: wrote %s (%d skills)" target catalog.Length
