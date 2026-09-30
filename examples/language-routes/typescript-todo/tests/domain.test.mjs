import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const dist = process.env.TYPESCRIPT_TODO_DIST_DIR ?? new URL("../dist/", import.meta.url).pathname;
const { addTask, deleteTask, editTask, remainingCount, toggleTask, visibleTasks } = await import(pathToFileURL(resolve(dist, "domain.js")));

test("compiled todo domain covers add, edit, complete, filter and delete", () => {
  let tasks = addTask([], "  Write notes  ", "one");
  tasks = addTask(tasks, "Book train", "two");
  tasks = editTask(tasks, "one", "Write release notes");
  tasks = toggleTask(tasks, "two");
  assert.deepEqual(visibleTasks(tasks, "active").map((task) => task.id), ["one"]);
  assert.deepEqual(visibleTasks(tasks, "completed").map((task) => task.id), ["two"]);
  assert.equal(remainingCount(tasks), 1);
  assert.deepEqual(deleteTask(tasks, "one").map((task) => task.id), ["two"]);
});

test("compiled todo domain refuses blank task text", () => {
  assert.throws(() => addTask([], "  ", "one"), /Task text is required/);
});
