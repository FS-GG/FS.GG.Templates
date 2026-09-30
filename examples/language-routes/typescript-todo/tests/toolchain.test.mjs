import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("toolchain lock names exact candidate versions without claiming an image", async () => {
  const lock = JSON.parse(await readFile(new URL("../toolchain-lock.json", import.meta.url), "utf8"));
  assert.equal(lock.typescript, "5.9.2");
  assert.equal(lock.node, "24.8.0");
  assert.equal(lock.qualificationImage, null);
  assert.match(lock.note, /preparatory source evidence only/i);
});
