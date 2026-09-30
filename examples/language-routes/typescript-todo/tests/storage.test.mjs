import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const dist = process.env.TYPESCRIPT_TODO_DIST_DIR ?? new URL("../dist/", import.meta.url).pathname;
const { createTaskStore, decodeTasks, encodeTasks, STORAGE_KEY } = await import(pathToFileURL(resolve(dist, "storage.js")));

test("compiled storage retains valid versioned tasks", () => {
  const task = { id: "one", text: "Retained", completed: true };
  assert.deepEqual(decodeTasks(encodeTasks([task])), [task]);
});

test("compiled storage reports malformed retained state without false success", () => {
  assert.throws(() => decodeTasks("{invalid"));
  const writes = [];
  const store = createTaskStore({
    getItem(key) { assert.equal(key, STORAGE_KEY); return "{invalid"; },
    setItem(key, value) { writes.push([key, value]); },
  });
  assert.deepEqual(store.load(), {
    tasks: [],
    error: "Saved tasks could not be read. Existing saved data was ignored.",
  });
  assert.equal(store.save([{ id: "recovered", text: "Recovered", completed: false }]), null);
  assert.equal(writes.length, 1);
});
