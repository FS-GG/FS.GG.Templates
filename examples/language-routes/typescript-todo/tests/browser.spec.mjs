import { expect, test } from "@playwright/test";

test("served compiled TypeScript supports the complete retained todo journey", async ({ browser, request }) => {
  const script = await request.get("/app.js");
  expect(script.ok()).toBe(true);
  expect(await script.text()).toContain('from "./domain.js"');
  expect((await request.get("/app.ts")).status()).toBe(404);

  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Things to do" })).toBeVisible();
  const input = page.getByLabel("What needs doing?");
  await input.fill("Write notes"); await input.press("Enter");
  await input.fill("Book train"); await input.press("Enter");
  await page.getByRole("button", { name: "Edit Write notes" }).click();
  await page.getByLabel("Edit text for Write notes").fill("Write release notes");
  await page.getByLabel("Edit text for Write notes").press("Enter");
  await page.getByRole("checkbox", { name: "Mark Book train complete" }).click();
  await page.getByRole("button", { name: "Active" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("Write release notes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Completed" }).click();
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "All" }).click();
  await page.getByRole("button", { name: "Delete Write release notes" }).click();
  await page.reload();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByText("Book train", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Mark Book train active" })).toBeChecked();
  expect(errors).toEqual([]);
  await context.close();
});

test("malformed retained state is visible and recovery is genuinely saved", async ({ page }) => {
  await page.addInitScript(() => {
    if (localStorage.getItem("fs-gg.typescript-todo.v1") === null) {
      localStorage.setItem("fs-gg.typescript-todo.v1", "{invalid");
    }
  });
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("could not be read");
  await expect(page.getByText("No tasks yet.")).toBeVisible();
  await page.getByLabel("What needs doing?").fill("Recovered task");
  await page.getByRole("button", { name: "Add task" }).click();
  await page.reload();
  await expect(page.getByText("Recovered task", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toBeHidden();
});
