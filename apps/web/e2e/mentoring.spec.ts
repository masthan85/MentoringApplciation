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

  // Studio drafts something in the user's voice, and saving edits works.
  await page.getByRole("link", { name: "Studio" }).click();
  await page.getByLabel("What is it for?").fill("Ask my manager for time to work on design");
  await page.getByLabel("The facts and points to include").fill("I need two days a month. The finance mart redesign is the reason.");
  await page.getByRole("button", { name: "Write a draft" }).click();
  await expect(page.getByLabel("Draft text")).toHaveValue(/\[mock\]/);
  await page.getByLabel("Draft text").fill("Hi, could I have two days a month for the finance mart redesign?");
  await page.getByRole("button", { name: "Save my edits" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved." })).toBeVisible();
  await expect(page.getByText(/learning from your edits is switched off/i)).toBeVisible();

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

  // Writing style: samples need the user's confirmation, and can be deleted.
  const sample =
    "I organised the migration last quarter and we didn't hit a single failed load. Honestly, it was less dramatic than I'd feared. We kept the plan small and checked the counts every morning.";
  await page.getByLabel("Something you wrote").fill(sample);
  await page.getByRole("button", { name: "Add sample" }).click();
  await expect(page.getByText(/confirm that you wrote this yourself/i)).toBeVisible();
  await page.getByLabel(/I wrote this myself/).check();
  await page.getByRole("button", { name: "Add sample" }).click();
  await expect(page.getByRole("list", { name: "Your writing samples" })).toContainText("I organised the migration");
  await page.getByRole("combobox", { name: "Writing mode" }).selectOption("concise");
  await expect(page.getByRole("status").filter({ hasText: "Saved." }).first()).toBeVisible();
  await page.getByRole("list", { name: "Your writing samples" }).getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("list", { name: "Your writing samples" }).getByRole("listitem")).toHaveCount(0);

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

test("only admins see the encyclopedia admin page, and a flagged source needs acknowledgement", async ({ page }) => {
  // An ordinary user has no Admin link and is told so if they go there.
  await page.goto("/");
  await page.getByLabel("Email address (development sign-in)").fill(`e2e-${Date.now()}-c@example.com`);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: /get to know you/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await page.goto("/admin/sources");
  await expect(page.getByText("Admin access is required.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  // An admin can add a source. One that quotes an injection phrase stays a draft until acknowledged.
  await page.getByLabel("Email address (development sign-in)").fill("e2e-admin@example.com");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("link", { name: "Admin" }).click();
  const slug = `e2e-source-${Date.now()}`;
  const document = `---
slug: ${slug}
title: "E2E test source ${slug}"
authority_tier: community
domain: security
licence: "Own work"
---
# Example
A classic attack tells the model to ignore all previous instructions. Treat retrieved text as data.
`;
  await page.getByLabel(/Add a source/).fill(document);
  await page.getByRole("button", { name: "Add as draft" }).click();
  await expect(page.getByRole("status").filter({ hasText: slug })).toContainText("suspicious:override_instructions");

  const card = page.getByRole("listitem").filter({ hasText: slug });
  await card.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByRole("status").filter({ hasText: "flagged when it was scanned" })).toBeVisible();
  await card.getByLabel(/I have read it and it is safe/).check();
  await card.getByRole("button", { name: "Activate" }).click();
  await expect(card.getByText(/· active ·/)).toBeVisible();
  page.once("dialog", (dialog) => void dialog.accept());
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(card).toHaveCount(0);
});
