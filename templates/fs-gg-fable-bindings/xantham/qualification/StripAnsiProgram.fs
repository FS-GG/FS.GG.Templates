module Qualification.XanthamStripAnsi

let ansi = "\u001B[4mcake\u001B[0m"

if StripAnsi.Exports.stripAnsi ansi <> "cake" then
    failwith "strip-ansi did not remove the ANSI sequence"

if StripAnsi.Exports.stripAnsi "cake" <> "cake" then
    failwith "strip-ansi changed the plain-text control"

printfn "PASS Xantham strip-ansi ANSI and plain-text runtime witness"
