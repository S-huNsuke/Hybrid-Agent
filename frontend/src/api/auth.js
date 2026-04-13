import http from "./http";

export function login(payload) {
  return http.post("/auth/login", payload);
}

export function register(payload) {
  return http.post("/auth/register", payload);
}

export function getCurrentUser() {
  return http.get("/auth/me");
}

export function refreshToken() {
  return http.post("/auth/refresh");
}

export function logout() {
  return http.post("/auth/logout");
}

export function fetchProviders(params = {}) {
  return http.get("/providers", { params });
}

export function getProvider(providerId) {
  return http.get(`/providers/${providerId}`);
}

export function createProvider(payload) {
  return http.post("/providers", payload);
}

export function updateProvider(providerId, payload) {
  return http.patch(`/providers/${providerId}`, payload);
}

export function deleteProvider(providerId) {
  return http.delete(`/providers/${providerId}`);
}

export function normalizeProviderHealth(data = {}) {
  const ok = Boolean(data?.ok);
  const status = typeof data?.status === "string" && data.status ? data.status : ok ? "healthy" : "unknown_error";
  const message =
    typeof data?.message === "string" && data.message
      ? data.message
      : ok
        ? "Provider endpoint is reachable"
        : "Provider health check failed";
  return {
    provider_id: data?.provider_id || "",
    ok,
    status,
    message,
    latency_ms: typeof data?.latency_ms === "number" ? data.latency_ms : null,
    model: data?.model || null,
    http_status: typeof data?.http_status === "number" ? data.http_status : null,
    error: typeof data?.error === "string" ? data.error : "",
  };
}

export function checkProviderHealth(providerId) {
  return http
    .post(`/providers/${providerId}/health`)
    .then((response) => ({
      ...response,
      data: normalizeProviderHealth(response?.data),
    }));
}
