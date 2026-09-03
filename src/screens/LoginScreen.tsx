import { useState, useRef, useEffect } from 'react';
import { useAuthStore, getReporterPhoto, saveReporterPhoto } from '@/store';
import { authService } from '@/services/auth.service';
import { supabase } from '@/lib/supabase';
import { Loader2, Mail, Lock, Camera, User as UserIcon } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';

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
        const finalPhoto = avatarUrl || getReporterPhoto(email) || (userObj as any)?.user_metadata?.avatar_url;
        if (finalPhoto) {
          userObj.avatarUrl = finalPhoto;
          saveReporterPhoto(email, finalPhoto);
          supabase.auth.updateUser({ data: { avatar_url: finalPhoto } }).catch(() => {});
        }
        login(userObj, res.data.token);
        navigate('/');
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
          const finalPhoto = avatarUrl || getReporterPhoto(googleEmail) || userObj?.user_metadata?.avatar_url || userObj?.user_metadata?.picture;
          if (finalPhoto) {
            userObj.avatarUrl = finalPhoto;
            saveReporterPhoto(googleEmail, finalPhoto);
          }
          login(userObj, sessionData.session.access_token);
          navigate('/');
        }
      }

    } catch (err: any) {
      setError(err.message || 'Failed to sign up with Google');
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#dceef8] relative font-sans text-[#0a1a2e]">
      {/* ── RTI Express watermark (faint on light bg) ── */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
         <LogoWatermark darkBackground={false} opacity={0.04} />
      </div>

      {/* ── HEADER ──────────────────────────────────────────────────────── */}
      <div className="bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center justify-center py-4 px-4 shrink-0 shadow-sm relative z-20">
         <div className="flex items-center gap-2">
           <img src={logoUrl} alt="Spot News" className="w-10 h-10 object-contain rounded-md shadow-sm" />
           <div className="flex flex-col">
             <span className="text-white font-bold text-[18px] leading-tight tracking-wide font-serif">SPOT NEWS</span>
             <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">24X7 News Generator</span>
           </div>
         </div>
      </div>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            {/* PORTAL BADGE */}
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              Spot News Portal
            </div>
            
            {/* WELCOME TEXT */}
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Welcome Back, Journalist</h1>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full"></div>
          </div>

          {showSignupPrompt && (
            <div className="mb-5 p-4 bg-amber-50 border-2 border-amber-400 rounded-xl text-[#0a1a2e] text-xs shadow-sm flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <span className="text-base">⚠️</span>
                <span className="font-bold text-sm text-[#0a2540]">Account Not Found</span>
              </div>
              <p className="text-gray-700 leading-relaxed">
                No account was found for <strong className="text-[#0a2540]">{email || 'this email'}</strong>. Please create your reporter account first to get started.
              </p>
              <button
                type="button"
                onClick={() => navigate('/signup', { state: { email, avatarUrl } })}
                className="w-full py-2.5 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-md font-bold text-xs font-serif tracking-wide transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer mt-1"
              >
                Create Account Now &rarr;
              </button>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          {/* REPORTER PHOTO SELECTOR */}
          <div className="flex flex-col items-center justify-center mb-6">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="relative w-20 h-20 rounded-full border-2 border-dashed border-[#cc2222] bg-[#dceef8] flex items-center justify-center cursor-pointer hover:opacity-90 active:scale-95 transition-all shadow-md group overflow-hidden"
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="Reporter" className="w-full h-full object-cover" />
              ) : (
                <div className="flex flex-col items-center justify-center text-[#0a2540]">
                  <UserIcon className="w-8 h-8 text-[#0a2540]/60 mb-0.5" />
                  <span className="text-[8px] font-bold uppercase tracking-wider text-[#0a2540]/70">Photo</span>
                  <div className="absolute bottom-1 right-1 bg-[#cc2222] text-white rounded-full p-1 shadow-sm">
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
              className="text-[#0a2540] text-xs font-bold mt-2 hover:underline flex items-center gap-1.5"
            >
              <Camera className="w-3.5 h-3.5 text-[#cc2222]" />
              {avatarUrl ? 'Change Reporter Photo' : 'Upload Reporter Photo'}
            </button>
            <span className="text-[10px] text-[#5b7e9a] font-medium text-center mt-0.5">
              Will be placed on your newspaper clippings &amp; app header
            </span>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
              <input
                type="email"
                placeholder="Email Address"
                value={email}
                onChange={handleEmailChange}
                className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-sm placeholder:text-[#a0c4dc] focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium"
                required
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#dceef8] rounded-[6px] py-[10px] pl-[36px] pr-3 text-[#0a1a2e] text-sm placeholder:text-[#a0c4dc] focus:outline-none focus:ring-1 focus:ring-[#0a2540] font-medium"
                required
              />
            </div>
            <div className="flex justify-end -mt-1 mb-1">
              <Link to="/forgot-password" state={{ email }} className="text-[11px] font-bold text-[#cc2222] hover:underline">
                Forgot Password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-[12px] mt-2 bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[6px] font-bold text-sm font-serif tracking-wide transition-colors shadow-sm flex items-center justify-center disabled:opacity-70 disabled:hover:bg-[#cc2222]"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-center gap-3">
            <div className="h-px bg-[#b8d4e8] flex-1"></div>
            <span className="text-[#a0c4dc] text-[10px] uppercase font-bold tracking-wider">Or</span>
            <div className="h-px bg-[#b8d4e8] flex-1"></div>
          </div>

          <button
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full py-[12px] mt-6 bg-white active:bg-gray-50 border border-[#b8d4e8] text-[#0a1a2e] rounded-[6px] font-bold text-sm tracking-wide transition-colors shadow-sm flex items-center justify-center gap-3 disabled:opacity-70"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            Sign in with Google
          </button>

          <div className="mt-8 text-center flex flex-col gap-2">
            <p className="text-[#a0c4dc] text-xs font-medium">
              Don't have an account?{' '}
              <Link to="/signup" className="text-[#0a2540] font-bold hover:underline transition-colors">
                Sign Up
              </Link>
            </p>
            <Link to="/login/otp" className="text-[#0a2540] text-xs font-bold hover:underline transition-colors mt-2">
              Login with OTP instead
            </Link>
          </div>
        </div>
      </div>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <div className="bg-[#0a2540] border-t-[2px] border-[#cc2222] py-4 px-4 flex items-center justify-center shrink-0 relative z-20">
        <span className="text-[#a0c4dc] text-[9px] font-medium tracking-wide">
          Terms of Service &middot; Privacy Policy &middot; Help
        </span>
      </div>
    </div>
  );
};
