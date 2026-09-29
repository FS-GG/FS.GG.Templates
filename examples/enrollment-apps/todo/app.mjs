import {
  addTask,
  deleteTask,
  editTask,
  remainingCount,
  toggleTask,
  visibleTasks,
} from "./domain.mjs";
import { createTaskStore } from "./storage.mjs";

const form = document.querySelector("#todo-form");
const input = document.querySelector("#todo-input");
const formError = document.querySelector("#form-error");
const list = document.querySelector("#todo-list");
const emptyState = document.querySelector("#empty-state");
const count = document.querySelector("#remaining-count");
const storageStatus = document.querySelector("#storage-status");
const template = document.querySelector("#todo-template");
const filterButtons = [...document.querySelectorAll("[data-filter]")];

function browserStorage() {
  try {
    return window.localStorage;
  } catch {
    return {
      getItem() { throw new Error("Storage unavailable"); },
      setItem() { throw new Error("Storage unavailable"); },
    };
  }
}

const store = createTaskStore(browserStorage());
const loaded = store.load();
let tasks = loaded.tasks;
let filter = "all";
let editingId = null;

function showStorageStatus(message) {
  storageStatus.hidden = !message;
  storageStatus.textContent = message ?? "";
}

function persist() {
  showStorageStatus(store.save(tasks));
}

function taskName(text) {
  return text.length > 60 ? `${text.slice(0, 57)}…` : text;
}

function focusAfterMutation(preferredId) {
  const preferred = preferredId && list.querySelector(`[data-id="${CSS.escape(preferredId)}"]`);
  const target = preferred?.querySelector(".edit-button") ?? input;
  target.focus();
}

function render() {
  list.replaceChildren();
  const shown = visibleTasks(tasks, filter);
  emptyState.hidden = shown.length > 0;
  emptyState.textContent = tasks.length === 0
    ? "No tasks yet. Add one above when you are ready."
    : `No ${filter} tasks.`;

  const remaining = remainingCount(tasks);
  count.textContent = `${remaining} ${remaining === 1 ? "task" : "tasks"} remaining`;

  for (const task of shown) {
    const item = template.content.firstElementChild.cloneNode(true);
    item.dataset.id = task.id;
    item.classList.toggle("completed", task.completed);

    const toggle = item.querySelector(".todo-toggle");
    const text = item.querySelector(".todo-text");
    const editButton = item.querySelector(".edit-button");
    const deleteButton = item.querySelector(".delete-button");
    const editForm = item.querySelector(".edit-form");
    const editInput = item.querySelector(".edit-input");
    const cancelButton = item.querySelector(".cancel-button");
    const editError = item.querySelector(".edit-error");
    const shortName = taskName(task.text);

    toggle.checked = task.completed;
    toggle.setAttribute("aria-label", `Mark ${shortName} ${task.completed ? "active" : "complete"}`);
    text.textContent = task.text;
    editButton.setAttribute("aria-label", `Edit ${shortName}`);
    deleteButton.setAttribute("aria-label", `Delete ${shortName}`);
    editInput.value = task.text;
    editInput.setAttribute("aria-label", `Edit text for ${shortName}`);

    if (editingId === task.id) {
      item.querySelector(".todo-view").hidden = true;
      editForm.hidden = false;
      queueMicrotask(() => {
        editInput.focus();
        editInput.select();
      });
    }

    toggle.addEventListener("change", () => {
      tasks = toggleTask(tasks, task.id);
      persist();
      render();
      focusAfterMutation(task.id);
    });
    editButton.addEventListener("click", () => {
      editingId = task.id;
      render();
    });
    deleteButton.addEventListener("click", () => {
      const index = shown.findIndex((candidate) => candidate.id === task.id);
      tasks = deleteTask(tasks, task.id);
      editingId = null;
      persist();
      render();
      const next = visibleTasks(tasks, filter)[Math.min(index, visibleTasks(tasks, filter).length - 1)];
      focusAfterMutation(next?.id);
    });
    editForm.addEventListener("submit", (event) => {
      event.preventDefault();
      try {
        tasks = editTask(tasks, task.id, editInput.value);
        editingId = null;
        persist();
        render();
        focusAfterMutation(task.id);
      } catch (error) {
        editError.textContent = error.message;
        editError.hidden = false;
        editInput.focus();
      }
    });
    editInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        editingId = null;
        render();
        focusAfterMutation(task.id);
      }
    });
    cancelButton.addEventListener("click", () => {
      editingId = null;
      render();
      focusAfterMutation(task.id);
    });

    list.append(item);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    tasks = addTask(tasks, input.value, crypto.randomUUID());
    input.value = "";
    formError.hidden = true;
    persist();
    render();
    input.focus();
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
    input.focus();
  }
});

for (const button of filterButtons) {
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    editingId = null;
    for (const candidate of filterButtons) {
      candidate.setAttribute("aria-pressed", String(candidate === button));
    }
    render();
    button.focus();
  });
}

showStorageStatus(loaded.error);
render();
