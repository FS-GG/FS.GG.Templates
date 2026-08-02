module FableGameWorkspaceNamespace.Server.Tests.BootstrapEndpointTests

open System.Net.Http
open System.Text
open Microsoft.AspNetCore.Mvc.Testing
open Xunit
open FableGameWorkspaceNamespace.Protocol.Http
open FableGameWorkspaceNamespace.Server

/// Exercises the one plain-HTTP typed request/response call #348's acceptance names,
/// through a real ASP.NET Core pipeline (`WebApplicationFactory`), not a bare function
/// call -- this proves the minimal-API handler, the JSON content type, and the named
/// codec functions all agree end to end.
type BootstrapEndpointTests() =
    do RoomAuthority.resetForTests () // isolates this test from RoomAuthority's process-wide static state
    let factory = new WebApplicationFactory<Program>()

    [<Fact>]
    member _.``POST /api/bootstrap returns a decodable, versioned response assigning a distinct player and the arena's fixed dimensions``() =
        task {
            use client = factory.CreateClient()
            let request: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }
            use content = new StringContent(BootstrapV1.encodeRequest request, Encoding.UTF8, "application/json")
            use! response = client.PostAsync("/api/bootstrap", content)
            let! body = response.Content.ReadAsStringAsync()
            Assert.True(response.IsSuccessStatusCode, body)
            match BootstrapV1.responseFromJson body with
            | Error message -> Assert.Fail $"response did not decode: {message}"
            | Ok parsed ->
                Assert.Equal(1, parsed.Version)
                Assert.False(System.String.IsNullOrWhiteSpace parsed.PlayerId)
                Assert.Equal(RoomAuthority.RoomId, parsed.RoomId)
                Assert.Equal(RoomAuthority.ArenaWidth, parsed.ArenaWidth)
                Assert.Equal(RoomAuthority.ArenaHeight, parsed.ArenaHeight)
        }

    [<Fact>]
    member _.``two bootstrap calls assign two distinct player ids and two distinct spawn cells``() =
        task {
            use client = factory.CreateClient()
            let call () =
                task {
                    let request: BootstrapV1.Request = { Version = 1; PlayerName = "Rogue" }
                    use content = new StringContent(BootstrapV1.encodeRequest request, Encoding.UTF8, "application/json")
                    use! response = client.PostAsync("/api/bootstrap", content)
                    let! body = response.Content.ReadAsStringAsync()
                    return BootstrapV1.responseFromJson body |> Result.map (fun r -> r.PlayerId, (r.SpawnCol, r.SpawnRow))
                }
            let! first = call ()
            let! second = call ()
            match first, second with
            | Ok(id1, spawn1), Ok(id2, spawn2) ->
                Assert.NotEqual<string>(id1, id2)
                Assert.NotEqual<int * int>(spawn1, spawn2)
            | _ -> Assert.Fail "both bootstrap calls must decode"
        }

    [<Fact>]
    member _.``POST /api/bootstrap rejects a malformed request body``() =
        task {
            use client = factory.CreateClient()
            use content = new StringContent("""{"version":1}""", Encoding.UTF8, "application/json")
            use! response = client.PostAsync("/api/bootstrap", content)
            Assert.Equal(System.Net.HttpStatusCode.BadRequest, response.StatusCode)
        }

    interface System.IDisposable with
        member _.Dispose() = factory.Dispose()
