import { expect, test, type Page } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";

const selected = existsSync("../SvgFoundation/Examples/ExternalAuthority/reference.json")
  && !existsSync("../SvgFoundation/LegacyPreview.props")
  && (process.env.FsGgExternalReferenceCandidate === "true"
    || readFileSync("../SvgFoundation/SvgFoundation.fsproj", "utf8").includes(">true</FsGgExternalReferenceCandidate>"));

// Only the opt-in complete composition declares these cases. The qualification
// runner requires all eight local/external cases, so omission cannot pass there.
test.describe("external authority reference command outcomes", () => {
  if (!selected) return;
  const reference = (page: Page) => page.locator("#external-authority-reference");
  // Reference action buttons are direct children; scene selection controls can share their labels.
  const press = (page: Page, name: string) => reference(page).getByRole("button", { name, exact: true })
    .and(reference(page).locator(":scope > button")).click();
  const open = async (page: Page) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Mount external authority reference", exact: true }).click();
    await press(page, "Connect sample authority");
    await press(page, "Complete current external snapshot");
  };
  const lose = async (page: Page) => {
    await press(page, "Lose next command receipt");
    await reference(page).focus();
    await page.keyboard.press("Enter");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown");
    await expect(reference(page)).toHaveAttribute("data-unknown-correlation", "sample:1");
    await expect(reference(page)).toHaveAttribute("data-command-suspended", "true");
  };

  test("unknown receipt survives projection and reconnect without replay", async ({ page }) => {
    await open(page); await lose(page);
    const originalGeneration = await reference(page).getAttribute("data-unknown-generation");
    await press(page, "Request external burst");
    await press(page, "Complete current external snapshot");
    await expect(reference(page)).toHaveAttribute("data-applied-value", "1");
    await press(page, "Increment external value");
    await reference(page).focus(); await page.keyboard.press("Enter");
    await press(page, "Disconnect sample authority");
    await press(page, "Connect sample authority");
    await press(page, "Complete current external snapshot");
    await expect(reference(page)).toHaveAttribute("data-command-order", "sample:1:external.increment");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown");
    await expect(reference(page)).toHaveAttribute("data-unknown-generation", originalGeneration!);
    await expect(reference(page)).toHaveAttribute("data-authority-revision", "2");
    await expect(reference(page)).toHaveAttribute("data-command-suspended", "true");
    await expect(reference(page).locator(':scope > [role="status"]')).toContainText("reconnect never retries");
  });

  test("explicit reconciliation and rearm retain the original and use a fresh correlation", async ({ page }) => {
    await open(page); await lose(page);
    await press(page, "Rearm sample commands");
    await expect(reference(page)).toHaveAttribute("data-command-suspended", "true");
    await press(page, "Reconcile unknown command");
    await expect(reference(page)).toHaveAttribute("data-command-recovery", "Reconciled");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown");
    await expect(reference(page)).toHaveAttribute("data-command-suspended", "true");
    await press(page, "Rearm sample commands");
    await press(page, "Increment external value");
    await press(page, "Reject sample command");
    await press(page, "Request external burst");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown,sample:2:accepted,sample:3:rejected");
    await expect(reference(page)).toHaveAttribute("data-command-order", "sample:1:external.increment,sample:2:external.increment,sample:3:external.reject");
    await expect(reference(page)).toHaveAttribute("data-authority-revision", "3");
    await expect(reference(page)).toHaveAttribute("data-unknown-correlation", "sample:1");
    await expect(reference(page)).toHaveAttribute("data-command-owned", "0");
  });

  test("old generation completion is inert and abandonment requires explicit rearm", async ({ page }) => {
    await open(page); await lose(page);
    await press(page, "Replace sample authority");
    await press(page, "Complete delayed command receipt");
    await press(page, "Reconcile unknown command");
    await expect(reference(page)).toHaveAttribute("data-command-recovery", "Awaiting");
    await expect(reference(page)).toHaveAttribute("data-authority-revision", "1");
    await expect(reference(page)).toHaveAttribute("data-authority-epoch", "epoch-B");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown");
    await press(page, "Abandon unknown command");
    await expect(reference(page)).toHaveAttribute("data-command-recovery", "Abandoned");
    await press(page, "Increment external value");
    await expect(reference(page)).toHaveAttribute("data-command-order", "sample:1:external.increment");
    await press(page, "Rearm sample commands");
    await press(page, "Increment external value");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown,sample:2:accepted");
    await expect(reference(page)).toHaveAttribute("data-authority-revision", "2");
    await expect(reference(page)).toHaveAttribute("data-unknown-epoch", "epoch-A");
  });

  test("delayed completion settles once and disposal makes retained controls inert", async ({ page }) => {
    await open(page); await lose(page);
    await press(page, "Complete delayed command receipt");
    await press(page, "Complete delayed command receipt");
    await expect(reference(page)).toHaveAttribute("data-command-recovery", "Reconciled");
    await expect(reference(page)).toHaveAttribute("data-authority-revision", "2");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown");
    await press(page, "Rearm sample commands");
    await press(page, "Lose next command receipt");
    await press(page, "Reject sample command");
    await press(page, "Increment external value");
    await expect(reference(page)).toHaveAttribute("data-receipt-order", "sample:1:unknown,sample:2:rejected,sample:3:unknown");
    await expect(reference(page)).toHaveAttribute("data-command-owned", "1");
    await reference(page).evaluate(element => {
      (window as any).__commandButtons = [...element.querySelectorAll<HTMLButtonElement>("button")];
    });
    const receipts = await reference(page).getAttribute("data-receipt-order");
    const revision = await reference(page).getAttribute("data-authority-revision");
    await press(page, "Dispose external reference");
    for (const owner of ["command", "gateway", "host", "input", "button", "svg"]) {
      await expect(reference(page)).toHaveAttribute(`data-${owner}-owned`, "0");
    }
    await page.evaluate(() => (window as any).__commandButtons.forEach((button: HTMLButtonElement) => button.click()));
    await expect(reference(page)).toHaveAttribute("data-receipt-order", receipts!);
    await expect(reference(page)).toHaveAttribute("data-authority-revision", revision!);
    await expect(reference(page)).toHaveAttribute("data-disposed", "true");
  });
});
