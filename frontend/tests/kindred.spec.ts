import { expect, test } from "@playwright/test";

test("create, chat, autonomous message, notification setup, and export", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    permissions: ["notifications"],
  });
  const page = await context.newPage();
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/");
  const existingResponse = await page.request.get("/api/characters");
  const existingCharacters = (await existingResponse.json()) as Array<{
    id: number;
    name: string;
  }>;
  for (const character of existingCharacters.filter((item) => item.name === "Rowan Test")) {
    await page.request.delete(`/api/characters/${character.id}`);
  }
  await page.reload();
  consoleErrors.length = 0;
  await expect(page).toHaveTitle("Kindred");
  await expect(page.getByRole("button", { name: "Kindred" })).toBeVisible();
  await expect(page.getByText("Local model ready", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "New character" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByLabel("Name").fill("Rowan Test");
  await page
    .getByLabel("Description")
    .fill("A steady test companion who answers in compact messages.");
  await page.getByLabel("Personality").fill("Calm, curious, and direct.");
  await page.getByLabel("Speaking style").fill("One or two short sentences.");
  await page.getByRole("button", { name: "Save character" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();

  const rowanChat = page.getByRole("button", { name: /Rowan Test.*No messages yet/ });
  await expect(rowanChat).toBeVisible();
  await rowanChat.click();
  await expect(page.getByRole("heading", { name: "Begin with Rowan Test" })).toBeVisible();

  await page.getByLabel("Message").fill("Are you awake?");
  await page.getByRole("button", { name: "Send" }).click();
  const conversation = page.getByLabel("Selected conversation");
  await expect(
    conversation.getByText("Mock reply: I heard you. What are we making tonight?"),
  ).toBeVisible();
  await expect(conversation.getByText("Are you awake?", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Test one character now").selectOption({ label: "Rowan Test" });
  await expect(page.getByText("Forced manual daemon check")).toBeVisible();

  await page.getByRole("button", { name: "Chats" }).click();
  await expect(
    conversation.getByText(
      "Mock initiative: The rain started. It made me wonder how your work is going.",
    ),
  ).toBeVisible();

  await page.screenshot({ path: "/tmp/kindred-desktop.png", fullPage: false });

  await page.getByRole("button", { name: "Enable notifications" }).click();
  await expect(
    page.getByText("In-app alerts enabled. Add VAPID keys for background Web Push."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Activity" }).click();
  await expect(page.getByRole("link", { name: "Export Markdown" })).toBeVisible();
  await expect(page.getByText("Are you awake?", { exact: true })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("kindred-logs.json");

  expect(consoleErrors).toEqual([]);
  await context.close();
});

test("mobile chat remains readable and navigable", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Chats" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Characters" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  await page.screenshot({ path: "/tmp/kindred-mobile.png", fullPage: false });
  await context.close();
});
