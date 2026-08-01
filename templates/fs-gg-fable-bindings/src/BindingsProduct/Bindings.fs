module BindingsProductNamespace.Bindings

open Fable.Core
open Fable.Core.JsInterop

// This is intentionally a reviewed starting point, not generated API. Replace the module path
// and shape after reviewing generated-candidates/ against declaration-lock.json.
[<Import("default", "NpmPackage")>]
let private importedModule: obj = jsNative

/// Explicit typed boundary for the reviewed upstream module.
let moduleValue () = importedModule

/// Side-effect imports are explicit and reviewable; add them here rather than relying on load order.
let initialiseSideEffects () = ()

/// Dynamic escape hatches stay outside the curated public surface and do not count as coverage.
let internalDynamic (value: obj) = value
