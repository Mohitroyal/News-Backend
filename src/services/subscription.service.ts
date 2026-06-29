import api from "@/lib/axios";
import type { ApiResponse, Subscription, Plan } from "@/types";

export const subscriptionService = {
  async getPlans(): Promise<ApiResponse<Plan[]>> {
    const res = await api.get("/api/v1/subscriptions/plans");
    return res.data;
  },

  async getCurrentSubscription(): Promise<ApiResponse<Subscription>> {
    const res = await api.get("/api/v1/subscriptions/current");
    return res.data;
  },

  async createCheckout(planId: string, billingInterval: "monthly" | "annual"): Promise<ApiResponse<{ checkoutUrl: string }>> {
    const res = await api.post("/api/v1/subscriptions/checkout", { planId, billingInterval });
    return res.data;
  },

  async cancelSubscription(): Promise<ApiResponse<Subscription>> {
    const res = await api.post("/api/v1/subscriptions/cancel");
    return res.data;
  },

  async reactivateSubscription(): Promise<ApiResponse<Subscription>> {
    const res = await api.post("/api/v1/subscriptions/reactivate");
    return res.data;
  },
};
