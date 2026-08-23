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
// WHO OWNS A PRODUCT'S .agents/skills/skill-manifest.json — DECIDED AT FS.GG.Templates#385.
// THE PRODUCT DOES. It is a SHARED, MULTI-PRODUCER, UPPER-BOUND CATALOG, and this producer owns
// the ROWS it supplies, never the FILE. That is a decision, so here is what decided it:
//   1. The org already grades this exact file that way. The shared skill-union assertion
//      (FS-GG/.github, ADR-0014 F3, reached from tests/composition/lib/skill-union.sh) reads
//      `.agents/skills/skill-manifest.json` with "superset-catalog set semantics": declared-but-
//      absent ids are legitimate, and every materialized skill must be manifest-declared OR a
//      co-tenant. Two assertions grading one file under contradictory ownership rules is not a
//      contract; one of them had to move, and it was not the org-wide one.
//   2. The row schema already names the supplier: `"scope"`. This producer writes `"product"`;
//      `fsgg-sdd scaffold` appends `"scope": "driver"` rows for the five `always` `.github` driver
//      skills, which have their own producer manifest (.github registry/driver-skill-manifest.json).
//      A single-owner file would have no use for that field.
//   3. This file's OWN co-tenant note (below) already concedes that the skill ROOT is shared.
//      Demanding byte-equality of a manifest that lives IN that shared root demanded sole
//      ownership of a file in a directory this script itself documents as jointly occupied.
// So the divergence check below is a SUBSET-AND-OWNERSHIP check, not a byte comparison: every row
// this catalog renders must appear in the product's manifest carrying EXACTLY the fields this
// catalog declares, with the same values — no field missing, none added. Every row must also carry
// a `scope`, because that is the field the ownership half is decided on. A product-scoped row
// outside this catalog is foreign only when `supplied-by` is a valid path outside this producer's
// `template/product-skills` namespace. Public SDD 1.2.5 preserves that producer attribution when
// it adds Rendering-owned rows such as `fs-gg-feedback-report`. This keeps the whole of what
// byte-equality was protecting — "its digests describe THIS catalog" — while permitting rows that
// explicitly name another supplier. An unattributed/malformed row, or an unknown row claiming this
// producer's namespace, is still refused rather than guessed foreign. The rejected alternative was
// to make `fsgg-sdd` stop rewriting the file; that
// is cross-repo work in FS.GG.SDD, and it would have to fight requirement 1 as well.
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
// `schemaVersion` is a constant of the FORMAT, not of this catalog: the product's copy is read back
// under exactly these semantics, so a product shipping some other version is refused rather than
// parsed hopefully (see assertProduct).
let schemaVersion = 1
let manifestOf (rows: string list) =
    sprintf "{\n  \"schemaVersion\": %d,\n  \"skills\": [\n%s\n  ]\n}\n" schemaVersion (String.concat ",\n" rows)

/// The rows THIS producer supplies, rendered individually so the divergence check and the
/// self-demonstration can both address them without re-parsing the whole document.
let renderedRows =
    catalog |> List.sortBy (fun (id, _, _) -> id) |> List.map (fun (id, source, templates) ->
        let when_ = sprintf "template in [%s]" (templates |> List.map shortName |> String.concat ", ")
        let suppliedBy = source.Substring(0, source.LastIndexOf('/') + 1)
        sprintf "    {\n      \"id\": \"%s\",\n      \"scope\": \"product\",\n      \"sha256\": \"%s\",\n      \"resolvablePath\": \"%s/%s/SKILL.md\",\n      \"materializes-when\": \"%s\",\n      \"supplied-by\": \"%s\"\n    }" id (digest (File.ReadAllText(path source))) skillRoot id (esc when_) (esc suppliedBy))

let rendered = manifestOf renderedRows

/// A manifest's rows as (id, field map), in file order. Every row is a flat object of scalar
/// fields; a non-string scalar is compared by its raw text so no field is silently ignored.
let parseRows (text: string) =
    use doc = JsonDocument.Parse text
    [ for s in doc.RootElement.GetProperty("skills").EnumerateArray() ->
        let fields =
            [ for p in s.EnumerateObject() ->
                p.Name, (if p.Value.ValueKind = JsonValueKind.String then p.Value.GetString() else p.Value.GetRawText()) ]
            |> Map.ofList
        (fields.TryFind "id" |> Option.defaultValue "<a row with no id>"), fields ]

let schemaVersionOf (text: string) =
    use doc = JsonDocument.Parse text
    match doc.RootElement.TryGetProperty "schemaVersion" with
    | true, v -> v.GetRawText()
    | _ -> "<absent>"

type SupplierOwnership = TemplatesOwned | Foreign | Invalid

let templatesSupplierRoot = "template/product-skills"

/// Supplier attribution is a relative producer path, not merely a non-empty scalar. In particular,
/// an unknown row at or under this producer's `template/product-skills` namespace remains this producer's
/// claim and must red; only a valid path outside that namespace establishes foreign ownership.
let classifySupplier (supplier: string) =
    if String.IsNullOrWhiteSpace supplier
       || supplier <> supplier.Trim()
       || supplier.Contains '\\'
       || supplier.Contains ':'
       || supplier.Contains "//"
       || Path.IsPathRooted supplier then Invalid
    else
        let normalized = supplier.TrimEnd '/'
        let segments = normalized.Split('/', StringSplitOptions.None)
        if segments |> Array.exists (fun segment -> String.IsNullOrWhiteSpace segment || segment <> segment.Trim() || segment = "." || segment = "..") then Invalid
        elif supplier = templatesSupplierRoot
             || supplier.StartsWith(templatesSupplierRoot + "/", StringComparison.Ordinal) then TemplatesOwned
        else Foreign

/// Keep this read separate from `parseRows`: that comparison intentionally preserves raw scalar
/// text, while ownership must not mistake JSON null/number/bool for supplier attribution.
let supplierOwnershipById (text: string) =
    use doc = JsonDocument.Parse text
    [ for row in doc.RootElement.GetProperty("skills").EnumerateArray() do
        match row.TryGetProperty "id", row.TryGetProperty "supplied-by" with
        | (true, id), (true, supplier)
            when id.ValueKind = JsonValueKind.String
                 && supplier.ValueKind = JsonValueKind.String ->
            yield id.GetString(), classifySupplier (supplier.GetString())
        | (true, id), _ when id.ValueKind = JsonValueKind.String ->
            yield id.GetString(), Invalid
        | _ -> () ]
    |> Map.ofList

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
        // ── DIVERGENCE: THIS CATALOG'S ROWS, NOT THIS CATALOG'S FILE (FS.GG.Templates#385) ───────
        // This was `productText <> rendered`. Byte-equality was unsatisfiable by construction on the
        // provider route — `fsgg-sdd scaffold` APPENDS its driver rows to the product's copy — so the
        // fable-game lane could never go green no matter what this producer packed. See the ownership
        // decision at the top of this file. What byte-equality was actually protecting is preserved
        // in full below, as two checks with names:
        //   (a) SUBSET — every row this catalog renders appears in the product's manifest, field for
        //       field. A dropped, truncated or edited producer row still reds, which is the whole of
        //       "its digests describe THIS catalog".
        //   (b) OWNERSHIP — an OTHER `scope: "product"` row is foreign only when it explicitly
        //       names its supplier. An unattributed product row still reds instead of being waved
        //       through as somebody else's business.
        // Rows at any other scope are another producer's declarations. They are legitimate, they are
        // still graded for DELIVERY below like any other declared row, and they are not required to
        // match anything here.
        if schemaVersionOf productText <> string schemaVersion then
            bad "the product's %s/skill-manifest.json declares schemaVersion %s, but this assertion reads a manifest under schemaVersion %d semantics — it reds rather than grading a document whose format it may be misreading" skillRoot (schemaVersionOf productText) schemaVersion
        let canonicalById = parseRows rendered |> Map.ofList
        let productRows = parseRows productText
        let productById = productRows |> Map.ofList
        let supplierOwnership = supplierOwnershipById productText
        for (id, n) in productRows |> List.countBy fst |> List.filter (fun (_, n) -> n > 1) do
            bad "the product's %s/skill-manifest.json declares '%s' %d times — a duplicated id makes every verdict below depend on row order, so this reds rather than grading one of them arbitrarily" skillRoot id n
        for KeyValue (id, canonFields) in canonicalById do
            match productById.TryFind id with
            | None ->
                bad "the product's %s/skill-manifest.json does not declare '%s', which %s does — the packed manifest and the owner catalog have diverged, so this product's skills are graded against some other catalog" skillRoot id manifestRel
            | Some prodFields ->
                for KeyValue (field, canonValue) in canonFields do
                    match prodFields.TryFind field with
                    | Some v when v = canonValue -> ()
                    | Some v ->
                        bad "the product's manifest row for '%s' carries %s '%s' where %s declares '%s' — the packed manifest and the owner catalog have diverged" id field v manifestRel canonValue
                    | None ->
                        bad "the product's manifest row for '%s' is missing the field '%s' that %s declares — the packed manifest and the owner catalog have diverged" id field manifestRel
                // FIELD FOR FIELD MEANS EXACTLY THESE FIELDS, IN BOTH DIRECTIONS. Iterating only the
                // canonical fields would make the rule "AT LEAST these", which is not what this file's
                // header and the README claim, and not what byte-equality guaranteed. A field this
                // assertion does not read is a field that can change what the row MEANS — a future
                // `"disabled": true` or an override key would sail through a subset check while the
                // digests still matched. That is the same shape this whole repair exists to remove:
                // a form the predicate cannot read, graded as though it were fine.
                for KeyValue (field, prodValue) in prodFields do
                    if not (canonFields.ContainsKey field) then
                        bad "the product's manifest row for '%s' carries an extra field '%s' ('%s') that %s does not declare — this catalog's own rows are graded field for field, and a field this assertion cannot read could change what the row means" id field prodValue manifestRel
        for (id, fields) in productRows do
            if fields.TryFind "scope" = Some "product"
               && not (canonicalById.ContainsKey id) then
                match supplierOwnership.TryFind id with
                | Some Foreign -> ()
                | Some TemplatesOwned ->
                    bad "the product's %s/skill-manifest.json declares product-scoped skill '%s', but %s declares no such skill and its 'supplied-by' claims this producer's '%s' namespace — an unknown row in this producer's namespace is refused, not laundered as foreign" skillRoot id manifestRel templatesSupplierRoot
                | Some Invalid
                | None ->
                    bad "the product's %s/skill-manifest.json declares product-scoped skill '%s', but %s declares no such skill and the row carries no valid foreign 'supplied-by' path — an unattributed or malformed product row cannot be classified as another producer's output" skillRoot id manifestRel
        // Grade against the manifest the PRODUCT carries, not this repository's copy. A row missing
        // a field this grading needs is refused outright: skipping it would let an unreadable row
        // pass as a delivered one.
        //
        // `scope` IS REQUIRED, AND IT IS THE FIELD THE OWNERSHIP RULE ABOVE IS BUILT ON. The check at
        // `fields.TryFind "scope" = Some "product"` asks whether a row is THIS producer's claim, and an
        // ABSENT scope answers "no" just as confidently as an explicit foreign one — so a row with no
        // scope at all would be waved through as somebody else's business, which is precisely the
        // never-read-form-graded-as-a-negative defect this file was repaired to stop, one field over.
        // An explicit NON-product scope is a different thing entirely and stays legitimate: that is
        // ADR-0014 F3's "manifest-declared OR co-tenant" rule working as intended, not a hole.
        let declared =
            productRows |> List.choose (fun (id, fields) ->
                let missing = [ "scope"; "sha256"; "materializes-when" ] |> List.filter (fields.ContainsKey >> not)
                if not (List.isEmpty missing) then
                    bad "the product's manifest row for '%s' is missing %s, so this assertion cannot grade it — 'scope' decides whose row it is, 'sha256' whether the shipped bytes are the declared ones, and 'materializes-when' whether it belongs in this template. An absent field is REFUSED, never read as a confident negative" id (String.concat " and " missing)
                    None
                else Some(id, fields.["sha256"], fields.["materializes-when"]))
        if List.isEmpty declared then bad "the product's shipped manifest declares no skills at all"
        // ── `materializes-when` IS A GRAMMAR, AND AN UNREADABLE FORM MUST RED ────────────────────
        // Two forms are legitimate in a product's shared manifest:
        //   "always"                                   — its supplier materializes it in every product
        //   "template in [fable-game, fable-bindings]" — selected per template id
        // `always` needs an ARM, not a fallthrough. The old parse took the substring after '[', so on
        // the literal "always" `IndexOf '['` returned -1, `Substring 0` handed back "always" itself,
        // and the row graded as "does not select this template" — turning five correctly delivered
        // driver skills into UNEXPECTED (FS.GG.Templates#385). The failure mode to notice is that a
        // form this predicate could not read was reported as a confident NEGATIVE. So an unreadable
        // form now reds on its own; it is never silently graded as "not selected".
        let selects (materializesWhen: string) =
            let w = materializesWhen.Trim()
            if w = "always" then Ok true
            else
                let i = w.IndexOf '['
                if i >= 0 && w.EndsWith "]" then
                    w.Substring(i + 1, w.Length - i - 2).Split ','
                    |> Array.map (fun s -> s.Trim())
                    |> Array.filter (fun s -> s <> "")
                    |> Array.contains (shortName templateId)
                    |> Ok
                else Error w
        let mutable present = 0
        let mutable coTenantRows = 0
        for (id, sha, when_) in declared do
            let file = Path.Combine(skillsDir, id, "SKILL.md")
            let ownedHere = canonicalById.ContainsKey id
            match selects when_ with
            | Error w ->
                bad "UNREADABLE: '%s' declares materializes-when '%s', which is neither 'always' nor 'template in [...]' — this assertion cannot decide whether it belongs in %s, so it reds rather than grading the row as 'not selected'" id w (shortName templateId)
            | Ok sel ->
                if not ownedHere then coTenantRows <- coTenantRows + 1
                match sel, File.Exists file with
                | true, false ->
                    bad "ABSENT: '%s' is declared to materialize here (%s) but %s/%s/SKILL.md is not in the generated product" id when_ skillRoot id
                | false, true ->
                    bad "UNEXPECTED: '%s' materialized in %s, but its declaration (%s) does not select this template" id (shortName templateId) when_
                | false, false -> ()
                | true, true ->
                    if ownedHere then present <- present + 1
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
            // The denominator is THIS producer's row count, not the shared manifest's total: a count
            // taken over a population it was not about is the shape .github#1506 retired.
            let coTenantNote =
                if List.isEmpty coTenants then ""
                else sprintf ", %d co-tenant directory(ies) accepted as '%s'" coTenantCount (String.concat " " coTenants)
            let coTenantRowNote =
                if coTenantRows = 0 then ""
                else sprintf ", %d co-tenant manifest row(s) from another producer graded and delivered" coTenantRows
            printfn "skill-manifest: %s product OK — %d of %d producer-declared skills materialized, every digest matches the shipped manifest, none dangling%s%s"
                (shortName templateId) present canonicalById.Count coTenantRowNote coTenantNote

// ── THE ASSERTION'S OWN DEMONSTRATION THAT IT CAN STILL RED (FS.GG.Templates#385) ───────────────
// #385 RELAXED a check — byte-equality became subset-and-ownership — and a relaxed check is exactly
// the kind that quietly becomes a no-op. A gate that never fires and a gate that always passes are
// indistinguishable from outside (the reasoning tests/composition/lib/skill-union.sh records at
// .github#1611 category D), and this producer has already shipped one catalog that no product could
// receive while every source-side check stayed green (#347). So the negative lanes are DEMONSTRATED
// rather than asserted in a comment.
//
// It runs from `--check`, which tests/composition/run.sh:270 already calls on the required
// `composition` job, so it executes on every CI run with no lane wiring of its own. It is entirely
// offline and deterministic — temp directories, no network, no packed archive, no `dotnet new` — so
// it can neither flake nor cost the job's timeout budget.
let demonstrateAssertion () =
    let demoTemplate = "fs-gg-fable-game"
    let sandbox = Path.Combine(Path.GetTempPath(), "fs-gg-skill-manifest-demo-" + Guid.NewGuid().ToString "n")
    let bodies = catalog |> List.map (fun (id, source, _) -> id, File.ReadAllText(path source)) |> Map.ofList
    let selected = catalog |> List.filter (fun (_, _, t) -> List.contains demoTemplate t) |> List.map (fun (id, _, _) -> id)
    let materialized = selected |> List.map (fun id -> id, bodies.[id])
    let notSelected = catalog |> List.map (fun (id, _, _) -> id) |> List.except selected
    let driverBody (id: string) = sprintf "# %s\n\nSeeded into the shared skill root by another producer.\n" id
    let foreignRow (scope: string) (id: string) (when_: string) =
        sprintf "    {\n      \"id\": \"%s\",\n      \"scope\": \"%s\",\n      \"sha256\": \"%s\",\n      \"resolvablePath\": \"%s/%s/SKILL.md\",\n      \"materializes-when\": \"%s\"\n    }"
            id scope (digest (driverBody id)) skillRoot id when_
    let suppliedForeignRow (scope: string) (id: string) (when_: string) (supplier: string) =
        foreignRow scope id when_
        |> fun row -> row.Replace("\n    }", sprintf ",\n      \"supplied-by\": \"%s\"\n    }" (esc supplier))
    // Run the real assertion against a synthetic product, capture what it reported, and restore the
    // live failure list. `assertProduct` speaks through `failures` and `printfn`, so both are
    // intercepted — this drives the ASSERTION, not a copy of its predicates.
    let capture (dir: string) (tenants: string list) =
        let saved = failures |> Seq.toList
        failures.Clear()
        let out = Console.Out
        use sink = new StringWriter()
        Console.SetOut sink
        try assertProduct dir demoTemplate tenants
        finally Console.SetOut out
        let got = failures |> Seq.toList
        failures.Clear()
        failures.AddRange saved
        got
    let mutable cases = 0
    // expect = None means the case must PASS; Some marker means it must RED with that marker.
    let case (name: string) (expect: string option) (manifestText: string option) (skills: (string * string) list) (tenants: string list) =
        cases <- cases + 1
        let dir = Path.Combine(sandbox, sprintf "case-%02d" cases)
        let skillsDir = Path.Combine(dir, skillRoot.Replace('/', Path.DirectorySeparatorChar))
        Directory.CreateDirectory skillsDir |> ignore
        manifestText |> Option.iter (fun t -> File.WriteAllText(Path.Combine(skillsDir, "skill-manifest.json"), t))
        for (id, body) in skills do
            Directory.CreateDirectory(Path.Combine(skillsDir, id)) |> ignore
            File.WriteAllText(Path.Combine(skillsDir, id, "SKILL.md"), body)
        let got = capture dir tenants
        let reported = if List.isEmpty got then "NOTHING AT ALL — this lane can no longer fire" else String.concat " | " got
        match expect with
        | None ->
            if not (List.isEmpty got) then
                bad "the product-skill assertion's self-demonstration BROKE: the '%s' case must PASS, but the assertion red with: %s" name reported
        | Some marker ->
            if not (got |> List.exists (fun f -> f.Contains marker)) then
                bad "the product-skill assertion's self-demonstration BROKE: the '%s' case must RED with '%s', but the assertion reported: %s. Do NOT delete this demonstration — a negative lane that stopped firing is the defect it exists to catch (FS.GG.Templates#385)" name marker reported
    let sddCoTenants = [ "fs-gg-sdd-*"; "padd-item"; "work-board" ]
    let driverRows = [ foreignRow "driver" "padd-item" "always"; foreignRow "driver" "work-board" "always" ]
    let driverSkills = [ "padd-item", driverBody "padd-item"; "work-board", driverBody "work-board" ]
    let renderingRow = suppliedForeignRow "product" "fs-gg-feedback-report" "always" "template/feedback-report/skill/"
    let renderingSkill = "fs-gg-feedback-report", driverBody "fs-gg-feedback-report"
    try
        // ── the two lanes that must PASS ────────────────────────────────────────────────────────
        // (1) the direct `dotnet new` route: the product's manifest IS this catalog's, untouched.
        case "direct route — the product ships this catalog's manifest verbatim"
            None (Some rendered) materialized []
        // (2) the public SDD 1.2.4 provider route, which is #385 itself: `fsgg-sdd scaffold` has
        //     appended its `always` driver rows and a supplier-attributed Rendering product row to
        //     the product's copy, then seeded those plus its undeclared process skills into the root.
        case "provider route — shared manifest carrying driver rows and an attributed foreign product row"
            None (Some(manifestOf (renderedRows @ driverRows @ [ renderingRow ])))
            (materialized @ driverSkills @ [ renderingSkill; ("fs-gg-sdd-plan", "# fs-gg-sdd-plan\n") ]) sddCoTenants
        // ── every lane this assertion was built to catch, still firing ──────────────────────────
        case "a selected skill did not materialize"
            (Some "ABSENT:") (Some rendered) (materialized |> List.filter (fun (id, _) -> id <> List.head selected)) []
        case "a materialized skill's bytes drifted from its declared digest"
            (Some "DRIFTED:") (Some rendered)
            (materialized |> List.map (fun (id, b) -> id, (if id = List.head selected then b + "\ndrifted\n" else b))) []
        case "a skill directory nobody declares and no co-tenant claims"
            (Some "DANGLING:") (Some rendered) (materialized @ [ ("nobodys-skill", "# nobodys-skill\n") ]) []
        case "a skill declared only for another template materialized here"
            (Some "UNEXPECTED:") (Some rendered)
            (materialized @ (notSelected |> List.map (fun id -> id, bodies.[id]))) []
        // ── the byte-equality replacement: both halves of what it protected ─────────────────────
        case "a producer row whose digest is not this catalog's"
            (Some "diverged") (Some(manifestOf (renderedRows |> List.map (fun r -> r.Replace(digest bodies.[List.head selected], String.replicate 64 "a")))))
            materialized []
        case "a producer row this catalog renders is missing from the product's manifest"
            (Some "diverged") (Some(manifestOf (renderedRows |> List.skip 1))) materialized []
        case "an unattributed product-scoped row this catalog does not own"
            (Some "carries no valid foreign 'supplied-by' path") (Some(manifestOf (renderedRows @ [ foreignRow "product" "forged-skill" "always" ])))
            (materialized @ [ ("forged-skill", driverBody "forged-skill") ]) []
        case "an unknown product row claiming this producer's supplier namespace"
            (Some "claims this producer's 'template/product-skills' namespace")
            (Some(manifestOf (renderedRows @ [ suppliedForeignRow "product" "forged-skill" "always" "template/product-skills/forged-skill/" ])))
            (materialized @ [ ("forged-skill", driverBody "forged-skill") ]) []
        case "an unknown product row claiming this producer's exact supplier root"
            (Some "claims this producer's 'template/product-skills' namespace")
            (Some(manifestOf (renderedRows @ [ suppliedForeignRow "product" "forged-root-skill" "always" "template/product-skills" ])))
            (materialized @ [ ("forged-root-skill", driverBody "forged-root-skill") ]) []
        // A row that omits `scope` ALTOGETHER. `scope` is the field the ownership half is decided on,
        // so an absent one used to fall through to "somebody else's row" and pass — the same
        // unreadable-form-graded-as-a-negative shape as the `always` defect, one field over (repair 1).
        case "a row that declares no scope at all"
            (Some "is missing scope")
            (Some(manifestOf (renderedRows @ [ sprintf "    {\n      \"id\": \"scopeless\",\n      \"sha256\": \"%s\",\n      \"resolvablePath\": \"%s/scopeless/SKILL.md\",\n      \"materializes-when\": \"always\"\n    }" (digest (driverBody "scopeless")) skillRoot ])))
            (materialized @ [ ("scopeless", driverBody "scopeless") ]) []
        // An EXTRA field on a row this catalog owns. "Field for field" has to mean both directions,
        // or the documented claim and the executed check disagree (repair 1).
        case "an extra field on a row this catalog owns"
            (Some "extra field")
            (Some(manifestOf (renderedRows |> List.mapi (fun i r ->
                if i = 0 then r.Replace("\n      \"scope\": \"product\",", "\n      \"scope\": \"product\",\n      \"disabled\": true,") else r))))
            materialized []
        // ── AND THE BOUNDARY THE TIGHTENING MUST NOT CROSS ──────────────────────────────────────
        // An explicitly non-product row with NO co-tenant glob is LEGITIMATE — ADR-0014 F3's
        // "manifest-declared OR co-tenant" rule. This case exists to red if a future tightening of
        // the ownership half turns that into a failure.
        case "an explicitly foreign-scoped row with no co-tenant glob passed"
            None (Some(manifestOf (renderedRows @ [ foreignRow "driver" "padd-item" "always" ])))
            (materialized @ [ ("padd-item", driverBody "padd-item") ]) []
        // ── the fail-closed arms ────────────────────────────────────────────────────────────────
        case "a materializes-when form this predicate cannot read"
            (Some "UNREADABLE:") (Some(manifestOf (renderedRows @ [ foreignRow "driver" "mystery-skill" "sometimes" ])))
            (materialized @ [ ("mystery-skill", driverBody "mystery-skill") ]) []
        case "a row missing a field the grading needs"
            (Some "is missing sha256")
            (Some(manifestOf (renderedRows @ [ sprintf "    {\n      \"id\": \"halfrow\",\n      \"scope\": \"driver\",\n      \"materializes-when\": \"always\"\n    }" ])))
            materialized []
        case "a manifest at a schemaVersion these semantics were not written for"
            (Some "schemaVersion") (Some(rendered.Replace("\"schemaVersion\": 1", "\"schemaVersion\": 2"))) materialized []
        case "the product ships no producer manifest at all"
            (Some "ships no") None materialized []
        cases
    finally
        try Directory.Delete(sandbox, true) with _ -> ()

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
        let demoCases = demonstrateAssertion ()
        if failures.Count = 0 then
            // This line stays FIRST on stdout: tests/composition/run.sh reads `sed -n '1p'` of this
            // log into the lane's own ok message.
            printfn "skill-manifest: up to date (%d skills, packed into %s)" (List.length catalog) (String.concat " + " templateIds)
            printfn "skill-manifest: the product-side assertion can FIRE — %d cases driven offline, including both delivery routes passing, a legitimate foreign-scoped row still passing, and every red lane (absent, drifted, dangling, wrong-template, catalog divergence, forged ownership, absent scope, extra field, unreadable declaration, schemaVersion) reproducing" demoCases
    else
        Directory.CreateDirectory(Path.GetDirectoryName target) |> ignore
        File.WriteAllText(target, rendered)
        printfn "skill-manifest: wrote %s (%d skills)" target (List.length catalog)

if failures.Count > 0 then
    eprintfn "skill-manifest: FAILED"
    for f in failures do eprintfn "  - %s" f
    exit 1
