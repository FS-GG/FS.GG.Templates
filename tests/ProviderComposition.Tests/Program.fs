open FsGgTemplates.ProviderComposition
open System
open System.Security.Cryptography

let productName: Parameter = { Key = "productName"; Required = true; Default = None }
let lifecycle: Parameter = { Key = "lifecycle"; Required = false; Default = Some "sdd" }

let alpha: Provider = {
    Name = "alpha"
    ContractVersion = "1.1.0"
    TemplateId = "fs-gg-alpha"
    Source = "Alpha.Template::1.0.0"
    NameParameter = Some "productName"
    IdentifierParameter = Some "rootNamespace"
    Floor = Some "1.4.0-preview.1"
    Parameters = [ productName; lifecycle ]
    File = "alpha.providers.yml"
    Line = 3
}
let beta = { alpha with Name = "beta"; TemplateId = "fs-gg-beta"; Source = "Beta.Template::2.0.0" }
let known = [ alpha; beta ]
let assertEqual name expected actual =
    if expected <> actual then failwithf "%s: expected %A, got %A" name expected actual
    printfn "PASS %s" name

[<EntryPoint>]
let main _ =
    let selected = select known known
    assertEqual "two known providers compose" (Ok known) selected
    assertEqual "subset keeps requested identity" (Ok [ beta ]) (select known [ beta ])
    assertEqual "owner files may enumerate in filename order" (Ok known) (select [ beta; alpha ] known)
    assertEqual "empty request refuses" (Error EmptySelection) (select known [])
    assertEqual "unknown provider refuses" (Error(UnknownProvider "gamma")) (select known [ { alpha with Name = "gamma" } ])
    assertEqual "duplicate request refuses" (Error(DuplicateProvider "alpha")) (select known [ alpha; alpha ])
    assertEqual "duplicate owner source refuses" (Error(DuplicateProvider "alpha")) (select [ alpha; alpha ] [ alpha ])
    assertEqual "unordered request refuses" (Error UnorderedProviders) (select known [ beta; alpha ])
    assertEqual "invalid name refuses" (Error(InvalidProvider "../alpha")) (select known [ { alpha with Name = "../alpha" } ])
    let newlineName = { alpha with Name = "alpha\n" }
    assertEqual "terminal newline owner name refuses before selection"
        (Error(InvalidProvider "alpha\n")) (select [ newlineName; beta ] [ newlineName ])
    assertEqual "empty package source refuses" (Error(InvalidProvider "alpha")) (select known [ { alpha with Source = "" } ])
    assertEqual "missing owner floor refuses" (Error(MissingFloor "alpha")) (select [ { alpha with Floor = None }; beta ] [ alpha ])
    assertEqual "missing request floor refuses" (Error(MissingFloor "alpha")) (select known [ { alpha with Floor = None } ])
    assertEqual "invalid floor refuses" (Error(InvalidFloor "alpha")) (select known [ { alpha with Floor = Some "not-a-version" } ])
    let newlineFloor = { alpha with Floor = Some "1.4.0-preview.1\n" }
    assertEqual "terminal newline owner floor refuses before selection"
        (Error(InvalidFloor "alpha")) (select [ newlineFloor; beta ] [ newlineFloor ])
    assertEqual "source drift refuses" (Error(DifferentProvider "alpha")) (select known [ { alpha with Source = "Alpha.Template::9.9.9" } ])
    assertEqual "name route drift refuses" (Error(DifferentProvider "alpha"))
        (select known [ { alpha with NameParameter = Some "otherName" } ])
    assertEqual "identifier route drift refuses" (Error(DifferentProvider "alpha"))
        (select known [ { alpha with IdentifierParameter = Some "otherNamespace" } ])
    assertEqual "malformed route refuses" (Error(InvalidProvider "alpha"))
        (select known [ { alpha with NameParameter = Some "../outside" } ])
    assertEqual "registry pin admits coherent owner and request"
        (Ok [ beta ]) (selectAtRegistryFloor "1.4.0-preview.1" known [ beta ])
    assertEqual "unselected owner floor drift refuses"
        (Error(RegistryFloorMismatch("alpha", "1.4.0-preview.2", "1.4.0-preview.1")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ { alpha with Floor = Some "1.4.0-preview.2" }; beta ] [ beta ])
    assertEqual "malformed registry pin refuses"
        (Error(InvalidRegistryFloor "1.4.0 garbage"))
        (selectAtRegistryFloor "1.4.0 garbage" known [ beta ])
    assertEqual "terminal newline registry pin refuses"
        (Error(InvalidRegistryFloor "1.4.0-preview.1\n"))
        (selectAtRegistryFloor "1.4.0-preview.1\n" known [ beta ])
    assertEqual "unknown request still refuses with a coherent pin"
        (Error(UnknownProvider "gamma"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "gamma" } ])
    assertEqual "malformed request still refuses with a coherent pin"
        (Error(InvalidProvider "../alpha"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "../alpha" } ])
    assertEqual "parameter declaration drift refuses"
        (Error(DifferentProvider "alpha"))
        (selectAtRegistryFloor "1.4.0-preview.1" known
            [ { alpha with Parameters = [ productName ] } ])
    let staleAlpha = { alpha with Floor = Some "1.4.0-preview.2" }
    assertEqual "selected owner floor drift refuses"
        (Error(RegistryFloorMismatch("alpha", "1.4.0-preview.2", "1.4.0-preview.1")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ staleAlpha; beta ] [ staleAlpha ])
    assertEqual "malformed declared parameter key refuses"
        (Error(InvalidParameter("alpha", "../name")))
        (selectAtRegistryFloor "1.4.0-preview.1"
            [ { alpha with Parameters = [ { productName with Key = "../name" } ] }; beta ] [ beta ])
    let newlineParameter = { alpha with Parameters = [ { productName with Key = "productName\n" } ] }
    assertEqual "terminal newline declared parameter key refuses"
        (Error(InvalidParameter("alpha", "productName\n")))
        (select [ newlineParameter; beta ] [ newlineParameter ])
    let newlineRoute = { alpha with NameParameter = Some "productName\n" }
    assertEqual "terminal newline parameter route refuses"
        (Error(InvalidProvider "alpha")) (select [ newlineRoute; beta ] [ newlineRoute ])
    assertEqual "duplicate declared parameter refuses"
        (Error(DuplicateParameter("alpha", "productName")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ { alpha with Parameters = [ productName; productName ] }; beta ] [ beta ])
    assertEqual "unknown requested parameter refuses"
        (Error(UnknownParameter("alpha", "surprise")))
        (resolveParameters alpha [ "productName", "Demo"; "surprise", "yes" ])
    assertEqual "duplicate requested parameter refuses"
        (Error(DuplicateParameter("alpha", "productName")))
        (resolveParameters alpha [ "productName", "Demo"; "productName", "Again" ])
    assertEqual "missing required parameter refuses"
        (Error(MissingRequiredParameter("alpha", "productName")))
        (resolveParameters alpha [])
    assertEqual "defaults and declared order resolve deterministically"
        (Ok [ "productName", "Demo"; "lifecycle", "sdd" ])
        (resolveParameters alpha [ "productName", "Demo" ])
    assertEqual "exact UTF-8 summary bytes match Python fixture"
        "02dff0dfdd49d147f2ec933426d6bc9910848d568fda85fc0e730678435f6b7b"
        (Convert.ToHexString(SHA256.HashData(renderEffectiveBytes true known)).ToLowerInvariant())
    assertEqual "exact UTF-8 summary without final newline matches Python fixture"
        "3f2694267343ae48149ab7b082f96727590c73a3b6b5d921566c9f0de8b033b3"
        (Convert.ToHexString(SHA256.HashData(renderEffectiveBytes false known)).ToLowerInvariant())
    let rendered =
        match selected with
        | Ok value -> renderEffective value
        | Error issue -> failwithf "valid selection refused: %A" issue
    assertEqual "summary output deterministic"
        [ "# Effective providers — generated; ordered by unique provider name."
          "# Review this block for the current selection; the release narrative remains in PIN HISTORY."
          "# effective[1]: name=alpha | template=fs-gg-alpha | source=Alpha.Template::1.0.0 | contract=1.1.0"
          "# effective[2]: name=beta | template=fs-gg-beta | source=Beta.Template::2.0.0 | contract=1.1.0" ] rendered
    0
