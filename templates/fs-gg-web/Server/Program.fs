namespace WebWorkspaceNamespace.Server

open System
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Http

module Program =
    let message () = {| message = "Hello from WebWorkspace" |}

    [<EntryPoint>]
    let main args =
        let builder = WebApplication.CreateBuilder args
        let app = builder.Build()

        app.MapGet("/api/message", Func<IResult>(fun () -> Results.Json(message ()))) |> ignore
        app.UseDefaultFiles() |> ignore
        app.UseStaticFiles() |> ignore
        app.MapFallbackToFile("index.html") |> ignore

        app.Run()
        0
