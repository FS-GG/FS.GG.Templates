import { test, expect } from "@playwright/test";

const selected = process.env.FsGgWasmPolicyExample === "true";
const base = process.env.FSGG_WASM_POLICY_BASE ?? "/wasm-example/";

test.describe("explicit Complete WASM policy", () => {
  // Observe owned Worker wrapper handles/terminate-call receipts, not native exit acknowledgments.
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      const NativeWorker = globalThis.Worker;
      const owned = new Set<Worker>();
      Object.defineProperty(globalThis, "__wasmPolicyOwnedWorkers", { get: () => owned.size });
      globalThis.Worker = class extends NativeWorker {
        private policyOwned: boolean;
        constructor(url: string | URL, options?: WorkerOptions) {
          super(url, options);
          this.policyOwned = options?.name?.startsWith("template-policy-") ?? false;
          if (this.policyOwned) owned.add(this);
        }
        terminate() {
          super.terminate();
          if (this.policyOwned) owned.delete(this);
        }
      };
    });
  });

  const ownedWorkers = async (page: import("@playwright/test").Page, expected: number) => {
    await expect.poll(() => page.evaluate(() =>
      (globalThis as typeof globalThis & { __wasmPolicyOwnedWorkers: number }).__wasmPolicyOwnedWorkers
    )).toBe(expected);
  };
  test.skip(!selected, "requires the explicitly compiled production WASM example");

  test("installed Worker returns validated advisory bytes without game effects", async ({ page }) => {
    await page.goto(base);
    const root = page.locator("#wasm-policy-example");
    await expect(root).toHaveAttribute("data-game-effects", "0");
    await root.getByRole("button", { name: "Load policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    await root.getByRole("button", { name: "Request advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "advice");
    await expect(page.locator("#wasm-policy-status")).toContainText("Advice: observe");
    await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "disposed");
    await ownedWorkers(page, 0);
    await root.getByRole("button", { name: "Use retained advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "refused");
  });

  test("replacement invalidates actual retained advice and accepts independent Rust input", async ({ page }) => {
    await page.goto(base);
    const root = page.locator("#wasm-policy-example");
    await root.getByRole("button", { name: "Load policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    await root.getByRole("button", { name: "Request advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "advice");
    await root.getByRole("combobox", { name: "Policy guest" }).selectOption("rust-normal");
    await root.getByRole("button", { name: "Replace policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    await root.getByRole("button", { name: "Use retained advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "refused");
    await root.getByRole("button", { name: "Request advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "advice");
  });

  test("disposed replacement preparation cannot become current advice", async ({ page }) => {
    await page.goto(base);
    const root = page.locator("#wasm-policy-example");
    await root.getByRole("button", { name: "Load policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    // Hold the actual second artifact acquisition while disposing the mounted owner.
    let releaseArtifact!: () => void;
    const held = new Promise<void>(resolve => { releaseArtifact = resolve; });
    let observed!: () => void;
    const requested = new Promise<void>(resolve => { observed = resolve; });
    await page.route("**/wasm-policy/rust-normal.wasm", async route => {
      observed();
      await held;
      await route.continue();
    });
    await root.getByRole("combobox", { name: "Policy guest" }).selectOption("rust-normal");
    await root.getByRole("button", { name: "Replace policy", exact: true }).click();
    await requested;
    await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
    const delivered = page.waitForResponse(response => response.url().endsWith("/wasm-policy/rust-normal.wasm"));
    releaseArtifact();
    await delivered;
    await expect(root).toHaveAttribute("data-state", "disposed");
    await ownedWorkers(page, 0);
    await root.getByRole("button", { name: "Request advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "refused");
  });

  test("each repeated page mount explicitly disposes its policy Worker handles", async ({ page }) => {
    for (let iteration = 0; iteration < 3; iteration++) {
      await page.goto(base);
      const root = page.locator("#wasm-policy-example");
      await ownedWorkers(page, 0);
      await root.getByRole("button", { name: "Load policy", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "ready");
      await ownedWorkers(page, 1);
      await root.getByRole("button", { name: "Request advice", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "advice");
      await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "disposed");
      await ownedWorkers(page, 0);
      await expect(root).toHaveAttribute("data-game-effects", "0");
    }
  });

  test("settled shutdown is followed by idempotent disposal and no owned Worker handles", async ({ page }) => {
    await page.goto(base);
    const root = page.locator("#wasm-policy-example");
    await root.getByRole("button", { name: "Load policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    await root.getByRole("button", { name: "Shutdown policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "shutdown");
    await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "disposed");
    await ownedWorkers(page, 0);
    await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
    await ownedWorkers(page, 0);
    await root.getByRole("button", { name: "Use retained advice", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "refused");
  });

  test("malformed candidate admission cannot become advice and disposal terminates owned handles", async ({ page }) => {
    await page.goto(base);
    const root = page.locator("#wasm-policy-example");
    await root.getByRole("button", { name: "Load policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "ready");
    await ownedWorkers(page, 1);
    // Deliver an incomplete WASM header to the production candidate admission path.
    await page.route("**/wasm-policy/rust-normal.wasm", route => route.fulfill({
      status: 200, contentType: "application/wasm", body: Buffer.from([0, 97, 115, 109])
    }));
    await root.getByRole("combobox", { name: "Policy guest" }).selectOption("rust-normal");
    await root.getByRole("button", { name: "Replace policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "refused");
    await expect(page.locator("#wasm-policy-status")).not.toContainText("Advice:");
    await expect(root).toHaveAttribute("data-game-effects", "0");
    await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
    await expect(root).toHaveAttribute("data-state", "disposed");
    await ownedWorkers(page, 0);
  });

  for (const variant of ["c-malformed", "c-trap", "c-loop"]) {
    test(`${variant} is refused without replay or game authority`, async ({ page }) => {
      await page.goto(base);
      const root = page.locator("#wasm-policy-example");
      await root.getByRole("combobox", { name: "Policy guest" }).selectOption(variant);
      await root.getByRole("button", { name: "Load policy", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "ready");
      await root.getByRole("button", { name: "Request advice", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "refused");
      await expect(root).toHaveAttribute("data-game-effects", "0");
      await root.getByRole("button", { name: "Dispose policy", exact: true }).click();
      await expect(root).toHaveAttribute("data-state", "disposed");
    await ownedWorkers(page, 0);
    });
  }
});
