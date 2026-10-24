module FS.GG.Templates.PolyglotProviderTool.Program

open System
open System.IO
open FS.GG.Templates.PolyglotProviderTool

[<EntryPoint>]
let main argv =
    try
        match Array.toList argv with
        | [ "fixture"; provider; catalog; policy; archive; output ] ->
            Fixture.emit provider catalog policy archive output
            0
        | [ "readback"; provenance; summary ] ->
            Provenance.check provenance summary
            0
        | [ "self-test" ] ->
            printfn "public SDK authoring controls: %d" (Catalog.controls ())
            0
        | [ operation; "--package-version"; version; "--output"; output ]
            when operation = "emit" || operation = "check" ->
            let bytes = Catalog.bytes version
            if operation = "check" then
                if File.ReadAllBytes(output) <> bytes then failwith "Catalog bytes differ from the typed public-SDK producer."
            else
                let full = Path.GetFullPath output
                if not (Directory.Exists(Path.GetDirectoryName full)) then failwith "Output parent must already exist."
                use stream = new FileStream(full, FileMode.CreateNew, FileAccess.Write, FileShare.None)
                stream.Write(bytes, 0, bytes.Length)
                stream.Flush(true)
            0
        | _ ->
            eprintfn "Use emit|check --package-version <exact> --output <file>, or self-test."
            2
    with error ->
        eprintfn "%s" error.Message
        1
