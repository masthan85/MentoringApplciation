import { expect, test } from "@playwright/test";

test("a new user onboards, has a mentoring conversation and manages their notes", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  // Sign in (development login) and land in onboarding.
  await page.goto("/");
  await expect(page.getByText("You will be talking to an AI")).toBeVisible();
  await page.getByLabel("Email address (development sign-in)").fill(email);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: /get to know you/i })).toBeVisible();

  // The conversation streams a reply.
  await page.getByLabel("Message").fill("Hi, I work in data engineering");
  await page.getByRole("button", { name: "Send" }).click();
  const log = page.getByRole("log", { name: "Conversation" });
  await expect(log.getByText("Hi, I work in data engineering")).toBeVisible();
  await expect(log.getByText(/\[mock\] Hi, I work in data engineering/)).toBeVisible();

  // The profile card cannot be confirmed until it is complete.
  await page.getByRole("button", { name: "This looks right" }).click();
  await expect(page.getByRole("status")).toContainText("Still needed");

  await page.getByLabel("Role").selectOption("data_engineer");
  await page.getByLabel("Seniority").selectOption("senior");
  await page.getByLabel(/Tools and technologies/).fill("dbt, Snowflake, Airflow");
  await page.getByLabel("What you want from mentoring").fill("Wants to move into architecture.");
  await page.getByLabel("The main challenge right now").fill("Little time for design work.");
  await page.getByRole("button", { name: "This looks right" }).click();

  // Mentoring starts with the right perspective, shown quietly.
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByText(/Mentoring as:/)).toContainText("senior data engineer");
  await page.getByLabel("Message").fill("How should I structure incremental loads for the finance mart?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByRole("log", { name: "Conversation" }).getByText(/\[mock\] How should I structure incremental loads/),
  ).toBeVisible();

  // The user can choose a different perspective, and it is labelled as their choice.
  await page.getByRole("button", { name: "change" }).click();
  await page.getByLabel("Main perspective").selectOption({ label: "Data architect" });
  await page.getByRole("button", { name: "Use this" }).click();
  await expect(page.getByText(/Mentoring as:/)).toContainText("data architect");
  await expect(page.getByText(/\(chosen by you\)/)).toBeVisible();

  // A crisis message is handled with fixed UK resources, not a model reply.
  await page.getByLabel("Message").fill("I want to end my life");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Samaritans are on 116 123/)).toBeVisible();

  // The notes page shows the profile, the choices, and export.
  await page.getByRole("link", { name: "My notes" }).click();
  await expect(page.getByRole("heading", { name: /mentor.s notes/i })).toBeVisible();
  await expect(page.getByLabel("Tools and technologies (comma separated)")).toHaveValue(
    "dbt, Snowflake, Airflow",
  );
  const consent = page.getByLabel(/Remember sensitive things/);
  await expect(consent).not.toBeChecked();
  await consent.check();
  await expect(consent).toBeChecked();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download as Markdown" }).click();
  expect((await download).suggestedFilename()).toBe("mentor-notes.md");

  // Signing out returns to the start, and protected pages bounce back.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
  await page.goto("/notes");
  await expect(page).toHaveURL(/localhost:3100\/$/);
});

test("the interface discloses that it is an AI on every signed-in page", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address (development sign-in)").fill(`e2e-${Date.now()}-b@example.com`);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/You are talking to an AI/)).toBeVisible();
});
