import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  attachBrowserDiagnostics,
  expectEventually,
  resolveApiBaseURL,
} from "./support/harness.mjs";

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirPath = path.dirname(currentFilePath);
const fixturePath = path.resolve(currentDirPath, "fixtures", "sample.txt");

test("smoke: register/login -> provider -> user -> upload -> chat", async ({ page }, testInfo) => {
  test.slow();

  const seed = `${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const adminUsername = `smoke_admin_${seed}`;
  const adminPassword = "SmokePass_123!";
  const userUsername = `smoke_user_${seed}`;
  const userPassword = "UserPass_123!";
  const consoleErrors = [];
  const pageErrors = [];
  const authRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  page.on("response", (response) => {
    const url = response.url();
    if (!url.includes("/auth/")) {
      return;
    }
    const record = {
      url,
      status: response.status(),
    };
    authRequests.push(record);
    console.log(`[auth-response] ${record.status} ${record.url}`);
  });

  try {
    await test.step("register admin and enter app", async () => {
      await page.goto("/login", { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("button", { name: "注册" })).toBeVisible();

      await page.getByRole("button", { name: "注册" }).click();
      await page.getByLabel("用户名").fill(adminUsername);
      await page.getByLabel("邮箱").fill(`smoke_${seed}@example.com`);
      await page.getByLabel("密码").fill(adminPassword);
      await page.getByRole("button", { name: "注册并登录" }).click();

      await expect(page).toHaveURL(/\/$/);
    });

    await test.step("open settings and validate runtime model catalog", async () => {
      await page.goto("/settings", { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: "个人设置" })).toBeVisible();

      const modelsResponse = await page.request.get(`${resolveApiBaseURL()}/api/v1/models`);
      expect(modelsResponse.ok()).toBeTruthy();
      const modelsPayload = await modelsResponse.json();
      const models =
        Array.isArray(modelsPayload)
          ? modelsPayload
          : modelsPayload?.models || modelsPayload?.items || modelsPayload?.data || [];

      expect(Array.isArray(models)).toBeTruthy();
      expect(models.length).toBeGreaterThan(0);
      expect(typeof models[0]?.id).toBe("string");
      expect(typeof models[0]?.name).toBe("string");
    });

    await test.step("create provider and managed user", async () => {
      await page.getByPlaceholder("例如：OpenAI 主账号").fill(`Smoke Provider ${seed}`);
      await page.locator("select").first().selectOption("openai");
      await page.getByPlaceholder("仅创建/更新时可提交").fill("sk-smoke-test-key");
      await page.getByRole("textbox", { name: "模型列表" }).fill("gpt-4.1-mini");
      await page.getByRole("textbox", { name: "默认模型" }).fill("gpt-4.1-mini");
      await page.getByRole("button", { name: "创建提供商" }).click();

      await expect(page.getByText(`Smoke Provider ${seed}`, { exact: false })).toBeVisible();

      await page.goto("/admin", { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: "管理后台" })).toBeVisible();

      await page.getByLabel("用户名", { exact: true }).fill(userUsername);
      await page.getByLabel("邮箱").fill(`smoke_user_${seed}@example.com`);
      await page.getByLabel("初始密码").fill(userPassword);
      await page.getByRole("button", { name: "创建账号" }).click();

      await expect(page.locator(".table-row").filter({ hasText: userUsername }).first()).toBeVisible();
    });

    await test.step("upload fixture document and wait parsing", async () => {
      await page.goto("/documents", { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: "文档管理工作台" })).toBeVisible();

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(fixturePath);
      await page.getByRole("button", { name: /上传|批量上传/ }).click();

      await expect(page.getByText("上传任务", { exact: false })).toBeVisible();
      await expectEventually(
        async () => {
          const doneCount = await page.getByText("解析完成", { exact: false }).count();
          return doneCount > 0;
        },
        {
          timeoutMs: 90000,
          message: "Document parsing did not reach '解析完成' in time.",
        },
      );
    });

    await test.step("chat and wait assistant answer", async () => {
      await page.goto("/chat", { waitUntil: "domcontentloaded" });
      await expect(page.getByRole("heading", { name: "对话工作台" })).toBeVisible();

      await page.getByPlaceholder("输入你的问题").fill("你好，简单介绍一下项目。");
      await page.getByRole("button", { name: "发送" }).click();

      const assistantMessage = page.locator(".message-card.assistant .message-card__content").first();
      await expect(assistantMessage).toBeVisible({ timeout: 90000 });
      await expectEventually(
        async () => {
          const text = (await assistantMessage.textContent())?.trim() || "";
          return text.length > 0;
        },
        {
          timeoutMs: 90000,
          message: "Assistant message stayed empty.",
        },
      );
    });
  } finally {
    await testInfo.attach("console-errors.json", {
      body: Buffer.from(JSON.stringify(consoleErrors, null, 2), "utf-8"),
      contentType: "application/json",
    });
    await testInfo.attach("page-errors.json", {
      body: Buffer.from(JSON.stringify(pageErrors, null, 2), "utf-8"),
      contentType: "application/json",
    });
    await testInfo.attach("auth-requests.json", {
      body: Buffer.from(JSON.stringify(authRequests, null, 2), "utf-8"),
      contentType: "application/json",
    });
    await attachBrowserDiagnostics(page, testInfo);
  }
});
