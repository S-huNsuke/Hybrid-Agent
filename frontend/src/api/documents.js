import http from "./http";

const BASE_PATH = "/documents";

export function unwrapApiResponse(response) {
  return response?.data ?? response ?? null;
}

export function extractApiError(error, fallback = "请求失败") {
  const detail =
    error?.response?.data?.detail
    || error?.response?.data?.error
    || error?.message;
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }
  return fallback;
}

export function fetchDocuments(params = {}) {
  return http.get(BASE_PATH, { params });
}

export function fetchDocumentsWithQuery(params = {}) {
  return http.get(BASE_PATH, { params });
}

export function uploadDocument(formData, params = {}) {
  return http.post(`${BASE_PATH}/upload`, formData, {
    params,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

export function deleteDocument(docId, params = {}) {
  return http.delete(`${BASE_PATH}/${docId}`, { params });
}

export function fetchUploadTask(taskId) {
  return http.get(`${BASE_PATH}/tasks/${taskId}`);
}
