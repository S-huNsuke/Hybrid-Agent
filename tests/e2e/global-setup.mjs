const FRONTEND_WAIT_TIMEOUT_MS = Number(process.env.E2E_FRONTEND_TIMEOUT_MS || 90000);
const API_WAIT_TIMEOUT_MS = Number(process.env.E2E_API_TIMEOUT_MS || 60000);
const POLL_INTERVAL_MS = Number(process.env.E2E_WAIT_INTERVAL_MS || 1500);

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHttp(url, timeoutMs, label) {
  const startedAt = Date.now();
  let lastError = "";

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url, {
        method: "GET",
        cache: "no-store",
      });
      if (response.ok || response.status === 401 || response.status === 404) {
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error(`${label} not reachable at ${url}. Last error: ${lastError}`);
}

export default async function globalSetup(config) {
  if (process.env.E2E_SKIP_SERVICE_CHECK === "1") {
    return;
  }

  const configuredBaseURL = config.projects?.[0]?.use?.baseURL;
  const baseURL = process.env.E2E_BASE_URL || configuredBaseURL || "http://127.0.0.1:3000";
  const apiHealthURL = process.env.E2E_API_HEALTH_URL || "http://127.0.0.1:18000/health";

  await waitForHttp(baseURL, FRONTEND_WAIT_TIMEOUT_MS, "Frontend");
  await waitForHttp(apiHealthURL, API_WAIT_TIMEOUT_MS, "API health endpoint");
}
