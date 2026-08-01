namespace WebWorkspaceNamespace.Server.Tests

open WebWorkspaceNamespace.Server
open Xunit

type MessageTests() =
    [<Fact>]
    member _.``message endpoint has the documented payload`` () =
        Assert.Equal("Hello from WebWorkspace", (Program.message ()).message)
