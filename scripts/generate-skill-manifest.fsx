// Owner of the generic Fable product-skill catalog: it GENERATES the producer manifest, CHECKS that
// the manifest and the package items in FS.GG.Templates.csproj still agree with the catalog, and
// ASSERTS that a packed-and-instantiated product actually received what the manifest promised.
//
// One catalog, three consumers, so the three cannot drift apart silently (FS.GG.Templates#347). The
// rows below are the single source of truth for which skills exist, which templates each one
// materializes into, and what its canonical digest is. `--check` reds when the checked-in manifest
// or the csproj package items disagree with the rows; `--assert-product` reds when a generated
// product disagrees with the manifest IT shipped.
//
// WHY --assert-product READS THE PRODUCT'S OWN MANIFEST. A green `--check` proves only that a
// repository file is current. Before #347's repair this catalog lived in a tree no package item
// referenced, so every source-side check was green while no generated product could receive a
// single skill. The product-side arm is the one that can observe that, and it must therefore grade
// the shipped manifest against the shipped skills rather than re-derive both from this file.
//
// Digest semantics are UTF-8 text SHA-256, matching Fsgg.SkillMirror: File.ReadAllText removes an
// optional BOM before hashing. `--assert-product` hashes the MATERIALIZED file the same way, so a
// reported drift means the bytes really differ, not that two hashers disagree.
//
// Usage:
//   dotnet fsi scripts/generate-skill-manifest.fsx                       regenerate the manifest
//   dotnet fsi scripts/generate-skill-manifest.fsx --check               catalog <-> manifest <-> csproj
//   dotnet fsi scripts/generate-skill-manifest.fsx --assert-product <dir> --template <templateId>
//                                                 [--co-tenants "<glob> <glob> …"]
open System
open System.IO
open System.Security.Cryptography
open System.Text
open System.Text.Json

let root =
    let rec find (dir: string) =
        if File.Exists(Path.Combine(dir, "FS.GG.Templates.csproj")) then dir
        else match Directory.GetParent dir |> Option.ofObj with Some p -> find p.FullName | None -> failwith "FS.GG.Templates root not found"
    find __SOURCE_DIRECTORY__
let path (rel: string) = Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar))
let manifestRel = "template/skill-manifest/skill-manifest.json"
let csprojRel = "FS.GG.Templates.csproj"
// The producer skill root inside a generated product. The `.claude` twin is materialized downstream
// by the scaffolding lane (ADR-0065); the producer ships this one, and it is the root the shared
// skill-union assertion reads `skill-manifest.json` from.
let skillRoot = ".agents/skills"

let argv = Environment.GetCommandLineArgs()
let hasFlag f = argv |> Array.contains f
let flagValue f =
    match argv |> Array.tryFindIndex ((=) f) with
    | Some i when i + 1 < argv.Length -> Some argv.[i + 1]
    | _ -> None

if hasFlag "--list" then printfn "skill-manifest\t%s\t" manifestRel; exit 0

/// id, owner source (the ONE authored file), and the templateIds whose packed payload receives it.
let catalog =
    [ "fable-project",  "template/product-skills/fable-project/SKILL.md",  [ "fs-gg-fable-game"; "fs-gg-fable-bindings" ]
      "fable-interop",  "template/product-skills/fable-interop/SKILL.md",  [ "fs-gg-fable-game"; "fs-gg-fable-bindings" ]
      "fable-remoting", "template/product-skills/fable-remoting/SKILL.md", [ "fs-gg-fable-game" ]
      "fable-signalr",  "template/product-skills/fable-signalr/SKILL.md",  [ "fs-gg-fable-game" ]
      "fable-testing",  "template/product-skills/fable-testing/SKILL.md",  [ "fs-gg-fable-game"; "fs-gg-fable-bindings" ]
      "fable-bindings", "template/product-skills/fable-bindings/SKILL.md", [ "fs-gg-fable-bindings" ] ]

let templateIds = catalog |> List.collect (fun (_, _, t) -> t) |> List.distinct |> List.sort
let shortName (templateId: string) = templateId.Substring "fs-gg-".Length
let digest (text: string) = Encoding.UTF8.GetBytes text |> SHA256.HashData |> Array.map (fun b -> b.ToString "x2") |> String.concat ""
let esc (s: string) = s.Replace("\\", "\\\\").Replace("\"", "\\\"")

let failures = ResizeArray<string>()
let bad fmt = Printf.kprintf failures.Add fmt

// ── the canonical manifest ──────────────────────────────────────────────────────────────────────
let rendered =
    let rows =
        catalog |> List.sortBy (fun (id, _, _) -> id) |> List.map (fun (id, source, templates) ->
            let when_ = sprintf "template in [%s]" (templates |> List.map shortName |> String.concat ", ")
            let suppliedBy = source.Substring(0, source.LastIndexOf('/') + 1)
            sprintf "    {\n      \"id\": \"%s\",\n      \"scope\": \"product\",\n      \"sha256\": \"%s\",\n      \"resolvablePath\": \"%s/%s/SKILL.md\",\n      \"materializes-when\": \"%s\",\n      \"supplied-by\": \"%s\"\n    }" id (digest (File.ReadAllText(path source))) skillRoot id (esc when_) (esc suppliedBy))
        |> String.concat ",\n"
    sprintf "{\n  \"schemaVersion\": 1,\n  \"skills\": [\n%s\n  ]\n}\n" rows

let target = path manifestRel

// ── product-side assertion ──────────────────────────────────────────────────────────────────────
// `--co-tenants` carries the same meaning it has in the shared FS-GG/.github skill-union assertion:
// a materialized skill is legitimate when it is manifest-declared OR matches a declared co-tenant
// glob; anything else is DANGLING (ADR-0014 F3). It is needed because a product's skill root is
// shared. `dotnet new` alone yields only this producer's payload, but once `fsgg-sdd` has scaffolded
// or the governance overlay has run, the same root also holds SDD's `fs-gg-sdd-*` process skills and
// the five `always` `.github` driver skills — none of which this producer's manifest declares, and
// none of which it should. Without the glob list a delivery assertion would either red on another
// producer's correct output or drop the dangling class entirely; with it, an id belonging to NOBODY
// still reds.
//
// The globs are passed at each call site rather than defaulted here, because which co-tenants are
// expected is a fact about the LANE (which scaffolder ran), not about this catalog.
let globMatches (pattern: string) (name: string) =
    let rx =
        "^" + (pattern.Split '*' |> Array.map System.Text.RegularExpressions.Regex.Escape |> String.concat ".*") + "$"
    System.Text.RegularExpressions.Regex.IsMatch(name, rx)

let assertProduct (productDir: string) (templateId: string) (coTenants: string list) =
    if not (templateIds |> List.contains templateId) then
        bad "--template '%s' is not a template this catalog supplies (expected one of: %s)" templateId (String.concat ", " templateIds)
    let skillsDir = Path.Combine(productDir, skillRoot.Replace('/', Path.DirectorySeparatorChar))
    let productManifest = Path.Combine(skillsDir, "skill-manifest.json")
    if not (Directory.Exists skillsDir) then
        bad "the generated product has no %s/ at all (looked in %s) — not one declared product skill reached it" skillRoot skillsDir
    elif not (File.Exists productManifest) then
        bad "the generated product ships no %s/skill-manifest.json — the producer manifest is absent from the packed payload, so whatever skills it does carry are undeclared" skillRoot
    else
        let productText = File.ReadAllText productManifest
        if productText <> rendered then
            bad "the product's %s/skill-manifest.json is NOT the canonical producer manifest (%s) — the packed manifest and the owner catalog have diverged, so its digests describe some other catalog" skillRoot manifestRel
        // Grade against the manifest the PRODUCT carries, not this repository's copy.
        let declared =
            use doc = JsonDocument.Parse productText
            [ for s in doc.RootElement.GetProperty("skills").EnumerateArray() ->
                s.GetProperty("id").GetString(),
                s.GetProperty("sha256").GetString(),
                s.GetProperty("materializes-when").GetString() ]
        if List.isEmpty declared then bad "the product's shipped manifest declares no skills at all"
        // "template in [fable-game, fable-bindings]"
        let selects (materializesWhen: string) =
            let inside = materializesWhen.Substring(materializesWhen.IndexOf '[' + 1).TrimEnd(']')
            inside.Split ',' |> Array.map (fun s -> s.Trim()) |> Array.contains (shortName templateId)
        let mutable present = 0
        for (id, sha, when_) in declared do
            let file = Path.Combine(skillsDir, id, "SKILL.md")
            match selects when_, File.Exists file with
            | true, false ->
                bad "ABSENT: '%s' is declared to materialize here (%s) but %s/%s/SKILL.md is not in the generated product" id when_ skillRoot id
            | false, true ->
                bad "UNEXPECTED: '%s' materialized in %s, but its declaration (%s) does not select this template" id (shortName templateId) when_
            | false, false -> ()
            | true, true ->
                present <- present + 1
                let actual = digest (File.ReadAllText file)
                if actual <> sha then
                    bad "DRIFTED: '%s' materialized with sha256 %s, but its manifest row declares %s — the shipped bytes are not the bytes the producer digested" id actual sha
        // Anything in the product's skill root that no manifest row declares and no declared
        // co-tenant glob claims reached a product with no owner, no digest, and no rule.
        let declaredIds = declared |> List.map (fun (id, _, _) -> id) |> Set.ofList
        let mutable coTenantCount = 0
        for dir in Directory.GetDirectories skillsDir do
            let name = Path.GetFileName dir
            if not (declaredIds.Contains name) then
                if coTenants |> List.exists (fun g -> globMatches g name) then coTenantCount <- coTenantCount + 1
                else
                    bad "DANGLING: %s/%s/ is materialized in the generated product, but no manifest row declares it and no declared co-tenant (%s) claims it"
                        skillRoot name (if List.isEmpty coTenants then "none passed" else String.concat " " coTenants)
        if failures.Count = 0 then
            let coTenantNote =
                if List.isEmpty coTenants then ""
                else sprintf ", %d co-tenant skill(s) accepted as '%s'" coTenantCount (String.concat " " coTenants)
            printfn "skill-manifest: %s product OK — %d of %d declared skills materialized, every digest matches the shipped manifest, none dangling%s"
                (shortName templateId) present (List.length declared) coTenantNote

// ── csproj coherence ────────────────────────────────────────────────────────────────────────────
// The catalog reaches a product ONLY because FS.GG.Templates.csproj projects it into each template's
// packed payload. Adding a row here and forgetting the package item there reproduces exactly the
// unreachable-catalog defect #347 repairs, so this reads the csproj rather than trusting it.
let checkCsproj () =
    let text = File.ReadAllText(path csprojRel)
    for (id, source, templates) in catalog do
        if not (text.Contains source) then
            bad "FS.GG.Templates.csproj declares no package item for '%s' (%s) — it is authored but packed into nothing, so no generated product can receive it" id source
        for templateId in templateIds do
            let entry = sprintf "content/templates/%s/%s/%s/" templateId skillRoot id
            match templates |> List.contains templateId, text.Contains entry with
            | true, false ->
                bad "FS.GG.Templates.csproj does not pack '%s' into %s (expected the PackagePath entry '%s'), but the catalog says it materializes there" id templateId entry
            | false, true ->
                bad "FS.GG.Templates.csproj packs '%s' into %s, but the catalog does not select that template — the product would carry an undeclared skill" id templateId
            | _ -> ()
    if not (text.Contains manifestRel) then
        bad "FS.GG.Templates.csproj declares no package item for %s — products would ship skills with no producer manifest to grade them against" manifestRel
    for templateId in templateIds do
        let entry = sprintf "content/templates/%s/%s/" templateId skillRoot
        if not (text.Contains entry) then
            bad "FS.GG.Templates.csproj does not pack %s into %s's %s/ — that product would ship skills with no producer manifest" manifestRel templateId skillRoot

// ── entry points ────────────────────────────────────────────────────────────────────────────────
match flagValue "--assert-product" with
| Some productDir ->
    let coTenants =
        flagValue "--co-tenants"
        |> Option.map (fun v -> v.Split([| ' '; '\t'; ',' |], StringSplitOptions.RemoveEmptyEntries) |> List.ofArray)
        |> Option.defaultValue []
    match flagValue "--template" with
    | Some templateId -> assertProduct productDir templateId coTenants
    | None -> eprintfn "skill-manifest: --assert-product requires --template <templateId>"; exit 2
| None ->
    if hasFlag "--check" then
        if not (File.Exists target) then
            bad "%s does not exist — run `dotnet fsi scripts/generate-skill-manifest.fsx`" manifestRel
        elif File.ReadAllText target <> rendered then
            bad "%s is STALE against the catalog — run `dotnet fsi scripts/generate-skill-manifest.fsx`" manifestRel
        checkCsproj ()
        if failures.Count = 0 then
            printfn "skill-manifest: up to date (%d skills, packed into %s)" (List.length catalog) (String.concat " + " templateIds)
    else
        Directory.CreateDirectory(Path.GetDirectoryName target) |> ignore
        File.WriteAllText(target, rendered)
        printfn "skill-manifest: wrote %s (%d skills)" target (List.length catalog)

if failures.Count > 0 then
    eprintfn "skill-manifest: FAILED"
    for f in failures do eprintfn "  - %s" f
    exit 1
