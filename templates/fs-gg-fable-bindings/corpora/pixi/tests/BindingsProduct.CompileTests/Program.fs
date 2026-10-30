open Fable.Core
open Qualification.Pixi

// Test-only promise, DOM and event-boundary helpers; the binding itself exposes only Pixi calls.
[<Emit("if (typeof document !== 'undefined') document.querySelector('output').textContent = $0")>]
let private mark (text: string) : unit = jsNative

[<Emit("$0.then($1)")>]
let private andThen (promise: JS.Promise<'T>) (continuation: 'T -> JS.Promise<'U>) : JS.Promise<'U> = jsNative

[<Emit("Promise.resolve($0)")>]
let private resolved (value: 'T) : JS.Promise<'T> = jsNative

[<Emit("new Promise((resolve) => setTimeout(resolve, $0))")>]
let private delay (milliseconds: int) : JS.Promise<unit> = jsNative

[<Emit("$0.catch((error) => { console.error(error); if (typeof document !== 'undefined') document.querySelector('output').textContent = 'Pixi smoke failed: ' + error; if (typeof process !== 'undefined') process.exitCode = 1; })")>]
let private reportFailure (promise: JS.Promise<unit>) : unit = jsNative

/// Event dispatch without a DOM: a real EventBoundary hit-tests `root` and dispatches a real
/// FederatedPointerEvent. Returns whether the event found a target.
[<Import("EventBoundary", "pixi.js"); Emit("new $0($1)")>]
let private boundaryFor (root: Container) : obj = jsNative

[<Import("FederatedPointerEvent", "pixi.js"); Emit("(() => { const e = new $0($1); e.global.set($3, $4); e.button = 0; e.pointerType = 'mouse'; e.target = $1.hitTest($3, $4); e.type = $2; if (e.target) $1.dispatchEvent(e, $2); return e.target !== null })()")>]
let private dispatchPointer (boundary: obj) (kind: string) (x: float) (y: float) : bool = jsNative

/// Real DOM pointer events on the page's canvas; Pixi's EventSystem maps them to the stage.
[<Emit("(() => { const r = $0.getBoundingClientRect(); $0.dispatchEvent(new PointerEvent($1, { clientX: r.left + $2, clientY: r.top + $3, pointerId: 1, pointerType: 'mouse', isPrimary: true, button: 0, buttons: 1, bubbles: true })) })()")>]
let private domPointer (canvas: Canvas) (kind: string) (x: float) (y: float) : unit = jsNative

/// The WebGL driver's unmasked renderer string, so the evidence says which device drew the frame.
[<Emit("(() => { const gl = $0.renderer.gl; const info = gl.getExtension('WEBGL_debug_renderer_info'); return info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER) })()")>]
let private glRenderer (app: Application) : string = jsNative

let private expect condition message =
    if not condition then failwith message

let private near (expected: float) (actual: float) = abs (expected - actual) < 1e-6

/// 2x2 opaque red PNG, so Assets can decode a real image without a server.
let private redPng =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEUlEQVR4nGP4z8DwH4QZYAwAR8oH+WdZbrcAAAAASUVORK5CYII="

/// A module-level function. Fable wraps it in a new JavaScript closure at every use site, so only
/// the returned subscription (not the name) identifies the listener Pixi holds.
let private moduleLevelCalls = ref 0
let private moduleLevelStep (_: Ticker) = moduleLevelCalls.Value <- moduleLevelCalls.Value + 1

/// Representative workload: a sprite field, the scale a small 2D game scene reaches.
let private spriteField = 1000
let private columns = 40

/// Deterministic journey without a renderer: the same in Node and Chromium.
let private headless () =
    enableEvents ()
    expect (eventsRegistered ()) "pixi.js/events side-effect import did not register the event mixin"

    // Textures: shared, empty and a frame of an existing source.
    let white = whiteTexture ()
    expect (textureWidth white = 1. && textureHeight white = 1.) "the white texture is not 1x1"
    expect (textureWidth (emptyTexture ()) = 1.) "the empty texture is not 1x1"
    let cell = textureFrame white (rectangle 0. 0. 1. 1.)
    expect (textureWidth cell = 1.) "the sub-texture frame was not applied"

    // Scene graph: a 1,000-sprite field in one container, sized and tinted per cell.
    let world = container ()
    setLabel world "world"
    for i in 0 .. spriteField - 1 do
        let s = sprite white
        setSize s 8. 8.
        setPosition s (float (i % columns) * 10.) (float (i / columns) * 10.)
        setTint s (0x010101 * (i % 255))
        addChild world s
    expect (childCount world = spriteField) "the sprite field did not add every child"
    let field = boundsOf world
    expect (near 398. (rectangleWidth field) && near 248. (rectangleHeight field)) "sprite field bounds are not the expected 398x248"
    expect (near 0. (rectangleX field) && near 0. (rectangleY field)) "sprite field bounds do not start at the origin"
    let first = childAt world 0
    expect (not (isNull (parentOf first))) "child has no parent"
    setPosition world 100. 50.
    let moved = boundsOf world
    expect (near 100. (rectangleX moved) && near 50. (rectangleY moved)) "container position did not move its bounds"
    setScale world 2. 2.
    expect (near 796. (rectangleWidth (boundsOf world))) "container scale did not scale its bounds"
    setPosition world 0. 0.
    setScale world 1. 1.
    setVisible world false
    setAlpha world 0.5
    setRotation world 0.
    setPivot world 0. 0.
    setZIndex world 3
    setSortableChildren world true
    removeChild world first
    expect (childCount world = spriteField - 1 && isNull (parentOf first)) "removeChild did not detach the child"
    removeChildren world
    expect (childCount world = 0) "removeChildren left children"

    // Graphics: a path is built, filled and stroked; bounds follow the geometry.
    let shape = graphics ()
    rect shape 10. 20. 30. 40.
    fill shape 0xff0000 1.
    expect (near 30. (rectangleWidth (boundsOf shape)) && near 40. (rectangleHeight (boundsOf shape))) "rect fill bounds are wrong"
    clearGraphics shape
    circle shape 50. 50. 10.
    fill shape 0x00ff00 0.5
    expect (near 20. (rectangleWidth (boundsOf shape))) "circle bounds are wrong"
    clearGraphics shape
    roundRect shape 0. 0. 20. 10. 3.
    ellipse shape 40. 5. 8. 4.
    polygon shape [| 60.; 0.; 70.; 0.; 65.; 10. |]
    moveTo shape 80. 0.
    lineTo shape 90. 10.
    closePath shape
    stroke shape 2. 0x0000ff
    expect (rectangleWidth (boundsOf shape) > 60.) "composite path has no extent"
    clearGraphics shape
    expect (rectangleWidth (boundsOf shape) = 0.) "clear left geometry"
    destroyNode shape false

    // Text: content and style mutate without a layout pass (measuring needs a document).
    let label = text "score" 0xffffff 24. "monospace"
    expect (textContent label = "score") "text content was not applied"
    setText label "score: 10"
    setTextFill label 0xffcc00
    setFontSize label 32.
    expect (textContent label = "score: 10") "setText did not update the content"

    // Events: mode, listeners, a real hit test and dispatch through an EventBoundary.
    let stageRoot = container ()
    let button = graphics ()
    rect button 0. 0. 50. 50.
    fill button 0x336699 1.
    setEventMode button "static"
    setCursor button "pointer"
    expect (eventMode button = "static") "eventMode was not set"
    let downs = ref 0
    let lastX = ref -1.
    let onDown (e: FederatedPointerEvent) =
        downs.Value <- downs.Value + 1
        lastX.Value <- eventGlobalX e
    let downSubscription = onEvent button "pointerdown" onDown
    expect (listenerCount button "pointerdown" = 1) "listener was not registered"
    addChild stageRoot button
    let boundary = boundaryFor stageRoot
    expect (dispatchPointer boundary "pointerdown" 25. 25.) "pointer inside the node found no target"
    expect (downs.Value = 1 && near 25. lastX.Value) "pointerdown listener did not run with the event position"
    expect (not (dispatchPointer boundary "pointerdown" 200. 200.)) "pointer outside the node hit something"
    expect (downs.Value = 1) "listener ran for a miss"
    setHitArea button (rectangle 100. 100. 10. 10.)
    expect (not (dispatchPointer boundary "pointerdown" 25. 25.)) "hit area did not replace the geometry"
    expect (dispatchPointer boundary "pointerdown" 105. 105.) "hit area did not receive the pointer"
    expect (downs.Value = 2) "listener did not run for the hit area"
    offEvent button "pointerdown" downSubscription
    expect (listenerCount button "pointerdown" = 0) "listener was not removed"
    let fired = ref 0
    onceEvent button "custom" (fun _ -> fired.Value <- fired.Value + 1) |> ignore
    expect (emitEvent button "custom" 1) "emit reported no listener"
    expect (not (emitEvent button "custom" 1)) "once listener ran twice"
    expect (fired.Value = 1) "once listener count is wrong"
    removeAllListeners button
    destroyNode stageRoot true

    // Ticker: a manual ticker advances deterministically; listeners get the frame times.
    let clock = ticker ()
    expect (not (tickerStarted clock)) "a new ticker must start stopped"
    let mover = sprite white
    let frames = ref 0
    let travelled = ref 0.
    let step (t: Ticker) =
        frames.Value <- frames.Value + 1
        travelled.Value <- travelled.Value + deltaMs t * 0.1
        setPosition mover travelled.Value 0.
    let stepSubscription = addTicker clock step
    let once = ref 0
    addTickerOnce clock (fun _ -> once.Value <- once.Value + 1) |> ignore
    expect (tickerListenerCount clock = 2) "ticker listener count is wrong"
    updateTicker clock 1000.
    for frame in 1 .. 59 do
        updateTicker clock (1000. + float frame * 16.)
    expect (frames.Value = 60 && once.Value = 1) "ticker did not run every listener per update"
    expect (tickerListenerCount clock = 1) "addOnce listener stayed registered"
    expect (near 16. (deltaMs clock) && near 16. (elapsedMs clock)) "ticker frame time is wrong"
    // The first frame is capped at 100 ms (minFPS 10); the remaining 59 frames are 16 ms each.
    expect (near 104.4 travelled.Value) "listener did not accumulate the capped and scaled frame times"
    expect (positionX mover = travelled.Value) "the ticker-driven sprite did not move"
    setTickerSpeed clock 0.5
    updateTicker clock 1960.
    expect (near 8. (deltaMs clock) && near 16. (elapsedMs clock)) "speed must scale deltaMs but not elapsedMs"
    removeTicker clock stepSubscription
    expect (tickerListenerCount clock = 0) "removeTicker left the listener"
    let second = ticker ()
    let moduleLevel = addTicker second moduleLevelStep
    updateTicker second 1000.
    removeTicker second moduleLevel
    expect (tickerListenerCount second = 0) "removing a module-level listener by its subscription left it registered"
    updateTicker second 1016.
    expect (moduleLevelCalls.Value = 1) "a removed module-level listener still ran"
    setMaxFps clock 60.
    setMinFps clock 10.
    expect (framesPerSecond clock >= 0.) "ticker FPS is not available"
    expect (not (isNull (sharedTicker ()))) "the shared ticker is missing"

    // Assets: aliases are registered, and nothing is cached before a load.
    addAsset "red" redPng
    expect (not (assetCached "red")) "an unloaded asset is cached"
    expect (isNull (getAsset "red")) "an unloaded asset returned a texture"

    printfn "headless workload sprites=%d children=%d bounds=%gx%g tickerFrames=%d" spriteField spriteField (rectangleWidth field) (rectangleHeight field) frames.Value
    resolved ()

/// Browser-only: a real renderer draws, a real pointer reaches the stage, the application
/// ticker runs, an image asset loads, and WebGPU initialises when the browser supports it.
/// Outside a document there is no canvas and this is skipped.
let private browser () =
    let canvas = canvasById "renderCanvas"
    if isNull canvas then
        resolved ()
    else
        let app = application ()
        andThen (initApplication app canvas 320 240 0x102030 false "webgl") (fun () ->
            expect (rendererName app = "webgl") "the application did not create a WebGL renderer"
            expect (screenWidth app = 320. && screenHeight app = 240.) "the screen is not the requested size"
            let root = stage app
            let panel = graphics ()
            rect panel 20. 20. 100. 60.
            fill panel 0xff0000 1.
            setEventMode panel "static"
            let clicks = ref 0
            let localX = ref -1.
            onEvent panel "pointerdown" (fun e ->
                clicks.Value <- clicks.Value + 1
                localX.Value <- pointX (eventLocalPosition e panel)) |> ignore
            addChild root panel
            let swatch = createCanvas 16 16
            fillCanvas swatch 0x00ff00
            let green = sprite (textureFromCanvas swatch)
            setPosition green 200. 100.
            addChild root green
            let caption = text "Pixi" 0xffffff 24. "sans-serif"
            setPosition caption 20. 150.
            addChild root caption
            renderApplication app
            // Layout needs a font: a host with none (a bare headless Chromium) measures a width of 0,
            // so the width is compared only when it can be measured. The height always scales.
            let width = textWidth caption
            let height = textHeight caption
            expect (height > 0.) "text was not laid out"
            setText caption "Pixi 2D renderer"
            expect (textWidth caption >= width) "longer text must not be narrower"
            if width > 0. then expect (textWidth caption > width) "longer text did not widen"
            setFontSize caption 48.
            expect (textHeight caption > height) "a larger font did not increase the text height"
            setFontSize caption 24.
            renderApplication app
            let px (x, y) = readPixel app x y
            expect (px (60, 50) = [| 255; 0; 0; 255 |]) "the red rectangle was not rendered"
            expect (px (205, 105) = [| 0; 255; 0; 255 |]) "the canvas-backed sprite was not rendered"
            // Extraction renders the stage on its own, so an empty position is transparent (the renderer background is not part of it).
            expect (px (300, 220) = [| 0; 0; 0; 0 |]) "an empty stage position was not transparent"
            // Move the panel so the local position differs from the canvas position.
            setPosition panel 10. 0.
            // Pointer events hit-test the last rendered frame, and pixel extraction renders its own copy.
            renderApplication app
            domPointer (applicationCanvas app) "pointerdown" 60. 50.
            expect (clicks.Value = 1) "a DOM pointer event did not reach the stage listener"
            expect (near 50. localX.Value) "the event local position is not relative to the panel"
            domPointer (applicationCanvas app) "pointerdown" 300. 220.
            expect (clicks.Value = 1) "a pointer miss reached the listener"
            let appFrames = ref 0
            addTicker (applicationTicker app) (fun _ -> appFrames.Value <- appFrames.Value + 1) |> ignore
            andThen (delay 200) (fun () ->
                expect (appFrames.Value > 0) "the application ticker never ran"
                andThen (loadTexture redPng) (fun texture ->
                    expect (textureWidth texture = 2. && textureHeight texture = 2.) "the PNG asset did not decode to 2x2"
                    expect (assetCached redPng) "the loaded asset is not cached"
                    let red = sprite texture
                    setSize red 20. 20.
                    setPosition red 250. 20.
                    addChild root red
                    renderApplication app
                    expect (px (255, 25) = [| 255; 0; 0; 255 |]) "the loaded image was not rendered"
                    andThen (unloadAsset redPng) (fun () ->
                        removeChild root red
                        printfn "browser workload stageChildren=%d appFrames=%d renderer=%s" (childCount root) appFrames.Value (rendererName app)
                        printfn "webgl device=%s" (glRenderer app)
                        destroyApplication app
                        // Preferring WebGPU initialises a WebGPU renderer where the browser supports it and
                        // falls back to WebGL where it does not, so both outcomes prove the preference.
                        andThen (webGpuSupported ()) (fun supported ->
                            printfn "webgpu supported=%b" supported
                            let preferred = application ()
                            andThen (initApplication preferred (canvasById "gpuCanvas") 320 240 0x203040 false "webgpu") (fun () ->
                                expect (rendererName preferred = (if supported then "webgpu" else "webgl")) "the renderer preference was not honoured"
                                destroyApplication preferred
                                resolved ()))))))

andThen (headless ()) (fun () -> browser ())
|> fun journey -> andThen journey (fun () ->
    mark "Pixi browser smoke passed"
    printfn "curated Pixi binding compile smoke passed"
    resolved ())
|> reportFailure
