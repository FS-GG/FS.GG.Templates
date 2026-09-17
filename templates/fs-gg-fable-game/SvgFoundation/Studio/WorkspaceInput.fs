module FableGameWorkspaceNamespace.SvgFoundation.Studio.WorkspaceInput

open FS.GG.UI.KeyboardInput

let private command id label trigger =
    {
        Id = id
        Label = label
        Contexts = [ "workspace" ]
        AvailabilityKey = None
        Trigger = trigger
        Argument = CommandArgumentPolicy.NoArgument
        Alternatives = [ CommandAlternative.Palette; CommandAlternative.Pointer label ]
    }

let catalog =
    {
        Contexts =
            [
                {
                    Id = "workspace"
                    Priority = 10
                    Exclusive = false
                    Overlaps = [ "workspace.palette"; "workspace.help"; "workspace.rebind" ]
                }
                {
                    Id = "workspace.palette"
                    Priority = 30
                    Exclusive = true
                    Overlaps = [ "workspace" ]
                }
                {
                    Id = "workspace.help"
                    Priority = 30
                    Exclusive = true
                    Overlaps = [ "workspace" ]
                }
                {
                    Id = "workspace.rebind"
                    Priority = 30
                    Exclusive = true
                    Overlaps = [ "workspace" ]
                }
            ]
        Commands =
            [
                command "workspace.mode.create" "Create mode" CommandTriggerPolicy.OncePerPress
                command "workspace.mode.arrange" "Arrange mode" CommandTriggerPolicy.OncePerPress
                command "workspace.mode.play" "Play mode" CommandTriggerPolicy.OncePerPress
                command "workspace.mode.review" "Review mode" CommandTriggerPolicy.OncePerPress
                command "workspace.palette" "Open command palette" CommandTriggerPolicy.OncePerPress
                command "workspace.help" "Open possible input help" CommandTriggerPolicy.OncePerPress
                command "workspace.rebind" "Rebind command" CommandTriggerPolicy.OncePerPress
                command "workspace.pointer" "Pointer workspace action" CommandTriggerPolicy.OncePerPress
                command "workspace.touch" "Touch workspace action" CommandTriggerPolicy.OncePerPress
                command "workspace.gamepad" "Gamepad workspace action" CommandTriggerPolicy.OncePerPress
            ]
        ReservedGestures = []
        AllowTerminalPrefixes = false
    }

let private mods = CommandInput.noModifiers
let private ctrl = { mods with Ctrl = true }
let private meta = { mods with Meta = true }

let profile =
    {
        Schema = CommandInput.profileSchema
        Id = "generated-workspace"
        Defaults =
            [
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "1", mods)
                    Command = "workspace.mode.create"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "2", mods)
                    Command = "workspace.mode.arrange"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "3", mods)
                    Command = "workspace.mode.play"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "4", mods)
                    Command = "workspace.mode.review"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "k", ctrl)
                    Command = "workspace.palette"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "k", meta)
                    Command = "workspace.palette"
                    Context = "workspace"
                }
                {
                    Gesture =
                        InputGesture.KeySequence
                            [ InputKeyIdentity.LogicalKey "g", mods; InputKeyIdentity.LogicalKey "h", mods ]
                    Command = "workspace.help"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.KeyChord(InputKeyIdentity.LogicalKey "r", mods)
                    Command = "workspace.rebind"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.Pointer "primary"
                    Command = "workspace.pointer"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.Touch "primary"
                    Command = "workspace.touch"
                    Context = "workspace"
                }
                {
                    Gesture = InputGesture.Gamepad "button-0"
                    Command = "workspace.gamepad"
                    Context = "workspace"
                }
            ]
        Overrides = []
    }

let compile value = CommandInput.compile catalog value
