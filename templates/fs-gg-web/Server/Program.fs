namespace WebWorkspace.Server

open System
open System.IO
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Http
open Microsoft.Extensions.FileProviders

module Program =
    let private message () = {| message = "Hello from WebWorkspace" |}

    [<EntryPoint>]
    let main args =
        let builder = WebApplication.CreateBuilder args
        let app = builder.Build()

        app.MapGet("/api/message", Func<IResult>(fun () -> Results.Json(message ()))) |> ignore

        let webRoot = Path.Combine(app.Environment.ContentRootPath, "..", "Web", "dist")
        if Directory.Exists webRoot then
            app.UseDefaultFiles(new DefaultFilesOptions(FileProvider = new PhysicalFileProvider(webRoot))) |> ignore
            app.UseStaticFiles(new StaticFileOptions(FileProvider = new PhysicalFileProvider(webRoot))) |> ignore
            app.MapFallbackToFile("index.html") |> ignore

        app.Run()
        0
