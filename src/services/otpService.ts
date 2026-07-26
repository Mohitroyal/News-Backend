import axios from 'axios';

const authKey = import.meta.env.VITE_MSG91_AUTHKEY || '<ADD_AUTHKEY_HERE>';
const templateId = import.meta.env.VITE_MSG91_TEMPLATE_ID || '<ADD_TEMPLATE_ID_HERE>';

/**
 * A service that mimics the MSG91 SendOTP React Native SDK interface,
 * but uses the standard REST APIs directly for Web/Capacitor compatibility.
 */
export const OTPWidget = {
  /**
   * Mock initialization.
   */
  initializeWidget: () => {
    console.log('MSG91 OTP Service initialized with:', { templateId });
  },

  /**
   * Send OTP to a mobile number
   */
  sendOTP: async (data: { identifier: string }) => {
    try {
      const response = await axios.post('https://control.msg91.com/api/v5/otp', {
        template_id: templateId,
        mobile: data.identifier
      }, {
        headers: {
          'Content-Type': 'application/json',
          'authkey': authKey
        }
      });
      return response.data;
    } catch (error: any) {
      if (error.response && error.response.data) {
        throw error.response.data;
      }
      throw error;
    }
  },

  /**
   * Retry sending OTP
   */
  retryOTP: async (data: { reqId: string, retryType?: string, mobile?: string }) => {
    try {
      const response = await axios.post(`https://control.msg91.com/api/v5/otp/retry?retrytype=${data.retryType || 'text'}&mobile=${data.mobile}`, {}, {
        headers: {
          'Content-Type': 'application/json',
          'authkey': authKey
        }
      });
      return response.data;
    } catch (error: any) {
      if (error.response && error.response.data) {
        throw error.response.data;
      }
      throw error;
    }
  },

  /**
   * Verify the received OTP
   */
  verifyOTP: async (data: { reqId: string, otp: string, mobile?: string }) => {
    try {
      const response = await axios.get(`https://control.msg91.com/api/v5/otp/verify?otp=${data.otp}&mobile=${data.mobile}`, {
        headers: {
          'authkey': authKey
        }
      });
      return response.data;
    } catch (error: any) {
      if (error.response && error.response.data) {
        throw error.response.data;
      }
      throw error;
    }
  }
};
