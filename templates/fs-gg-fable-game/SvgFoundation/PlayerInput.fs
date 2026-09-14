module FableGameWorkspaceNamespace.SvgFoundation.PlayerInput

open FS.GG.UI.KeyboardInput

#if SVG_RUNTIME_CANDIDATE
let private command id label trigger =
    { Id = id
      Label = label
      Contexts = [ "game.play" ]
      AvailabilityKey = None
      Trigger = trigger
      Argument = CommandArgumentPolicy.NoArgument
      Alternatives = [ CommandAlternative.Palette; CommandAlternative.Pointer label ] }

let catalog =
    { Contexts = [ { Id = "game.play"; Priority = 10; Exclusive = false; Overlaps = [] } ]
      Commands =
        [ command "game.move-up" "Move up" CommandTriggerPolicy.RepeatWhileHeld
          command "game.move-down" "Move down" CommandTriggerPolicy.RepeatWhileHeld
          command "game.move-left" "Move left" CommandTriggerPolicy.RepeatWhileHeld
          command "game.move-right" "Move right" CommandTriggerPolicy.RepeatWhileHeld
          command "game.stop" "Stop moving" CommandTriggerPolicy.OncePerPress
          command "game.pause" "Pause game" CommandTriggerPolicy.OncePerPress
          command "game.interact" "Interact" CommandTriggerPolicy.OncePerPress
          command "game.restart" "Restart game" CommandTriggerPolicy.OncePerPress ]
      ReservedGestures = []
      AllowTerminalPrefixes = false }

let profile =
    { Schema = CommandInput.profileSchema
      Id = "generated-player"
      Defaults =
        [ { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "w", CommandInput.noModifiers); Command = "game.move-up"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "s", CommandInput.noModifiers); Command = "game.move-down"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "a", CommandInput.noModifiers); Command = "game.move-left"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "d", CommandInput.noModifiers); Command = "game.move-right"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.PhysicalCode "Space", CommandInput.noModifiers); Command = "game.stop"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "p", CommandInput.noModifiers); Command = "game.pause"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "e", CommandInput.noModifiers); Command = "game.interact"; Context = "game.play" }
          { Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "r", CommandInput.noModifiers); Command = "game.restart"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "move-up"; Command = "game.move-up"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "move-down"; Command = "game.move-down"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "move-right"; Command = "game.move-right"; Context = "game.play" }
          { Gesture = InputGesture.Touch "move-left"; Command = "game.move-left"; Context = "game.play" }
          { Gesture = InputGesture.Gamepad "button-0"; Command = "game.move-up"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "pause"; Command = "game.pause"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "interact"; Command = "game.interact"; Context = "game.play" }
          { Gesture = InputGesture.Pointer "restart"; Command = "game.restart"; Context = "game.play" } ]
      Overrides = [] }
#else
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
#endif

let effective =
    CommandInput.compile catalog profile
    |> Result.defaultWith (fun issues -> failwithf "Generated player input profile is invalid: %A" issues)
