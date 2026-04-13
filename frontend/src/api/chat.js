import http from "./http";

const TOKEN_STORAGE_KEY = "hybrid-agent-token";
const API_KEY_STORAGE_KEY = "hybrid-agent-api-key";

function normalizeBaseUrl(baseUrl) {
  if (!baseUrl) {
    return "";
  }
  return baseUrl.replace(/\/+$/, "");
}

function toModelOption(candidate) {
  if (!candidate) {
    return null;
  }
  if (typeof candidate === "string") {
    const id = candidate.trim();
    if (!id) {
      return null;
    }
    return { id, name: id, description: "" };
  }
  const id = String(
    candidate.id ||
      candidate.model_id ||
      candidate.model ||
      candidate.value ||
      candidate.name ||
      "",
  ).trim();
  if (!id) {
    return null;
  }
  const name = String(
    candidate.name ||
      candidate.display_name ||
      candidate.label ||
      candidate.title ||
      id,
  ).trim();
  const description = String(
    candidate.description ||
      candidate.desc ||
      candidate.provider ||
      candidate.provider_type ||
      "",
  ).trim();
  const provider = String(candidate.provider || candidate.provider_type || "").trim();
  return {
    id,
    name: name || id,
    description,
    provider,
  };
}

export function normalizeModelsPayload(data) {
  const rawList = Array.isArray(data)
    ? data
    : Array.isArray(data?.models)
      ? data.models
      : Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data?.data)
          ? data.data
          : [];
  const seen = new Set();
  return rawList
    .map(toModelOption)
    .filter((item) => item && !seen.has(item.id) && seen.add(item.id));
}

export function resolveModelUsed(data, fallback = "") {
  const modelUsed = data?.model_used ?? data?.modelUsed ?? data?.meta?.model_used;
  if (typeof modelUsed === "string" && modelUsed.trim()) {
    return modelUsed.trim();
  }
  if (typeof fallback === "string" && fallback.trim()) {
    return fallback.trim();
  }
  return "";
}

export function getChatEndpoint() {
  const baseUrl = normalizeBaseUrl(http.defaults.baseURL);
  if (!baseUrl) {
    return "/api/v1/chat";
  }
  if (baseUrl.endsWith("/api/v1")) {
    return `${baseUrl}/chat`;
  }
  if (baseUrl.endsWith("/api")) {
    return `${baseUrl}/v1/chat`;
  }
  return `${baseUrl}/api/v1/chat`;
}

export function buildChatHeaders() {
  const headers = {
    "Content-Type": "application/json",
  };
  const apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export function sendChat(payload) {
  return http.post("/chat", payload);
}

export function fetchModels(params = {}) {
  return http.get("/models", { params }).then((response) => ({
    ...response,
    data: normalizeModelsPayload(response?.data),
  }));
}

export function fetchChatSessions(params = {}) {
  return http.get("/chat/sessions", { params });
}

export function renameChatSession(sessionId, payload) {
  return http.patch(`/chat/sessions/${sessionId}`, payload);
}

export function deleteChatSession(sessionId) {
  return http.delete(`/chat/sessions/${sessionId}`);
}
