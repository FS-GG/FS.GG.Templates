export const FILTERS = ["all", "active", "completed"] as const;
export type Filter = typeof FILTERS[number];

export interface Task {
  readonly id: string;
  readonly text: string;
  readonly completed: boolean;
}

export function normalizeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function createTask(text: string, id: string): Task {
  const normalized = normalizeText(text);
  if (!normalized) throw new Error("Task text is required.");
  if (!id) throw new Error("Task ID is required.");
  return { id, text: normalized, completed: false };
}

export const addTask = (tasks: readonly Task[], text: string, id: string): Task[] => [...tasks, createTask(text, id)];

export function editTask(tasks: readonly Task[], id: string, text: string): Task[] {
  const normalized = normalizeText(text);
  if (!normalized) throw new Error("Task text is required.");
  return tasks.map((task) => task.id === id ? { ...task, text: normalized } : task);
}

export const toggleTask = (tasks: readonly Task[], id: string): Task[] =>
  tasks.map((task) => task.id === id ? { ...task, completed: !task.completed } : task);

export const deleteTask = (tasks: readonly Task[], id: string): Task[] => tasks.filter((task) => task.id !== id);

export function visibleTasks(tasks: readonly Task[], filter: Filter): Task[] {
  if (filter === "active") return tasks.filter((task) => !task.completed);
  if (filter === "completed") return tasks.filter((task) => task.completed);
  return [...tasks];
}

export const remainingCount = (tasks: readonly Task[]): number => tasks.filter((task) => !task.completed).length;

export function isTask(value: unknown): value is Task {
  if (value === null || typeof value !== "object") return false;
  const task = value as Partial<Task>;
  return typeof task.id === "string" && task.id.length > 0
    && typeof task.text === "string" && normalizeText(task.text).length > 0
    && typeof task.completed === "boolean";
}
