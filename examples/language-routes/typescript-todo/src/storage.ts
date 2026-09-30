import { isTask, type Task } from "./domain.js";

export const STORAGE_KEY = "fs-gg.typescript-todo.v1";
const VERSION = 1;

interface StorageRecord { readonly version: number; readonly tasks: unknown[] }
export interface TaskStore {
  load(): { tasks: Task[]; error: string | null };
  save(tasks: readonly Task[]): string | null;
}

export function decodeTasks(raw: string | null): Task[] {
  if (raw === null) return [];
  const record = JSON.parse(raw) as Partial<StorageRecord> | null;
  if (record === null || typeof record !== "object" || record.version !== VERSION
      || !Array.isArray(record.tasks) || !record.tasks.every(isTask)
      || new Set(record.tasks.map((task) => task.id)).size !== record.tasks.length) {
    throw new Error("Saved task data is invalid.");
  }
  return record.tasks.map((task) => ({ ...task, text: task.text.trim() }));
}

export function encodeTasks(tasks: readonly Task[]): string {
  if (!Array.isArray(tasks) || !tasks.every(isTask)) throw new Error("Tasks cannot be saved because they are invalid.");
  return JSON.stringify({ version: VERSION, tasks });
}

export function createTaskStore(storage: Pick<Storage, "getItem" | "setItem">): TaskStore {
  return {
    load() {
      try { return { tasks: decodeTasks(storage.getItem(STORAGE_KEY)), error: null }; }
      catch { return { tasks: [], error: "Saved tasks could not be read. Existing saved data was ignored." }; }
    },
    save(tasks) {
      try { storage.setItem(STORAGE_KEY, encodeTasks(tasks)); return null; }
      catch { return "Changes cannot be saved in this browser. You can keep using the list for this visit."; }
    },
  };
}
