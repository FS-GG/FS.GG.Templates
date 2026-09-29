export const FILTERS = Object.freeze(["all", "active", "completed"]);

export function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function createTask(text, id) {
  const normalized = normalizeText(text);
  if (!normalized) throw new Error("Task text is required.");
  if (typeof id !== "string" || !id) throw new Error("Task ID is required.");
  return { id, text: normalized, completed: false };
}

export function addTask(tasks, text, id) {
  return [...tasks, createTask(text, id)];
}

export function editTask(tasks, id, text) {
  const normalized = normalizeText(text);
  if (!normalized) throw new Error("Task text is required.");
  return tasks.map((task) => (task.id === id ? { ...task, text: normalized } : task));
}

export function toggleTask(tasks, id) {
  return tasks.map((task) =>
    task.id === id ? { ...task, completed: !task.completed } : task,
  );
}

export function deleteTask(tasks, id) {
  return tasks.filter((task) => task.id !== id);
}

export function visibleTasks(tasks, filter) {
  if (filter === "active") return tasks.filter((task) => !task.completed);
  if (filter === "completed") return tasks.filter((task) => task.completed);
  return tasks;
}

export function remainingCount(tasks) {
  return tasks.filter((task) => !task.completed).length;
}

export function isTask(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    typeof value.id === "string" &&
    value.id.length > 0 &&
    typeof value.text === "string" &&
    normalizeText(value.text).length > 0 &&
    typeof value.completed === "boolean"
  );
}
