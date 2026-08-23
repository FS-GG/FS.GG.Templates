namespace FableGameWorkspaceNamespace.Client

open Fable.Core
open Fable.Core.JsInterop

/// The narrow, template-owned Fable binding over the official `@microsoft/signalr`
/// npm client (ADR-0071 Section 5, unchanged by ADR-0073): only the surface this
/// template actually calls, not a general-purpose wrapper. The stale `Fable.SignalR`
/// NuGet package is deliberately not used.
[<RequireQualifiedAccess>]
module SignalR =

    /// A value of this type is never constructed in F# -- it only ever comes back from
    /// `HubConnectionBuilder.build()` below -- so it is declared as a pure type shape
    /// (`abstract` members, no bodies) rather than an `[<Import>]`-attributed class:
    /// there is nothing to import a constructor for.
    type HubConnection =
        abstract on: methodName: string * handler: (string -> unit) -> unit
        abstract onreconnecting: handler: (obj -> unit) -> unit
        abstract onreconnected: handler: (string -> unit) -> unit
        abstract onclose: handler: (obj -> unit) -> unit
        abstract start: unit -> JS.Promise<unit>
        abstract stop: unit -> JS.Promise<unit>
        abstract invoke: methodName: string * argument: string -> JS.Promise<obj>

    [<Import("HubConnectionBuilder", "@microsoft/signalr")>]
    type HubConnectionBuilder() =
        member this.withUrl(url: string) : HubConnectionBuilder = jsNative
        member this.withAutomaticReconnect() : HubConnectionBuilder = jsNative
        member this.build() : HubConnection = jsNative

    /// Builds (but does not start) a connection to `url`, with automatic reconnect
    /// enabled -- the client half of #348's "bounded full authoritative resync"
    /// acceptance: on reconnect, `App.fs` always re-requests a full snapshot rather
    /// than assuming any buffered state survived.
    let build (url: string) : HubConnection = HubConnectionBuilder().withUrl(url).withAutomaticReconnect().build ()
