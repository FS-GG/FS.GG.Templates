open FsGgTemplates.ProviderComposition

let alpha: Provider = {
    Name = "alpha"
    ContractVersion = "1.1.0"
    TemplateId = "fs-gg-alpha"
    Source = "Alpha.Template::1.0.0"
    Floor = Some "1.4.0-preview.1"
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
    assertEqual "empty package source refuses" (Error(InvalidProvider "alpha")) (select known [ { alpha with Source = "" } ])
    assertEqual "missing owner floor refuses" (Error(MissingFloor "alpha")) (select [ { alpha with Floor = None }; beta ] [ alpha ])
    assertEqual "missing request floor refuses" (Error(MissingFloor "alpha")) (select known [ { alpha with Floor = None } ])
    assertEqual "invalid floor refuses" (Error(InvalidFloor "alpha")) (select known [ { alpha with Floor = Some "not-a-version" } ])
    assertEqual "source drift refuses" (Error(DifferentProvider "alpha")) (select known [ { alpha with Source = "Alpha.Template::9.9.9" } ])
    assertEqual "registry pin admits coherent owner and request"
        (Ok [ beta ]) (selectAtRegistryFloor "1.4.0-preview.1" known [ beta ])
    assertEqual "unselected owner floor drift refuses"
        (Error(RegistryFloorMismatch("alpha", "1.4.0-preview.2", "1.4.0-preview.1")))
        (selectAtRegistryFloor "1.4.0-preview.1" [ { alpha with Floor = Some "1.4.0-preview.2" }; beta ] [ beta ])
    assertEqual "malformed registry pin refuses"
        (Error(InvalidRegistryFloor "1.4.0 garbage"))
        (selectAtRegistryFloor "1.4.0 garbage" known [ beta ])
    assertEqual "unknown request still refuses with a coherent pin"
        (Error(UnknownProvider "gamma"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "gamma" } ])
    assertEqual "malformed request still refuses with a coherent pin"
        (Error(InvalidProvider "../alpha"))
        (selectAtRegistryFloor "1.4.0-preview.1" known [ { alpha with Name = "../alpha" } ])
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
