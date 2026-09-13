import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { Settings, Plus, Newspaper } from 'lucide-react';
// import { useTranslation } from './lib/i18n';
import mastheadLogo from './assets/rti_express_logo.png';
import watermarkLogo from './assets/rti_express_watermark.png';
import { SplashScreen } from './screens/SplashScreen';
import { LoginScreen } from './screens/LoginScreen';
import { SignupScreen } from './screens/SignupScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { GenerateScreen } from './screens/GenerateScreen';
import { TemplatesScreen } from './screens/TemplatesScreen';
import { NewsScreen } from './screens/NewsScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { ProfileSettingsScreen } from './screens/ProfileSettingsScreen';
import { PreviewScreen } from './screens/PreviewScreen';
import { LoginOtpScreen } from './screens/LoginOtpScreen';
import { VerifyOtpScreen } from './screens/VerifyOtpScreen';
import { CreatePasswordScreen } from './screens/CreatePasswordScreen';
import { ForgotPasswordScreen } from './screens/ForgotPasswordScreen';
import { AdminScreen } from './screens/AdminScreen';
import { useAuthStore, useUIStore, getReporterPhoto, getReporterName, isAdminUser } from './store';
import { supabase } from './lib/supabase';
import { App as CapacitorApp } from '@capacitor/app';
import { Browser } from '@capacitor/browser';

import { ErrorBoundary } from './ErrorBoundary';

// Mobile Layout with Bottom Navigation
const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const isGeneratePage = location.pathname === '/' || location.pathname === '/generate';
  // const { t } = useTranslation();
  const { user } = useAuthStore();
  const userAvatar = getReporterPhoto(user?.email) || user?.avatarUrl || (user as any)?.user_metadata?.avatar_url || (user as any)?.user_metadata?.picture || (user as any)?.avatar_url;
  const userName = getReporterName(user?.email) || (user as any)?.user_metadata?.full_name || (user as any)?.user_metadata?.name || user?.full_name || user?.firstName || 'Reporter';
  const userInitials = userName.split(' ').filter(Boolean).map((n: string) => n[0]).join('').substring(0, 2).toUpperCase() || 'RP';

  const headerBg = '#015BB3';

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


      {/* Main Content Area — masthead scrolls with content on long pages, locked without scroll on generation page */}
      <main
        className={`flex-1 flex flex-col ${isGeneratePage ? 'overflow-hidden pb-[68px]' : 'overflow-y-auto pb-[76px]'}`}
        style={{
          position: 'relative',
          zIndex: 3,
          overscrollBehavior: isGeneratePage ? 'none' : 'auto',
          touchAction: isGeneratePage ? 'pan-x' : 'auto'
        }}
      >
        {/* ── Masthead (scrolls with page) ── */}
        <header className="w-full flex flex-col pt-safe" style={{ background: '#EAF2FB' }}>
          <div style={{ background: headerBg, paddingBottom: '12px' }}>
            {/* ── Main Header Content ── */}
            <div className="w-full flex items-start justify-between px-3.5 pt-3.5 pb-2 gap-2">
              {/* Left Column: Logo + Title + Date below */}
              <div className="flex flex-col gap-1 shrink-0">
                <div className="flex items-center gap-2">
                  {/* Logo box */}
                  <div className="rounded-[8px] flex items-center justify-center h-[46px] overflow-hidden bg-white p-1 border border-[#0B56A6]/20 shrink-0">
                    <img src={mastheadLogo} alt="Spot News Logo" className="h-full w-auto object-contain" style={{ maxWidth: '92px', borderRadius: '4px' }} />
                  </div>
                  <div className="flex flex-col justify-center">
                    <span className="font-bold text-white text-[23px] leading-[1.15] tracking-wide" style={{ fontFamily: "'Georgia', serif" }}>
                      Spot News<br/>24x7
                    </span>
                  </div>
                </div>

                {/* Date text (italic serif font) */}
                <span className="text-white/90 text-[11.5px] tracking-wide font-medium font-serif italic pt-1 whitespace-nowrap">
                  {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>

              {/* Right Column: Profile Avatar -> Reporter Name UP */}
              <div className="flex flex-col items-end text-right pt-0.5 shrink-0">
                <Link to="/settings" className="flex flex-col items-center gap-0.5 active:scale-95 transition-transform" title="Reporter Profile">
                  {userAvatar ? (
                    <img
                      src={userAvatar}
                      alt="Reporter Profile"
                      className="w-11 h-11 rounded-full object-cover border-2 border-[#CC1E1E] shadow-sm bg-white"
                    />
                  ) : (
                    <div className="w-11 h-11 rounded-full bg-[#1e3a5f] border-2 border-[#CC1E1E] flex items-center justify-center text-white font-bold text-sm shadow-sm">
                      {userInitials}
                    </div>
                  )}
                  <div className="flex flex-col items-center leading-tight text-center mt-1">
                    <span className="text-white/80 text-[8.5px] uppercase tracking-wider font-extrabold">REPORTER:</span>
                    <span className="text-white text-[9.5px] uppercase tracking-wider font-extrabold">{userName}</span>
                  </div>
                </Link>
              </div>
            </div>
          </div>

          {/* ── Smooth Wave Divider Transition ── */}
          <div style={{ width: '100%', overflow: 'hidden', lineHeight: 0, background: '#EAF2FB' }}>
            <svg
              viewBox="0 0 1440 240"
              preserveAspectRatio="none"
              style={{ position: 'relative', display: 'block', width: '100%', height: '52px' }}
            >
              <path
                d="M0,0 L1440,0 L1440,100 C1100,240 500,10 0,170 Z"
                fill={headerBg}
              />
            </svg>
          </div>
        </header>

        <ErrorBoundary>
          {children}
        </ErrorBoundary>
      </main>


      <nav className="fixed bottom-0 left-0 right-0 w-full pb-safe flex items-center justify-around h-[68px] z-30 shadow-md border-t border-[#E2EDF8]" style={{ background: '#FFFFFF' }}>
        {/* 1. News Tab */}
        <Link
          to="/news"
          className="flex flex-col items-center justify-center flex-1 h-full pt-1 active:scale-95 transition-transform"
        >
          <Newspaper className="w-6 h-6" style={{ color: '#0C447C' }} />
          <span className="text-[11px] font-bold mt-1" style={{ color: '#0C447C' }}>
            News
          </span>
        </Link>

        {/* 2. Create Tab (Center Raised) */}
        <Link
          to="/generate"
          className="flex flex-col items-center justify-center flex-1 relative h-full active:scale-95 transition-transform"
        >
          <div
            className="absolute -top-5 w-[54px] h-[54px] rounded-full flex items-center justify-center"
            style={{
              background: '#FFFFFF',
              border: '2.5px solid #CC1E1E',
              padding: '3px',
              boxShadow: '0 4px 12px rgba(204,30,30,0.22)',
            }}
          >
            <div
              className="w-full h-full rounded-full flex items-center justify-center"
              style={{ background: '#CC1E1E' }}
            >
              <Plus className="w-7 h-7 text-white" strokeWidth={2.8} />
            </div>
          </div>
          <span
            className="text-[11px] font-bold mt-[26px]"
            style={{ color: '#CC1E1E' }}
          >
            Create
          </span>
        </Link>

        {/* 3. Settings Tab */}
        <Link
          to="/settings"
          className="flex flex-col items-center justify-center flex-1 h-full pt-1 active:scale-95 transition-transform"
        >
          <Settings className="w-6 h-6" style={{ color: '#0C447C' }} />
          <span className="text-[11px] font-bold mt-1" style={{ color: '#0C447C' }}>
            Settings
          </span>
        </Link>
      </nav>
    </div>
  );
};

import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';


function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const login = useAuthStore((state) => state.login);
  const updateUser = useAuthStore((state) => state.updateUser);
  const setPendingCropImageSrc = useUIStore((state) => state.setPendingCropImageSrc);

  const [isAdminVerified, setIsAdminVerified] = useState(false);

  const isAdmin =
    isAdminVerified ||
    isAdminUser(user) ||
    (user as any)?.role === 'admin' ||
    (user as any)?.app_metadata?.role === 'admin' ||
    (user as any)?.user_metadata?.role === 'admin';

  useEffect(() => {
    const checkAdminRole = async () => {
      if (!user?.id) {
        setIsAdminVerified(false);
        return;
      }
      if (
        isAdminUser(user) ||
        (user as any)?.role === 'admin' ||
        (user as any)?.app_metadata?.role === 'admin' ||
        (user as any)?.user_metadata?.role === 'admin'
      ) {
        setIsAdminVerified(true);
        return;
      }

      try {
        const { data: prof } = await supabase
          .from('profiles')
          .select('role')
          .eq('id', user.id)
          .single();
        if (prof?.role === 'admin') {
          updateUser({ role: 'admin' } as any);
          setIsAdminVerified(true);
          return;
        }
      } catch { /* silent */ }

      try {
        const token = useAuthStore.getState().token;
        if (token) {
          const res = await fetch(
            'https://news-backend-sjw6.onrender.com/api/v1/admin/stats',
            { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(6000) }
          );
          const isDbAdmin = res.status === 200;
          if (isDbAdmin) {
            updateUser({ role: 'admin' } as any);
          }
          setIsAdminVerified(isDbAdmin);
        }
      } catch {
        setIsAdminVerified(false);
      }
    };
    checkAdminRole();
  }, [user?.id]);

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
        await Browser.close().catch(() => { });
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

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
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
      }
    });

    // Initial splash screen dismiss timer (runs once on cold start only)
    const timer = setTimeout(() => setIsInitializing(false), 1200);
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

        {/* ── Admin Route (standalone, only for verified admins) ── */}
        <Route
          path="/admin"
          element={
            !isAuthenticated ? (
              <Navigate to="/login" replace />
            ) : isAdmin ? (
              <AdminScreen />
            ) : (
              <Navigate to="/" replace />
            )
          }
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
                  <Route path="/news" element={<NewsScreen />} />
                  <Route path="/history" element={<NewsScreen />} />
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
