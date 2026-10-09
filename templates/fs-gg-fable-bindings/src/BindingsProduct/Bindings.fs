module Qualification.Babylon

open Fable.Core
open Fable.Core.JsInterop

/// Distinct opaque native objects for the curated qualification slice.
/// Interfaces have no F# runtime wrapper or implementation to ship as source.
[<AllowNullLiteral>]
type Engine = interface end
[<AllowNullLiteral>]
type Scene = interface end
[<AllowNullLiteral>]
type Vector3 = interface end
[<AllowNullLiteral>]
type Camera = interface end
[<AllowNullLiteral>]
type Light = interface end
[<AllowNullLiteral>]
type Box = interface end

// Import + Emit metadata is available to a consumer of the compiled binding DLL.
[<Import("NullEngine", "@babylonjs/core/Engines/nullEngine.js"); EmitConstructor>]
let nullEngine () : Engine = jsNative

[<Import("Scene", "@babylonjs/core/scene.js"); EmitConstructor>]
let scene (engine: Engine) : Scene = jsNative

[<Import("Vector3", "@babylonjs/core/Maths/math.vector.js"); EmitConstructor>]
let vector3 (x: float) (y: float) (z: float) : Vector3 = jsNative

[<Import("FreeCamera", "@babylonjs/core/Cameras/freeCamera.js"); EmitConstructor>]
let freeCamera (name: string) (position: Vector3) (scene: Scene) : Camera = jsNative

[<Import("HemisphericLight", "@babylonjs/core/Lights/hemisphericLight.js"); EmitConstructor>]
let hemisphericLight (name: string) (direction: Vector3) (scene: Scene) : Light = jsNative

[<Import("MeshBuilder", "@babylonjs/core/Meshes/meshBuilder.js"); Emit("$0.CreateBox($1, {}, $2)")>]
let box (name: string) (scene: Scene) : Box = jsNative

// Keep the namespace import as an emitted statement so the glTF registration executes.
[<ImportAll("@babylonjs/loaders/glTF/index.js"); Emit("void $0", true)>]
let initialiseLoader () : unit = jsNative

[<Import("SceneLoader", "@babylonjs/core/Loading/sceneLoader.js"); Emit("$0.IsPluginForExtensionAvailable('.gltf')")>]
let loaderRegistered () : bool = jsNative

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
