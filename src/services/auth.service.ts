import api from "@/lib/axios";
import { supabase } from "@/lib/supabase";
import type { ApiResponse, User, LoginFormData, SignupFormData } from "@/types";

export const authService = {
  async login(data: LoginFormData): Promise<ApiResponse<{ user: User; token: string }>> {
    const { data: sessionData, error } = await supabase.auth.signInWithPassword({
      email: data.email,
      password: data.password,
    });
    
    if (error) throw error;
    if (!sessionData.session) throw new Error("No session returned");

    return {
      success: true,
      message: "Login successful",
      data: {
        user: sessionData.session.user as any,
        token: sessionData.session.access_token,
      }
    };
  },

  async signup(data: SignupFormData): Promise<ApiResponse<{ user: User; token: string }>> {
    const { data: sessionData, error } = await supabase.auth.signUp({
      email: data.email,
      password: data.password,
      options: {
        data: {
          full_name: `${data.firstName} ${data.lastName}`,
        }
      }
    });

    if (error) throw error;
    if (!sessionData.session) throw new Error("No session returned. Check email for confirmation.");

    return {
      success: true,
      message: "Signup successful",
      data: {
        user: sessionData.session.user as any,
        token: sessionData.session.access_token,
      }
    };
  },

  async logout(): Promise<void> {
    await supabase.auth.signOut();
  },

  async getProfile(): Promise<ApiResponse<User>> {
    const res = await api.get("/api/v1/auth/me");
    return res.data;
  },

  async updateProfile(data: Partial<User>): Promise<ApiResponse<User>> {
    const res = await api.patch("/api/v1/auth/me", data);
    return res.data;
  },

  async forgotPassword(email: string): Promise<ApiResponse<void>> {
    const { error } = await supabase.auth.resetPasswordForEmail(email);
    if (error) throw error;
    return {
      success: true,
      message: "Password reset email sent",
      data: undefined
    };
  },
};
