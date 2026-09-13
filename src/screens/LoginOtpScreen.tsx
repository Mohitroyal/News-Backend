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
