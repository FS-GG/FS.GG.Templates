module FableGameWorkspaceNamespace.Client.Program

open Elmish
open FableGameWorkspaceNamespace.Client
open FableGameWorkspaceNamespace.Client.App

/// The DOM grid is `App.view`; `Stage.present` keeps the three renderers (when the player has chosen one
/// with `#renderer-backend`) presenting the same model.
let view (model: Model) (dispatch: Msg -> unit) : unit =
    App.view model dispatch
    Stage.present model dispatch

Program.mkProgram init update view |> Program.run
