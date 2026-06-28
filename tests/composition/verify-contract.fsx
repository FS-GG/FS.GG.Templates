// Contract verification: bind providers/rendering.providers.yml to the canonical
// FS.GG.Contracts 1.0.0 typed surface and validate it against the package itself.
//
// This is how FS.GG.Templates *consumes* FS.GG.Contracts (Tmpl#13 / FS-GG/.github#16,
// H2): rather than re-asserting field names by hand, it loads the provider registry into
// `Fsgg.Provider.ProviderDescriptor` / `Fsgg.Schemas.ProvidersSchema` and checks the
// invariants with the package's own functions and version constants — so the descriptor
// can only pass if it actually conforms to the published contract. If SDD bumps the
// providers schema version or the name-parameter default, this turns red here, not in a
// downstream scaffold.
//
// The registry encoding it parses is specified in FS.GG.SDD
// specs/038-retype-provider-contracts/contracts/provider-registry-encoding.md.
//
// Usage:  dotnet fsi verify-contract.fsx <path-to-providers.yml>
// Exit:   0 = all invariants hold, 1 = a contract assertion failed.
// FS.GG.Contracts resolves from the registered local NuGet feed (or the global cache);
// run.sh gates this stage on the package being restorable so CI stays honest, not green.

#r "nuget: FS.GG.Contracts, 1.0.0"

open System
open System.IO
open Fsgg

// ── A tiny indentation-driven YAML reader (block maps/seqs, inline [..] flow seqs,
//    quoted scalars, # comments) — just enough for the provider registry shape. ──
type Yaml =
    | Scalar of string
    | Map of (string * Yaml) list
    | Seq of Yaml list

let private stripComment (s: string) =
    // Drop a trailing " # comment"; values in this registry never contain '#'.
    match s.IndexOf(" #") with
    | -1 -> s
    | i -> s.Substring(0, i)

let private unquote (s: string) =
    let t = s.Trim()
    if t.Length >= 2 && ((t.[0] = '"' && t.[t.Length - 1] = '"') || (t.[0] = '\'' && t.[t.Length - 1] = '\'')) then
        t.Substring(1, t.Length - 2)
    else t

let private indentOf (s: string) = s.Length - s.TrimStart(' ').Length

// Inline flow sequence: [a, b, c] -> Seq [Scalar a; Scalar b; Scalar c]
let private parseFlowSeq (s: string) =
    let inner = s.Trim().TrimStart('[').TrimEnd(']')
    if inner.Trim() = "" then Seq []
    else inner.Split(',') |> Array.map (fun x -> Scalar(unquote x)) |> Array.toList |> Seq

// Recursive block parser over a windowed line list. Returns (node, linesConsumed).
let rec private parseBlock (lines: (int * string)[]) (start: int) (minIndent: int) : Yaml * int =
    if start >= lines.Length then Map [], 0
    else
        let _, first = lines.[start]
        let ind = indentOf first
        if ind < minIndent then Map [], 0
        elif first.TrimStart().StartsWith("- ") || first.TrimStart() = "-" then
            // Block sequence at this indent.
            let items = ResizeArray<Yaml>()
            let mutable i = start
            let mutable go = true
            while go && i < lines.Length do
                let _, line = lines.[i]
                let li = indentOf line
                let trimmed = line.TrimStart()
                if li = ind && (trimmed.StartsWith("- ") || trimmed = "-") then
                    // Re-emit the item's content as a map/scalar one indent deeper.
                    let content = trimmed.Substring(1).TrimStart()
                    let childIndent = li + 2
                    // Splice the "- " item: treat its first key inline, then deeper lines.
                    let rebuilt =
                        Array.append
                            [| (i, String(' ', childIndent) + content) |]
                            (lines.[(i + 1)..] |> Array.takeWhile (fun (_, l) -> indentOf l > ind || l.Trim() = "")
                                               |> Array.filter (fun (_, l) -> l.Trim() <> ""))
                    let node, _ = parseBlock rebuilt 0 childIndent
                    items.Add node
                    // Advance past this item's lines.
                    i <- i + 1
                    while i < lines.Length && (indentOf (snd lines.[i]) > ind || (snd lines.[i]).Trim() = "") do
                        i <- i + 1
                else go <- false
            Seq(List.ofSeq items), (i - start)
        else
            // Block mapping at this indent.
            let pairs = ResizeArray<string * Yaml>()
            let mutable i = start
            let mutable go = true
            while go && i < lines.Length do
                let _, line = lines.[i]
                let li = indentOf line
                if line.Trim() = "" then i <- i + 1
                elif li < ind then go <- false
                elif li > ind then i <- i + 1 // defensive: consumed by recursion already
                else
                    let trimmed = line.Trim()
                    let colon = trimmed.IndexOf(':')
                    if colon < 0 then go <- false
                    else
                        let key = trimmed.Substring(0, colon).Trim()
                        let valRaw = trimmed.Substring(colon + 1).Trim()
                        if valRaw = "" then
                            // Nested block follows (deeper indent).
                            let child, _ = parseBlock lines (i + 1) (ind + 1)
                            pairs.Add(key, child)
                            i <- i + 1
                            while i < lines.Length && (indentOf (snd lines.[i]) > ind || (snd lines.[i]).Trim() = "") do
                                i <- i + 1
                        elif valRaw.StartsWith("[") then
                            pairs.Add(key, parseFlowSeq valRaw); i <- i + 1
                        else
                            pairs.Add(key, Scalar(unquote valRaw)); i <- i + 1
            Map(List.ofSeq pairs), (i - start)

let parseYaml (text: string) =
    let lines =
        text.Split('\n')
        |> Array.map stripComment
        |> Array.mapi (fun idx l -> idx, l.TrimEnd())
        |> Array.filter (fun (_, l) -> l.Trim() <> "" && not ((l.TrimStart()).StartsWith("#")))
    fst (parseBlock lines 0 0)

// ── Lookup helpers over the parsed tree. ──
let private field k = function Map m -> m |> List.tryFind (fst >> (=) k) |> Option.map snd | _ -> None
let private scalar k node = field k node |> Option.bind (function Scalar s -> Some s | _ -> None)
let private scalarOr k d node = scalar k node |> Option.defaultValue d
let private seqItems k node = field k node |> Option.map (function Seq xs -> xs | x -> [x]) |> Option.defaultValue []

// DeclaredCommand option from a build/test/run/verify mapping (absent -> None).
let private declared k node : Provider.DeclaredCommand option =
    field k node
    |> Option.map (fun m ->
        let exe = scalarOr "executable" "" m
        let args =
            seqItems "arguments" m
            |> List.choose (function Scalar s -> Some s | _ -> None)
        ({ Executable = exe; Arguments = args }: Provider.DeclaredCommand))

// ── Build the typed records from the YAML, then assert against the package. ──
let path =
    match fsi.CommandLineArgs |> Array.tryItem 1 with
    | Some p -> p
    | None -> failwith "usage: dotnet fsi verify-contract.fsx <providers.yml>"

let root = parseYaml (File.ReadAllText path)

let schemaVersion =
    match scalar "schemaVersion" root with
    | Some s -> int s
    | None -> failwith "registry has no top-level schemaVersion"

let providerNodes = seqItems "providers" root

let toDescriptor node : Provider.ProviderDescriptor =
    { Name = scalarOr "name" "" node
      ContractVersion = scalarOr "contractVersion" "" node
      TemplateId = scalarOr "templateId" "" node
      Source = scalarOr "source" "" node
      Parameters =
        seqItems "parameters" node
        |> List.map (fun p ->
            ({ Key = scalarOr "key" "" p
               Required = (scalarOr "required" "false" p).Trim().ToLowerInvariant() = "true"
               Default = scalar "default" p }: Provider.ProviderParameterSpec))
      Build = declared "build" node
      Test = declared "test" node
      Run = declared "run" node
      Verify = declared "verify" node
      NameParameter = scalarOr "nameParameter" Provider.defaultNameParameter node }

let descriptors = providerNodes |> List.map toDescriptor

let mutable failures = 0
let check ok msg =
    if ok then printfn "  ✓ %s" msg
    else (failures <- failures + 1; printfn "  ✗ %s" msg)

printfn "verify-contract: %s (FS.GG.Contracts %s)" (Path.GetFileName path) ContractVersion.value

// (1) schemaVersion matches the package's authoritative providers-schema constant.
check (schemaVersion = Schemas.providersVersion)
      (sprintf "schemaVersion %d == Schemas.providersVersion %d" schemaVersion Schemas.providersVersion)

// (2) at least one provider, and each binds to a well-formed descriptor.
check (not descriptors.IsEmpty) "registry declares at least one provider"

for d in descriptors do
    let lbl = if String.IsNullOrWhiteSpace d.Name then "<unnamed>" else d.Name
    // Required scalars present (an entry missing any is dropped by SDD's parser).
    check (List.forall (String.IsNullOrWhiteSpace >> not)
            [ d.Name; d.ContractVersion; d.TemplateId; d.Source ])
          (sprintf "[%s] required scalars (name/contractVersion/templateId/source) all present" lbl)
    // (3) canonical name parameter round-trips through the contract resolver.
    let resolved = Provider.resolveNameParameter d
    check (resolved = "name")
          (sprintf "[%s] resolveNameParameter -> '%s' (canonical 'name')" lbl resolved)
    // (4) no declared command is malformed (declared but blank executable).
    let bad =
        [ "build", d.Build; "test", d.Test; "run", d.Run; "verify", d.Verify ]
        |> List.choose (fun (k, c) -> c |> Option.filter Provider.isMalformed |> Option.map (fun _ -> k))
    check bad.IsEmpty
          (sprintf "[%s] declared commands well-formed (no blank executables)%s" lbl
             (if bad.IsEmpty then "" else sprintf " — malformed: %s" (String.concat "," bad)))

printfn "verify-contract: %d check(s) failed" failures
exit (if failures = 0 then 0 else 1)
