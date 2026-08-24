module FableGameWorkspaceNamespace.Server.Tests.BootstrapEndpointTests

open System
open System.Net
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

    [<Fact>]
    member _.``bootstrap admission is bounded and expired unbound sessions release their cells``() =
        task {
            use client = factory.CreateClient()
            let call index =
                task {
                    let request: BootstrapV1.Request = { Version = 1; PlayerName = $"player-{index}" }
                    use content = new StringContent(BootstrapV1.encodeRequest request, Encoding.UTF8, "application/json")
                    use! response = client.PostAsync("/api/bootstrap", content)
                    let! body = response.Content.ReadAsStringAsync()
                    return response.StatusCode, body
                }

            let cells = ResizeArray<int * int>()
            for index in 1 .. RoomAuthority.MaxSessions do
                let! status, body = call index
                Assert.Equal(HttpStatusCode.OK, status)
                match BootstrapV1.responseFromJson body with
                | Ok response -> cells.Add(response.SpawnCol, response.SpawnRow)
                | Error error -> Assert.Fail $"accepted bootstrap did not decode: {error}"

            Assert.Equal(RoomAuthority.MaxSessions, cells.Count)
            Assert.Equal(RoomAuthority.MaxSessions, cells |> Seq.distinct |> Seq.length)

            let! overflowStatus, overflowBody = call (RoomAuthority.MaxSessions + 1)
            Assert.Equal(HttpStatusCode.TooManyRequests, overflowStatus)
            Assert.Contains("session capacity reached", overflowBody)

            RoomAuthority.expireSessionsAt(DateTimeOffset.UtcNow.Add(RoomAuthority.SessionLifetime).AddSeconds 1.0)
            let! recoveredStatus, recoveredBody = call (RoomAuthority.MaxSessions + 2)
            Assert.Equal(HttpStatusCode.OK, recoveredStatus)
            match BootstrapV1.responseFromJson recoveredBody with
            | Ok response ->
                Assert.InRange(response.SpawnCol, 0, RoomAuthority.ArenaWidth - 1)
                Assert.InRange(response.SpawnRow, 0, RoomAuthority.ArenaHeight - 1)
            | Error error -> Assert.Fail $"bootstrap after expiry did not decode: {error}"
        }

    interface System.IDisposable with
        member _.Dispose() = factory.Dispose()
