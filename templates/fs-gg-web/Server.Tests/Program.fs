module WebWorkspace.Server.Tests

[<EntryPoint>]
let main _ =
    let payload = {| message = "Hello from WebWorkspace" |}
    if payload.message = "Hello from WebWorkspace" then 0 else 1
