import api from "@/lib/axios";
import type { ApiResponse, PaginatedResponse, Generation, GenerationConfig } from "@/types";

// ─── Logging helpers ──────────────────────────────────────────────────────────
function log(stage: string, detail?: string) {
  const ts = new Date().toISOString();
  console.log(`[GEN] [${ts}] ${stage}${detail ? ` — ${detail}` : ""}`);
}

// ─── Image compression ────────────────────────────────────────────────────────
/**
 * Compress + resize an image File before uploading.
 * Limits output to maxWidthPx × maxWidthPx, quality = 0.82.
 * This prevents large 4–12 MB phone images from timing out on upload.
 */
export async function compressImage(
  file: File,
  maxWidthPx = 1600,
  quality = 0.82
): Promise<File> {
  return new Promise((resolve) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const ratio = Math.min(1, maxWidthPx / Math.max(img.width, img.height));
      const w = Math.round(img.width * ratio);
      const h = Math.round(img.height * ratio);

      const canvas = document.createElement("canvas");
      canvas.width  = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0, w, h);

      canvas.toBlob(
        (blob) => {
          if (!blob) { resolve(file); return; }
          const compressed = new File([blob], file.name, { type: "image/jpeg" });
          log("Image Compressed", `${(file.size / 1024).toFixed(0)} KB → ${(compressed.size / 1024).toFixed(0)} KB (${w}×${h})`);
          resolve(compressed);
        },
        "image/jpeg",
        quality
      );
    };
    img.onerror = () => { URL.revokeObjectURL(objectUrl); resolve(file); };
    img.src = objectUrl;
  });
}

// ─── Service ──────────────────────────────────────────────────────────────────
export const generationService = {

  /**
   * Submit a generation job.
   *
   * Timeout: NONE (timeout: 0).
   * The Render free-tier backend runs Playwright + Supabase upload and can
   * legitimately take 2–5 minutes.  The 60 s axios global timeout was the
   * root cause of "timeout of 60000ms exceeded".
   * The 10-minute guard lives in PreviewScreen polling, not here.
   */
  async generate(config: GenerationConfig): Promise<ApiResponse<Generation>> {
    log("Generation Started", `template=${config.templateId} lang=${config.language} images=${(config as any).imageUrls?.length ?? 0}`);
    const res = await api.post("/generate/", config, {
      timeout: 0, // No timeout — generation can take several minutes
    });
    log("Generation Response Received", `status=${res.status}`);
    return res.data;
  },

  async getAll(page = 1, pageSize = 10): Promise<PaginatedResponse<Generation>> {
    const res = await api.get("/generate/", {
      params: { page, pageSize },
      timeout: 15_000,
    });
    return res.data;
  },

  /**
   * Poll for a single generation by ID.
   * Short 15-second timeout per poll — if it fails we retry next interval.
   */
  async getById(id: string): Promise<ApiResponse<Generation>> {
    const res = await api.get(`/generate/${id}`, { timeout: 15_000 });
    return res.data;
  },

  async getByIdPublic(id: string): Promise<ApiResponse<Generation>> {
    const res = await api.get(`/generate/${id}/public`, { timeout: 15_000 });
    return res.data;
  },

  async delete(id: string): Promise<ApiResponse<void>> {
    const res = await api.delete(`/generate/${id}`, { timeout: 15_000 });
    return res.data;
  },

  async exportPng(id: string): Promise<Blob> {
    const res = await api.get(`/generations/${id}/export/png`, {
      responseType: "blob",
      timeout: 60_000,
    });
    return res.data;
  },

  async exportPdf(id: string): Promise<Blob> {
    const res = await api.get(`/generations/${id}/export/pdf`, {
      responseType: "blob",
      timeout: 60_000,
    });
    return res.data;
  },

  /**
   * Upload a single image to the backend.
   *
   * The image is compressed to ≤1600 px / 82% quality before upload.
   * Timeout: 120 s (2 minutes) — allows large compressed images on slow connections.
   */
  async uploadImage(file: File): Promise<ApiResponse<{ url: string }>> {
    log("Image Upload Started", `name=${file.name} size=${(file.size / 1024).toFixed(0)} KB`);

    // Compress before upload to reduce network time
    const compressed = await compressImage(file);
    log("Image Upload Compressing", `compressed size=${(compressed.size / 1024).toFixed(0)} KB`);

    const buffer = await compressed.arrayBuffer();
    const blob   = new Blob([buffer], { type: compressed.type });

    const formData = new FormData();
    formData.append("file", blob, compressed.name || "image.jpg");

    let token = "";
    try {
      const authStore = localStorage.getItem("newscraft-auth");
      if (authStore) {
        const parsed = JSON.parse(authStore);
        token = parsed?.state?.token || "";
      }
    } catch (e) {}

    const API_URL = "https://news-backend-sjw6.onrender.com";

    // Use fetch with an AbortController so we get a 2-minute window
    const controller = new AbortController();
    const uploadTimeoutId = setTimeout(() => {
      controller.abort();
    }, 120_000); // 2 minutes for image upload

    try {
      const res = await fetch(`${API_URL}/uploads/image`, {
        method:  "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body:    formData,
        signal:  controller.signal,
      });

      clearTimeout(uploadTimeoutId);

      if (!res.ok) {
        throw new Error(`Image Upload Failed: ${res.statusText} (HTTP ${res.status})`);
      }

      const data = await res.json();
      log("Image Upload Complete", `url=${data?.data?.url || data?.url || "(no url)"}`);
      return data;
    } catch (e: any) {
      clearTimeout(uploadTimeoutId);
      if (e.name === "AbortError") {
        throw new Error("Image Upload Failed: Request timed out after 2 minutes. Check network and try a smaller image.");
      }
      log("Image Upload Error", e.message);
      throw e;
    }
  },
};
