import { readFile } from "node:fs/promises";
import { Application, Assets, Container, Graphics, Rectangle, Sprite, Text, Texture, Ticker, isWebGPUSupported } from "pixi.js";
import "pixi.js/events";

// Every runtime entry point the binding plan declares must resolve in Node.
const plan = JSON.parse(await readFile(new URL("../../binding-plan.json", import.meta.url), "utf8"));
for (const entry of plan.slice.entryPoints) await import(entry);
for (const [name, value] of Object.entries({ Application, Assets, Container, Graphics, Rectangle, Sprite, Text, Texture, Ticker })) {
  if (typeof value !== "function" && typeof value !== "object") throw new Error(`Pixi ${name} did not resolve`);
}
if (typeof isWebGPUSupported !== "function") throw new Error("Pixi isWebGPUSupported did not resolve");

// The same renderer-free journey the Fable program runs, written directly against Pixi.
const world = new Container();
for (let i = 0; i < 1000; i++) {
  const sprite = new Sprite(Texture.WHITE);
  sprite.setSize(8, 8);
  sprite.position.set((i % 40) * 10, Math.floor(i / 40) * 10);
  sprite.tint = 0x010101 * (i % 255);
  world.addChild(sprite);
}
const bounds = world.getBounds().rectangle;
if (world.children.length !== 1000 || bounds.width !== 398 || bounds.height !== 248) throw new Error("Pixi sprite field did not have the expected extent");
const shape = new Graphics().rect(10, 20, 30, 40).fill({ color: 0xff0000, alpha: 1 });
const shapeBounds = shape.getBounds().rectangle;
if (shapeBounds.width !== 30 || shapeBounds.height !== 40) throw new Error("Pixi graphics bounds are wrong");
const label = new Text({ text: "score", style: { fill: 0xffffff, fontSize: 24, fontFamily: "monospace" } });
label.text = "score: 10";
if (label.text !== "score: 10") throw new Error("Pixi text content did not update");
if (!("eventMode" in Container.prototype)) throw new Error("pixi.js/events side-effect import did not register the event mixin");
const clock = new Ticker();
let frames = 0;
clock.add(() => { frames += 1; });
clock.update(1000);
clock.update(1016);
if (frames !== 2 || clock.deltaMS !== 16) throw new Error("Pixi ticker did not advance deterministically");
Assets.add({ alias: "red", src: "red.png" });
if (Assets.cache.has("red")) throw new Error("Pixi cached an asset that was never loaded");
console.log("Pixi runtime smoke passed");
