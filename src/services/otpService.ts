import api from '@/lib/axios';

export interface SendOTPPayload {
  phone?: string;
  identifier?: string;
  mobile?: string;
}

export interface VerifyOTPPayload {
  phone?: string;
  mobile?: string;
  otp: string;
  reqId?: string;
}

export interface OTPResponse {
  success: boolean;
  type?: 'success' | 'error';
  message: string;
  token?: string;
  token_type?: string;
  user?: any;
}

function normalizePhone(input?: string): string {
  if (!input) return '';
  let cleaned = input.trim();
  if (!cleaned.startsWith('+')) {
    if (cleaned.length === 10) {
      cleaned = `+91${cleaned}`;
    } else if (cleaned.length === 12 && cleaned.startsWith('91')) {
      cleaned = `+${cleaned}`;
    } else {
      cleaned = `+${cleaned}`;
    }
  }
  return cleaned;
}

function extractErrorMessage(err: any): string {
  if (err?.response?.data) {
    const data = err.response.data;
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof data.detail === 'string' && data.detail) return data.detail;
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      return data.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join(', ');
    }
  }
  if (err?.message) return err.message;
  return 'An unexpected error occurred. Please try again.';
}

/**
 * Service to connect directly to the backend MSG91 OTP endpoints:
 * - POST /api/auth/send-otp
 * - POST /api/auth/verify-otp
 */
export const OTPWidget = {
  /**
   * Initialization helper
   */
  initializeWidget: () => {
    console.log('[OTPService] Backend MSG91 OTP service ready');
  },

  /**
   * Send 6-digit OTP to mobile number via backend MSG91 Flow API
   */
  sendOTP: async (data: SendOTPPayload): Promise<OTPResponse> => {
    const phone = normalizePhone(data.phone || data.identifier || data.mobile);
    if (!phone) {
      throw new Error('Please enter a valid phone number');
    }

    try {
      const response = await api.post('/api/auth/send-otp', { phone });
      return {
        success: response.data.success ?? true,
        type: 'success',
        message: response.data.message || 'OTP sent successfully',
      };
    } catch (err: any) {
      const message = extractErrorMessage(err);
      throw new Error(message);
    }
  },

  /**
   * Retry/Resend OTP
   */
  retryOTP: async (data: { reqId?: string; retryType?: string; mobile?: string; phone?: string }): Promise<OTPResponse> => {
    return OTPWidget.sendOTP({ phone: data.mobile || data.phone });
  },

  /**
   * Verify 6-digit OTP via backend
   */
  verifyOTP: async (data: VerifyOTPPayload): Promise<OTPResponse> => {
    const phone = normalizePhone(data.phone || data.mobile);
    const otp = data.otp?.trim();

    if (!phone) {
      throw new Error('Missing phone number for OTP verification');
    }
    if (!otp || otp.length !== 6) {
      throw new Error('Please enter a valid 6-digit OTP');
    }

    try {
      const response = await api.post('/api/auth/verify-otp', { phone, otp });
      return {
        success: response.data.success ?? true,
        type: 'success',
        message: response.data.message || 'OTP verified successfully',
        token: response.data.token,
        token_type: response.data.token_type,
        user: response.data.user,
      };
    } catch (err: any) {
      const message = extractErrorMessage(err);
      throw new Error(message);
    }
  },
};
