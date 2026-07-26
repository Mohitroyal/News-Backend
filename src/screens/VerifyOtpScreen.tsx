import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Loader2, KeyRound } from 'lucide-react';
import { OTPWidget } from '@/services/otpService';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';
import { useAuthStore } from '@/store';

export const VerifyOtpScreen = () => {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state: any) => state.login);
  
  const { phoneNumber, reqId } = location.state || {};

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp || otp.length !== 6) {
      setError('Please enter a valid 6-digit OTP');
      return;
    }
    
    setLoading(true);
    setError('');

    try {
      const res = await OTPWidget.verifyOTP({ reqId, otp, mobile: phoneNumber });
      
      if (res.type === 'success' || res.message === 'OTP verified success') {
        // Mocking user session since MSG91 OTP doesn't create a Supabase session by default.
        // In a real app, you would exchange this verification for a JWT from your backend.
        const mockUser = {
          id: 'otp-user-' + Date.now(),
          email: phoneNumber + '@msg91.com',
          user_metadata: { full_name: phoneNumber },
          app_metadata: {},
          aud: 'authenticated',
          created_at: new Date().toISOString()
        };
        const mockToken = 'msg91-mock-token-' + Date.now();

        login(mockUser, mockToken);
        navigate('/');
      } else {
        setError(res.message || 'Invalid OTP');
      }
    } catch (err: any) {
      setError(err.message || 'Error verifying OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setResendLoading(true);
    setError('');
    try {
      const res = await OTPWidget.retryOTP({ reqId, retryType: 'text', mobile: phoneNumber });
      if (res.type === 'success') {
        alert('OTP Resent successfully!');
      } else {
        setError(res.message || 'Failed to resend OTP');
      }
    } catch (err: any) {
      setError(err.message || 'Network error resending OTP');
    } finally {
      setResendLoading(false);
    }
  };

  if (!phoneNumber || !reqId) {
    return (
      <div className="flex flex-col min-h-screen bg-[#dceef8] items-center justify-center">
        <p className="text-red-500 font-bold">Invalid OTP Session. Please go back.</p>
        <Link to="/login/otp" className="mt-4 text-[#0a2540] underline font-medium">Back to OTP Login</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#dceef8] relative font-sans text-[#0a1a2e]">
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
         <LogoWatermark darkBackground={false} opacity={0.04} />
      </div>

      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-center py-4 px-4 shrink-0 shadow-sm relative z-20">
         <div className="flex items-center gap-2">
           <img src={logoUrl} alt="RTI" className="w-10 h-10 object-contain rounded-md shadow-sm" />
           <div className="flex flex-col">
             <span className="text-white font-bold text-[18px] leading-tight tracking-wide font-serif">EXPRESS</span>
             <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">News Generator</span>
           </div>
         </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              Verification
            </div>
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Verify OTP</h1>
            <p className="text-sm text-[#a0c4dc] font-medium">Sent to +{phoneNumber}</p>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full mt-2"></div>
          </div>

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
                placeholder="6-digit OTP"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-center tracking-widest text-lg focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-bold"
                maxLength={6}
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading || otp.length !== 6}
              className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-70 disabled:hover:bg-[#cc2222]"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Verify OTP'}
            </button>
          </form>

          <div className="mt-6 flex flex-col items-center gap-3">
            <button 
              onClick={handleResendOtp}
              disabled={resendLoading}
              className="text-[#a0c4dc] text-xs font-bold hover:text-[#0a2540] transition-colors flex items-center gap-2"
            >
              {resendLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Resend OTP'}
            </button>
            <Link to="/login/otp" className="text-[#a0c4dc] text-xs font-bold hover:text-[#0a2540] transition-colors mt-2">
              Change Phone Number
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
