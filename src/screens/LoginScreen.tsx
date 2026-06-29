import { useState } from 'react';
import { useAuthStore } from '@/store';
import { authService } from '@/services/auth.service';
import { supabase } from '@/lib/supabase';
import { Loader2, Mail, Lock } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';
import { LogoWatermark } from '@/components/LogoWatermark';
import logoUrl from '@/assets/rti_express_logo.png';

export const LoginScreen = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await authService.login({ email, password });
      if (res.data) {
        login(res.data.user, res.data.token);
        navigate('/');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to login');
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
          login(sessionData.session.user as any, sessionData.session.access_token);
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
           <img src={logoUrl} alt="RTI" className="w-10 h-10 object-contain rounded-md shadow-sm" />
           <div className="flex flex-col">
             <span className="text-white font-bold text-[18px] leading-tight tracking-wide font-serif">EXPRESS</span>
             <span className="text-[#a0c4dc] text-[8px] uppercase tracking-widest font-semibold leading-none">News Generator</span>
           </div>
         </div>
      </div>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        
        <div className="w-full max-w-md bg-white border border-[#b8d4e8] rounded-xl p-8 shadow-sm">
          
          <div className="mb-6 flex flex-col items-start">
            {/* PORTAL BADGE */}
            <div className="bg-[#0a2540] text-white text-[9px] uppercase tracking-widest font-bold py-1 px-2.5 rounded-full mb-3 shadow-sm">
              NewsCraft Portal
            </div>
            
            {/* WELCOME TEXT */}
            <h1 className="text-[#0a1a2e] text-2xl font-bold font-serif mb-2">Welcome Back, Journalist</h1>
            <div className="w-12 h-[3px] bg-[#cc2222] rounded-full"></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-[#cc2222] rounded-[8px] text-[#cc2222] text-xs font-semibold text-center shadow-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a0c4dc]" />
              <input
                type="email"
                placeholder="Email Address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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

          <div className="mt-8 text-center">
            <p className="text-[#a0c4dc] text-xs font-medium">
              Don't have an account?{' '}
              <Link to="/signup" className="text-[#0a2540] font-bold hover:underline transition-colors">
                Sign Up
              </Link>
            </p>
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
