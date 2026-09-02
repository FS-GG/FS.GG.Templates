open Fable.Core
open Qualification.Babylon

[<Emit("if (typeof document !== 'undefined') document.querySelector('output').textContent = 'Babylon browser smoke passed'")>]
let private markBrowserPass (): unit = jsNative

let engine = nullEngine ()
let scene = scene engine
let _camera = freeCamera "camera" (vector3 0. 0. 0.) scene
let _light = hemisphericLight "light" (vector3 0. 1. 0.) scene
let _ = box "compile-smoke" scene
initialiseLoader ()
if not (loaderRegistered ()) then failwith "glTF loader side-effect import did not register the plugin"
markBrowserPass ()
printfn "curated Babylon binding compile smoke passed"
