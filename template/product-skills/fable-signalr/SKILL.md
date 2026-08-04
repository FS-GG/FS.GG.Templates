---
name: fable-signalr
description: Integrate the official SignalR JavaScript client through a narrow Fable binding for connection-oriented browser traffic, including reconnect, disposal, and resynchronization.
---

# Fable SignalR capability

Use SignalR for connection/session traffic: presence, pushed snapshots, input streams,
acknowledgements, reconnect, and resync. Keep request/response operations elsewhere. Bind only the
official `@microsoft/signalr` npm client through reviewed Fable imports; do not adopt the stale
`Fable.SignalR` NuGet package as a generated baseline.

```fsharp
// Narrow binding shape: createHubConnection, on, start, invoke, stop and onreconnecting/onreconnected.
// Own the callback subscriptions and call stop/dispose when the Elmish component/session ends.
```

Protocol payloads have explicit version/compatibility fields. On reconnect, treat prior local state as
suspect: resubscribe, request a fresh snapshot or cursor-based catch-up, and make duplicate messages
idempotent. Surface connection, authorization, transport, and server errors as product states rather
than dropping them in JavaScript callbacks.

Lock the npm package, Node/npm, Fable compiler, and browser used for the smoke test. The proof is a
real browser session that starts, receives a server event, reconnects/resynchronizes, disposes its
subscription, and reports a failed invocation; a Node-only import check is insufficient.

## Sources

- [ASP.NET Core SignalR JavaScript client](https://learn.microsoft.com/aspnet/core/signalr/javascript-client)
- [SignalR hubs](https://learn.microsoft.com/aspnet/core/signalr/hubs)
- [`@microsoft/signalr` npm package](https://www.npmjs.com/package/@microsoft/signalr)
