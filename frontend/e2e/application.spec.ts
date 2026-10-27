import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Local development token").fill("e2e-only-token-not-a-real-secret-123456");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Numbers, one next step at a time" })).toBeVisible();
}

async function answerSession(page: Page, dontKnow = false) {
  let last: Record<string, unknown> = {};
  for (let i = 0; i < 14; i++) {
    await expect(page.getByRole("button", { name: "Submit", exact: true })).toBeVisible();
    if (!dontKnow) await page.getByLabel("Your answer (a whole number)").fill("3");
    const saved = page.waitForResponse((r) => r.url().endsWith("/submit") && r.request().method() === "POST");
    await page.getByRole("button", { name: dontKnow ? "I don't know" : "Submit", exact: true }).click();
    const response = await saved;
    expect(response.status()).toBe(200);
    last = await response.json();
    if (last.session_complete) return last;
    // The next question fetch must complete before sending its answer.
    await expect(page.getByRole("button", { name: "I don't know", exact: true })).toBeEnabled();
  }
  throw new Error("Synthetic session did not complete within its documented maximum.");
}

test("diagnosis, tutoring, adaptive practice, retest and scheduled review", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "The stateful full journey runs once; mobile gets independent layout and account checks.");
  await login(page);
  await page.getByRole("checkbox", { name: "Divisibility rules", exact: true }).check();
  await page.getByRole("button", { name: "Set goal", exact: true }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Diagnostic", exact: true })).toBeVisible();
  const diagnosis = await answerSession(page, true);
  expect(diagnosis.decision).toBe("gap");
  await page.getByRole("link", { name: "Understand my mistakes" }).click();
  await expect(page.getByRole("combobox", { name: "Topic", exact: true })).toHaveValue("divisibility");
  await page.getByRole("button", { name: "Open tutoring" }).click();
  await expect(page.getByRole("heading", { name: "Your missed questions" })).toBeVisible();
  await expect(page.getByText("Fallback explanation").first()).toBeVisible();
  await page.getByRole("button", { name: "Continue to practice" }).click();
  let result = await answerSession(page);
  for (let block = 0; block < 6; block++) {
    await page.getByRole("link", { name: "Back to roadmap" }).click();
    const suggestion = page.locator("section[aria-labelledby='next-step-title']");
    if ((await suggestion.innerText()).includes("independent check")) break;
    await suggestion.getByRole("button", { name: "Start", exact: true }).click();
    result = await answerSession(page);
    if (block === 5) throw new Error("Practice never unlocked the synthetic retest.");
  }
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Retest", exact: true })).toBeVisible();
  result = await answerSession(page);
  expect(result.result).toBe("retest_passed");
  await page.reload();
  await expect(page.getByText("Retest passed. The gap is resolved.", { exact: true })).toBeVisible();
  await expect(page.getByText("10 of 10 correct.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to roadmap" }).click();
  await expect(page.getByText("Resolved", { exact: true }).first()).toBeVisible();
  const today = await page.request.get("/api/v1/me/today", { headers: { Authorization: "Bearer e2e-only-token-not-a-real-secret-123456" } });
  const scheduled = (await today.json()).reviews;
  expect(scheduled.length).toBeGreaterThan(0);
  expect(Date.parse(scheduled[0].due_at)).toBeGreaterThan(Date.now());
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your learning history" })).toBeVisible();
  await expect(page.getByText("divisibility · verification")).toBeVisible();
});

test("reviewer can save drafts and explicitly publish notes", async ({ page }, info) => {
  await login(page);
  await page.getByRole("link", { name: "Account", exact: true }).click();
  await page.getByRole("link", { name: "Open content review" }).click();
  await page.getByLabel("Content document").selectOption("notes:divisibility");
  await page.getByRole("button", { name: "Review document", exact: true }).click();
  const editor = page.getByLabel("Content JSON");
  await expect(editor).toBeVisible();
  await editor.fill(JSON.stringify({ text: "Synthetic browser-test notes. Divisibility by 6 requires both 2 and 3." }, null, 2));
  await expect(page.getByRole("button", { name: "Publish reviewed content" })).toBeDisabled();
  await page.getByRole("button", { name: "Save edits as draft" }).click();
  await expect(page.getByRole("status")).toContainText("Saved as a new draft");
  await page.getByRole("checkbox", { name: /I personally checked/ }).check();
  await page.getByRole("button", { name: "Publish reviewed content" }).click();
  await expect(page.getByRole("status")).toContainText("Published with your authenticated reviewer identity");
});

test("timed practice withholds results until finished", async ({ page }, info) => {
  await login(page);
  await page.getByRole("link", { name: "Timed practice", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Timed mixed practice", exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Divisibility rules", exact: true }).check();
  await expect(page.getByRole("checkbox", { name: "Divisibility rules", exact: true })).toBeChecked();
  await page.getByLabel("Questions", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Start timed practice", exact: true }).click();
  for (let i = 0; i < 3; i++) {
    await page.getByLabel("Your answer", { exact: true }).fill("3");
    await page.getByRole("button", { name: "Save answer", exact: true }).click();
    if (i < 2) await expect(page.getByRole("timer")).toContainText(`${i + 1} of 3 answered`);
  }
  await expect(page.getByText("3 of 3 correct · 3 answered")).toBeVisible();
});

test("account controls, mobile layout and sign-out", async ({ page }, info) => {
  await login(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your account", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete my account" })).toBeDisabled();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download my data" }).click();
  expect((await download).suggestedFilename()).toBe("mastrr-learning-data.json");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("account.png"), fullPage: true });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/tutor");
  await expect(page).toHaveURL(/\/login$/);
});
