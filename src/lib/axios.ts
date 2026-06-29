import axios from "axios";
import { useAuthStore } from "@/store";

export const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : "http://localhost:8000";

/**
 * Axios instance.
 *
 * ─── NO global timeout ───────────────────────────────────────────────────────
 * The clipping generation endpoint (/generate/) runs Playwright + Supabase
 * upload on a Render free instance and can legitimately take 2–5 minutes.
 * A 60 000 ms global timeout was the direct cause of:
 *   "Failed to generate clipping: timeout of 60000ms exceeded"
 *
 * Per-call timeouts are set explicitly in generation.service.ts:
 *   • generate()     → timeout: 0  (no limit — polling handles the 10-min guard)
 *   • polling calls  → timeout: 15_000  (15 s per poll attempt)
 *   • upload         → timeout: 120_000 (2 min for large images)
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  // timeout is intentionally omitted here — set per-request in the service layer
});

// ─── Request Interceptor — Attach JWT ─────────────────────────────────────────
api.interceptors.request.use((config) => {
  // If sending FormData, delete the default JSON Content-Type so the browser
  // can auto-set multipart/form-data with the correct boundary parameter.
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  if (typeof window !== "undefined") {
    const raw = localStorage.getItem("newscraft-auth");
    if (raw) {
      try {
        const { state } = JSON.parse(raw);
        if (state?.token) {
          config.headers.Authorization = `Bearer ${state.token}`;
        }
      } catch {
        // ignore parse errors
      }
    }
  }
  return config;
});

// ─── Response Interceptor — Handle 401 ───────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Do NOT redirect to login if we are on the preview/polling route.
      // A token expiry mid-generation would otherwise kick the user to the
      // login screen while Playwright is still rendering in the background.
      const isPolling =
        typeof window !== "undefined" &&
        window.location.pathname.startsWith("/preview");

      if (!isPolling && typeof window !== "undefined") {
        console.warn("[API] 401 received — logging out and redirecting to login.");
        useAuthStore.getState().logout();
        window.location.href = "/login";
      } else {
        console.warn("[API] 401 received during generation polling — ignoring redirect.");
      }
    }

    return Promise.reject(error);
  }
);

export default api;
