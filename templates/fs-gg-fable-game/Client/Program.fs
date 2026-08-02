module FableGameWorkspaceNamespace.Client.Program

open Elmish
open FableGameWorkspaceNamespace.Client.App

Program.mkProgram init update view |> Program.run
