module Qualification.Pixi

open Fable.Core
open Fable.Core.JsInterop

/// Distinct opaque native objects for the curated PixiJS 2D renderer slice.
/// Interfaces have no F# runtime wrapper or implementation to ship as source, so every call
/// below is emitted as a direct native import, property access or method call.
[<AllowNullLiteral>]
type Application = interface end
/// Scene-graph node. `Sprite`, `Graphics` and `Text` are containers, so the container
/// functions accept all of them.
[<AllowNullLiteral>]
type Container = interface end
[<AllowNullLiteral>]
type Sprite =
    inherit Container
[<AllowNullLiteral>]
type Graphics =
    inherit Container
[<AllowNullLiteral>]
type Text =
    inherit Container
[<AllowNullLiteral>]
type Texture = interface end
[<AllowNullLiteral>]
type Ticker = interface end
[<AllowNullLiteral>]
type Rectangle = interface end
[<AllowNullLiteral>]
type Point = interface end
/// The registered listener function, returned by `addTicker`, `onEvent` and friends so it can be
/// removed. Fable turns a module-level F# function passed as an argument into a fresh JavaScript
/// closure at every call site, so removing "the same function" by name would silently remove
/// nothing; the returned subscription is the exact function Pixi holds.
[<AllowNullLiteral>]
type Subscription = interface end
/// The event object handed to pointer, mouse and touch listeners.
[<AllowNullLiteral>]
type FederatedPointerEvent = interface end
/// Browser shim: an `HTMLCanvasElement`. Pixi owns no DOM type, so the binding keeps the
/// canvas opaque instead of depending on a browser binding package.
[<AllowNullLiteral>]
type Canvas = interface end

// Import + Emit metadata is available to a consumer of the compiled binding DLL.
// Every import names the package root `pixi.js`, so a bundler or import map decides which
// build (ESM `lib`, or the self-contained `dist`) satisfies it.

// ── Browser shims ───────────────────────────────────────────────────────────────────────────
/// Browser shim over `document.getElementById`; null when absent or outside a document.
[<Emit("(typeof document === 'undefined' ? null : document.getElementById($0))")>]
let canvasById (id: string) : Canvas = jsNative

/// Browser shim: a detached `<canvas>` of the given pixel size, for drawing a texture source.
[<Emit("(() => { const c = document.createElement('canvas'); c.width = $0; c.height = $1; return c })()")>]
let createCanvas (width: int) (height: int) : Canvas = jsNative

/// Fills a canvas with one opaque colour (0xRRGGBB); a deterministic texture source.
[<Emit("(() => { const g = $0.getContext('2d'); g.fillStyle = '#' + ($1 >>> 0).toString(16).padStart(6, '0'); g.fillRect(0, 0, $0.width, $0.height) })()")>]
let fillCanvas (canvas: Canvas) (color: int) : unit = jsNative

// ── Application and the renderer ────────────────────────────────────────────────────────────
[<Import("Application", "pixi.js"); EmitConstructor>]
let application () : Application = jsNative

/// Asynchronously initialises the renderer on `canvas` (null lets Pixi create one).
/// `preference` is "webgl" or "webgpu"; `background` is 0xRRGGBB.
[<Emit("$0.init({ canvas: ($1 ?? undefined), width: $2, height: $3, background: $4, antialias: $5, preference: $6 })")>]
let initApplication (app: Application) (canvas: Canvas) (width: int) (height: int) (background: int) (antialias: bool) (preference: string) : JS.Promise<unit> = jsNative

/// The root container; everything rendered is a descendant of the stage.
[<Emit("$0.stage")>]
let stage (app: Application) : Container = jsNative

[<Emit("$0.canvas")>]
let applicationCanvas (app: Application) : Canvas = jsNative

/// Name of the renderer that was actually created: "webgl" or "webgpu".
[<Emit("$0.renderer.name")>]
let rendererName (app: Application) : string = jsNative

[<Emit("$0.screen.width")>]
let screenWidth (app: Application) : float = jsNative

[<Emit("$0.screen.height")>]
let screenHeight (app: Application) : float = jsNative

[<Emit("$0.renderer.resize($1, $2)")>]
let resizeRenderer (app: Application) (width: int) (height: int) : unit = jsNative

[<Emit("$0.renderer.background.color = $1")>]
let setBackground (app: Application) (color: int) : unit = jsNative

/// Renders one frame now. The application's ticker also calls this once per frame.
[<Emit("$0.render()")>]
let renderApplication (app: Application) : unit = jsNative

/// The application's own ticker (drives rendering).
[<Emit("$0.ticker")>]
let applicationTicker (app: Application) : Ticker = jsNative

/// Destroys the application, its renderer and every descendant of the stage. The canvas is kept.
[<Emit("$0.destroy({ removeView: false }, { children: true })")>]
let destroyApplication (app: Application) : unit = jsNative

/// Reads one rendered pixel of the stage as [r; g; b; a]. Extraction renders the stage on its own,
/// so a position with no content is transparent: the renderer background is not part of it.
[<Import("Rectangle", "pixi.js"); Emit("Array.from($1.renderer.extract.pixels({ target: $1.stage, frame: new $0($2, $3, 1, 1) }).pixels)")>]
let readPixel (app: Application) (x: int) (y: int) : int array = jsNative

/// Resolves true when this browser can create a WebGPU adapter.
[<Import("isWebGPUSupported", "pixi.js"); Emit("$0()")>]
let webGpuSupported () : JS.Promise<bool> = jsNative

// ── Containers ──────────────────────────────────────────────────────────────────────────────
[<Import("Container", "pixi.js"); EmitConstructor>]
let container () : Container = jsNative

[<Emit("$0.addChild($1)")>]
let addChild (parent: #Container) (child: #Container) : unit = jsNative

[<Emit("$0.removeChild($1)")>]
let removeChild (parent: #Container) (child: #Container) : unit = jsNative

[<Emit("$0.removeChildren()")>]
let removeChildren (parent: #Container) : unit = jsNative

[<Emit("$0.children.length")>]
let childCount (parent: #Container) : int = jsNative

[<Emit("$0.getChildAt($1)")>]
let childAt (parent: #Container) (index: int) : Container = jsNative

[<Emit("$0.parent")>]
let parentOf (child: #Container) : Container = jsNative

[<Emit("$0.position.set($1, $2)")>]
let setPosition (target: #Container) (x: float) (y: float) : unit = jsNative

[<Emit("$0.x")>]
let positionX (target: #Container) : float = jsNative

[<Emit("$0.y")>]
let positionY (target: #Container) : float = jsNative

[<Emit("$0.scale.set($1, $2)")>]
let setScale (target: #Container) (x: float) (y: float) : unit = jsNative

[<Emit("$0.pivot.set($1, $2)")>]
let setPivot (target: #Container) (x: float) (y: float) : unit = jsNative

/// Rotation in radians.
[<Emit("$0.rotation = $1")>]
let setRotation (target: #Container) (radians: float) : unit = jsNative

[<Emit("$0.alpha = $1")>]
let setAlpha (target: #Container) (alpha: float) : unit = jsNative

[<Emit("$0.visible = $1")>]
let setVisible (target: #Container) (visible: bool) : unit = jsNative

[<Emit("$0.zIndex = $1")>]
let setZIndex (target: #Container) (zIndex: int) : unit = jsNative

[<Emit("$0.sortableChildren = $1")>]
let setSortableChildren (parent: #Container) (sortable: bool) : unit = jsNative

[<Emit("$0.label = $1")>]
let setLabel (target: #Container) (label: string) : unit = jsNative

/// Destroys the node; `children` also destroys its descendants.
[<Emit("$0.destroy({ children: $1 })")>]
let destroyNode (target: #Container) (children: bool) : unit = jsNative

/// World-space bounds as a new rectangle.
[<Emit("$0.getBounds().rectangle")>]
let boundsOf (target: #Container) : Rectangle = jsNative

// ── Sprites and textures ────────────────────────────────────────────────────────────────────
[<Import("Sprite", "pixi.js"); EmitConstructor>]
let sprite (texture: Texture) : Sprite = jsNative

[<Emit("$0.anchor.set($1, $2)")>]
let setAnchor (target: Sprite) (x: float) (y: float) : unit = jsNative

/// Tint colour (0xRRGGBB).
[<Emit("$0.tint = $1")>]
let setTint (target: Sprite) (color: int) : unit = jsNative

[<Emit("$0.texture = $1")>]
let setTexture (target: Sprite) (texture: Texture) : unit = jsNative

[<Emit("$0.setSize($1, $2)")>]
let setSize (target: Sprite) (width: float) (height: float) : unit = jsNative

[<Import("Texture", "pixi.js"); Emit("$0.WHITE")>]
let whiteTexture () : Texture = jsNative

[<Import("Texture", "pixi.js"); Emit("$0.EMPTY")>]
let emptyTexture () : Texture = jsNative

/// Texture backed by a canvas source.
[<Import("Texture", "pixi.js"); Emit("$0.from($1)")>]
let textureFromCanvas (canvas: Canvas) : Texture = jsNative

/// Sub-texture: the `frame` rectangle of an existing texture's source (an atlas cell).
[<Import("Texture", "pixi.js"); Emit("new $0({ source: $1.source, frame: $2 })")>]
let textureFrame (texture: Texture) (frame: Rectangle) : Texture = jsNative

[<Emit("$0.width")>]
let textureWidth (texture: Texture) : float = jsNative

[<Emit("$0.height")>]
let textureHeight (texture: Texture) : float = jsNative

/// Destroys the texture; `destroySource` also releases the underlying source.
[<Emit("$0.destroy($1)")>]
let destroyTexture (texture: Texture) (destroySource: bool) : unit = jsNative

// ── Assets ──────────────────────────────────────────────────────────────────────────────────
/// Loads and caches a texture; the URL is also its cache key.
[<Import("Assets", "pixi.js"); Emit("$0.load($1)")>]
let loadTexture (url: string) : JS.Promise<Texture> = jsNative

/// Registers `alias` for `url` without loading it.
[<Import("Assets", "pixi.js"); Emit("$0.add({ alias: $1, src: $2 })")>]
let addAsset (alias: string) (url: string) : unit = jsNative

[<Import("Assets", "pixi.js"); Emit("$0.load($1)")>]
let loadAsset (alias: string) : JS.Promise<Texture> = jsNative

/// The cached texture for an alias or URL; null until it has loaded.
[<Import("Assets", "pixi.js"); Emit("($0.cache.has($1) ? $0.cache.get($1) : null)")>]
let getAsset (alias: string) : Texture = jsNative

[<Import("Assets", "pixi.js"); Emit("$0.cache.has($1)")>]
let assetCached (alias: string) : bool = jsNative

[<Import("Assets", "pixi.js"); Emit("$0.unload($1)")>]
let unloadAsset (alias: string) : JS.Promise<unit> = jsNative

// ── Graphics ────────────────────────────────────────────────────────────────────────────────
// Shape calls build a path; `fill` and `stroke` paint it. Colours are 0xRRGGBB.
[<Import("Graphics", "pixi.js"); EmitConstructor>]
let graphics () : Graphics = jsNative

[<Emit("$0.rect($1, $2, $3, $4)")>]
let rect (target: Graphics) (x: float) (y: float) (width: float) (height: float) : unit = jsNative

[<Emit("$0.roundRect($1, $2, $3, $4, $5)")>]
let roundRect (target: Graphics) (x: float) (y: float) (width: float) (height: float) (radius: float) : unit = jsNative

[<Emit("$0.circle($1, $2, $3)")>]
let circle (target: Graphics) (x: float) (y: float) (radius: float) : unit = jsNative

[<Emit("$0.ellipse($1, $2, $3, $4)")>]
let ellipse (target: Graphics) (x: float) (y: float) (radiusX: float) (radiusY: float) : unit = jsNative

/// Closed polygon from a flat [x0; y0; x1; y1; ...] array.
[<Emit("$0.poly($1, true)")>]
let polygon (target: Graphics) (points: float array) : unit = jsNative

[<Emit("$0.moveTo($1, $2)")>]
let moveTo (target: Graphics) (x: float) (y: float) : unit = jsNative

[<Emit("$0.lineTo($1, $2)")>]
let lineTo (target: Graphics) (x: float) (y: float) : unit = jsNative

[<Emit("$0.closePath()")>]
let closePath (target: Graphics) : unit = jsNative

[<Emit("$0.fill({ color: $1, alpha: $2 })")>]
let fill (target: Graphics) (color: int) (alpha: float) : unit = jsNative

[<Emit("$0.stroke({ width: $1, color: $2 })")>]
let stroke (target: Graphics) (width: float) (color: int) : unit = jsNative

/// Removes all shapes so the object can be redrawn.
[<Emit("$0.clear()")>]
let clearGraphics (target: Graphics) : unit = jsNative

// ── Text ────────────────────────────────────────────────────────────────────────────────────
[<Import("Text", "pixi.js"); Emit("new $0({ text: $1, style: { fill: $2, fontSize: $3, fontFamily: $4 } })")>]
let text (content: string) (fill: int) (fontSize: float) (fontFamily: string) : Text = jsNative

[<Emit("$0.text = $1")>]
let setText (target: Text) (content: string) : unit = jsNative

[<Emit("$0.text")>]
let textContent (target: Text) : string = jsNative

[<Emit("$0.style.fill = $1")>]
let setTextFill (target: Text) (color: int) : unit = jsNative

[<Emit("$0.style.fontSize = $1")>]
let setFontSize (target: Text) (size: float) : unit = jsNative

/// Laid-out width. Measuring needs a document, so this is browser-only. A browser with no
/// usable font measures a width of 0.
[<Emit("$0.width")>]
let textWidth (target: Text) : float = jsNative

/// Laid-out height. Measuring needs a document, so this is browser-only.
[<Emit("$0.height")>]
let textHeight (target: Text) : float = jsNative

// ── Geometry ────────────────────────────────────────────────────────────────────────────────
[<Import("Rectangle", "pixi.js"); EmitConstructor>]
let rectangle (x: float) (y: float) (width: float) (height: float) : Rectangle = jsNative

[<Emit("$0.x")>]
let rectangleX (r: Rectangle) : float = jsNative

[<Emit("$0.y")>]
let rectangleY (r: Rectangle) : float = jsNative

[<Emit("$0.width")>]
let rectangleWidth (r: Rectangle) : float = jsNative

[<Emit("$0.height")>]
let rectangleHeight (r: Rectangle) : float = jsNative

[<Emit("$0.contains($1, $2)")>]
let rectangleContains (r: Rectangle) (x: float) (y: float) : bool = jsNative

[<Import("Point", "pixi.js"); EmitConstructor>]
let point (x: float) (y: float) : Point = jsNative

[<Emit("$0.x")>]
let pointX (p: Point) : float = jsNative

[<Emit("$0.y")>]
let pointY (p: Point) : float = jsNative

// ── Ticker ──────────────────────────────────────────────────────────────────────────────────
/// A new, independent ticker. It is stopped until `startTicker`; `updateTicker` advances it by hand.
[<Import("Ticker", "pixi.js"); EmitConstructor>]
let ticker () : Ticker = jsNative

/// The process-wide shared ticker.
[<Import("Ticker", "pixi.js"); Emit("$0.shared")>]
let sharedTicker () : Ticker = jsNative

/// Registers a per-frame listener and returns the subscription that removes it.
[<Emit("((f) => ($0.add(f), f))($1)")>]
let addTicker (target: Ticker) (listener: Ticker -> unit) : Subscription = jsNative

/// Registers a listener that runs on the next frame only; it can still be removed before then.
[<Emit("((f) => ($0.addOnce(f), f))($1)")>]
let addTickerOnce (target: Ticker) (listener: Ticker -> unit) : Subscription = jsNative

[<Emit("$0.remove($1)")>]
let removeTicker (target: Ticker) (subscription: Subscription) : unit = jsNative

/// Number of registered listeners.
[<Emit("$0.count")>]
let tickerListenerCount (target: Ticker) : int = jsNative

[<Emit("$0.start()")>]
let startTicker (target: Ticker) : unit = jsNative

[<Emit("$0.stop()")>]
let stopTicker (target: Ticker) : unit = jsNative

[<Emit("$0.started")>]
let tickerStarted (target: Ticker) : bool = jsNative

/// Advances the ticker to `currentTime` (milliseconds) and runs its listeners once.
[<Emit("$0.update($1)")>]
let updateTicker (target: Ticker) (currentTime: float) : unit = jsNative

/// Frame time in milliseconds, capped by `minFPS` and scaled by `speed`.
[<Emit("$0.deltaMS")>]
let deltaMs (target: Ticker) : float = jsNative

/// Frame time in 1/60 s units, capped by `minFPS` and scaled by `speed`.
[<Emit("$0.deltaTime")>]
let deltaTime (target: Ticker) : float = jsNative

/// Raw milliseconds since the previous frame, uncapped and unscaled.
[<Emit("$0.elapsedMS")>]
let elapsedMs (target: Ticker) : float = jsNative

[<Emit("$0.FPS")>]
let framesPerSecond (target: Ticker) : float = jsNative

[<Emit("$0.speed = $1")>]
let setTickerSpeed (target: Ticker) (speed: float) : unit = jsNative

[<Emit("$0.maxFPS = $1")>]
let setMaxFps (target: Ticker) (fps: float) : unit = jsNative

[<Emit("$0.minFPS = $1")>]
let setMinFps (target: Ticker) (fps: float) : unit = jsNative

// ── Events ──────────────────────────────────────────────────────────────────────────────────
// Pixi's event system is registered by the `pixi.js/events` side effect, which
// `initApplication` also loads in a browser. Without either, `eventMode` is not a property of a node.
// Keep the namespace import as an emitted statement so the registration executes.
[<ImportAll("pixi.js/events"); Emit("void $0", true)>]
let enableEvents () : unit = jsNative

/// True once the event mixin is on `Container`, that is, `eventMode` is a property of every node.
[<Import("Container", "pixi.js"); Emit("('eventMode' in $0.prototype)")>]
let eventsRegistered () : bool = jsNative

/// "none", "passive", "auto", "static" or "dynamic". Use "static" for ordinary interactive nodes.
[<Emit("$0.eventMode = $1")>]
let setEventMode (target: #Container) (mode: string) : unit = jsNative

[<Emit("$0.eventMode")>]
let eventMode (target: #Container) : string = jsNative

[<Emit("$0.cursor = $1")>]
let setCursor (target: #Container) (cursor: string) : unit = jsNative

[<Emit("$0.hitArea = $1")>]
let setHitArea (target: #Container) (area: Rectangle) : unit = jsNative

/// Listens for an event by name, for example "pointerdown", "pointertap", "pointermove" or "pointerup",
/// and returns the subscription that removes the listener.
[<Emit("((f) => ($0.on($1, f), f))($2)")>]
let onEvent (target: #Container) (name: string) (handler: FederatedPointerEvent -> unit) : Subscription = jsNative

[<Emit("((f) => ($0.once($1, f), f))($2)")>]
let onceEvent (target: #Container) (name: string) (handler: FederatedPointerEvent -> unit) : Subscription = jsNative

/// Removes a listener added with `onEvent` or `onceEvent`.
[<Emit("$0.off($1, $2)")>]
let offEvent (target: #Container) (name: string) (subscription: Subscription) : unit = jsNative

[<Emit("$0.emit($1, $2)")>]
let emitEvent (target: #Container) (name: string) (payload: 'T) : bool = jsNative

[<Emit("$0.listenerCount($1)")>]
let listenerCount (target: #Container) (name: string) : int = jsNative

[<Emit("$0.removeAllListeners()")>]
let removeAllListeners (target: #Container) : unit = jsNative

/// Pointer position in canvas (global) coordinates.
[<Emit("$0.global.x")>]
let eventGlobalX (e: FederatedPointerEvent) : float = jsNative

[<Emit("$0.global.y")>]
let eventGlobalY (e: FederatedPointerEvent) : float = jsNative

[<Emit("$0.button")>]
let eventButton (e: FederatedPointerEvent) : int = jsNative

/// Pointer position in the local space of `target`.
[<Emit("$0.getLocalPosition($1)")>]
let eventLocalPosition (e: FederatedPointerEvent) (target: #Container) : Point = jsNative

[<Emit("$0.stopPropagation()")>]
let stopPropagation (e: FederatedPointerEvent) : unit = jsNative
