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
        // Save authenticated session in Zustand store
        login(res.user, res.token);
        // Direct navigation to admin or home dashboard
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
