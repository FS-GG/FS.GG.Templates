open Qualification.Babylon

let engine = nullEngine ()
let scene = scene engine
let _camera = freeCamera "camera" (vector3 0. 0. 0.) scene
let _light = hemisphericLight "light" (vector3 0. 1. 0.) scene
let _box = box "box" scene
initialiseLoader ()
printfn "babylon binding smoke passed"
