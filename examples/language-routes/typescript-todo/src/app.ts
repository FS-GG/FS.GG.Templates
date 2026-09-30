import { addTask, deleteTask, editTask, remainingCount, toggleTask, visibleTasks, type Filter, type Task } from "./domain.js";
import { createTaskStore } from "./storage.js";

function required<T extends Element>(selector: string): T {
  const value = document.querySelector<T>(selector);
  if (!value) throw new Error(`Missing required element: ${selector}`);
  return value;
}

const form = required<HTMLFormElement>("#todo-form");
const input = required<HTMLInputElement>("#todo-input");
const formError = required<HTMLElement>("#form-error");
const list = required<HTMLUListElement>("#todo-list");
const emptyState = required<HTMLElement>("#empty-state");
const count = required<HTMLElement>("#remaining-count");
const storageStatus = required<HTMLElement>("#storage-status");
const template = required<HTMLTemplateElement>("#todo-template");
const filterButtons = [...document.querySelectorAll<HTMLButtonElement>("[data-filter]")];
const store = createTaskStore(window.localStorage);
const loaded = store.load();
let tasks: Task[] = loaded.tasks;
let filter: Filter = "all";
let editingId: string | null = null;

function showStorageStatus(message: string | null): void {
  storageStatus.hidden = !message;
  storageStatus.textContent = message ?? "";
}

function persist(): void { showStorageStatus(store.save(tasks)); }
const taskName = (text: string): string => text.length > 60 ? `${text.slice(0, 57)}…` : text;

function focusAfterMutation(preferredId?: string): void {
  const preferred = preferredId ? list.querySelector<HTMLElement>(`[data-id="${CSS.escape(preferredId)}"]`) : null;
  (preferred?.querySelector<HTMLButtonElement>(".edit-button") ?? input).focus();
}

function render(): void {
  list.replaceChildren();
  const shown = visibleTasks(tasks, filter);
  emptyState.hidden = shown.length > 0;
  emptyState.textContent = tasks.length === 0 ? "No tasks yet. Add one above when you are ready." : `No ${filter} tasks.`;
  const remaining = remainingCount(tasks);
  count.textContent = `${remaining} ${remaining === 1 ? "task" : "tasks"} remaining`;

  for (const task of shown) {
    const item = template.content.firstElementChild?.cloneNode(true) as HTMLElement | undefined;
    if (!item) throw new Error("Todo template is empty.");
    item.dataset.id = task.id;
    item.classList.toggle("completed", task.completed);
    const toggle = item.querySelector<HTMLInputElement>(".todo-toggle")!;
    const text = item.querySelector<HTMLElement>(".todo-text")!;
    const editButton = item.querySelector<HTMLButtonElement>(".edit-button")!;
    const deleteButton = item.querySelector<HTMLButtonElement>(".delete-button")!;
    const editForm = item.querySelector<HTMLFormElement>(".edit-form")!;
    const editInput = item.querySelector<HTMLInputElement>(".edit-input")!;
    const cancelButton = item.querySelector<HTMLButtonElement>(".cancel-button")!;
    const editError = item.querySelector<HTMLElement>(".edit-error")!;
    const shortName = taskName(task.text);
    toggle.checked = task.completed;
    toggle.setAttribute("aria-label", `Mark ${shortName} ${task.completed ? "active" : "complete"}`);
    text.textContent = task.text;
    editButton.setAttribute("aria-label", `Edit ${shortName}`);
    deleteButton.setAttribute("aria-label", `Delete ${shortName}`);
    editInput.value = task.text;
    editInput.setAttribute("aria-label", `Edit text for ${shortName}`);
    if (editingId === task.id) {
      item.querySelector<HTMLElement>(".todo-view")!.hidden = true;
      editForm.hidden = false;
      queueMicrotask(() => { editInput.focus(); editInput.select(); });
    }
    toggle.addEventListener("change", () => { tasks = toggleTask(tasks, task.id); persist(); render(); focusAfterMutation(task.id); });
    editButton.addEventListener("click", () => { editingId = task.id; render(); });
    deleteButton.addEventListener("click", () => {
      const index = shown.findIndex((candidate) => candidate.id === task.id);
      tasks = deleteTask(tasks, task.id); editingId = null; persist(); render();
      const next = visibleTasks(tasks, filter)[Math.min(index, visibleTasks(tasks, filter).length - 1)];
      focusAfterMutation(next?.id);
    });
    editForm.addEventListener("submit", (event) => {
      event.preventDefault();
      try { tasks = editTask(tasks, task.id, editInput.value); editingId = null; persist(); render(); focusAfterMutation(task.id); }
      catch (error) { editError.textContent = error instanceof Error ? error.message : "Task could not be edited."; editError.hidden = false; editInput.focus(); }
    });
    editInput.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); editingId = null; render(); focusAfterMutation(task.id); } });
    cancelButton.addEventListener("click", () => { editingId = null; render(); focusAfterMutation(task.id); });
    list.append(item);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  try { tasks = addTask(tasks, input.value, crypto.randomUUID()); input.value = ""; formError.hidden = true; persist(); render(); input.focus(); }
  catch (error) { formError.textContent = error instanceof Error ? error.message : "Task could not be added."; formError.hidden = false; input.focus(); }
});

for (const button of filterButtons) button.addEventListener("click", () => {
  const selected = button.dataset.filter;
  if (selected !== "all" && selected !== "active" && selected !== "completed") return;
  filter = selected; editingId = null;
  for (const candidate of filterButtons) candidate.setAttribute("aria-pressed", String(candidate === button));
  render(); button.focus();
});

showStorageStatus(loaded.error);
render();
