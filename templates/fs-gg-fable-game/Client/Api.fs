namespace FableGameWorkspaceNamespace.Client

open Fable.Core
open Fable.Core.JsInterop
open FableGameWorkspaceNamespace.Protocol.Http

/// The plain-HTTP typed request/response leg (ADR-0073): calls the endpoint with the
/// browser's global `fetch`, encoding and decoding through the *named codec functions*
/// in `Protocol/Http.fs` -- never a generated client proxy, never `Decode.Auto`.
[<RequireQualifiedAccess>]
module Api =

    [<Global>]
    let private fetch (url: string, options: obj) : JS.Promise<obj> = jsNative

    /// Raises on a non-decodable response so callers can use `Cmd.OfAsync.either`'s
    /// ordinary (ok, error) shape without a nested `Result`.
    let bootstrap (request: BootstrapV1.Request) : Async<BootstrapV1.Response> =
        async {
            let options =
                createObj
                    [ "method" ==> "POST"
                      "headers" ==> createObj [ "Content-Type" ==> "application/json" ]
                      "body" ==> BootstrapV1.encodeRequest request ]
            let! response = fetch ("/api/bootstrap", options) |> Async.AwaitPromise
            let! text = response?text () |> Async.AwaitPromise
            match BootstrapV1.responseFromJson (text: string) with
            | Ok parsed -> return parsed
            | Error message -> return failwith $"bootstrap response did not decode: {message}"
        }
