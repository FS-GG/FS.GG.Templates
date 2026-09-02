import { SceneLoader } from "@babylonjs/core/Loading/sceneLoader.js";

if (SceneLoader.IsPluginForExtensionAvailable(".gltf")) {
  throw new Error("negative control unexpectedly found glTF registration without its side-effect import");
}

console.log("Babylon loader side-effect negative control passed");
