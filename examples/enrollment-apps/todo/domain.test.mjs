import test from "node:test";
import assert from "node:assert/strict";

import {
  addTask,
  deleteTask,
  editTask,
  remainingCount,
  toggleTask,
  visibleTasks,
} from "./domain.mjs";
import { createTaskStore, decodeTasks, encodeTasks, STORAGE_KEY } from "./storage.mjs";

test("task mutations are immutable and preserve stable IDs", () => {
  const first = addTask([], "  Write tests  ", "task-1");
  const second = addTask(first, "Ship sample", "task-2");
  const edited = editTask(second, "task-1", "Review tests");
  const completed = toggleTask(edited, "task-2");

  assert.deepEqual(first, [{ id: "task-1", text: "Write tests", completed: false }]);
  assert.deepEqual(completed, [
    { id: "task-1", text: "Review tests", completed: false },
    { id: "task-2", text: "Ship sample", completed: true },
  ]);
  assert.equal(remainingCount(completed), 1);
  assert.deepEqual(visibleTasks(completed, "active").map((task) => task.id), ["task-1"]);
  assert.deepEqual(visibleTasks(completed, "completed").map((task) => task.id), ["task-2"]);
  assert.deepEqual(deleteTask(completed, "task-1").map((task) => task.id), ["task-2"]);
});

test("blank task text is rejected for add and edit", () => {
  assert.throws(() => addTask([], " \n ", "task-1"), /required/);
  assert.throws(
    () => editTask([{ id: "task-1", text: "Keep", completed: false }], "task-1", "  "),
    /required/,
  );
});

test("versioned storage validates shape, uniqueness, and JSON", () => {
  const tasks = [{ id: "task-1", text: "Keep", completed: false }];
  assert.deepEqual(decodeTasks(encodeTasks(tasks)), tasks);
  assert.deepEqual(decodeTasks(null), []);
  assert.throws(() => decodeTasks("not json"));
  assert.throws(() => decodeTasks(JSON.stringify({ version: 2, tasks })));
  assert.throws(() => decodeTasks(JSON.stringify({ version: 1, tasks: [...tasks, ...tasks] })));
});

test("storage failures return a usable in-memory state", () => {
  const failingStorage = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
  };
  const store = createTaskStore(failingStorage);
  const loaded = store.load();
  assert.deepEqual(loaded.tasks, []);
  assert.match(loaded.error, /could not be read/);
  assert.match(store.save([]), /cannot be saved/);

  const values = new Map();
  const workingStore = createTaskStore({
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  });
  assert.equal(workingStore.save([{ id: "x", text: "Stored", completed: true }]), null);
  assert.match(values.get(STORAGE_KEY), /"version":1/);
});
