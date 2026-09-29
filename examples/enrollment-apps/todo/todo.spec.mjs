import { test, expect } from "@playwright/test";

const appPath = "/todo/";

test("a user manages and retains a todo list", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(appPath);
  await expect(page.getByRole("heading", { name: "Things to do" })).toBeVisible();
  await expect(page.getByText("No tasks yet.")).toBeVisible();

  const input = page.getByLabel("What needs doing?");
  await input.focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Add task" })).toBeFocused();
  await input.fill("   ");
  await page.getByRole("button", { name: "Add task" }).click();
  await expect(page.getByRole("alert")).toHaveText("Task text is required.");

  await input.fill("Write <strong>notes</strong>");
  await input.press("Enter");
  await input.fill("Book train");
  await input.press("Enter");
  await expect(page.getByRole("listitem")).toHaveCount(2);
  await expect(page.getByText("Write <strong>notes</strong>", { exact: true })).toBeVisible();
  await expect(page.locator(".todo-text strong")).toHaveCount(0);

  await page.getByRole("button", { name: "Edit Write <strong>notes</strong>" }).click();
  const firstEdit = page.getByLabel("Edit text for Write <strong>notes</strong>");
  await firstEdit.fill("Write release notes");
  await firstEdit.press("Enter");
  await expect(page.getByText("Write release notes", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Edit Book train" }).click();
  await page.getByLabel("Edit text for Book train").fill("This must not save");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit Book train" }).click();
  await page.getByLabel("Edit text for Book train").fill("This also must not save");
  await page.getByLabel("Edit text for Book train").press("Escape");
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();

  await page.getByRole("checkbox", { name: "Mark Book train complete" }).press("Space");
  await expect(page.getByText("1 task remaining")).toBeVisible();
  await page.getByRole("button", { name: "Active" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("Write release notes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Completed" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await page.getByRole("checkbox", { name: "Mark Book train active" }).click();
  await expect(page.getByText("No completed tasks.")).toBeVisible();

  await page.getByRole("button", { name: "All" }).click();
  await page.getByRole("checkbox", { name: "Mark Book train complete" }).click();
  await page.getByRole("button", { name: "Delete Write release notes" }).click();
  await expect(page.getByRole("button", { name: "Edit Book train" })).toBeFocused();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Mark Book train active" })).toBeChecked();

  await page.close();
  const reopened = await context.newPage();
  await reopened.goto(appPath);
  await expect(reopened.getByText("Book train", { exact: true })).toBeVisible();
  await context.close();

  const freshContext = await browser.newContext();
  const freshPage = await freshContext.newPage();
  await freshPage.goto(appPath);
  await expect(freshPage.getByText("No tasks yet.")).toBeVisible();
  await freshContext.close();
  expect(errors).toEqual([]);
});

test("the narrow layout remains operable without horizontal spill", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto(appPath);
  await page.getByLabel("What needs doing?").fill("A narrow-screen task");
  await page.getByRole("button", { name: "Add task" }).click();
  await expect(page.getByRole("button", { name: "Edit A narrow-screen task" })).toBeVisible();
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width);
});

test("invalid saved data is explained and does not disable the app", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fs-gg.todo.v1", "{invalid"));
  await page.goto(appPath);
  await expect(page.getByRole("status")).toContainText("could not be read");
  await page.getByLabel("What needs doing?").fill("Recovered task");
  await page.getByRole("button", { name: "Add task" }).click();
  await expect(page.getByText("Recovered task", { exact: true })).toBeVisible();
});

test("rejected storage is explained while in-memory changes remain usable", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new DOMException("Storage disabled", "SecurityError");
    };
  });
  await page.goto(appPath);
  await page.getByLabel("What needs doing?").fill("Temporary task");
  await page.getByRole("button", { name: "Add task" }).click();
  await expect(page.getByRole("status")).toContainText("cannot be saved");
  await expect(page.getByText("Temporary task", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Mark Temporary task complete" }).click();
  await expect(page.getByText("0 tasks remaining")).toBeVisible();
});
