import { useState } from 'react';
import { authService } from '@/services/auth.service';
import { Loader2, Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';

export const ForgotPasswordScreen = () => {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email || '');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleResetRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await authService.forgotPassword(email.trim());
      setSent(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send reset link. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#dceef8] relative font-sans text-[#0a1a2e]">
      {/* ── RTI Express watermark ── */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
         <LogoWatermark darkBackground={false} opacity={0.04} />
      </div>

      {/* ── HEADER ── */}
      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-center py-4 px-4 shrink-0 shadow-sm relative z-20">
         <div className="flex items-center gap-2">
           <img src={logoUrl} alt="Spot News" className="w-10 h-10 object-contain rounded-md shadow-sm" />
           <div className="flex flex-col">
             <span className="text-white font-bold text-[18px] leading-tight tracking-wide font-serif">SPOT NEWS</span>
             <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">24X7 News Generator</span>
           </div>
         </div>
      </div>

      {/* ── MAIN CONTENT ── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              Account Recovery
            </div>
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Forgot Password?</h1>
            <p className="text-xs text-[#5b7e9a] font-medium leading-relaxed">
              Enter your registered email address and we'll send you a link to reset your password.
            </p>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full mt-3"></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          {sent ? (
            <div className="flex flex-col items-center text-center p-4 bg-emerald-50 border border-emerald-300 rounded-xl">
              <CheckCircle2 className="w-12 h-12 text-emerald-600 mb-3" />
              <h3 className="text-[#0a2540] font-bold text-base font-serif mb-1">Reset Link Sent!</h3>
              <p className="text-xs text-gray-700 leading-relaxed mb-4">
                We've sent a password reset link to <strong className="text-[#0a2540]">{email}</strong>. Please check your inbox (and spam folder) to set a new password.
              </p>
              <button
                type="button"
                onClick={() => navigate('/login', { state: { email } })}
                className="w-full py-3 bg-[#0a2540] hover:bg-[#143d66] text-white rounded-[6px] font-bold text-xs tracking-wide transition-colors shadow-sm"
              >
                Back to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleResetRequest} className="space-y-4">
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
                <input
                  type="email"
                  placeholder="Registered Email Address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-sm placeholder:text-[#a0c4dc] focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-70 disabled:hover:bg-[#cc2222]"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send Reset Link'}
              </button>

              <div className="mt-6 text-center pt-2">
                <Link to="/login" className="text-[#0a2540] text-xs font-bold hover:underline transition-colors inline-flex items-center gap-1.5">
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back to Sign In
                </Link>
              </div>
            </form>
          )}

        </div>
      </div>

      {/* ── FOOTER ── */}
      <div className="bg-[#0a2540] border-t-[2px] border-[#cc2222] py-4 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#a0c4dc] text-[9px] font-medium tracking-wide">
          Terms of Service &middot; Privacy Policy &middot; Help
        </span>
      </div>
    </div>
  );
};
