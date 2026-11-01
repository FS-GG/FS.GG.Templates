namespace FableGameWorkspaceNamespace.Client

open Browser.Dom
open Browser.Types
open FS.GG.Game.Core
open FS.GG.Game.Render
open FS.GG.Game.Render.Browser

/// The game page's renderer stage (GAME-RENDER-ADOPT, FS.GG.Templates#840).
///
/// `index.html` offers the arena two ways: the DOM grid `App.view` maintains (the default, and the page the existing
/// journeys drive), and the same arena drawn by the SVG, Pixi or Babylon renderers of `Renderers.fs`. The selector
/// `#renderer-backend` switches between them at run time. The game state is the Elmish `App.Model`, so a switch keeps it
/// whatever the surface: the stage only presents the model it is given and turns the player's selections back into the
/// messages the DOM grid dispatches, so the server stays the only authority for movement.
///
/// A selection on a renderer surface (a pointer press on a cell, the keyboard, or a button of the accessible mirror) is a
/// `SelectionRequest`; `Select` becomes `CellClicked`, exactly what a click or Enter on a DOM grid cell does, and `Clear`
/// (Escape) becomes `SelectionCleared`.
module Stage =

    type private Running =
        {
            Driver: RendererDriver<App.Model>
            Selection: SelectionRoute
        }

    let mutable private running: Running option = None
    let mutable private latest: App.Model option = None
    let mutable private latestDispatch: (App.Msg -> unit) option = None
    let mutable private bound = false

    let private element (id: string) : HTMLElement option =
        match document.getElementById id with
        | null -> None
        | found -> Some found

    let private setText (id: string) (text: string) =
        match element id with
        | Some found when found.textContent <> text -> found.textContent <- text
        | _ -> ()

    let private show (id: string) (visible: bool) =
        match element id with
        | Some found ->
            if visible then
                found.removeAttribute "hidden"
            else
                found.setAttribute ("hidden", "")
        | None -> ()

    /// What the page says about the renderer in use: the backend, and why the one asked for is not the one drawing.
    let private describe (model: RendererModel<App.Model>) : string =
        let backend = RendererBackend.id model.Selected

        match model.Refusal with
        | None -> sprintf "Renderer: %s" backend
        | Some refusal -> sprintf "Renderer: %s (%A)" backend refusal

    let private onChange (model: RendererModel<App.Model>) : unit =
        match element "renderer-backend" with
        | Some (:? HTMLSelectElement as selector) ->
            let wanted = RendererBackend.id model.Selected

            if selector.value <> wanted then
                selector.value <- wanted
        | _ -> ()

        setText "renderer-status" (describe model)

    let private stop () : unit =
        match running with
        | Some live ->
            SelectionRoute.unbind live.Selection
            (live.Driver :> System.IDisposable).Dispose()
            running <- None
        | None -> ()

    let private start (model: App.Model) (dispatch: App.Msg -> unit) : Running option =
        match element "renderer-stage" with
        | None -> None
        | Some stage ->
            let selection = SelectionRoute.create ()
            let driver = Renderers.start stage model selection onChange

            selection
            |> SelectionRoute.bind (fun request ->
                match request with
                | SelectionRequest.Select id ->
                    match Renderers.tryCell id with
                    | Some cell -> dispatch (App.CellClicked cell)
                    | None -> ()
                | SelectionRequest.Clear -> dispatch App.SelectionCleared)

            let live = { Driver = driver; Selection = selection }
            running <- Some live
            Some live

    /// The selector's value is `grid` or a renderer backend's id.
    let private choose (value: string) : unit =
        match latest, latestDispatch with
        | Some model, Some dispatch ->
            if value = "grid" then
                stop ()
                show "arena" true
                show "renderer-stage" false
                setText "renderer-status" "Renderer: DOM grid"
            else
                show "arena" false
                show "renderer-stage" true

                let live =
                    match running with
                    | Some live -> Some live
                    | None -> start model dispatch

                match live, RendererBackend.all |> List.tryFind (fun backend -> RendererBackend.id backend = value) with
                | Some live, Some backend -> live.Driver.Dispatch(RendererMsg.SelectBackend backend)
                | _ -> ()
        | _ -> ()

    let private bind () : unit =
        if not bound then
            match element "renderer-backend" with
            | Some selector ->
                bound <- true
                selector.addEventListener ("change", fun _ -> choose (selector :?> HTMLSelectElement).value)
            | None -> ()

    /// Called after every model update with the model the page now shows: binds the selector once, and keeps the running
    /// renderers (if any) presenting the model.
    let present (model: App.Model) (dispatch: App.Msg -> unit) : unit =
        latest <- Some model
        latestDispatch <- Some dispatch
        bind ()

        match running with
        | Some live -> live.Driver.Dispatch(RendererMsg.StateChanged model)
        | None -> ()
