module FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayExampleTestEntry

open Xunit

[<Fact>]
let ``Local save replay finite conformance`` () =
    LocalSaveReplayExampleTests.run ()
