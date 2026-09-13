import { useState, useRef, useEffect } from 'react';
import { useAuthStore, getReporterPhoto, saveReporterPhoto, isAdminUser } from '@/store';
import { authService } from '@/services/auth.service';
import { supabase } from '@/lib/supabase';
import { Loader2, Mail, Lock, Camera, Phone, User as UserIcon } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';
import logoUrl from '@/assets/rti_express_logo.png';
import watermarkLogo from '@/assets/rti_express_watermark.png';

export const LoginScreen = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [avatarUrl, setAvatarUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();

  useEffect(() => {
    const saved = getReporterPhoto(email);
    if (saved) {
      setAvatarUrl(saved);
    }
  }, []);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    if (newEmail.trim().length > 3) {
      const stored = getReporterPhoto(newEmail);
      if (stored) {
        setAvatarUrl(stored);
      }
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const size = Math.min(img.width, img.height);
        const targetSize = 250;
        canvas.width = targetSize;
        canvas.height = targetSize;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          const offsetX = (img.width - size) / 2;
          const offsetY = (img.height - size) / 2;
          ctx.drawImage(img, offsetX, offsetY, size, size, 0, 0, targetSize, targetSize);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
          setAvatarUrl(dataUrl);
          saveReporterPhoto(email, dataUrl);
        } else {
          const dataUrl = event.target?.result as string;
          setAvatarUrl(dataUrl);
          saveReporterPhoto(email, dataUrl);
        }
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
  };

  const [showSignupPrompt, setShowSignupPrompt] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setShowSignupPrompt(false);

    try {
      const res = await authService.login({ email, password });
      if (res.data) {
        const userObj = { ...res.data.user };
        try {
          const { data: profile } = await supabase
            .from('profiles')
            .select('role')
            .eq('id', userObj.id)
            .single();
          if (profile?.role) {
            userObj.role = profile.role;
          }
        } catch {}

        const finalPhoto = avatarUrl || getReporterPhoto(email) || (userObj as any)?.user_metadata?.avatar_url;
        if (finalPhoto) {
          userObj.avatarUrl = finalPhoto;
          saveReporterPhoto(email, finalPhoto);
          supabase.auth.updateUser({ data: { avatar_url: finalPhoto } }).catch(() => {});
        }
        login(userObj, res.data.token);
        navigate(isAdminUser(userObj) ? '/admin' : '/');
      }
    } catch (err: any) {
      const errMsg = err.message || err.response?.data?.message || '';
      if (
        errMsg.toLowerCase().includes('invalid login credentials') ||
        errMsg.toLowerCase().includes('invalid_credentials') ||
        errMsg.toLowerCase().includes('user not found') ||
        errMsg.toLowerCase().includes('invalid_grant')
      ) {
        setShowSignupPrompt(true);
      } else {
        setError(errMsg || 'Failed to login. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await GoogleAuth.signIn();

      if (response && response.authentication) {
        const { error: authError, data: sessionData } = await supabase.auth.signInWithIdToken({
          provider: 'google',
          token: response.authentication.idToken,
        });

        if (authError) throw authError;

        if (sessionData.session) {
          const userObj = { ...sessionData.session.user } as any;
          const googleEmail = userObj?.email;

          // Fetch latest role from profiles table (user can read their own profile row)
          try {
            const { data: profile } = await supabase
              .from('profiles')
              .select('role')
              .eq('id', userObj.id)
              .single();
            if (profile?.role) {
              userObj.role = profile.role;
            }
          } catch {}

          const finalPhoto = avatarUrl || getReporterPhoto(googleEmail) || userObj?.user_metadata?.avatar_url || userObj?.user_metadata?.picture;
          if (finalPhoto) {
            userObj.avatarUrl = finalPhoto;
            saveReporterPhoto(googleEmail, finalPhoto);
          }
          login(userObj, sessionData.session.access_token);
          navigate(isAdminUser(userObj) ? '/admin' : '/');
        }
      }

    } catch (err: any) {
      setError(err.message || 'Failed to sign up with Google');
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
            {/* Logo box + Spot News 24x7 */}
            <div className="flex items-center gap-2.5">
              <div className="rounded-[8px] flex items-center justify-center h-[46px] overflow-hidden bg-white p-1 border border-[#0B56A6]/20 shrink-0 shadow-sm">
                <img src={logoUrl} alt="Spot News Logo" className="h-full w-auto object-contain" style={{ maxWidth: '92px', borderRadius: '4px' }} />
              </div>
              <div className="flex flex-col justify-center">
                <span className="font-bold text-white text-[22px] leading-[1.15] tracking-wide" style={{ fontFamily: "'Georgia', serif" }}>
                  Spot News<br/>24x7
                </span>
              </div>
            </div>

            {/* Portal Badge */}
            <div className="flex flex-col items-end shrink-0">
              <div className="bg-white/15 border border-white/25 text-white text-[9.5px] uppercase tracking-widest font-extrabold py-1 px-3 rounded-full shadow-sm">
                REPORTER PORTAL
              </div>
            </div>
          </div>
        </div>

        {/* ── Smooth Wave Divider ── */}
        <div style={{ width: '100%', overflow: 'hidden', lineHeight: 0, background: '#EAF2FB', position: 'relative' }}>
          <svg
            viewBox="0 0 1440 240"
            preserveAspectRatio="none"
            style={{ position: 'relative', display: 'block', width: '100%', height: '42px' }}
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
            {/* PORTAL BADGE */}
            <div className="bg-[#EAF2FB] border border-[#D6E4F5] text-[#0F487F] text-[9.5px] uppercase tracking-wider font-extrabold py-1 px-2.5 rounded-full mb-2.5 shadow-sm">
              Spot News Portal
            </div>
            
            {/* WELCOME TEXT */}
            <h1 className="text-[#163E6C] text-2xl font-bold font-serif mb-1.5" style={{ fontFamily: "'Georgia', serif" }}>
              Welcome Back, Journalist
            </h1>
            <div className="w-12 h-[3px] bg-[#CC1E1E] rounded-full"></div>
          </div>

          {showSignupPrompt && (
            <div className="mb-5 p-4 bg-amber-50 border-2 border-amber-400 rounded-xl text-[#0F172A] text-xs shadow-sm flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <span className="text-base">⚠️</span>
                <span className="font-bold text-sm text-[#0F487F]">Account Not Found</span>
              </div>
              <p className="text-gray-700 leading-relaxed">
                No account was found for <strong className="text-[#0F487F]">{email || 'this email'}</strong>. Please create your reporter account first to get started.
              </p>
              <button
                type="button"
                onClick={() => navigate('/signup', { state: { email, avatarUrl } })}
                className="w-full py-2.5 bg-[#CC1E1E] hover:bg-[#b51919] active:bg-[#991515] text-white rounded-lg font-bold text-xs font-serif tracking-wide transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer mt-1"
              >
                Create Account Now &rarr;
              </button>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#CC1E1E] rounded-[10px] text-[#CC1E1E] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          {/* REPORTER PHOTO SELECTOR */}
          <div className="flex flex-col items-center justify-center mb-5">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="relative w-20 h-20 rounded-full border-2 border-[#CC1E1E] bg-[#EAF2FB] flex items-center justify-center cursor-pointer hover:opacity-90 active:scale-95 transition-all shadow-md group overflow-hidden"
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="Reporter" className="w-full h-full object-cover" />
              ) : (
                <div className="flex flex-col items-center justify-center text-[#0F487F]">
                  <UserIcon className="w-8 h-8 text-[#0F487F]/60 mb-0.5" />
                  <span className="text-[8px] font-bold uppercase tracking-wider text-[#0F487F]/70">Photo</span>
                  <div className="absolute bottom-1 right-1 bg-[#CC1E1E] text-white rounded-full p-1 shadow-sm">
                    <Camera className="w-3 h-3" />
                  </div>
                </div>
              )}
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleAvatarChange}
              accept="image/*"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-[#0F487F] text-xs font-bold mt-2 hover:underline flex items-center gap-1.5 cursor-pointer"
            >
              <Camera className="w-3.5 h-3.5 text-[#CC1E1E]" />
              {avatarUrl ? 'Change Reporter Photo' : 'Upload Reporter Photo'}
            </button>
            <span className="text-[10.5px] text-[#64748B] font-medium text-center mt-0.5">
              Will be placed on your newspaper clippings &amp; app header
            </span>
          </div>

          <form onSubmit={handleLogin} className="space-y-3.5">
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0F487F]" />
              <input
                type="email"
                placeholder="Email Address"
                value={email}
                onChange={handleEmailChange}
                className="w-full bg-white border border-[#D6E4F5] rounded-[10px] py-[11px] pl-[38px] pr-3 text-[#0F172A] text-sm placeholder:text-[#94A3B8] focus:outline-none focus:border-[#015BB3] focus:ring-2 focus:ring-[#015BB3]/15 transition-all shadow-sm font-medium"
                required
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0F487F]" />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white border border-[#D6E4F5] rounded-[10px] py-[11px] pl-[38px] pr-3 text-[#0F172A] text-sm placeholder:text-[#94A3B8] focus:outline-none focus:border-[#015BB3] focus:ring-2 focus:ring-[#015BB3]/15 transition-all shadow-sm font-medium"
                required
              />
            </div>
            <div className="flex justify-end -mt-1 mb-1">
              <Link to="/forgot-password" state={{ email }} className="text-[11.5px] font-bold text-[#CC1E1E] hover:underline">
                Forgot Password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-[12px] mt-1 bg-[#CC1E1E] hover:bg-[#b51919] active:bg-[#991515] text-white rounded-[10px] font-bold text-[15px] font-serif tracking-wide transition-all shadow-[0_2px_8px_rgba(204,30,30,0.25)] flex items-center justify-center disabled:opacity-70 cursor-pointer"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign In'}
            </button>
          </form>

          <div className="mt-5 flex items-center justify-center gap-3">
            <div className="h-px bg-[#D6E4F5] flex-1"></div>
            <span className="text-[#0F487F] text-[10.5px] uppercase font-bold tracking-wider">Or</span>
            <div className="h-px bg-[#D6E4F5] flex-1"></div>
          </div>

          <div className="flex flex-col gap-2.5 mt-5">
            <button
              type="button"
              onClick={() => navigate('/login/otp')}
              className="w-full py-[12px] bg-[#015BB3] hover:bg-[#1254A8] active:bg-[#0c4387] text-white rounded-[10px] font-bold text-[14.5px] tracking-wide transition-all shadow-[0_2px_8px_rgba(1,91,179,0.25)] flex items-center justify-center gap-2 cursor-pointer font-serif border border-[#0B56A6]/20"
            >
              <Phone className="w-4 h-4 text-white" />
              Login with Mobile OTP
            </button>

            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={loading}
              className="w-full py-[12px] bg-white hover:bg-[#F8FAFC] active:bg-[#F1F5F9] border border-[#D6E4F5] text-[#0F172A] rounded-[10px] font-bold text-[14px] tracking-wide transition-colors shadow-sm flex items-center justify-center gap-3 disabled:opacity-70 cursor-pointer"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              Sign in with Google
            </button>
          </div>

          <div className="mt-6 text-center flex flex-col gap-1.5">
            <p className="text-[#64748B] text-xs font-medium">
              Don't have an account?{' '}
              <Link to="/signup" className="text-[#015BB3] font-bold hover:underline transition-colors">
                Sign Up
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <div className="py-3 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#0F487F]/70 text-[10px] font-medium tracking-wide">
          Spot News 24x7 &middot; Secured Reporter Authentication
        </span>
      </div>
    </div>
  );
};
