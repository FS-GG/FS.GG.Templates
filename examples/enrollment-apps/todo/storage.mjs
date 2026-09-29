import { isTask } from "./domain.mjs";

export const STORAGE_KEY = "fs-gg.todo.v1";
const VERSION = 1;

export function decodeTasks(raw) {
  if (raw === null) return [];
  const record = JSON.parse(raw);
  if (
    record === null ||
    typeof record !== "object" ||
    record.version !== VERSION ||
    !Array.isArray(record.tasks) ||
    !record.tasks.every(isTask) ||
    new Set(record.tasks.map((task) => task.id)).size !== record.tasks.length
  ) {
    throw new Error("Saved task data is invalid.");
  }
  return record.tasks.map((task) => ({ ...task, text: task.text.trim() }));
}

export function encodeTasks(tasks) {
  if (!Array.isArray(tasks) || !tasks.every(isTask)) {
    throw new Error("Tasks cannot be saved because they are invalid.");
  }
  return JSON.stringify({ version: VERSION, tasks });
}

export function createTaskStore(storage) {
  return {
    load() {
      try {
        return { tasks: decodeTasks(storage.getItem(STORAGE_KEY)), error: null };
      } catch {
        return {
          tasks: [],
          error: "Saved tasks could not be read. You can keep using the list, but existing saved data was ignored.",
        };
      }
    },
    save(tasks) {
      try {
        storage.setItem(STORAGE_KEY, encodeTasks(tasks));
        return null;
      } catch {
        return "Changes cannot be saved in this browser. You can keep using the list for this visit.";
      }
    },
  };
}
