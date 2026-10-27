import { test, expect, type Page } from "@playwright/test";

const headers = { Authorization: "Bearer e2e-only-token-not-a-real-secret-123456" };
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Local development token").fill("e2e-only-token-not-a-real-secret-123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Numbers, one next step at a time" })).toBeVisible();
}

test("QA-5: a delayed old goal read cannot erase a newly saved roadmap", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "Deterministic network scheduling needs one browser run.");
  test.fail(true, "Known defect: the target-triggered load commits an obsolete goal after saving.");
  let reads = 0;
  let release!: () => void;
  let started!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const requested = new Promise<void>((resolve) => { started = resolve; });
  await page.route("**/api/v1/me/goal", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    reads++;
    if (reads === 1) return route.fulfill({ json: null });
    if (reads === 2) {
      started();
      await held;
      return route.fulfill({ json: null });
    }
    return route.continue();
  });
  await login(page);
  await page.getByRole("checkbox", { name: "Divisibility rules", exact: true }).check();
  await requested;
  await page.getByRole("button", { name: "Set goal", exact: true }).click();
  await expect(page.getByText("Recommended next step", { exact: true })).toBeVisible();
  const staleRead = page.waitForResponse((response) => response.url().endsWith("/v1/me/goal") && response.request().method() === "GET");
  release();
  await staleRead;
  await expect(page.getByText("Recommended next step", { exact: true })).toBeVisible({ timeout: 2000 });
});

test("QA-6: retrying after a lost save response reuses the whole submission", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "Deterministic network failure needs one browser run.");
  test.fail(true, "Known defect: the retry reuses its key but changes duration_ms, causing HTTP 409.");
  await login(page);
  const today = await (await page.request.get("/api/v1/me/today", { headers })).json();
  if (today.active_session_id) await page.request.post(`/api/v1/sessions/${today.active_session_id}/abandon`, { headers });
  const started = await page.request.post("/api/v1/sessions", { headers, data: { skill_id: "divisibility", mode: "practice" } });
  expect(started.status()).toBe(201);
  const { session_id } = await started.json();
  try {
    await page.goto("/session/" + session_id);
    await page.getByLabel("Your answer (a whole number)").fill("3");
    let attempts = 0;
    await page.route("**/api/v1/assignments/*/submit", async (route) => {
      if (++attempts === 1) {
        const response = await route.fetch();
        expect(response.status()).toBe(200);
        await route.abort("failed"); // Server committed; browser never received the response.
      } else await route.continue();
    });
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    await expect(page.getByText("Your answer was not saved. Try again.", { exact: true })).toBeVisible();
    const retry = page.waitForResponse((response) => response.url().endsWith("/submit"));
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    expect((await retry).status()).toBe(200);
  } finally {
    await page.request.post(`/api/v1/sessions/${session_id}/abandon`, { headers });
  }
});
