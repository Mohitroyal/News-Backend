# Frontend Mobile OTP Integration Guide (MSG91 Backend)

This document is the complete developer blueprint for integrating Mobile OTP Login into any updated frontend delivered by your frontend team. Follow this step-by-step checklist to connect new frontend files with the backend in under 5 minutes.

---

## 1. System Architecture

```
[ Mobile App (Capacitor / Web) ]
       │
       │  1. POST /api/auth/send-otp { phone: "+919876543210" }
       ▼
[ Backend (FastAPI / Render) ] ───► [ MSG91 Flow API (Template: FOUZIA_OTP) ] ───► [ User's Phone (SMS) ]
       │
       │  2. POST /api/auth/verify-otp { phone: "+919876543210", otp: "123456" }
       ▼
[ Backend (Validates Bcrypt Hash) ]
       │
       ▼  Returns { success: true, token: "JWT...", user: { ... } }
[ Mobile App (Zustand useAuthStore) ] ───► Auto-logs in & redirects to Dashboard
```

> **Security Rule**: The frontend **NEVER** calls MSG91 directly and **NEVER** contains the MSG91 Authkey. All SMS dispatching and OTP verification are handled securely by your backend server.

---

## 2. Backend API Contracts

### A. Send OTP Endpoint
- **URL**: `POST /api/auth/send-otp` (also mapped at `/auth/send-otp` and `/api/v1/auth/send-otp`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "phone": "+919876543210"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "OTP sent successfully"
  }
  ```
- **Error Responses**:
  - `422 Unprocessable Entity`: Invalid 10-digit Indian phone format.
  - `429 Too Many Requests`: Exceeded 3 requests per 15 minutes, or within the 60-second cooldown window.
  - `502 Bad Gateway`: MSG91 delivery failure or missing `MSG91_AUTHKEY`.

---

### B. Verify OTP Endpoint
- **URL**: `POST /api/auth/verify-otp` (also mapped at `/auth/verify-otp` and `/api/v1/auth/verify-otp`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "phone": "+919876543210",
    "otp": "123456"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "OTP verified successfully",
    "token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer",
    "user": {
      "id": "c1f7b8d4-...",
      "phone_number": "+919876543210",
      "email": "9876543210@phone.user",
      "full_name": "User 3210",
      "plan": "free",
      "is_active": true
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Invalid OTP, expired OTP (>10 mins), or exceeded 5 verification attempts.

---

## 3. Files to Update in the Frontend

Whenever the frontend team provides an updated project folder, ensure the following **5 files** are present or updated:

---

### File 1: `src/services/otpService.ts`
This file connects your frontend screens directly to your backend API client.

```typescript
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

export const OTPWidget = {
  initializeWidget: () => {
    console.log('[OTPService] Backend MSG91 OTP service initialized');
  },

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

  retryOTP: async (data: { reqId?: string; retryType?: string; mobile?: string; phone?: string }): Promise<OTPResponse> => {
    return OTPWidget.sendOTP({ phone: data.mobile || data.phone });
  },

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
```

---

### File 2: `src/screens/LoginOtpScreen.tsx`
The screen where journalists enter their mobile number to request an SMS OTP.

```tsx
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Phone, ArrowLeft } from 'lucide-react';
import { OTPWidget } from '@/services/otpService';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';
import { useAuthStore } from '@/store';

export const LoginOtpScreen = () => {
  const [countryCode, setCountryCode] = useState('91');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const setOtpState = useAuthStore((state: any) => state.setOtpState);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanDigits = phoneNumber.replace(/\D/g, '');

    if (!cleanDigits || cleanDigits.length !== 10) {
      setError('Please enter a valid 10-digit Indian mobile number');
      return;
    }

    if (!['6', '7', '8', '9'].includes(cleanDigits[0])) {
      setError('Indian mobile number must start with 6, 7, 8, or 9');
      return;
    }
    
    setLoading(true);
    setError('');

    const formattedPhone = `+${countryCode.replace(/\D/g, '') || '91'}${cleanDigits}`;

    try {
      OTPWidget.initializeWidget();
      const res = await OTPWidget.sendOTP({ phone: formattedPhone });
      
      if (res.success || res.type === 'success') {
        if (setOtpState) {
          setOtpState({ phoneNumber: formattedPhone, reqId: 'session' });
        }
        navigate('/login/verify', { state: { phoneNumber: formattedPhone } });
      } else {
        setError(res.message || 'Failed to send OTP');
      }
    } catch (err: any) {
      setError(err.message || 'Network failure or error sending OTP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#dceef8] relative font-sans text-[#0a1a2e]">
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <LogoWatermark darkBackground={false} opacity={0.04} />
      </div>

      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-between py-3.5 px-4 shrink-0 shadow-sm relative z-20">
        <button 
          onClick={() => navigate('/login')}
          className="flex items-center gap-1.5 text-white hover:text-[#a0c4dc] text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>
        <div className="flex items-center gap-2">
          <img src={logoUrl} alt="Spot News" className="w-9 h-9 object-contain rounded-md shadow-sm" />
          <div className="flex flex-col">
            <span className="text-white font-bold text-[16px] leading-tight tracking-wide font-serif">SPOT NEWS</span>
            <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">24X7 News Generator</span>
          </div>
        </div>
        <div className="w-12"></div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              OTP Authentication
            </div>
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Login via Mobile OTP</h1>
            <p className="text-xs text-[#5b7e9a]">We will send a 6-digit verification code to your Indian mobile number via MSG91.</p>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full mt-2"></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSendOtp} className="space-y-4">
            <div className="flex gap-2">
              <div className="w-1/4 relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#5b7e9a] font-bold text-xs">+</span>
                <input
                  type="tel"
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[18px] pr-1 text-[#0a1a2e] text-sm text-center focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-bold"
                  maxLength={4}
                  required
                />
              </div>
              <div className="flex-1 relative">
                <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
                <input
                  type="tel"
                  placeholder="10-digit Mobile Number"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-sm placeholder:text-[#a0c4dc] focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium tracking-wide"
                  maxLength={10}
                  autoFocus
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || phoneNumber.replace(/\D/g, '').length !== 10}
              className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-60 disabled:hover:bg-[#cc2222] cursor-pointer"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send OTP via SMS'}
            </button>
          </form>

          <div className="mt-8 text-center flex flex-col gap-2 border-t border-[#dceef8] pt-4">
            <Link to="/login" className="text-[#0a2540] text-xs font-bold hover:underline transition-colors">
              Login with Email &amp; Password Instead
            </Link>
          </div>
        </div>
      </div>

      <div className="bg-[#0a2540] border-t-[2px] border-[#cc2222] py-3.5 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#a0c4dc] text-[9px] font-medium tracking-wide">
          Spot News &middot; Powered by MSG91 Secure OTP Gateway
        </span>
      </div>
    </div>
  );
};
```

---

### File 3: `src/screens/VerifyOtpScreen.tsx`
The screen where journalists enter the 6-digit code received via SMS.

```tsx
import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Loader2, KeyRound, ArrowLeft, RotateCw } from 'lucide-react';
import { OTPWidget } from '@/services/otpService';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';
import { useAuthStore, isAdminUser } from '@/store';

export const VerifyOtpScreen = () => {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state: any) => state.login);
  
  const { phoneNumber } = location.state || {};

  useEffect(() => {
    let timer: any;
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [cooldown]);

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanOtp = otp.trim();
    if (!cleanOtp || cleanOtp.length !== 6) {
      setError('Please enter the 6-digit OTP code');
      return;
    }
    
    setLoading(true);
    setError('');
    setInfoMessage('');

    try {
      const res = await OTPWidget.verifyOTP({ mobile: phoneNumber, otp: cleanOtp });
      
      if (res.success && res.token && res.user) {
        // Automatically stores session token & user profile in Zustand
        login(res.user, res.token);
        // Automatically redirects to admin or user dashboard
        navigate(isAdminUser(res.user) ? '/admin' : '/');
      } else {
        setError(res.message || 'Invalid OTP code');
      }
    } catch (err: any) {
      setError(err.message || 'Error verifying OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (cooldown > 0 || resendLoading) return;
    setResendLoading(true);
    setError('');
    setInfoMessage('');

    try {
      const res = await OTPWidget.retryOTP({ mobile: phoneNumber });
      if (res.success) {
        setInfoMessage('New OTP sent successfully!');
        setCooldown(60);
      } else {
        setError(res.message || 'Failed to resend OTP');
      }
    } catch (err: any) {
      setError(err.message || 'Network error resending OTP');
    } finally {
      setResendLoading(false);
    }
  };

  if (!phoneNumber) {
    return (
      <div className="flex flex-col min-h-screen bg-[#dceef8] items-center justify-center p-6 text-center">
        <div className="bg-white p-6 rounded-xl border border-[#b8d4e8] shadow-sm max-w-sm w-full">
          <p className="text-[#cc2222] font-bold text-base mb-2">No Active Session</p>
          <p className="text-gray-600 text-xs mb-4">Please enter your mobile number to request an OTP code.</p>
          <Link 
            to="/login/otp" 
            className="inline-block w-full py-2.5 bg-[#0a2540] hover:bg-[#12395d] text-white text-xs font-bold rounded-md transition-colors"
          >
            Go to Mobile Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#dceef8] relative font-sans text-[#0a1a2e]">
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <LogoWatermark darkBackground={false} opacity={0.04} />
      </div>

      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-between py-3.5 px-4 shrink-0 shadow-sm relative z-20">
        <button 
          onClick={() => navigate('/login/otp')}
          className="flex items-center gap-1.5 text-white hover:text-[#a0c4dc] text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Change Number</span>
        </button>
        <div className="flex items-center gap-2">
          <img src={logoUrl} alt="Spot News" className="w-9 h-9 object-contain rounded-md shadow-sm" />
          <div className="flex flex-col">
            <span className="text-white font-bold text-[16px] leading-tight tracking-wide font-serif">SPOT NEWS</span>
            <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">24X7 News Generator</span>
          </div>
        </div>
        <div className="w-16"></div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              Verification
            </div>
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-1">Verify OTP</h1>
            <p className="text-xs text-[#5b7e9a]">
              Enter the 6-digit code sent to <strong className="text-[#0a2540]">{phoneNumber}</strong>
            </p>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full mt-2"></div>
          </div>

          {infoMessage && (
            <div className="mb-4 p-3 bg-green-50 border border-green-500 rounded-[8px] text-green-700 text-xs font-semibold text-center shadow-sm">
              {infoMessage}
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div className="relative">
              <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
              <input
                type="text"
                placeholder="• • • • • •"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-center tracking-[0.5em] text-xl focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-bold"
                maxLength={6}
                autoFocus
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading || otp.replace(/\D/g, '').length !== 6}
              className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-60 disabled:hover:bg-[#cc2222] cursor-pointer"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Verify & Login'}
            </button>
          </form>

          <div className="mt-6 flex flex-col items-center gap-3 border-t border-[#dceef8] pt-4">
            <button 
              type="button"
              onClick={handleResendOtp}
              disabled={resendLoading || cooldown > 0}
              className="text-[#0a2540] text-xs font-bold hover:underline transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:hover:no-underline cursor-pointer"
            >
              <RotateCw className={`w-3.5 h-3.5 ${resendLoading ? 'animate-spin' : ''}`} />
              {resendLoading ? 'Sending...' : cooldown > 0 ? `Resend OTP in ${cooldown}s` : 'Resend OTP'}
            </button>
            <Link to="/login/otp" className="text-[#5b7e9a] text-xs font-medium hover:text-[#0a2540] transition-colors">
              Wrong phone number? Change it
            </Link>
          </div>
        </div>
      </div>

      <div className="bg-[#0a2540] border-t-[2px] border-[#cc2222] py-3.5 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#a0c4dc] text-[9px] font-medium tracking-wide">
          Spot News &middot; Powered by MSG91 Secure OTP Gateway
        </span>
      </div>
    </div>
  );
};
```

---

### File 4: `src/screens/LoginScreen.tsx`
Add the "Login with Mobile OTP" button inside the options area:

```tsx
// Inside LoginScreen.tsx, import Phone icon from 'lucide-react':
import { Loader2, Mail, Lock, Camera, Phone, User as UserIcon } from 'lucide-react';

// In the JSX, add the button:
<div className="flex flex-col gap-3 mt-6">
  <button
    type="button"
    onClick={() => navigate('/login/otp')}
    className="w-full py-[12px] bg-[#0a2540] hover:bg-[#12395d] active:bg-[#07192c] text-white rounded-[6px] font-bold text-sm tracking-wide transition-colors shadow-sm flex items-center justify-center gap-2 cursor-pointer font-serif"
  >
    <Phone className="w-4 h-4 text-[#a0c4dc]" />
    Login with Mobile OTP
  </button>

  <button
    type="button"
    onClick={handleGoogleLogin}
    disabled={loading}
    className="w-full py-[12px] bg-white active:bg-gray-50 border border-[#b8d4e8] text-[#0a1a2e] rounded-[6px] font-bold text-sm tracking-wide transition-colors shadow-sm flex items-center justify-center gap-3 disabled:opacity-70 cursor-pointer"
  >
    {/* Google Icon */}
    Sign in with Google
  </button>
</div>
```

---

### File 5: `src/App.tsx`
Ensure the routes `/login/otp` and `/login/verify` are declared:

```tsx
import { LoginOtpScreen } from './screens/LoginOtpScreen';
import { VerifyOtpScreen } from './screens/VerifyOtpScreen';

// Inside <Routes>:
<Route
  path="/login/otp"
  element={!isAuthenticated ? <LoginOtpScreen /> : <Navigate to="/" />}
/>
<Route
  path="/login/verify"
  element={!isAuthenticated ? <VerifyOtpScreen /> : <Navigate to="/" />}
/>
```

---

## 4. How the Session is Stored & Handled

1. When `/api/auth/verify-otp` succeeds, `VerifyOtpScreen` executes:
   ```typescript
   login(res.user, res.token);
   ```
2. `useAuthStore` stores the user object and JWT token in `localStorage` under `newscraft-auth`.
3. `src/lib/axios.ts` contains a request interceptor that reads the stored token and automatically injects:
   ```http
   Authorization: Bearer <token>
   ```
   into every subsequent request to your backend (e.g. `/generate/`, `/posts/`, `/admin`).

---

## 5. How to Compile the Native Android APK

Whenever frontend updates are completed, run these 3 standard commands from the frontend directory:

```bash
# 1. Build the production React web bundle
npm run build

# 2. Sync the web bundle into Capacitor's Android native project
npx cap sync android

# 3. Compile the debug APK using Gradle (Windows PowerShell)
cd android
cmd.exe /c "set JAVA_HOME=C:\Program Files\Java\jdk-17&& set ANDROID_HOME=C:\Users\MOHIT\AppData\Local\Android\Sdk&& gradlew.bat assembleDebug"
```

The compiled APK will be created at:
```
android/app/build/outputs/apk/debug/app-debug.apk
```
Copy it to your desktop or distribution folder:
```powershell
Copy-Item ".\android\app\build\outputs\apk\debug\app-debug.apk" -Destination "..\..\Spot-News-24x7.apk" -Force
```

---

## 6. Quick Verification Checklist

- [ ] Phone input requires 10 digits starting with `6, 7, 8, or 9`.
- [ ] Code is auto-prefixed with `+91`.
- [ ] 60-second cooldown is enforced on the Resend button.
- [ ] No `MSG91_AUTHKEY` is hardcoded in the frontend.
- [ ] `MSG91_AUTHKEY` is configured in the **Render Dashboard Environment** tab.
- [ ] Successful OTP verification stores the token and redirects to `/` or `/admin`.
