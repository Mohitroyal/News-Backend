import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, GenerationConfig, Generation } from "@/types";

// ─── Auth Store ────────────────────────────────────────────────────────────────
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
  updateUser: (partial: Partial<User>) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (user, token) =>
        set({ user, token, isAuthenticated: true }),
      logout: () =>
        set({ user: null, token: null, isAuthenticated: false }),
      updateUser: (partial) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...partial } : null,
        })),
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
  templateId: "bharath_reporter",
  publicationName: "Bharath Reporter",
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
  headingBgColour: "#fff3f3",
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
  toggleLogoMode: () => void;
  setSidebarOpen: (open: boolean) => void;
  setLanguage: (lang: string) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      logoMode: false,
      sidebarOpen: true,
      language: "en",
      toggleLogoMode: () =>
        set((state) => ({ logoMode: !state.logoMode })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setLanguage: (lang) => set({ language: lang }),
    }),
    { name: "newscraft-ui" }
  )
);
