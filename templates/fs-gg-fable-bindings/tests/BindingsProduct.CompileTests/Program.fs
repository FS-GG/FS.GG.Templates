open Qualification.Babylon
let engine = nullEngine ()
let scene = scene engine
let _ = box "compile-smoke" scene
initialiseLoader ()
printfn "curated Babylon binding compile smoke passed"
