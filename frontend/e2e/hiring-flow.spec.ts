import { expect, test, type Page } from "@playwright/test";

/**
 * The full hiring story, in the browser, against the real API:
 *   1. a candidate registers, is told to upload a resume, uploads one and applies;
 *   2. the hiring manager shortlists the candidate and schedules an interview;
 *   3. the candidate sees the interview and confirms;
 *   4. the HR manager sees the candidate emails in the email log.
 */
const PASSWORD = process.env.E2E_PASSWORD || "";
const HR = "hr.e2e@instantmechanic.in";
const HIRING = "hiring.e2e@instantmechanic.in";
const JOB = "Roadside Mechanic (E2E)";
const stamp = Date.now();
const candidate = { name: `Ravi Test ${stamp}`, email: `ravi.${stamp}@example.com`, password: "Candidate-pass-123" };

// The smallest valid PDF the server accepts (it checks the %PDF- header, not the content).
const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");

test.describe.configure({ mode: "serial" });

async function signIn(page: Page, email: string, password: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

test.beforeAll(() => {
  if (PASSWORD.length < 12) throw new Error("Set E2E_PASSWORD to the password used with backend/scripts/e2e_seed.py");
});

test("candidate registers, uploads a resume and applies", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Full name").fill(candidate.name);
  await page.getByLabel("Email").fill(candidate.email);
  await page.getByLabel("Password", { exact: true }).fill(candidate.password);
  await page.getByLabel("Repeat password").fill(candidate.password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Account created" })).toBeVisible();

  await signIn(page, candidate.email, candidate.password);
  await page.goto("/portal/jobs");
  const card = page.locator("article", { hasText: JOB });
  await expect(card.getByRole("link", { name: "Upload resume to apply" })).toBeVisible();

  await page.goto("/portal/resume");
  await page.locator('input[type="file"]').setInputFiles({ name: "ravi-resume.pdf", mimeType: "application/pdf", buffer: PDF });
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Upload resume" }).click();
  await expect(page.getByText("ravi-resume.pdf")).toBeVisible();

  await page.goto("/portal/jobs");
  await card.getByRole("button", { name: "Apply" }).click();
  await expect(card.getByText(/applied/i)).toBeVisible();
  await page.goto("/portal/applications");
  await expect(page.getByText(JOB)).toBeVisible();
});

test("hiring manager shortlists and schedules an interview", async ({ page }) => {
  await signIn(page, HIRING, PASSWORD);
  await page.goto("/candidates");
  await page.getByRole("link", { name: candidate.name }).click();
  await expect(page.getByRole("heading", { name: candidate.name })).toBeVisible();

  await page.getByLabel("Move to stage").selectOption("shortlisted");
  await page.getByLabel("Note for this change").fill("Good experience with roadside repairs.");
  await page.getByRole("button", { name: "Move" }).click();
  await expect(page.locator(".pill", { hasText: /shortlisted/i }).first()).toBeVisible();

  const when = new Date(Date.now() + 3 * 24 * 3600 * 1000);
  when.setHours(11, 0, 0, 0);
  const local = `${when.getFullYear()}-${String(when.getMonth() + 1).padStart(2, "0")}-${String(when.getDate()).padStart(2, "0")}T11:00`;
  await page.getByLabel("Date and time").fill(local);
  await page.getByRole("button", { name: "Schedule interview" }).click();
  await expect(page.getByText("None scheduled.")).toHaveCount(0);
});

test("candidate sees the interview and confirms", async ({ page }) => {
  await signIn(page, candidate.email, candidate.password);
  await page.goto("/portal/interviews");
  await page.getByRole("button", { name: "I will attend" }).click();
  await expect(page.getByRole("button", { name: "I will attend" })).toHaveCount(0);
});

test("HR manager sees the candidate emails", async ({ page }) => {
  await signIn(page, HR, PASSWORD);
  await page.goto("/notifications");
  await page.getByRole("tab", { name: "Emails to candidates" }).click();
  await expect(page.getByText(candidate.email).first()).toBeVisible();
});

test("a signed-out visitor is sent to sign in", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
