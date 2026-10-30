import { readFile } from "node:fs/promises";
import { NullEngine } from "@babylonjs/core/Engines/nullEngine.js";
import { Engine } from "@babylonjs/core/Engines/engine.js";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine.js";
import { Scene } from "@babylonjs/core/scene.js";
import { Vector3 } from "@babylonjs/core/Maths/math.vector.js";
import { Color3 } from "@babylonjs/core/Maths/math.color.js";
import { FreeCamera } from "@babylonjs/core/Cameras/freeCamera.js";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera.js";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight.js";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight.js";
import { PointLight } from "@babylonjs/core/Lights/pointLight.js";
import { CreateBox } from "@babylonjs/core/Meshes/Builders/boxBuilder.js";
import { CreateSphere } from "@babylonjs/core/Meshes/Builders/sphereBuilder.js";
import { CreateGround } from "@babylonjs/core/Meshes/Builders/groundBuilder.js";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial.js";
import { PBRMaterial } from "@babylonjs/core/Materials/PBR/pbrMaterial.js";
import { ImportMeshAsync, SceneLoader } from "@babylonjs/core/Loading/sceneLoader.js";
import "@babylonjs/loaders/glTF/index.js";

// Every runtime entry point the binding plan declares must resolve in Node.
const plan = JSON.parse(await readFile(new URL("../../binding-plan.json", import.meta.url), "utf8"));
for (const entry of plan.slice.entryPoints) await import(entry);
if (typeof Engine !== "function" || typeof WebGPUEngine !== "function") throw new Error("Babylon engine constructors did not resolve");

const engine = new NullEngine();
const scene = new Scene(engine);
new ArcRotateCamera("orbit", 0.8, 1, 12, new Vector3(0, 0, 0), scene).setTarget(new Vector3(0, 1, 0));
new FreeCamera("free", new Vector3(0, 2, -8), scene);
new HemisphericLight("sky", new Vector3(0, 1, 0), scene);
new DirectionalLight("sun", new Vector3(-1, -2, -1), scene).intensity = 0.7;
new PointLight("lamp", new Vector3(0, 4, 0), scene);
const crate = CreateBox("crate", { size: 2 }, scene);
const ball = CreateSphere("ball", { diameter: 1.5, segments: 16 }, scene);
CreateGround("floor", { width: 10, height: 10 }, scene);
const painted = new StandardMaterial("painted", scene);
painted.diffuseColor = new Color3(0.8, 0.2, 0.2);
crate.material = painted;
const metal = new PBRMaterial("metal", scene);
metal.albedoColor = new Color3(0.6, 0.6, 0.7);
ball.material = metal;
if (scene.meshes.length !== 3) throw new Error("Babylon runtime slice did not construct three meshes");
if (!SceneLoader.IsPluginForExtensionAvailable(".gltf")) throw new Error("glTF loader side-effect import did not register the plugin");
const triangle = Buffer.from(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]).buffer).toString("base64");
const gltf = {
  asset: { version: "2.0" }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0, name: "triangle" }],
  meshes: [{ name: "triangle", primitives: [{ attributes: { POSITION: 0 } }] }],
  accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: "VEC3", min: [0, 0, 0], max: [1, 1, 0] }],
  bufferViews: [{ buffer: 0, byteLength: 36 }],
  buffers: [{ byteLength: 36, uri: `data:application/octet-stream;base64,${triangle}` }]
};
const imported = await ImportMeshAsync(`data:model/gltf+json;base64,${Buffer.from(JSON.stringify(gltf)).toString("base64")}`, scene, { pluginExtension: ".gltf" });
if (!imported.meshes.some(mesh => mesh.name === "triangle")) throw new Error("glTF import did not produce the triangle mesh");
scene.render();
scene.dispose();
engine.dispose();
console.log("Babylon runtime smoke passed");
