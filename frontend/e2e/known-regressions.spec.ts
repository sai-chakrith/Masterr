import { test, expect, type Page } from "@playwright/test";

const headers = { Authorization: "Bearer e2e-only-token-not-a-real-secret-123456" };
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Local development token").fill("e2e-only-token-not-a-real-secret-123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Numbers, one next step at a time" })).toBeVisible();
}

test("QA-5: editing targets does not refetch and erase a newly saved roadmap", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "Deterministic network scheduling needs one browser run.");
  let reads = 0;
  await page.route("**/api/v1/me/goal", async route => {
    if (route.request().method() === "GET") reads++;
    if (route.request().method() === "GET" && reads === 1) return route.fulfill({ json: null });
    return route.continue();
  });
  await login(page);
  const initialReads = reads;
  await page.getByRole("checkbox", { name: "Divisibility rules", exact: true }).check();
  await page.getByRole("button", { name: "Set goal", exact: true }).click();
  await expect(page.getByText("Recommended next step", { exact: true })).toBeVisible();
  expect(reads).toBe(initialReads + 1);
  await page.reload();
  await expect(page.getByText("Recommended next step", { exact: true })).toBeVisible();

});

test("QA-6: retrying after a lost save response reuses the whole submission", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "Deterministic network failure needs one browser run.");
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
    await expect(page.getByText("Could not confirm your answer. Try again to resend the same answer safely.", { exact: true })).toBeVisible();
    const retry = page.waitForResponse((response) => response.url().endsWith("/submit"));
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    expect((await retry).status()).toBe(200);
  } finally {
    await page.request.post(`/api/v1/sessions/${session_id}/abandon`, { headers });
  }
});


test("lesson Markdown is semantic and raw HTML remains harmless text", async ({ page }) => {
  await login(page);
  await page.route("**/api/v1/me/tutor/divisibility", route => route.fulfill({ json: {
    id: "render-fixture", skill_id: "divisibility", usage: [], parts: {
      lesson: { text: "# Sample lesson\n\nStatus: draft. Original material for human review.\n\n**Counting multiples**\n- **Count** the multiples.\n- Subtract overlaps.\n\n<img src=x onerror=alert(1)>", generated_by: "fallback", cached: false },
      personal: { text: "Your recorded answer.", generated_by: "fallback", cached: false }
    }
  }}));
  await page.goto("/tutor?topic=divisibility");
  await page.getByRole("button", { name: "Open tutoring", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sample lesson", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Counting multiples", exact: true })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Count the multiples." })).toBeVisible();
  await expect(page.getByText("Status: draft.", { exact: false })).toHaveCount(0);
  await expect(page.locator("img[src=x]")).toHaveCount(0);
  await expect(page.getByText("<img src=x onerror=alert(1)>", { exact: true })).toBeVisible();
});
