import { BrowserRouter, Routes, Route, Outlet, useLocation } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { DashboardScreen } from '../screens/DashboardScreen';
import { TemplatesScreen } from '../screens/TemplatesScreen';
import { TemplateCategoryScreen } from '../screens/TemplateCategoryScreen';
import { GenerateScreen } from '../screens/GenerateScreen';
import { PreviewScreen } from '../screens/PreviewScreen';
import { HistoryScreen } from '../screens/HistoryScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { LogoSelectionScreen } from '../screens/LogoSelectionScreen';
import { LoginScreen } from '../screens/LoginScreen';
import { SignupScreen } from '../screens/SignupScreen';
import { CreatePasswordScreen } from '../screens/CreatePasswordScreen';

const Layout = () => {
  const location = useLocation();
  const hideNavbar = location.pathname.includes('/preview'); // Hide navbar on preview if desired, or keep it.
  
  return (
    <div className="flex flex-col h-screen w-full bg-light-blue overflow-hidden">
      <div className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </div>
      {!hideNavbar && <Navbar />}
    </div>
  );
};

export const AppNavigator = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginScreen />} />
        <Route path="/signup" element={<SignupScreen />} />
        <Route path="/create-password" element={<CreatePasswordScreen />} />
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardScreen />} />
          <Route path="/home" element={<DashboardScreen />} />
          <Route path="/templates" element={<TemplatesScreen />} />
          <Route path="/templates/:categoryId" element={<TemplateCategoryScreen />} />
          <Route path="/generate" element={<GenerateScreen />} />
          <Route path="/history" element={<HistoryScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="/preview/:id" element={<PreviewScreen />} />
          <Route path="/logo-selection" element={<LogoSelectionScreen />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};
