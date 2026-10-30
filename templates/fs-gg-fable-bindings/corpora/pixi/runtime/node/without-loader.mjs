import { Container } from "pixi.js";

if ("eventMode" in Container.prototype) {
  throw new Error("negative control unexpectedly found the event mixin without its side-effect import");
}

console.log("Pixi events side-effect negative control passed");
