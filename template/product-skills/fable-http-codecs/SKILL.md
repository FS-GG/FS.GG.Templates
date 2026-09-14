---
name: fable-http-codecs
description: Build explicit versioned HTTP request and response codecs shared by Fable and ASP.NET Core, with server-owned authentication and authorization.
---

# Fable HTTP codec boundary

Use plain ASP.NET Core endpoints for bounded request/response operations. Define small versioned DTOs
and named encode/decode functions in shared F# source, compiling that source against `Thoth.Json.Net`
on .NET and `Thoth.Json` under Fable. Keep domain unions, persistence records, and server infrastructure
behind this boundary.

Authenticate before dispatch, authorize every operation from server-owned identity and claims, and map
validation and authorization failures to deliberate response DTOs and HTTP status codes. Route decoded
responses into the Elmish update path as explicit messages; browser checks never grant authority.

The generated `fable-game` workspace demonstrates the contract in `Protocol/Http.fs`,
`Server/Program.fs`, and `Client/Api.fs`. `Protocol.Tests/cross-runtime` round-trips each DTO in both
directions and refuses malformed payloads.

## Retiring managed Fable.Remoting guidance

`fable-http-codecs` supersedes the old `fable-remoting` product skill. During a managed workspace
upgrade, remove the old body only when its digest still matches the previously installed managed
version. If a user edited it, retain the file and report the collision; never delete or overwrite it.

## Sources

- [ASP.NET Core APIs](https://learn.microsoft.com/aspnet/core/fundamentals/apis)
- [ASP.NET Core authentication](https://learn.microsoft.com/aspnet/core/security/authentication/)
- [Thoth.Json](https://github.com/thoth-org/Thoth.Json)
