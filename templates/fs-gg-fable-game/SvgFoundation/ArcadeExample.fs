module FableGameWorkspaceNamespace.SvgFoundation.ArcadeExample

open System
open Browser.Dom
open Browser.Types
open Fable.Core
open Fable.Core.JsInterop
open FS.GG.Game.Core
open FS.GG.UI.KeyboardInput
open FS.GG.UI.Scene
open FS.GG.UI.Scene.SvgBrowser
open FS.GG.Audio.Core
open FS.GG.Audio.WebBrowser
open FableGameWorkspaceNamespace.ArcadeRules

[<ImportDefault("./Examples/Arcade/scene.json?raw")>]
let private seedJson: string = jsNative

[<Literal>]
let private seedSha256 =
    "692ca87a93aceba48da8d6f13c48610d4edf556ed49ef5cb974f3f1edd7db435"

let private rawSeed: obj = JS.JSON.parse seedJson
let private number (value: obj) = unbox<float> value

[<Emit("$0[$1]")>]
let private index (_values: obj) (_index: int) : obj = jsNative

let private seed =
    let obstacle = index (rawSeed?movingObstacles) 0
    let collectible = index (rawSeed?collectibles) 0

    {
        Id = unbox<string> rawSeed?id
        ContentId = $"sha256:{seedSha256}"
        Width = number rawSeed?arena?width
        Height = number rawSeed?arena?height
        Spawn =
            {
                X = number rawSeed?player?x
                Y = number rawSeed?player?y
                Width = 10.0
                Height = 10.0
            }
        InitialHealth = unbox<int> rawSeed?player?health
        CollectibleX = number collectible?x
        CollectibleY = number collectible?y
        CollectibleScore = unbox<int> collectible?score
        Hazard =
            {
                X = number obstacle?x
                Y = number obstacle?y
                Width = 18.0
                Height = 12.0
            }
        HazardVelocity = number obstacle?dx
        HazardDamage = unbox<int> obstacle?healthCost
        Goal =
            {
                X = number rawSeed?goal?x
                Y = number rawSeed?goal?y
                Width = 16.0
                Height = 18.0
            }
    }

let private compatibility = compatibilityFor seed
let private contract = contractForDefinition seed

let private initialize () =
    SessionRuntime.initialize
        {
            StepMicroseconds = 16_667UL
            MaxCatchUpSteps = 4u
        }
        contract
        {
            SessionId = seed.Id
            Compatibility = compatibility
            Configuration = ()
        }
    |> Result.defaultWith (fun error -> failwithf "Selected arcade session could not initialize: %A" error)

let private color r g b =
    {
        Red = r
        Green = g
        Blue = b
        Alpha = 255uy
    }

let private item id label nodes =
    {
        Id = id
        Selectable = true
        AccessibleLabel = label
        Content = { Nodes = nodes }
    }

let private scene state =
    let outcome =
        match state.Outcome with
        | ArcadeOutcome.Playing -> "playing"
        | ArcadeOutcome.Won -> "won"
        | ArcadeOutcome.Lost -> "lost"

    let content = state.Content

    {
        RootId = "selected-arcade-scene"
        Revision = int state.Revision
        Camera = { PanX = 0.0; PanY = 0.0; Zoom = 1.0 }
        Layers =
            [
                {
                    Id = "arcade"
                    Visible = true
                    Objects =
                        [
                            item
                                "arcade-player"
                                $"Arcade player, {outcome}, health {state.Health}, score {state.Score}"
                                [
                                    SceneNode.Rectangle(
                                        (state.Player.X, state.Player.Y, state.Player.Width, state.Player.Height),
                                        color 37uy 99uy 235uy
                                    )
                                ]
                            if not state.Collected then
                                item
                                    "arcade-collectible"
                                    "Arcade collectible"
                                    [
                                        SceneNode.Circle(
                                            {
                                                X = content.CollectibleX
                                                Y = content.CollectibleY
                                            },
                                            5.0,
                                            color 245uy 158uy 11uy
                                        )
                                    ]
                            item
                                "arcade-hazard"
                                "Arcade moving obstacle"
                                [
                                    SceneNode.Rectangle(
                                        (state.HazardX, content.Hazard.Y, content.Hazard.Width, content.Hazard.Height),
                                        color 220uy 38uy 38uy
                                    )
                                ]
                            item
                                "arcade-goal"
                                "Arcade goal"
                                [
                                    SceneNode.Rectangle(
                                        (content.Goal.X, content.Goal.Y, content.Goal.Width, content.Goal.Height),
                                        color 22uy 163uy 74uy
                                    )
                                ]
                        ]
                }
            ]
    }

let private command id label trigger =
    {
        Id = id
        Label = label
        Contexts = [ "arcade.play" ]
        AvailabilityKey = None
        Trigger = trigger
        Argument = CommandArgumentPolicy.NoArgument
        Alternatives = [ CommandAlternative.Pointer label ]
    }

let private inputCatalog =
    {
        Contexts =
            [
                {
                    Id = "arcade.play"
                    Priority = 10
                    Exclusive = false
                    Overlaps = []
                }
            ]
        Commands =
            [
                command "arcade.up" "Arcade move up" CommandTriggerPolicy.Continuous
                command "arcade.down" "Arcade move down" CommandTriggerPolicy.Continuous
                command "arcade.left" "Arcade move left" CommandTriggerPolicy.Continuous
                command "arcade.right" "Arcade move right" CommandTriggerPolicy.Continuous
                command "arcade.interact" "Arcade interact" CommandTriggerPolicy.OncePerPress
                command "arcade.restart" "Arcade restart" CommandTriggerPolicy.OncePerPress
            ]
        ReservedGestures = []
        AllowTerminalPrefixes = false
    }

let private noModifiers =
    {
        Ctrl = false
        Meta = false
        Alt = false
        Shift = false
        AltGraph = false
    }

let private binding gesture command =
    {
        Gesture = gesture
        Command = command
        Context = "arcade.play"
    }

let private key value =
    InputGesture.KeyChord(InputKeyIdentity.LogicalKey value, noModifiers)

let private inputProfile =
    {
        Schema = CommandInput.profileSchema
        Id = "selected-arcade"
        Defaults =
            [
                yield binding (key "w") "arcade.up"
                yield binding (key "ArrowUp") "arcade.up"
                yield binding (key "s") "arcade.down"
                yield binding (key "ArrowDown") "arcade.down"
                yield binding (key "a") "arcade.left"
                yield binding (key "ArrowLeft") "arcade.left"
                yield binding (key "d") "arcade.right"
                yield binding (key "ArrowRight") "arcade.right"
                for action in [ "up"; "down"; "left"; "right"; "interact"; "restart" ] do
                    yield binding (InputGesture.Pointer action) ("arcade." + action)
                    yield binding (InputGesture.Touch action) ("arcade." + action)
                yield binding (InputGesture.Gamepad "button-0") "arcade.interact"
            ]
        Overrides = []
    }

[<Emit("Array.from(navigator.getGamepads ? navigator.getGamepads() : []).filter(p => p && p.connected).map(p => ['gamepad-axis:' + p.index, Number(p.axes[0] || 0), Number(p.axes[1] || 0)])")>]
let private gamepadAxes () : (string * float * float) array = jsNative

let mount () : IDisposable =
    let root: HTMLElement = document.createElement ("section")
    root.id <- "selected-arcade-example"
    root.setAttribute ("aria-label", "Selected editable arcade example")
    root.setAttribute ("tabindex", "0")
    document.body.appendChild root |> ignore
    let canvas: HTMLElement = document.createElement ("div")
    root.appendChild canvas |> ignore
    let mutable runtime = initialize ()
    let mutable sequence = 0UL
    let mutable presentationRevision = 0UL
    let mutable sessionHost: SvgSessionHost<ArcadeState> option = None
    let mutable held = Map.empty<string, bool>
    let mutable axes = Map.empty<string, FS.GG.Game.Core.Point>
    let mutable disposed = false

    let svgHost =
        SvgBrowser.mount
            canvas
            {
                Width = seed.Width
                Height = seed.Height
                AccessibleLabel = "Continuous arcade example"
                WheelZoomFactor = 1.1
            }
            (scene runtime.Current)
            ignore
        |> Result.defaultWith (fun error -> failwithf "%A" error)

    let audio = new WebAudioHost(WebAudioHost.defaultConfig, ignore)
    let movementSound = SoundId "selected-arcade-movement"
    let unlock: HTMLElement = document.createElement ("button")
    unlock.textContent <- "Enable arcade audio"

    unlock.addEventListener (
        "click",
        fun _ ->
            audio.UnlockFromGesture()
            audio.LoadSound(movementSound, "./movement-cue.wav")
    )

    root.appendChild unlock |> ignore

    let animationCallbacks =
        {
            ApplySample =
                fun _ _ revision sample ->
                    let player = svgHost.Root.querySelector ("[data-scene-object-id='arcade-player']")

                    match sample.Values |> Map.tryFind Opacity with
                    | Some(ScalarValue value) -> player.setAttribute ("opacity", string value)
                    | _ -> ()

                    root.setAttribute ("data-animation-revision", string revision)
            DispatchCues =
                fun _ _ cues ->
                    if not cues.IsEmpty then
                        audio.Dispatch(FS.GG.Audio.Core.Audio.playSfx movementSound 0.35)
                        root.setAttribute ("data-audio-effect-dispatched", "true")
            Refused = fun refusal -> root.setAttribute ("data-animation-refusal", string refusal)
            Dispose = ignore
        }

    let animation =
        new SvgAnimationHost(animationCallbacks, SvgAnimationHost.defaultConfig, runtime.Current.Revision)

    let describe state =
        let outcome =
            match state.Outcome with
            | ArcadeOutcome.Playing -> "playing"
            | ArcadeOutcome.Won -> "won"
            | ArcadeOutcome.Lost -> "lost"

        root.setAttribute ("data-session-id", seed.Id)
        root.setAttribute ("data-revision", string state.Revision)
        root.setAttribute ("data-x", string state.Player.X)
        root.setAttribute ("data-y", string state.Player.Y)
        root.setAttribute ("data-health", string state.Health)
        root.setAttribute ("data-score", string state.Score)
        root.setAttribute ("data-outcome", outcome)
        root.setAttribute ("data-hazard-x", string state.HazardX)
        root.setAttribute ("data-motion-preference", string (animation.Observe().MotionPreference))

    let update observation =
        let next, _ = SessionRuntime.update contract observation runtime in runtime <- next

    let project () =
        sessionHost |> Option.iter _.DemandProjection()

    let admit command =
        sequence <- sequence + 1UL

        update (
            SessionRuntimeObservation.AdmitInput
                {
                    SessionId = seed.Id
                    InputId = $"arcade:{sequence}"
                    Sequence = sequence
                    Value = command
                }
        )

    let submit command =
        admit command
        project ()

    let combinedVelocity () : FS.GG.Game.Core.Point =
        let x =
            (if held |> Map.tryFind "arcade.right" |> Option.defaultValue false then
                 2.25
             else
                 0.0)
            - (if held |> Map.tryFind "arcade.left" |> Option.defaultValue false then
                   2.25
               else
                   0.0)

        let y =
            (if held |> Map.tryFind "arcade.down" |> Option.defaultValue false then
                 2.25
             else
                 0.0)
            - (if held |> Map.tryFind "arcade.up" |> Option.defaultValue false then
                   2.25
               else
                   0.0)

        let axis =
            axes
            |> Map.toList
            |> List.tryHead
            |> Option.map snd
            |> Option.defaultValue ({ X = 0.0; Y = 0.0 }: FS.GG.Game.Core.Point)

        ({
            X = (if abs axis.X > 0.2 then axis.X * 2.25 else x)
            Y = (if abs axis.Y > 0.2 then axis.Y * 2.25 else y)
        }
        : FS.GG.Game.Core.Point)

    let refreshAxes () =
        let current =
            gamepadAxes ()
            |> Array.map (fun (source, x, y) -> source, ({ X = x; Y = y }: FS.GG.Game.Core.Point))
            |> Map.ofArray

        if current <> axes then
            axes <- current
            admit (ArcadeCommand.SetVelocity(combinedVelocity ()))

        root.setAttribute ("data-gamepad-source-count", string axes.Count)

    let mutable previousOutcome = runtime.Current.Outcome
    let mutable previousMoving = false

    let callbacks =
        {
            AdvanceElapsed =
                fun elapsed ->
                    refreshAxes ()
                    update (SessionRuntimeObservation.AdvanceElapsed elapsed)
                    project ()
            Pause = fun () -> update SessionRuntimeObservation.Pause
            Resume = fun () -> update SessionRuntimeObservation.Resume
            StepOnce =
                fun () ->
                    update SessionRuntimeObservation.StepOnce
                    project ()
            Reset =
                fun () ->
                    update SessionRuntimeObservation.Reset
                    project ()
            RequestRecovery =
                fun _ ->
                    window.setTimeout ((fun () -> sessionHost |> Option.iter _.Resume()), 0)
                    |> ignore
            RequestProjection =
                fun generation ->
                    presentationRevision <- presentationRevision + 1UL

                    sessionHost
                    |> Option.iter (fun host ->
                        host.CompleteProjection(generation, presentationRevision, runtime.Current))
            ApplyProjection =
                fun revision state ->
                    svgHost.Dispatch(RetainedInteractionMessage.ReplaceScene(scene state)) |> ignore
                    let moving = state.Velocity.X <> 0.0 || state.Velocity.Y <> 0.0

                    if moving && not previousMoving then
                        animation.ReplaceAuthority revision

                        animation.Start(
                            {
                                Id = $"arcade-move-{revision}"
                                AuthorityRevision = revision
                                Clip = PresentationPlayer.movementClip
                                Importance = Decorative SvgReducedMotionBehavior.Settle
                            }
                        )

                    if previousOutcome <> state.Outcome then
                        animation.ReplaceAuthority revision

                        animation.Start(
                            {
                                Id = $"arcade-outcome-{revision}"
                                AuthorityRevision = revision
                                Clip = PresentationPlayer.outcomeClip
                                Importance = Essential
                            }
                        )

                    previousMoving <- moving
                    previousOutcome <- state.Outcome
                    describe state
            CancelGeneration = ignore
            Replace = ignore
            Dispose = ignore
        }

    let clock = new SvgSessionHost<ArcadeState>(callbacks, SvgSessionHost.defaultConfig)
    sessionHost <- Some clock

    let effective =
        CommandInput.compile inputCatalog inputProfile
        |> Result.defaultWith (fun issues -> failwithf "Selected arcade input is invalid: %A" issues)

    let isPaused () =
        clock.Observe().Status = SvgSessionStatus.Paused

    let onInput =
        function
        | CommandResolverEffect.HeldActionChanged(command, isHeld) ->
            held <- held |> Map.add command isHeld

            if not (isPaused ()) then
                submit (ArcadeCommand.SetVelocity(combinedVelocity ()))
        | CommandResolverEffect.InvokeCommand invocation when invocation.Command = "arcade.interact" ->
            if isPaused () then
                root.setAttribute ("data-paused-command", "interact-refused")
            else
                submit ArcadeCommand.Interact
        | CommandResolverEffect.InvokeCommand invocation when invocation.Command = "arcade.restart" ->
            submit ArcadeCommand.Restart

            if isPaused () then
                clock.Resume()
                root.setAttribute ("data-paused", "false")
        | _ -> ()

    let input =
        new SvgInputHost(
            root,
            inputCatalog,
            CommandResolver.init [ "arcade.play" ] effective,
            (fun () -> inputCatalog.Commands |> List.map _.Id),
            onInput,
            SvgInputHost.defaultOptions
        )

    let addControl action label =
        let control: HTMLElement = document.createElement ("span")
        control.textContent <- label
        control.setAttribute ("aria-label", label)
        control.setAttribute ("role", "button")
        control.setAttribute ("tabindex", "0")
        control.setAttribute ("data-fsgg-input-action", action)
        root.appendChild control |> ignore

    for action, label in
        [
            "right", "Arcade move right"
            "up", "Arcade move up"
            "down", "Arcade move down"
            "left", "Arcade move left"
            "interact", "Arcade interact"
            "restart", "Arcade restart"
        ] do
        addControl action label

    let pause: HTMLElement = document.createElement ("button")
    pause.textContent <- "Arcade pause"

    pause.addEventListener (
        "click",
        fun _ ->
            if clock.Observe().Status = SvgSessionStatus.Running then
                clock.Pause()
                root.setAttribute ("data-paused", "true")
            else
                clock.Resume()
                root.setAttribute ("data-paused", "false")
    )

    root.appendChild pause |> ignore

    let clearAxes (_: Event) =
        if not axes.IsEmpty then
            axes <- Map.empty
            submit (ArcadeCommand.SetVelocity(combinedVelocity ()))

    window.addEventListener ("gamepaddisconnected", clearAxes)
    window.addEventListener ("blur", clearAxes)
    describe runtime.Current
    root.setAttribute ("data-paused", "false")
    clock.DemandProjection()

    { new IDisposable with
        member _.Dispose() =
            if not disposed then
                disposed <- true
                window.removeEventListener ("gamepaddisconnected", clearAxes)
                window.removeEventListener ("blur", clearAxes)
                (input :> IDisposable).Dispose()
                (clock :> IDisposable).Dispose()
                (animation :> IDisposable).Dispose()
                (audio :> IDisposable).Dispose()
                (svgHost :> IDisposable).Dispose()
    }
