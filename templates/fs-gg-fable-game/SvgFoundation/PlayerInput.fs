module FableGameWorkspaceNamespace.SvgFoundation.PlayerInput

open FS.GG.UI.KeyboardInput

let private command id label =
    { Id = id
      Label = label
      Contexts = [ "game.play" ]
      AvailabilityKey = None
      Trigger = CommandTriggerPolicy.OncePerPress
      Argument = CommandArgumentPolicy.NoArgument
      Alternatives = [ CommandAlternative.Palette; CommandAlternative.Pointer label ] }

let catalog =
    { Contexts = [ { Id = "game.play"; Priority = 10; Exclusive = false; Overlaps = [] } ]
      Commands =
        [ command "game.focus-next" "Focus next game object"
          command "game.focus-previous" "Focus previous game object"
          command "game.activate" "Activate focused game object" ]
      ReservedGestures = []
      AllowTerminalPrefixes = false }

let profile =
    { Schema = CommandInput.profileSchema
      Id = "generated-player"
      Defaults =
        [ { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "n", CommandInput.noModifiers); Command = "game.focus-next"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "p", CommandInput.noModifiers); Command = "game.focus-previous"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "a", CommandInput.noModifiers); Command = "game.activate"; Context = "game.play" } ]
      Overrides = [] }

let effective =
    CommandInput.compile catalog profile
    |> Result.defaultWith (fun issues -> failwithf "Generated player input profile is invalid: %A" issues)

