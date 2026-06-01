// ─── Auth Types ───────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string;
  firstName?: string;
  lastName?: string;
  avatarUrl?: string;
  createdAt: string;
  plan: "free" | "pro" | "enterprise";
  credits: number;
  role?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

// ─── Generation Types ──────────────────────────────────────────────────────────
export type Language =
  | "en"
  | "te"
  | "hi"
  | "kn"
  | "ta"
  | "ml";

export type Tone = "formal" | "casual" | "dramatic" | "sensational";

export type TemplateId =
  | "classic-split"
  | "hero-image"
  | "broadsheet"
  | "tabloid"
  | "magazine"
  | "bharath_reporter"
  | "rti_express"
  | "national_news"
  | "extra_news";


export interface GenerationConfig {
  articleContent: string;
  headline: string;
  language: Language;
  tone: Tone;
  templateId: string;  // layout template (from Templates page)
  logoId?: string;    // brand/logo identity (from logo selector)
  imageUrl?: string;
  imageUrls?: string[];
  publicationName: string;
  publicationDate: string;
  layoutColumns: number;
  fontFamily?: string;
}

export interface Generation {
  id: string;
  userId: string;
  config: GenerationConfig;
  png_url?: string;
  pdf_url?: string;
  status: "pending" | "processing" | "rendering" | "completed" | "failed";
  createdAt: string;
  exportedAt?: string;
  custom_layout?: any;
  content_formatted?: any;
  logo_id?: string;
  [key: string]: any;
}

// ─── Subscription Types ────────────────────────────────────────────────────────
export type PlanId = "free" | "pro" | "enterprise";

export interface Plan {
  id: PlanId;
  name: string;
  monthlyPrice: number;
  annualPrice: number;
  features: string[];
  creditsPerMonth: number;
  maxExportsPerMonth: number;
  highResExport: boolean;
  apiAccess: boolean;
  customBranding: boolean;
}

export interface Subscription {
  id: string;
  userId: string;
  planId: PlanId;
  status: "active" | "canceled" | "past_due";
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
}

// ─── Template Types ────────────────────────────────────────────────────────────
export interface Template {
  id: TemplateId;
  name: string;
  description: string;
  previewUrl: string;
  isPremium: boolean;
  supportedLanguages: Language[];
  columns: 1 | 2 | 3;
}

// ─── API Response Types ────────────────────────────────────────────────────────
export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ─── Form Types ────────────────────────────────────────────────────────────────
export interface LoginFormData {
  email: string;
  password: string;
}

export interface SignupFormData {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  acceptTerms: boolean;
}
