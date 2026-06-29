import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { Home, FileText, Settings, History, Plus } from 'lucide-react';
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
import { PreviewScreen } from './screens/PreviewScreen';
import { useAuthStore } from './store';
import { supabase } from './lib/supabase';
import { App as CapacitorApp } from '@capacitor/app';
import { Browser } from '@capacitor/browser';

import { ErrorBoundary } from './ErrorBoundary';

// Mobile Layout with Bottom Navigation
const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;
  const { t } = useTranslation();
  const { user } = useAuthStore();

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
            REPORTER: {(user as any)?.user_metadata?.full_name || (user as any)?.user_metadata?.name || user?.full_name || user?.firstName || 'Journalist'}
          </span>
        </div>

        {/* ── Logo + Title row ── */}
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
        </div>

        {/* ── Date bar ── */}
        <div className="w-full flex items-center justify-center px-4 py-1.5 bg-[#0D1B2A]">
          <span className="text-white/60 text-[11px] tracking-wide font-medium">
            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
        </div>

        {/* ── Red ticker bar ── */}
        <div className="w-full bg-[#CC1E1E] py-2 px-4 flex items-center gap-3">
          <span className="bg-white text-[#CC1E1E] text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full whitespace-nowrap">
            {t.latest}
          </span>
          <span className="text-white text-[12px] truncate">
            Welcome to RTI Express · {t.tickerText}
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
      <nav className="bg-[#0D1B2A] fixed bottom-0 w-full pb-safe flex justify-around items-center h-[70px] z-20">
        <Link to="/" className={`flex flex-col items-center gap-1 ${isActive('/') ? 'text-[#CC1E1E]' : 'text-white/40'}`}>
          <Home className="w-6 h-6" />
          <span className="text-[9px] font-bold uppercase tracking-wider">{t.home}</span>
        </Link>
        <Link to="/templates" className={`flex flex-col items-center gap-1 ${isActive('/templates') ? 'text-[#CC1E1E]' : 'text-white/40'}`}>
          <FileText className="w-6 h-6" />
          <span className="text-[9px] font-bold uppercase tracking-wider">{t.templates}</span>
        </Link>
        
        {/* Center FAB */}
        <Link to="/generate" className="relative -top-5 flex items-center justify-center w-[48px] h-[48px] bg-[#CC1E1E] rounded-full text-white shadow-[0_4px_12px_rgba(204,30,30,0.4)] active:scale-95 transition-transform z-50">
          <Plus className="w-[22px] h-[22px]" strokeWidth={2.5} />
        </Link>

        <Link to="/history" className={`flex flex-col items-center gap-1 ${isActive('/history') ? 'text-[#CC1E1E]' : 'text-white/40'}`}>
          <History className="w-6 h-6" />
          <span className="text-[9px] font-bold uppercase tracking-wider">{t.history}</span>
        </Link>
        <Link to="/settings" className={`flex flex-col items-center gap-1 ${isActive('/settings') ? 'text-[#CC1E1E]' : 'text-white/40'}`}>
          <Settings className="w-6 h-6" />
          <span className="text-[9px] font-bold uppercase tracking-wider">{t.settings}</span>
        </Link>
      </nav>
    </div>
  );
};

import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';

function App() {
  const [isInitializing, setIsInitializing] = useState(true);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const login = useAuthStore((state) => state.login);

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
            // Force reload to dashboard
            window.location.href = '/';
          }
        }
      }
    });

    // Also set up the global auth listener
    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        login(session.user as any, session.access_token);
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
          path="/signup" 
          element={!isAuthenticated ? <SignupScreen /> : <Navigate to="/" />} 
        />
        
        <Route 
          path="/*" 
          element={
            isAuthenticated ? (
              <MainLayout>
                <Routes>
                  <Route path="/" element={<DashboardScreen />} />
                  <Route path="/generate" element={<GenerateScreen />} />
                  <Route path="/templates" element={<TemplatesScreen />} />
                  <Route path="/history" element={<HistoryScreen />} />
                  <Route path="/settings" element={<SettingsScreen />} />
                  <Route path="/preview/:id" element={<PreviewScreen />} />
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
