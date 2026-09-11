import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, GenerationConfig, Generation } from "@/types";

// ─── Permanent Reporter Name & Photo Helpers ─────────────────────────────────────
export const getReporterName = (email?: string): string => {
  try {
    if (typeof window === "undefined" || !window.localStorage) return "";
    if (email) {
      const cleanEmail = email.toLowerCase().trim();
      const name = localStorage.getItem(`spotnews_reporter_name_${cleanEmail}`);
      if (name) return name;
    }
    const lastName = localStorage.getItem("spotnews_last_reporter_name");
    if (lastName) return lastName;
  } catch (e) {
    console.warn("[NameStore] Error reading reporter name:", e);
  }
  return "";
};

export const saveReporterName = (email: string | undefined, name: string): void => {
  try {
    if (!name || typeof window === "undefined" || !window.localStorage) return;
    if (email) {
      const cleanEmail = email.toLowerCase().trim();
      localStorage.setItem(`spotnews_reporter_name_${cleanEmail}`, name.trim());
    }
    localStorage.setItem("spotnews_last_reporter_name", name.trim());
  } catch (e) {
    console.warn("[NameStore] Error saving reporter name:", e);
  }
};

export const getReporterPhoto = (email?: string): string => {
  try {
    if (typeof window === "undefined" || !window.localStorage) return "";
    if (email) {
      const cleanEmail = email.toLowerCase().trim();
      const photo = localStorage.getItem(`spotnews_reporter_photo_${cleanEmail}`);
      if (photo) return photo;
    }
    const lastPhoto = localStorage.getItem("spotnews_last_reporter_photo");
    if (lastPhoto) return lastPhoto;
  } catch (e) {
    console.warn("[PhotoStore] Error reading reporter photo:", e);
  }
  return "";
};

export const saveReporterPhoto = (email: string | undefined, photoUrl: string): void => {
  try {
    if (!photoUrl || typeof window === "undefined" || !window.localStorage) return;
    if (email) {
      const cleanEmail = email.toLowerCase().trim();
      localStorage.setItem(`spotnews_reporter_photo_${cleanEmail}`, photoUrl);
    }
    localStorage.setItem("spotnews_last_reporter_photo", photoUrl);
  } catch (e) {
    console.warn("[PhotoStore] Error saving reporter photo:", e);
  }
};

// ─── Auth Store ────────────────────────────────────────────────────────────────
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
  updateUser: (partial: Partial<User>) => void;
  otpState?: { phoneNumber: string; reqId: string } | null;
  setOtpState: (state: { phoneNumber: string; reqId: string } | null) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (user, token) => {
        const email = user?.email || (user as any)?.user_metadata?.email;
        const storedName = getReporterName(email);
        const storedPhoto = getReporterPhoto(email);

        const existingName =
          storedName ||
          (user as any)?.user_metadata?.full_name ||
          (user as any)?.user_metadata?.name ||
          user?.full_name ||
          user?.firstName ||
          "";

        const existingPhoto =
          storedPhoto ||
          user?.avatarUrl ||
          (user as any)?.user_metadata?.avatar_url ||
          (user as any)?.user_metadata?.picture ||
          "";

        const existingMetadata = (user as any)?.user_metadata || {};
        const updatedMetadata = {
          ...existingMetadata,
          ...(existingName ? { full_name: existingName, name: existingName } : {}),
          ...(existingPhoto ? { avatar_url: existingPhoto, picture: existingPhoto } : {}),
        };

        const enrichedUser: User = {
          ...user,
          full_name: existingName || user?.full_name || user?.firstName || "",
          firstName: existingName || user?.firstName || "",
          avatarUrl: existingPhoto || "",
          user_metadata: updatedMetadata,
        } as any;

        if (existingPhoto && email) {
          saveReporterPhoto(email, existingPhoto);
        }
        if (existingName && email) {
          saveReporterName(email, existingName);
        }

        set({ user: enrichedUser, token, isAuthenticated: true });
      },
      logout: () =>
        set({ user: null, token: null, isAuthenticated: false }),
      updateUser: (partial) =>
        set((state) => {
          if (!state.user) return { user: null };
          const updatedUser: User = { ...state.user, ...partial };
          const email = updatedUser.email || (updatedUser as any)?.user_metadata?.email;
          const newName =
            partial.full_name ||
            partial.firstName ||
            (partial as any)?.user_metadata?.full_name ||
            (partial as any)?.user_metadata?.name;

          if (newName) {
            saveReporterName(email, newName);
          }
          if (partial.avatarUrl) {
            saveReporterPhoto(email, partial.avatarUrl);
          }

          // Ensure user_metadata is also kept in sync
          if (newName || partial.avatarUrl) {
            const currentMetadata = (updatedUser as any)?.user_metadata || {};
            (updatedUser as any).user_metadata = {
              ...currentMetadata,
              ...(newName ? { full_name: newName, name: newName } : {}),
              ...(partial.avatarUrl ? { avatar_url: partial.avatarUrl, picture: partial.avatarUrl } : {}),
            };
          }

          return { user: updatedUser };
        }),
      otpState: null,
      setOtpState: (otpState) => set({ otpState }),
    }),
    { name: "newscraft-auth" }
  )
);

// ─── Generation Store ──────────────────────────────────────────────────────────
interface GenerationStore {
  currentConfig: Partial<GenerationConfig>;
  generations: Generation[];
  isGenerating: boolean;
  setConfig: (partial: Partial<GenerationConfig>) => void;
  resetConfig: () => void;
  addGeneration: (generation: Generation) => void;
  updateGeneration: (id: string, partial: Partial<Generation>) => void;
  setGenerations: (generations: Generation[]) => void;
  setGenerating: (value: boolean) => void;
}

const defaultConfig: Partial<GenerationConfig> = {
  language: "en",
  tone: "formal",
  templateId: "rti_express",
  publicationName: "RTI Express",
  publicationDate: new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }),
  layoutColumns: 3,
  imageUrls: [],
  fontFamily: "playfair",
  layoutPattern: "A",
  borderColour: "#cc2222",
  headingBgColour: "#cc2222",
};

export const useGenerationStore = create<GenerationStore>()(
  persist(
    (set) => ({
      currentConfig: defaultConfig,
      generations: [],
      isGenerating: false,
      setConfig: (partial) =>
        set((state) => ({
          currentConfig: { ...state.currentConfig, ...partial },
        })),
      resetConfig: () => set({ currentConfig: defaultConfig }),
      addGeneration: (generation) =>
        set((state) => {
          // Strip base64 imageUrls to prevent localStorage QuotaExceededError
          const cleanGen = JSON.parse(JSON.stringify(generation));
          if (cleanGen?.config?.imageUrls) {
            cleanGen.config.imageUrls = [];
          }
          return { generations: [cleanGen, ...state.generations].slice(0, 50) };
        }),
      updateGeneration: (id, partial) =>
        set((state) => ({
          generations: state.generations.map((g) => {
            if (g.id === id) {
              const updated = { ...g, ...partial };
              if (updated?.config?.imageUrls) {
                updated.config.imageUrls = [];
              }
              return updated;
            }
            return g;
          }),
        })),
      setGenerations: (generations) => set({ generations: generations.slice(0, 50) }),
      setGenerating: (value) => set({ isGenerating: value }),
    }),
    { name: "newscraft-generations" }
  )
);

// ─── UI Store ─────────────────────────────────────────────────────────────────
interface UIStore {
  logoMode: boolean;
  sidebarOpen: boolean;
  language: string;
  showInnerBorders: boolean;
  toggleLogoMode: () => void;
  toggleInnerBorders: () => void;
  setLogoMode: (val: boolean) => void;
  setSidebarOpen: (open: boolean) => void;
  setLanguage: (lang: string) => void;
  pendingCropImageSrc: string | null;
  setPendingCropImageSrc: (src: string | null) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      logoMode: false,
      showInnerBorders: true,
      sidebarOpen: true,
      language: "en",
      toggleLogoMode: () =>
        set((state) => ({ logoMode: !state.logoMode })),
      toggleInnerBorders: () =>
        set((state) => ({ showInnerBorders: !(state.showInnerBorders ?? true) })),
      setLogoMode: (val) => set({ logoMode: val }),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setLanguage: (lang) => set({ language: lang }),
      pendingCropImageSrc: null,
      setPendingCropImageSrc: (src) => set({ pendingCropImageSrc: src }),
    }),
    { name: "newscraft-ui" }
  )
);

// ─── Admin RBAC Helper ────────────────────────────────────────────────────────
/**
 * Returns true if the given email is in the admin list (VITE_ADMIN_EMAILS env var).
 * Use this as a quick client-side guard before the full Supabase role check.
 */
export const isAdminUser = (email?: string): boolean => {
  if (!email) return false;
  const adminEmails = (import.meta.env.VITE_ADMIN_EMAILS ?? 'mohithroyal16450@gmail.com')
    .split(',')
    .map((e: string) => e.trim().toLowerCase());
  return adminEmails.includes(email.toLowerCase().trim());
};

