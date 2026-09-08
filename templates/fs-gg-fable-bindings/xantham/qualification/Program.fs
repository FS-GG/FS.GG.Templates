module Qualification.XanthamAnsi

let ansi = "\u001B[4mcake\u001B[0m"
let omitted = AnsiRegex.Exports.ansiRegex ()
if not (omitted.IsMatch ansi) then failwith "omitted-options ANSI match failed"
if omitted.IsMatch "cake" then failwith "plain-text negative control failed"
let allMatches = omitted.Matches ansi
if allMatches.Count <> 2 then failwithf "default regex expected two matches, found %d" allMatches.Count
let first = AnsiRegex.Exports.ansiRegex (AnsiRegex.Options.Create true)
if not (first.IsMatch ansi) then failwith "onlyFirst ANSI match failed"
if Fable.Core.JsInterop.emitJsExpr first "$0.global" then failwith "onlyFirst must construct a non-global regex"
printfn "PASS Xantham ANSI candidate default import, omitted options, option constructor, controls and onlyFirst"
