---
name: fable-remoting
description: Use Fable.Remoting only for bounded typed request/response operations across an ASP.NET Core and Fable boundary, with explicit serialization, errors, and authentication ownership.
---

# Fable.Remoting capability

Use Fable.Remoting for queries and commands that have one typed request and one typed response. Keep
shared API records small and serialization-friendly; arbitrary domain discriminated unions, server
infrastructure, and persistence models are not automatically wire contracts. Version DTOs when
persisted clients or replays may outlive a deployment.

Register the server adapter at the ASP.NET Core boundary and construct the client from an explicit
base URL. Authentication and authorization remain server policy: authenticate before dispatch,
authorize each operation using server-owned identity/claims, and return a deliberate error DTO or
mapped HTTP failure. Never rely on a client-side check as authorization.

```fsharp
type TodoApi = { getTodos: unit -> Async<Result<Todo list, ApiError>> }
// Server: route the adapter through ASP.NET Core authentication/authorization middleware.
// Client: call only after a typed error boundary has been installed in the Elmish update path.
```

## Qualification gate

The local 2026-08-01 spike found Fable.Remoting.Client 8.0.0 plus Fable 5.13.0/Fable.Core 5.2.0
does not Fable-compile because of its transitive MsgPack source. Do not make that pair a generated
baseline. Before selecting any pair, lock exact server/client/Fable versions, run a clean restore,
compile the real Fable client, and exercise an authenticated success, validation failure,
unauthenticated failure, cancellation, and serialization round trip.

## Sources

- [Fable.Remoting repository and docs](https://github.com/Zaid-Ajaj/Fable.Remoting)
- [ASP.NET Core authentication](https://learn.microsoft.com/aspnet/core/security/authentication/)
- [System.Text.Json serialization](https://learn.microsoft.com/dotnet/standard/serialization/system-text-json/overview)
