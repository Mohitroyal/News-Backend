import api from "@/lib/axios";
import type { ApiResponse, User, LoginFormData, SignupFormData } from "@/types";

export const authService = {
  async login(data: LoginFormData): Promise<ApiResponse<{ user: User; token: string }>> {
    const res = await api.post("/auth/login", data);
    return res.data;
  },

  async signup(data: SignupFormData): Promise<ApiResponse<{ user: User; token: string }>> {
    const res = await api.post("/auth/signup", data);
    return res.data;
  },

  async logout(): Promise<void> {
    await api.post("/auth/logout");
  },

  async getProfile(): Promise<ApiResponse<User>> {
    const res = await api.get("/auth/me");
    return res.data;
  },

  async updateProfile(data: Partial<User>): Promise<ApiResponse<User>> {
    const res = await api.patch("/auth/me", data);
    return res.data;
  },

  async forgotPassword(email: string): Promise<ApiResponse<void>> {
    const res = await api.post("/auth/forgot-password", { email });
    return res.data;
  },
};
