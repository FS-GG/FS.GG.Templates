module Qualification.Babylon

open Fable.Core
open Fable.Core.JsInterop

/// Distinct opaque native objects for the curated 3D renderer slice.
/// Interfaces have no F# runtime wrapper or implementation to ship as source.
[<AllowNullLiteral>]
type Engine = interface end
[<AllowNullLiteral>]
type Scene = interface end
[<AllowNullLiteral>]
type Vector3 = interface end
[<AllowNullLiteral>]
type Color3 = interface end
[<AllowNullLiteral>]
type Camera = interface end
[<AllowNullLiteral>]
type Light = interface end
[<AllowNullLiteral>]
type Mesh = interface end
[<AllowNullLiteral>]
type Material = interface end
[<AllowNullLiteral>]
type StandardMaterial =
    inherit Material
[<AllowNullLiteral>]
type PbrMaterial =
    inherit Material
/// Result of a scene-loader import: the imported meshes, skeletons and animation groups.
[<AllowNullLiteral>]
type ImportResult = interface end
/// Browser shim: an `HTMLCanvasElement`. Babylon owns no DOM type, so the binding keeps
/// the canvas opaque instead of depending on a browser binding package.
[<AllowNullLiteral>]
type Canvas = interface end

// Import + Emit metadata is available to a consumer of the compiled binding DLL.

// ── Engines and the render loop ─────────────────────────────────────────────────────────────
[<Import("NullEngine", "@babylonjs/core/Engines/nullEngine.js"); EmitConstructor>]
let nullEngine () : Engine = jsNative

/// Browser shim over `document.getElementById`; null when absent or outside a document.
[<Emit("(typeof document === 'undefined' ? null : document.getElementById($0))")>]
let canvasById (id: string) : Canvas = jsNative

/// WebGL engine (`Engine`) on a canvas; throws when the browser has no WebGL context.
[<Import("Engine", "@babylonjs/core/Engines/engine.js"); EmitConstructor>]
let webGlEngine (canvas: Canvas) (antialias: bool) : Engine = jsNative

[<Import("WebGPUEngine", "@babylonjs/core/Engines/webgpuEngine.js"); Emit("$0.IsSupportedAsync")>]
let webGpuSupported () : JS.Promise<bool> = jsNative

/// WebGPU engine on a canvas, resolved after its asynchronous device initialisation.
[<Import("WebGPUEngine", "@babylonjs/core/Engines/webgpuEngine.js"); Emit("((e) => e.initAsync().then(() => e))(new $0($1))")>]
let webGpuEngine (canvas: Canvas) : JS.Promise<Engine> = jsNative

[<Emit("$0.runRenderLoop(() => $1.render())")>]
let runRenderLoop (engine: Engine) (scene: Scene) : unit = jsNative

[<Emit("$0.stopRenderLoop()")>]
let stopRenderLoop (engine: Engine) : unit = jsNative

[<Emit("$0.resize()")>]
let resize (engine: Engine) : unit = jsNative

[<Emit("$0.dispose()")>]
let disposeEngine (engine: Engine) : unit = jsNative

// ── Scene ───────────────────────────────────────────────────────────────────────────────────
[<Import("Scene", "@babylonjs/core/scene.js"); EmitConstructor>]
let scene (engine: Engine) : Scene = jsNative

/// Renders one frame; `runRenderLoop` calls this once per animation frame.
[<Emit("$0.render()")>]
let render (scene: Scene) : unit = jsNative

[<Emit("$0.clearColor = $1.toColor4(1)")>]
let setClearColor (scene: Scene) (color: Color3) : unit = jsNative

[<Emit("$0.meshes.length")>]
let meshCount (scene: Scene) : int = jsNative

[<Emit("$0.dispose()")>]
let disposeScene (scene: Scene) : unit = jsNative

// ── Maths ───────────────────────────────────────────────────────────────────────────────────
[<Import("Vector3", "@babylonjs/core/Maths/math.vector.js"); EmitConstructor>]
let vector3 (x: float) (y: float) (z: float) : Vector3 = jsNative

[<Import("Color3", "@babylonjs/core/Maths/math.color.js"); EmitConstructor>]
let color3 (r: float) (g: float) (b: float) : Color3 = jsNative

// ── Cameras ─────────────────────────────────────────────────────────────────────────────────
[<Import("FreeCamera", "@babylonjs/core/Cameras/freeCamera.js"); EmitConstructor>]
let freeCamera (name: string) (position: Vector3) (scene: Scene) : Camera = jsNative

/// Orbit camera: longitude `alpha` and latitude `beta` in radians, `radius` from `target`.
[<Import("ArcRotateCamera", "@babylonjs/core/Cameras/arcRotateCamera.js"); EmitConstructor>]
let arcRotateCamera (name: string) (alpha: float) (beta: float) (radius: float) (target: Vector3) (scene: Scene) : Camera = jsNative

[<Emit("$0.setTarget($1)")>]
let setCameraTarget (camera: Camera) (target: Vector3) : unit = jsNative

// ── Lights ──────────────────────────────────────────────────────────────────────────────────
[<Import("HemisphericLight", "@babylonjs/core/Lights/hemisphericLight.js"); EmitConstructor>]
let hemisphericLight (name: string) (direction: Vector3) (scene: Scene) : Light = jsNative

[<Import("DirectionalLight", "@babylonjs/core/Lights/directionalLight.js"); EmitConstructor>]
let directionalLight (name: string) (direction: Vector3) (scene: Scene) : Light = jsNative

[<Import("PointLight", "@babylonjs/core/Lights/pointLight.js"); EmitConstructor>]
let pointLight (name: string) (position: Vector3) (scene: Scene) : Light = jsNative

[<Emit("$0.intensity = $1")>]
let setLightIntensity (light: Light) (intensity: float) : unit = jsNative

// ── Meshes (tree-shakeable builder functions) ───────────────────────────────────────────────
[<Import("CreateBox", "@babylonjs/core/Meshes/Builders/boxBuilder.js"); Emit("$0($1, { size: $2 }, $3)")>]
let box (name: string) (size: float) (scene: Scene) : Mesh = jsNative

[<Import("CreateSphere", "@babylonjs/core/Meshes/Builders/sphereBuilder.js"); Emit("$0($1, { diameter: $2, segments: $3 }, $4)")>]
let sphere (name: string) (diameter: float) (segments: int) (scene: Scene) : Mesh = jsNative

[<Import("CreateGround", "@babylonjs/core/Meshes/Builders/groundBuilder.js"); Emit("$0($1, { width: $2, height: $3 }, $4)")>]
let ground (name: string) (width: float) (height: float) (scene: Scene) : Mesh = jsNative

[<Emit("$0.position = $1")>]
let setPosition (mesh: Mesh) (position: Vector3) : unit = jsNative

[<Emit("$0.rotation = $1")>]
let setRotation (mesh: Mesh) (radians: Vector3) : unit = jsNative

[<Emit("$0.scaling = $1")>]
let setScaling (mesh: Mesh) (scaling: Vector3) : unit = jsNative

[<Emit("$0.material = $1")>]
let setMaterial (mesh: Mesh) (material: #Material) : unit = jsNative

[<Emit("$0.dispose()")>]
let disposeMesh (mesh: Mesh) : unit = jsNative

// ── Materials ───────────────────────────────────────────────────────────────────────────────
[<Import("StandardMaterial", "@babylonjs/core/Materials/standardMaterial.js"); EmitConstructor>]
let standardMaterial (name: string) (scene: Scene) : StandardMaterial = jsNative

[<Emit("$0.diffuseColor = $1")>]
let setDiffuseColor (material: StandardMaterial) (color: Color3) : unit = jsNative

[<Import("PBRMaterial", "@babylonjs/core/Materials/PBR/pbrMaterial.js"); EmitConstructor>]
let pbrMaterial (name: string) (scene: Scene) : PbrMaterial = jsNative

[<Emit("$0.albedoColor = $1")>]
let setAlbedoColor (material: PbrMaterial) (color: Color3) : unit = jsNative

[<Emit("$0.metallic = $1")>]
let setMetallic (material: PbrMaterial) (metallic: float) : unit = jsNative

[<Emit("$0.roughness = $1")>]
let setRoughness (material: PbrMaterial) (roughness: float) : unit = jsNative

// ── glTF loading ────────────────────────────────────────────────────────────────────────────
// Keep the namespace import as an emitted statement so the glTF registration executes.
[<ImportAll("@babylonjs/loaders/glTF/index.js"); Emit("void $0", true)>]
let initialiseLoader () : unit = jsNative

[<Import("SceneLoader", "@babylonjs/core/Loading/sceneLoader.js"); Emit("$0.IsPluginForExtensionAvailable('.gltf')")>]
let loaderRegistered () : bool = jsNative

/// Module-level `ImportMeshAsync`; the plugin is chosen from the source URL's extension.
[<Import("ImportMeshAsync", "@babylonjs/core/Loading/sceneLoader.js"); Emit("$0($1, $2)")>]
let importMeshAsync (source: string) (scene: Scene) : JS.Promise<ImportResult> = jsNative

/// `ImportMeshAsync` with an explicit plugin extension (".gltf", ".glb"), for data URLs or
/// extensionless sources.
[<Import("ImportMeshAsync", "@babylonjs/core/Loading/sceneLoader.js"); Emit("$0($2, $3, { pluginExtension: $1 })")>]
let importMeshWithExtensionAsync (pluginExtension: string) (source: string) (scene: Scene) : JS.Promise<ImportResult> = jsNative

[<Emit("$0.meshes")>]
let importedMeshes (result: ImportResult) : Mesh array = jsNative

// Retain the existing low-level public emitted helpers for explicit constructor interop.
[<Emit("new $0()")>]
let createNullEngine (constructor: obj) : obj = jsNative

[<Emit("new $0($1)")>]
let createScene (constructor: obj) (engine: obj) : obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createVector3 (constructor: obj) (x: float) (y: float) (z: float) : obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createFreeCamera (constructor: obj) (name: string) (position: obj) (scene: obj) : obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createHemisphericLight (constructor: obj) (name: string) (direction: obj) (scene: obj) : obj = jsNative

[<Emit("$0.CreateBox($1, {}, $2)")>]
let createBox (meshBuilder: obj) (name: string) (scene: obj) : obj = jsNative
