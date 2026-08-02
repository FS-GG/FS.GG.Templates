namespace FableGameWorkspaceNamespace.Protocol.Http

#if FABLE_COMPILER
open Thoth.Json
#else
open Thoth.Json.Net
#endif

/// Typed plain-HTTP request/response operations (ADR-0073: plain ASP.NET Core HTTP
/// endpoints with explicit versioned DTOs replace Fable.Remoting for `fable-game`'s
/// typed request/response leg; SignalR, in ../Realtime.fs, is unchanged).
///
/// Every operation here is an explicit, versioned request/response record pair with a
/// *named* codec function on both the .NET and Fable sides -- never reflection- or
/// attribute-driven automatic serialization (no `Decode.Auto`), and never a generated
/// RPC proxy. The client calls the corresponding endpoint with `fetch` (see
/// ../Client/Api.fs); there is no client-side proxy generation step.
[<RequireQualifiedAccess>]
module BootstrapV1 =

    /// Sent once, when the browser first loads: "who am I, what room am I joining".
    type Request = { Version: int; PlayerName: string }

    /// The authoritative bootstrap the server hands back: assigned identity, assigned
    /// room, and the arena's fixed dimensions the client needs before it can render or
    /// preview movement. `Version` lets a client and server built against different
    /// template generations fail an explicit version check instead of silently
    /// misinterpreting fields a persisted session or reconnecting tab might still send.
    type Response =
        { Version: int
          PlayerId: string
          RoomId: string
          SpawnCol: int
          SpawnRow: int
          ArenaWidth: int
          ArenaHeight: int }

    let encodeRequest (value: Request) : string =
        Encode.object [ "version", Encode.int value.Version; "playerName", Encode.string value.PlayerName ]
        |> Encode.toString 0

    let decodeRequest: Decoder<Request> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              PlayerName = get.Required.Field "playerName" Decode.string })

    let requestFromJson (json: string) : Result<Request, string> = Decode.fromString decodeRequest json

    let encodeResponse (value: Response) : string =
        Encode.object
            [ "version", Encode.int value.Version
              "playerId", Encode.string value.PlayerId
              "roomId", Encode.string value.RoomId
              "spawnCol", Encode.int value.SpawnCol
              "spawnRow", Encode.int value.SpawnRow
              "arenaWidth", Encode.int value.ArenaWidth
              "arenaHeight", Encode.int value.ArenaHeight ]
        |> Encode.toString 0

    let decodeResponse: Decoder<Response> =
        Decode.object (fun get ->
            { Version = get.Required.Field "version" Decode.int
              PlayerId = get.Required.Field "playerId" Decode.string
              RoomId = get.Required.Field "roomId" Decode.string
              SpawnCol = get.Required.Field "spawnCol" Decode.int
              SpawnRow = get.Required.Field "spawnRow" Decode.int
              ArenaWidth = get.Required.Field "arenaWidth" Decode.int
              ArenaHeight = get.Required.Field "arenaHeight" Decode.int })

    let responseFromJson (json: string) : Result<Response, string> = Decode.fromString decodeResponse json
