import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("toolchain lock names exact candidate versions without claiming native qualification", async () => {
  const lock = JSON.parse(await readFile(new URL("../toolchain-lock.json", import.meta.url), "utf8"));
  assert.equal(lock.typescript, "5.9.2");
  assert.equal(lock.node, "24.8.0");
  assert.equal(lock.nodeArchive.sha256, "daf68404b478b4c3616666580d02500a24148c0f439e4d0134d65ce70e90e655");
  assert.deepEqual(lock.qualificationImage, {
    recipe: "eng/typescript-todo-image/Containerfile",
    platform: "linux/amd64",
    base: "mcr.microsoft.com/playwright@sha256:bc6ab0d6d44ff4826e4cb8c1e6d801e185bfc42bb0753f8e2a30efc70db054c7",
    status: "source-preparation",
  });
  assert.match(lock.note, /source preparation/i);
});
