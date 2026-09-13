import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Phone, ArrowLeft } from 'lucide-react';
import { OTPWidget } from '@/services/otpService';
import logoUrl from '@/assets/rti_express_logo.png';
import watermarkLogo from '@/assets/rti_express_watermark.png';
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
    <div className="flex flex-col min-h-screen bg-[#EAF2FB] relative font-sans text-[#0F172A] overflow-x-hidden">
      {/* ══ RTI Express background watermark ══ */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%) rotate(-30deg)',
          zIndex: 0,
          pointerEvents: 'none',
          width: '100vw',
          maxWidth: '500px',
          opacity: 0.08,
          mixBlendMode: 'multiply'
        }}
      >
        <img
          src={watermarkLogo}
          alt=""
          draggable={false}
          style={{
            width: '100%',
            height: 'auto',
            display: 'block',
            userSelect: 'none',
            WebkitUserSelect: 'none'
          }}
        />
      </div>

      {/* ── Masthead Header (matches the inside app masthead & wave) ── */}
      <header className="w-full flex flex-col pt-safe relative z-20" style={{ background: '#EAF2FB' }}>
        <div style={{ background: '#015BB3', paddingBottom: '12px' }}>
          <div className="w-full flex items-center justify-between px-4 pt-3.5 pb-2 gap-2">
            <button 
              onClick={() => navigate('/login')}
              className="flex items-center gap-1 text-white hover:text-blue-100 text-xs font-bold py-1.5 px-2.5 rounded-lg bg-white/10 active:bg-white/20 transition-all border border-white/20"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>

            <div className="flex items-center gap-2">
              <div className="rounded-[8px] flex items-center justify-center h-[42px] overflow-hidden bg-white p-1 border border-[#0B56A6]/20 shrink-0 shadow-sm">
                <img src={logoUrl} alt="Spot News" className="h-full w-auto object-contain" style={{ maxWidth: '84px', borderRadius: '4px' }} />
              </div>
              <div className="flex flex-col justify-center">
                <span className="font-bold text-white text-[19px] leading-[1.1] tracking-wide" style={{ fontFamily: "'Georgia', serif" }}>
                  Spot News 24x7
                </span>
              </div>
            </div>

            <div className="w-14"></div>
          </div>
        </div>

        {/* ── Smooth Wave Divider ── */}
        <div style={{ width: '100%', overflow: 'hidden', lineHeight: 0, background: '#EAF2FB', position: 'relative' }}>
          <svg
            viewBox="0 0 1440 240"
            preserveAspectRatio="none"
            style={{ position: 'relative', display: 'block', width: '100%', height: '36px' }}
          >
            <path
              d="M0,0 L1440,0 L1440,100 C1100,240 500,10 0,170 Z"
              fill="#015BB3"
            />
          </svg>
        </div>
      </header>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-4 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#D6E4F5] rounded-[16px] p-6 sm:p-8 shadow-[0_4px_20px_rgba(18,84,168,0.08)]">
          
          <div className="mb-5 flex flex-col items-start">
            <div className="bg-[#EAF2FB] border border-[#D6E4F5] text-[#0F487F] text-[9.5px] uppercase tracking-wider font-extrabold py-1 px-2.5 rounded-full mb-2.5 shadow-sm">
              OTP Authentication
            </div>
            <h1 className="text-[#163E6C] text-2xl font-bold font-serif mb-1.5" style={{ fontFamily: "'Georgia', serif" }}>
              Login via Mobile OTP
            </h1>
            <p className="text-xs text-[#64748B] leading-relaxed">
              We will send a 6-digit verification code to your Indian mobile number via MSG91.
            </p>
            <div className="w-12 h-[3px] bg-[#CC1E1E] rounded-full mt-2.5"></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#CC1E1E] rounded-[10px] text-[#CC1E1E] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSendOtp} className="space-y-4">
            <div className="flex gap-2">
              <div className="w-[78px] relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#0F487F] font-bold text-xs">+</span>
                <input
                  type="tel"
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-white border border-[#D6E4F5] rounded-[10px] py-[11px] pl-[20px] pr-1 text-[#0F172A] text-sm text-center focus:outline-none focus:border-[#015BB3] focus:ring-2 focus:ring-[#015BB3]/15 font-bold shadow-sm"
                  maxLength={4}
                  required
                />
              </div>
              <div className="flex-1 relative">
                <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0F487F]" />
                <input
                  type="tel"
                  placeholder="10-digit Mobile Number"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value.replace(/\D/g, ''))}
                  className="w-full bg-white border border-[#D6E4F5] rounded-[10px] py-[11px] pl-[38px] pr-3 text-[#0F172A] text-sm placeholder:text-[#94A3B8] focus:outline-none focus:border-[#015BB3] focus:ring-2 focus:ring-[#015BB3]/15 font-medium tracking-wide shadow-sm"
                  maxLength={10}
                  autoFocus
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || phoneNumber.replace(/\D/g, '').length !== 10}
              className="w-full py-[12px] mt-2 bg-[#CC1E1E] hover:bg-[#b51919] active:bg-[#991515] text-white rounded-[10px] font-bold text-[15px] font-serif tracking-wide transition-all shadow-[0_2px_8px_rgba(204,30,30,0.25)] flex items-center justify-center disabled:opacity-60 cursor-pointer"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send OTP via SMS'}
            </button>
          </form>

          <div className="mt-7 text-center flex flex-col gap-2 border-t border-[#D6E4F5] pt-4">
            <Link to="/login" className="text-[#015BB3] text-xs font-bold hover:underline transition-colors">
              &larr; Login with Email &amp; Password Instead
            </Link>
          </div>
        </div>
      </div>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <div className="py-3 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#0F487F]/70 text-[10px] font-medium tracking-wide">
          Spot News &middot; Powered by MSG91 Secure OTP Gateway
        </span>
      </div>
    </div>
  );
};
