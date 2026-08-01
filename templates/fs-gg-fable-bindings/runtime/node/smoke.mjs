import { NullEngine } from "@babylonjs/core/Engines/nullEngine.js";
import { Scene } from "@babylonjs/core/scene.js";
import { Vector3 } from "@babylonjs/core/Maths/math.vector.js";
import { FreeCamera } from "@babylonjs/core/Cameras/freeCamera.js";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight.js";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder.js";
import "@babylonjs/loaders/glTF/index.js";

const engine = new NullEngine();
const scene = new Scene(engine);
new FreeCamera("camera", new Vector3(0, 0, 0), scene);
new HemisphericLight("light", new Vector3(0, 1, 0), scene);
const box = MeshBuilder.CreateBox("box", {}, scene);
if (!box || scene.meshes.length !== 1) throw new Error("Babylon runtime slice did not construct a mesh");
engine.dispose();
console.log("Babylon runtime smoke passed");
