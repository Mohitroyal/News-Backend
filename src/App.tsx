import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { Settings, Plus } from 'lucide-react';
import { useTranslation } from './lib/i18n';
import mastheadLogo from './assets/rti_express_logo.png';
import watermarkLogo from './assets/rti_express_watermark.png';
import { SplashScreen } from './screens/SplashScreen';
import { LoginScreen } from './screens/LoginScreen';
import { SignupScreen } from './screens/SignupScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { GenerateScreen } from './screens/GenerateScreen';
import { TemplatesScreen } from './screens/TemplatesScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { ProfileSettingsScreen } from './screens/ProfileSettingsScreen';
import { PreviewScreen } from './screens/PreviewScreen';
import { LoginOtpScreen } from './screens/LoginOtpScreen';
import { VerifyOtpScreen } from './screens/VerifyOtpScreen';
import { CreatePasswordScreen } from './screens/CreatePasswordScreen';
import { ForgotPasswordScreen } from './screens/ForgotPasswordScreen';
import { useAuthStore, useUIStore, getReporterPhoto, getReporterName } from './store';
import { AdminScreen } from './screens/AdminScreen';
import { supabase } from './lib/supabase';
import { App as CapacitorApp } from '@capacitor/app';
import { Browser } from '@capacitor/browser';

import { ErrorBoundary } from './ErrorBoundary';

// Mobile Layout with Bottom Navigation
const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const userAvatar = getReporterPhoto(user?.email) || user?.avatarUrl || (user as any)?.user_metadata?.avatar_url || (user as any)?.user_metadata?.picture || (user as any)?.avatar_url;
  const userName = getReporterName(user?.email) || (user as any)?.user_metadata?.full_name || (user as any)?.user_metadata?.name || user?.full_name || user?.firstName || 'Reporter';
  const userInitials = userName.split(' ').filter(Boolean).map((n: string) => n[0]).join('').substring(0, 2).toUpperCase() || 'RP';

  return (
    <div className="flex flex-col h-screen bg-[#EEF3F8] transition-colors duration-300 relative font-sans">

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
          opacity: 0.1,
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


      <header className="w-full bg-[#0D1B2A] flex flex-col pt-safe sticky top-0 z-10 shadow-sm">
        {/* ── Top meta row: EST. 2024 | INDIA  ·  REPORTER: username ── */}
        <div className="w-full flex items-center justify-between px-4 pt-2 pb-1">
          <span className="text-white/55 text-[10px] uppercase tracking-wider font-semibold">EST. 2024 | INDIA</span>
          <span className="text-white/55 text-[10px] uppercase tracking-wider font-semibold">
            REPORTER: {userName}
          </span>
        </div>

        {/* ── Logo + Title row with Top-Right Profile Avatar ── */}
        <div className="w-full flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-3">
            {/* Logo box */}
            <div className="rounded-[8px] flex items-center justify-center h-[46px] overflow-hidden">
              <img src={mastheadLogo} alt="RTI Express Logo" className="h-full w-auto object-contain" style={{ maxWidth: '90px', borderRadius: '4px' }} />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-white text-[24px] leading-none tracking-widest" style={{ fontFamily: "'Georgia', serif" }}>{t.rtiExpress}</span>
              <span className="text-white/50 text-[11px] uppercase font-bold tracking-widest mt-0.5">24X7</span>
            </div>
          </div>

          {/* Top-Right Profile Avatar Badge */}
          <Link to="/settings" className="flex items-center gap-2 active:scale-95 transition-transform" title="Reporter Profile">
            {userAvatar ? (
              <img
                src={userAvatar}
                alt="Reporter Profile"
                className="w-10 h-10 rounded-full object-cover border-2 border-[#CC1E1E] shadow-md bg-white"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-[#1e3a5f] border-2 border-[#CC1E1E] flex items-center justify-center text-white font-bold text-sm shadow-md">
                {userInitials}
              </div>
            )}
          </Link>
        </div>

        {/* ── Date bar ── */}
        <div className="w-full flex items-center justify-center px-4 py-1.5 bg-[#0D1B2A]">
          <span className="text-white/60 text-[11px] tracking-wide font-medium">
            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
        </div>

        {/* ── Ticker bar ── */}
        <div className="w-full bg-[#1e3a5f] py-2 px-4 flex items-center gap-3">
          <span className="bg-white text-[#1e3a5f] text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full whitespace-nowrap">
            {t.latest}
          </span>
          <span className="text-white text-[12px] truncate">
            Wanted Reporters:7668886666
          </span>
        </div>
      </header>

      {/* Main Content Area (Scrollable) */}
      <main className="flex-1 overflow-y-auto pb-4" style={{ position: 'relative', zIndex: 3 }}>
        <ErrorBoundary>
          {children}
        </ErrorBoundary>
      </main>


      {/* Bottom Navigation */}
      <nav className="bg-[#0a2540] fixed bottom-0 w-full pb-safe flex justify-center items-center gap-[64px] h-[78px] z-20">
        {/* Plus Tab */}
        <Link to="/generate" className="flex items-center justify-center w-[54px] h-[54px] bg-[#16334d] rounded-full text-[#dceef8] active:scale-95 transition-transform">
          <Plus className="w-[26px] h-[26px]" strokeWidth={2} />
        </Link>

        {/* Settings Tab */}
        <Link to="/settings" className="flex items-center justify-center w-[54px] h-[54px] bg-[#16334d] rounded-full text-[#dceef8] active:scale-95 transition-transform">
          <Settings className="w-[26px] h-[26px]" strokeWidth={2} />
        </Link>
      </nav>
    </div>
  );
};

import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';

// ── Admin email list ────────────────────────────────────────────────────────
const ADMIN_EMAILS = (import.meta.env.VITE_ADMIN_EMAILS ?? 'mohithroyal16450@gmail.com')
  .split(',')
  .map((e: string) => e.trim().toLowerCase());

function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const login = useAuthStore((state) => state.login);
  const setPendingCropImageSrc = useUIStore((state) => state.setPendingCropImageSrc);

  useEffect(() => {
    // Initialize Google Auth plugin
    GoogleAuth.initialize({
      clientId: '831106920430-h8h1nj7a5j2iirgki34ve8ariuj8uroi.apps.googleusercontent.com',
      scopes: ['profile', 'email'],
      grantOfflineAccess: true,
    });

    // Listen for deep links (e.g. Supabase OAuth callback)
    CapacitorApp.addListener('appUrlOpen', async (event) => {
      if (event.url.includes('access_token')) {
        await Browser.close().catch(() => {});
        const urlObj = new URL(event.url);
        // Supabase passes tokens in the hash like #access_token=...&refresh_token=...
        const hashStr = urlObj.hash.startsWith('#') ? urlObj.hash.substring(1) : urlObj.hash;
        const params = new URLSearchParams(hashStr);
        const access_token = params.get('access_token');
        const refresh_token = params.get('refresh_token');

        if (access_token && refresh_token) {
          const { data } = await supabase.auth.setSession({
            access_token,
            refresh_token,
          });
          if (data.session) {
            login(data.session.user as any, data.session.access_token);
            // Redirect admin emails to admin panel, others to dashboard
            const email = data.session.user?.email?.toLowerCase().trim() ?? '';
            window.location.href = ADMIN_EMAILS.includes(email) ? '/admin' : '/';
          }
        }
      }
    });

    // Listen for appRestoredResult to handle Android background killing during camera/gallery intents
    CapacitorApp.addListener('appRestoredResult', (data: any) => {
      console.log('App restored result:', data);
      if (data && data.pluginId === 'Camera' && data.methodName === 'pickImages') {
        if (data.data && data.data.photos && data.data.photos.length > 0) {
          const webPath = data.data.photos[0].webPath;
          if (webPath) {
            setPendingCropImageSrc(webPath);
          }
        }
      }
    });

    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      if (session) {
        const email = session.user?.email;
        const savedName = getReporterName(email);
        const savedPhoto = getReporterPhoto(email);
        const userObj = {
          ...session.user,
          full_name: savedName || (session.user as any)?.user_metadata?.full_name || (session.user as any)?.user_metadata?.name || (session.user as any)?.full_name || '',
          firstName: savedName || (session.user as any)?.user_metadata?.full_name || '',
          avatarUrl: savedPhoto || (session.user as any)?.user_metadata?.avatar_url || (session.user as any)?.user_metadata?.picture || '',
        };
        login(userObj as any, session.access_token);

        // Auto-redirect admin emails to /admin on SIGNED_IN event
        if (event === 'SIGNED_IN') {
          const emailLower = email?.toLowerCase().trim() ?? '';
          if (ADMIN_EMAILS.includes(emailLower)) {
            // Small delay to let React Router mount before navigating
            setTimeout(() => { window.location.href = '/admin'; }, 100);
          }
        }
      }
    });

    // Simulate splash screen / capacitor initialization
    const timer = setTimeout(() => setIsInitializing(false), 2000);
    return () => {
      clearTimeout(timer);
      authListener.subscription.unsubscribe();
      CapacitorApp.removeAllListeners();
    };
  }, []);

  if (isInitializing) return <SplashScreen />;

  return (
    <Router>
      <Routes>
        <Route 
          path="/login" 
          element={!isAuthenticated ? <LoginScreen /> : <Navigate to="/" />} 
        />
        <Route 
          path="/login/otp" 
          element={!isAuthenticated ? <LoginOtpScreen /> : <Navigate to="/" />} 
        />
        <Route 
          path="/login/verify" 
          element={!isAuthenticated ? <VerifyOtpScreen /> : <Navigate to="/" />} 
        />
        <Route 
          path="/signup" 
          element={!isAuthenticated ? <SignupScreen /> : <Navigate to="/" />} 
        />
        <Route 
          path="/create-password" 
          element={<CreatePasswordScreen />} 
        />
        <Route 
          path="/reset-password" 
          element={<CreatePasswordScreen />} 
        />
        <Route 
          path="/forgot-password" 
          element={<ForgotPasswordScreen />} 
        />

        {/* ── Admin Route (standalone, no MainLayout) ── */}
        <Route 
          path="/admin" 
          element={<AdminScreen />} 
        />
        
        <Route 
          path="/preview/:id" 
          element={isAuthenticated ? <PreviewScreen /> : <Navigate to="/login" />} 
        />
        
        <Route 
          path="/*" 
          element={
            isAuthenticated ? (
              <MainLayout>
                <Routes>
                  <Route path="/" element={<GenerateScreen />} />
                  <Route path="/dashboard" element={<DashboardScreen />} />
                  <Route path="/generate" element={<GenerateScreen />} />
                  <Route path="/templates" element={<TemplatesScreen />} />
                  <Route path="/history" element={<HistoryScreen />} />
                  <Route path="/settings" element={<SettingsScreen />} />
                  <Route path="/settings/profile" element={<ProfileSettingsScreen />} />
                  <Route path="*" element={<Navigate to="/" />} />
                </Routes>
              </MainLayout>
            ) : (
              <Navigate to="/login" />
            )
          } 
        />
      </Routes>
    </Router>
  );
}

export default App;
