module FsGgTemplates.ReferencePublication

open System
open System.IO
open System.IO.Compression
open System.Security.Cryptography
open System.Text
open System.Text.RegularExpressions
open System.Xml.Linq

type Request = {
    Archive: string
    Descriptor: string
    ExpectedSha256: string
    ExpectedRevision: string
}

let private packageId = "FS.GG.Workspace.Template"
let private version = "0.17.0"
let private source = packageId + "::" + version
let private hex64 = Regex("^[0-9a-f]{64}$", RegexOptions.CultureInvariant)
let private hex40 = Regex("^[0-9a-f]{40}$", RegexOptions.CultureInvariant)
let private required =
    [ "content/templates/fs-gg-fable-game/.template.config/template.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/FourDReference.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/Examples/FourD/reference.json"
      "content/templates/fs-gg-fable-game/SvgFoundation/SvgFoundation.fsproj"
      "content/templates/fs-gg-fable-game/SvgFoundation/Program.fs"
      "content/templates/fs-gg-fable-game/SvgFoundation/build.sh"
      "content/templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts" ]

let private refuse message = Error message
let private sha256 path =
    use stream = File.OpenRead path
    Convert.ToHexString(SHA256.HashData stream).ToLowerInvariant()

let private descriptorCheck path =
    let text = File.ReadAllText(path, UTF8Encoding(false, true)).Replace("\r\n", "\n")
    let exact line = Regex.Matches(text, "(?m)^" + Regex.Escape(line) + "$", RegexOptions.CultureInvariant).Count = 1
    let count pattern = Regex.Matches(text, pattern, RegexOptions.CultureInvariant ||| RegexOptions.Multiline).Count
    if count "^  - name:" <> 1 || not (exact "  - name: fable-game") then refuse "descriptor-provider-identity-refused"
    elif not (exact "    contractVersion: \"1.1.0\"") then refuse "descriptor-contract-refused"
    elif not (exact "    templateId: fs-gg-fable-game") then refuse "descriptor-template-refused"
    elif count "^    source:" <> 1 || not (exact ("    source: " + source)) then refuse "descriptor-source-refused"
    elif not (exact "        default: typed-sdd") then refuse "descriptor-lifecycle-refused"
    else Ok ()

let validate request =
    if not (File.Exists request.Archive) || not (File.Exists request.Descriptor) then refuse "input-file-missing"
    elif not (hex64.IsMatch request.ExpectedSha256) || not (hex40.IsMatch request.ExpectedRevision) then refuse "expected-identity-refused"
    elif sha256 request.Archive <> request.ExpectedSha256 then refuse "archive-sha256-refused"
    else
        match descriptorCheck request.Descriptor with
        | Error reason -> Error reason
        | Ok () ->
            try
                use archive = ZipFile.OpenRead request.Archive
                if archive.Entries.Count = 0 || archive.Entries.Count > 20000 then refuse "archive-entry-count-refused"
                else
                    let names = archive.Entries |> Seq.map (fun e -> e.FullName) |> Seq.toList
                    let invalid = names |> List.exists (fun n -> String.IsNullOrWhiteSpace n || n.StartsWith("/", StringComparison.Ordinal) || n.Contains("\\") || n.Split('/') |> Array.exists ((=) ".."))
                    let duplicate = names |> List.countBy _.ToUpperInvariant() |> List.exists (fun (_, count) -> count <> 1)
                    let oversized = archive.Entries |> Seq.exists (fun e -> e.Length < 0L || e.Length > 16L * 1024L * 1024L)
                    let total = archive.Entries |> Seq.sumBy _.Length
                    let linked = archive.Entries |> Seq.exists (fun e -> ((e.ExternalAttributes >>> 16) &&& 0xF000) = 0xA000)
                    if invalid then refuse "archive-path-refused"
                    elif duplicate then refuse "archive-duplicate-entry-refused"
                    elif oversized || total > 128L * 1024L * 1024L then refuse "archive-entry-bound-refused"
                    elif linked then refuse "archive-link-refused"
                    elif required |> List.exists (fun name -> archive.GetEntry(name) |> Option.ofObj |> Option.forall (fun e -> e.Length = 0L)) then refuse "reference-member-missing"
                    else
                        let nuspecs = archive.Entries |> Seq.filter (fun e -> e.FullName.EndsWith(".nuspec", StringComparison.OrdinalIgnoreCase)) |> Seq.toList
                        match nuspecs with
                        | [ nuspec ] ->
                            use stream = nuspec.Open()
                            let doc = XDocument.Load stream
                            let values name = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = name) |> Seq.map _.Value |> Seq.toList
                            let one name expected = values name = [ expected ]
                            let repository = doc.Descendants() |> Seq.filter (fun x -> x.Name.LocalName = "repository") |> Seq.toList
                            if not (one "id" packageId && one "version" version) then refuse "package-identity-refused"
                            elif repository.Length <> 1 || isNull (repository.Head.Attribute(XName.Get "commit")) || repository.Head.Attribute(XName.Get "commit").Value <> request.ExpectedRevision then refuse "package-source-revision-refused"
                            else Ok names.Length
                        | _ -> refuse "package-nuspec-census-refused"
            with :? InvalidDataException -> refuse "archive-format-refused"
