import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { Home, FileText, Settings, History, Plus } from 'lucide-react';
import { SplashScreen } from './screens/SplashScreen';
import { LoginScreen } from './screens/LoginScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { GenerateScreen } from './screens/GenerateScreen';
import { TemplatesScreen } from './screens/TemplatesScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { PreviewScreen } from './screens/PreviewScreen';
import { useAuthStore, useUIStore } from './store';
import { supabase } from './lib/supabase';
import { App as CapacitorApp } from '@capacitor/app';
import { Browser } from '@capacitor/browser';

import { ErrorBoundary } from './ErrorBoundary';

// Mobile Layout with Bottom Navigation
const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-300 relative">
      {/* Header */}
      <header className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md px-6 py-4 pt-safe z-10 flex justify-between items-center sticky top-0 border-b border-gray-100 dark:border-gray-800 transition-colors duration-300">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">NewsCraft</h1>
      </header>

      {/* Main Content Area (Scrollable) */}
      <main className="flex-1 overflow-y-auto" style={{ paddingBottom: 'calc(7rem + env(safe-area-inset-bottom))' }}>
        <ErrorBoundary>
          {children}
        </ErrorBoundary>
      </main>

      {/* Bottom Navigation */}
      <nav className="bg-white/90 dark:bg-gray-900/90 backdrop-blur-lg border-t border-gray-200 dark:border-gray-800 fixed bottom-0 w-full pb-safe flex justify-around items-center h-20 h-nav-safe z-20 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.05)] transition-colors duration-300">
        <Link to="/" className={`flex flex-col items-center gap-1 ${isActive('/') ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-400'}`}>
          <Home className={`w-6 h-6 ${isActive('/') ? 'fill-blue-100 dark:fill-blue-900/50' : ''}`} />
          <span className="text-[10px] font-medium">Home</span>
        </Link>
        <Link to="/templates" className={`flex flex-col items-center gap-1 ${isActive('/templates') ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 dark:text-gray-400'}`}>
          <FileText className={`w-6 h-6 ${isActive('/templates') ? 'fill-indigo-100 dark:fill-indigo-900/50' : ''}`} />
          <span className="text-[10px] font-medium">Templates</span>
        </Link>
        
        {/* FAB Style Center Button */}
        <Link to="/generate" className="relative -top-5 flex flex-col items-center justify-center w-14 h-14 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-full text-white shadow-lg shadow-blue-500/40 active:scale-95 transition-transform">
          <Plus className="w-8 h-8" />
        </Link>

        <Link to="/history" className={`flex flex-col items-center gap-1 ${isActive('/history') ? 'text-orange-600 dark:text-orange-400' : 'text-gray-400 dark:text-gray-400'}`}>
          <History className={`w-6 h-6 ${isActive('/history') ? 'fill-orange-100 dark:fill-orange-900/50' : ''}`} />
          <span className="text-[10px] font-medium">History</span>
        </Link>
        <Link to="/settings" className={`flex flex-col items-center gap-1 ${isActive('/settings') ? 'text-gray-900 dark:text-white' : 'text-gray-400 dark:text-gray-400'}`}>
          <Settings className={`w-6 h-6 ${isActive('/settings') ? 'fill-gray-200 dark:fill-gray-700' : ''}`} />
          <span className="text-[10px] font-medium">Settings</span>
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
  const theme = useUIStore((state) => state.theme);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

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
