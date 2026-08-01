module Qualification.Babylon

open Fable.Core
open Fable.Core.JsInterop

/// Curated, deliberately narrow Fable surface for the qualification slice.
/// Generated candidates never become this public API without review.
type Engine = private Engine of obj
type Scene = private Scene of obj
type Vector3 = private Vector3 of obj
type Camera = private Camera of obj
type Light = private Light of obj
type Box = private Box of obj

[<Import("NullEngine", "@babylonjs/core/Engines/nullEngine.js")>]
let private nullEngineConstructor: obj = jsNative

[<Import("Scene", "@babylonjs/core/scene.js")>]
let private sceneConstructor: obj = jsNative

[<Import("Vector3", "@babylonjs/core/Maths/math.vector.js")>]
let private vector3Constructor: obj = jsNative

[<Import("FreeCamera", "@babylonjs/core/Cameras/freeCamera.js")>]
let private freeCameraConstructor: obj = jsNative

[<Import("HemisphericLight", "@babylonjs/core/Lights/hemisphericLight.js")>]
let private hemisphericLightConstructor: obj = jsNative

[<Import("MeshBuilder", "@babylonjs/core/Meshes/meshBuilder.js")>]
let private meshBuilder: obj = jsNative

[<ImportAll("@babylonjs/loaders/glTF/index.js")>]
let private gltfLoader: obj = jsNative

[<Emit("new $0()")>]
let createNullEngine (constructor: obj): obj = jsNative

[<Emit("new $0($1)")>]
let createScene (constructor: obj) (engine: obj): obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createVector3 (constructor: obj) (x: float) (y: float) (z: float): obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createFreeCamera (constructor: obj) (name: string) (position: obj) (scene: obj): obj = jsNative

[<Emit("new $0($1, $2, $3)")>]
let createHemisphericLight (constructor: obj) (name: string) (direction: obj) (scene: obj): obj = jsNative

[<Emit("$0.CreateBox($1, {}, $2)")>]
let createBox (meshBuilder: obj) (name: string) (scene: obj): obj = jsNative

let nullEngine () = Engine (createNullEngine nullEngineConstructor)
let scene (Engine engine) = Scene (createScene sceneConstructor engine)
let vector3 x y z = Vector3 (createVector3 vector3Constructor x y z)
let freeCamera name (Vector3 position) (Scene scene) = Camera (createFreeCamera freeCameraConstructor name position scene)
let hemisphericLight name (Vector3 direction) (Scene scene) = Light (createHemisphericLight hemisphericLightConstructor name direction scene)
let box name (Scene scene) = Box (createBox meshBuilder name scene)
let initialiseLoader () = gltfLoader |> ignore
