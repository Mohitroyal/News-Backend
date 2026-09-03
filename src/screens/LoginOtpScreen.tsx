import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Phone } from 'lucide-react';
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
    if (!phoneNumber || phoneNumber.length < 10) {
      setError('Please enter a valid phone number');
      return;
    }
    
    setLoading(true);
    setError('');

    const identifier = `${countryCode}${phoneNumber}`;

    try {
      OTPWidget.initializeWidget();
      const res = await OTPWidget.sendOTP({ identifier });
      
      if (res.type === 'success') {
        // Store phone number and reqId in Zustand (or pass via state)
        if (setOtpState) {
          setOtpState({ phoneNumber: identifier, reqId: res.message }); // assuming res.message contains reqId, MSG91 format varies
        }
        // Navigate to verify screen, pass identifier and reqId
        navigate('/login/verify', { state: { phoneNumber: identifier, reqId: res.message } });
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

      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-center py-4 px-4 shrink-0 shadow-sm relative z-20">
         <div className="flex items-center gap-2">
           <img src={logoUrl} alt="Spot News" className="w-10 h-10 object-contain rounded-md shadow-sm" />
           <div className="flex flex-col">
             <span className="text-white font-bold text-[18px] leading-tight tracking-wide font-serif">SPOT NEWS</span>
             <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">24X7 News Generator</span>
           </div>
         </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              OTP Login
            </div>
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Enter Mobile Number</h1>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full"></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSendOtp} className="space-y-4">
            <div className="flex gap-2">
              <div className="w-1/4 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#a0c4dc]">+</span>
                <input
                  type="tel"
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[24px] pr-2 text-[#0a1a2e] text-sm text-center focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium"
                  maxLength={4}
                  required
                />
              </div>
              <div className="flex-1 relative">
                <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
                <input
                  type="tel"
                  placeholder="Phone Number"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-sm placeholder:text-[#a0c4dc] focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium"
                  maxLength={15}
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-70 disabled:hover:bg-[#cc2222]"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send OTP'}
            </button>
          </form>

          <div className="mt-8 text-center flex flex-col gap-2">
            <Link to="/login" className="text-[#a0c4dc] text-xs font-bold hover:text-[#0a2540] transition-colors">
              Login with Email Instead
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
