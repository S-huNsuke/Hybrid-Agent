import axios from "axios";

const TOKEN_STORAGE_KEY = "hybrid-agent-token";
const API_KEY_STORAGE_KEY = "hybrid-agent-api-key";
const DEFAULT_API_BASE_URL =
  typeof window !== "undefined"
    ? "/api/v1"
    : "http://127.0.0.1:8000/api/v1";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
  timeout: 30000,
});

http.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);

  if (apiKey) {
    config.headers["X-API-Key"] = apiKey;
  }

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    return Promise.reject(error);
  }
);

export default http;
