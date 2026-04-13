const DEFAULT_API_BASE_URL = "http://127.0.0.1:18000";

export function resolveApiBaseURL() {
  return (process.env.E2E_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

export async function expectEventually(fn, { timeoutMs = 60000, intervalMs = 1000, message }) {
  const startedAt = Date.now();
  let lastValue;
  let lastError;

  while (Date.now() - startedAt < timeoutMs) {
    try {
      lastValue = await fn();
      if (lastValue) {
        return lastValue;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  const errorMessage = message || "Condition was not met before timeout.";
  const debugValue = typeof lastValue === "undefined" ? "" : ` Last value: ${JSON.stringify(lastValue)}`;
  const debugError = lastError ? ` Last error: ${String(lastError)}` : "";
  throw new Error(`${errorMessage}${debugValue}${debugError}`);
}

export async function attachBrowserDiagnostics(page, testInfo) {
  const storageSnapshot = await page.evaluate(() => ({
    localStorage: { ...localStorage },
    sessionStorage: { ...sessionStorage },
  }));

  await testInfo.attach("browser-storage.json", {
    body: Buffer.from(JSON.stringify(storageSnapshot, null, 2), "utf-8"),
    contentType: "application/json",
  });
}
