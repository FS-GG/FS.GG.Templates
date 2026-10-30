open Fable.Core
open Qualification.Babylon

// Test-only promise and DOM helpers; the binding itself exposes only Babylon calls.
[<Emit("if (typeof document !== 'undefined') document.querySelector('output').textContent = $0")>]
let private mark (text: string) : unit = jsNative

[<Emit("$0.then($1)")>]
let private andThen (promise: JS.Promise<'T>) (continuation: 'T -> JS.Promise<'U>) : JS.Promise<'U> = jsNative

[<Emit("Promise.resolve($0)")>]
let private resolved (value: 'T) : JS.Promise<'T> = jsNative

[<Emit("new Promise((resolve) => setTimeout(resolve, $0))")>]
let private delay (milliseconds: int) : JS.Promise<unit> = jsNative

[<Emit("$0.catch((error) => { console.error(error); if (typeof document !== 'undefined') document.querySelector('output').textContent = 'Babylon smoke failed: ' + error; if (typeof process !== 'undefined') process.exitCode = 1; })")>]
let private reportFailure (promise: JS.Promise<unit>) : unit = jsNative

/// One-triangle glTF 2.0 document with an embedded buffer, so the loader runs without a server.
let private triangleGltf =
    "data:model/gltf+json;base64,eyJhc3NldCI6eyJ2ZXJzaW9uIjoiMi4wIn0sInNjZW5lIjowLCJzY2VuZXMiOlt7Im5vZGVzIjpbMF19XSwibm9kZXMiOlt7Im1lc2giOjAsIm5hbWUiOiJ0cmlhbmdsZSJ9XSwibWVzaGVzIjpbeyJuYW1lIjoidHJpYW5nbGUiLCJwcmltaXRpdmVzIjpbeyJhdHRyaWJ1dGVzIjp7IlBPU0lUSU9OIjowfX1dfV0sImFjY2Vzc29ycyI6W3siYnVmZmVyVmlldyI6MCwiY29tcG9uZW50VHlwZSI6NTEyNiwiY291bnQiOjMsInR5cGUiOiJWRUMzIiwibWluIjpbMCwwLDBdLCJtYXgiOlsxLDEsMF19XSwiYnVmZmVyVmlld3MiOlt7ImJ1ZmZlciI6MCwiYnl0ZUxlbmd0aCI6MzZ9XSwiYnVmZmVycyI6W3siYnl0ZUxlbmd0aCI6MzYsInVyaSI6ImRhdGE6YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtO2Jhc2U2NCxBQUFBQUFBQUFBQUFBQUFBQUFDQVB3QUFBQUFBQUFBQUFBQUFBQUFBZ0Q4QUFBQUEifV19"

/// Builds the renderer scene used on every engine: cameras, lights, meshes and materials.
let private populate (scene: Scene) =
    setClearColor scene (color3 0.1 0.1 0.15)
    let orbit = arcRotateCamera "orbit" 0.8 1.0 12. (vector3 0. 0. 0.) scene
    setCameraTarget orbit (vector3 0. 1. 0.)
    let _free = freeCamera "free" (vector3 0. 2. (-8.)) scene
    let _sky = hemisphericLight "sky" (vector3 0. 1. 0.) scene
    let sun = directionalLight "sun" (vector3 (-1.) (-2.) (-1.)) scene
    setLightIntensity sun 0.7
    let _lamp = pointLight "lamp" (vector3 0. 4. 0.) scene
    let crate = box "crate" 2. scene
    setPosition crate (vector3 (-2.) 1. 0.)
    setRotation crate (vector3 0. 0.5 0.)
    let ball = sphere "ball" 1.5 16 scene
    setPosition ball (vector3 2. 1. 0.)
    setScaling ball (vector3 1. 1.2 1.)
    let floor = ground "floor" 10. 10. scene
    let painted = standardMaterial "painted" scene
    setDiffuseColor painted (color3 0.8 0.2 0.2)
    setMaterial crate painted
    let metal = pbrMaterial "metal" scene
    setAlbedoColor metal (color3 0.6 0.6 0.7)
    setMetallic metal 0.9
    setRoughness metal 0.3
    setMaterial ball metal
    setMaterial floor painted

let private expect condition message =
    if not condition then failwith message

/// Deterministic journey on a NullEngine: the same in Node and Chromium.
let private headless () =
    let engine = nullEngine ()
    let scene = scene engine
    populate scene
    expect (meshCount scene = 3) "renderer slice did not construct three meshes"
    initialiseLoader ()
    expect (loaderRegistered ()) "glTF loader side-effect import did not register the plugin"
    andThen (importMeshWithExtensionAsync ".gltf" triangleGltf scene) (fun result ->
        let meshes = importedMeshes result
        expect (meshes |> Array.exists (fun mesh -> not (isNull mesh))) "glTF import returned no meshes"
        expect (meshCount scene = 3 + meshes.Length) "glTF meshes were not added to the scene"
        render scene
        runRenderLoop engine scene
        andThen (delay 50) (fun () ->
            stopRenderLoop engine
            let imported = (importedMeshes result).[0]
            disposeMesh imported
            disposeScene scene
            disposeEngine engine
            resolved ()))

/// Browser-only: a real WebGL engine renders the same scene on the page's canvas, and a
/// WebGPU engine initialises on its own canvas when the browser supports WebGPU. Outside a
/// document there is no canvas and both are skipped.
let private browser () =
    let canvas = canvasById "renderCanvas"
    if isNull canvas then
        resolved ()
    else
        let engine = webGlEngine canvas true
        let scene = scene engine
        populate scene
        resize engine
        render scene
        disposeScene scene
        disposeEngine engine
        andThen (webGpuSupported ()) (fun supported ->
            if supported then
                andThen (webGpuEngine (canvasById "gpuCanvas")) (fun gpu ->
                    disposeEngine gpu
                    resolved ())
            else
                resolved ())

andThen (headless ()) (fun () -> browser ())
|> fun journey -> andThen journey (fun () ->
    mark "Babylon browser smoke passed"
    printfn "curated Babylon binding compile smoke passed"
    resolved ())
|> reportFailure
