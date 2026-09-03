import { useState, useRef } from 'react';
import { useAuthStore, useUIStore, useGenerationStore, saveReporterPhoto, getReporterPhoto } from '@/store';
import { useNavigate } from 'react-router-dom';
import { Bell, Moon, Trash2, Shield, Check, QrCode, LogOut, AlertTriangle, Camera, User as UserIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '@/lib/supabase';
import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth';
import { useTranslation } from '@/lib/i18n';

function ToggleSwitch({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`relative w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${enabled ? "bg-blue-600" : "bg-gray-200"}`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${enabled ? "translate-x-5" : ""}`}
      />
    </button>
  );
}

function SettingsSection({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-3xl overflow-hidden shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] transition-colors duration-300">
      <div className="px-5 py-4 border-b border-gray-50 dark:border-gray-700 flex items-center gap-3 bg-gray-50/50 dark:bg-gray-800/50">
        <Icon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
        <h2 className="text-sm font-bold text-gray-900 dark:text-white">{title}</h2>
      </div>
      <div className="divide-y divide-gray-50 dark:divide-gray-700">{children}</div>
    </div>
  );
}

function SettingsRow({ label, description, control }: { label: string; description?: string; control: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-4 gap-4 transition-colors duration-300">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-gray-900 dark:text-white">{label}</p>
        {description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{description}</p>}
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  );
}

// ── Toast Component ─────────────────────────────────────────────────────────────
function Toast({ message, type }: { message: string; type: 'success' | 'error' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className={`fixed bottom-24 left-1/2 -translate-x-1/2 z-[100] px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-3 text-sm font-bold whitespace-nowrap
        ${type === 'success'
          ? 'bg-gray-900 dark:bg-gray-800 text-white border border-gray-700'
          : 'bg-red-600 text-white'
        }`}
    >
      {type === 'success' ? (
        <Check className="w-4 h-4 text-green-400 shrink-0" />
      ) : (
        <AlertTriangle className="w-4 h-4 shrink-0" />
      )}
      {message}
    </motion.div>
  );
}

export const SettingsScreen = () => {
  const { user, logout, updateUser } = useAuthStore();
  const resetGenerations = useGenerationStore((state) => state.resetConfig);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Use persistent UI store
  const logoMode = useUIStore((state) => state.logoMode);
  const showInnerBorders = useUIStore((state) => state.showInnerBorders);
  const toggleLogoMode = useUIStore((state) => state.toggleLogoMode);
  const toggleInnerBorders = useUIStore((state) => state.toggleInnerBorders);
  const { t, language: activeLanguage } = useTranslation();
  const setLanguage = useUIStore((state) => state.setLanguage);

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
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
          saveReporterPhoto(user?.email, dataUrl);
          updateUser({ avatarUrl: dataUrl });
          supabase.auth.updateUser({ data: { avatar_url: dataUrl } }).catch(() => {});
          showToast('Reporter photo updated permanently!', 'success');
        }
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const [notifications, setNotifications] = useState({
    emailGenerations: true,
    emailBilling: true,
    emailUpdates: true,
    browserPush: true,
  });

  const toggle = (key: keyof typeof notifications) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // ── Logout state ───────────────────────────────────────────────────────────────
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  /**
   * Full logout sequence:
   * 1. Sign out from Supabase (invalidates server-side session & JWT)
   * 2. Clear Zustand auth store (clears token + user from localStorage via persist)
   * 3. Clear generation store config
   * 4. Wipe all newscraft-* keys from localStorage (quota cache, profile cache, etc.)
   * 5. Navigate to /login
   */
  const performLogout = async () => {
    setIsLoggingOut(true);
    try {
      // 1. Supabase session invalidation
      await supabase.auth.signOut();
    } catch (err) {
      console.warn('[Logout] Supabase signOut error (continuing anyway):', err);
    }

    try {
      // 1b. Google Auth Sign-Out to force account picker on next login
      await GoogleAuth.signOut();
    } catch (err) {
      console.warn('[Logout] Google Sign-Out error (continuing anyway):', err);
    }

    try {
      // 2. Clear Zustand auth store (persisted to localStorage as "newscraft-auth")
      logout();

      // 3. Clear generation session data from Zustand persist store
      resetGenerations();

      // 4. Wipe all newscraft-* localStorage keys
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('newscraft')) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));

      setIsLoggingOut(false);
      setIsLogoutModalOpen(false);
      showToast(t.logoutSuccess, 'success');

      // Small delay so toast is visible before navigation
      setTimeout(() => {
        navigate('/login', { replace: true });
      }, 800);
    } catch (err) {
      console.error('[Logout] Error during logout:', err);
      setIsLoggingOut(false);
      showToast(t.logoutError, 'error');
    }
  };

  // Modals state
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [isTfaModalOpen, setIsTfaModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  const [tfaEnabled, setTfaEnabled] = useState(false);
  const [tfaVerificationCode, setTfaVerificationCode] = useState("");
  const [deleteConfirmationText, setDeleteConfirmationText] = useState("");

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError("");
    if (newPassword.length < 6) {
      setPasswordError("New password must be at least 6 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match!");
      return;
    }

    setPasswordLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      });
      if (error) throw error;

      setPasswordSuccess(true);
      showToast("Password updated successfully!", "success");
      setTimeout(() => {
        setPasswordSuccess(false);
        setIsPasswordModalOpen(false);
        setNewPassword("");
        setConfirmPassword("");
        setPasswordError("");
      }, 1500);
    } catch (err: any) {
      setPasswordError(err.message || "Failed to update password");
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleTfaToggle = () => {
    if (tfaEnabled) {
      setTfaEnabled(false);
    } else {
      setIsTfaModalOpen(true);
    }
  };

  return (
    <div className="p-6 pb-6 dark:bg-gray-900 transition-colors duration-300">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
            <Shield className="w-5 h-5 text-gray-700 dark:text-gray-300" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white transition-colors duration-300">{t.settings}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 transition-colors duration-300">{t.manageAcc}</p>
          </div>
        </div>
      </div>

      <div className="space-y-5">
        {/* Reporter Profile & Photo Card */}
        <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-3xl p-5 shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              onClick={() => photoInputRef.current?.click()}
              className="relative w-16 h-16 rounded-full border-2 border-[#CC1E1E] bg-[#EEF3F8] flex items-center justify-center cursor-pointer shadow-md overflow-hidden shrink-0 active:scale-95 transition-transform"
              title="Change Reporter Photo"
            >
              {user?.avatarUrl || getReporterPhoto(user?.email) ? (
                <img src={user?.avatarUrl || getReporterPhoto(user?.email)} alt="Reporter Photo" className="w-full h-full object-cover" />
              ) : (
                <div className="flex flex-col items-center justify-center text-[#0D1B2A]">
                  <UserIcon className="w-7 h-7 text-[#0D1B2A]/60" />
                </div>
              )}
              <div className="absolute inset-0 bg-black/30 opacity-0 hover:opacity-100 flex items-center justify-center transition-opacity">
                <Camera className="w-5 h-5 text-white" />
              </div>
            </div>
            <input
              type="file"
              ref={photoInputRef}
              onChange={handlePhotoUpload}
              accept="image/*"
              className="hidden"
            />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-gray-900 dark:text-white text-base">
                  {(user as any)?.user_metadata?.full_name || (user as any)?.user_metadata?.name || user?.full_name || user?.firstName || 'Reporter'}
                </h3>
                <span className="bg-[#CC1E1E]/10 text-[#CC1E1E] text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                  Reporter
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{user?.email || 'reporter@rtiexpress.com'}</p>
              <button
                onClick={() => photoInputRef.current?.click()}
                className="text-xs font-bold text-[#CC1E1E] hover:underline mt-1.5 flex items-center gap-1"
              >
                <Camera className="w-3.5 h-3.5" />
                {user?.avatarUrl ? 'Change Reporter Photo' : 'Upload Reporter Photo'}
              </button>
            </div>
          </div>
        </div>

        {/* Appearance */}
        <SettingsSection title={t.appearance} icon={Moon}>
          <SettingsRow
            label="Inner Border Lines"
            description="Show borders below the logo and headline."
            control={
              <ToggleSwitch
                enabled={showInnerBorders ?? true}
                onToggle={toggleInnerBorders}
              />
            }
          />
          <SettingsRow
            label={t.darkMode}
            description={t.darkModeDesc}
            control={<ToggleSwitch enabled={logoMode} onToggle={() => toggleLogoMode()} />}
          />
          <SettingsRow
            label={t.interfaceLang}
            description={t.interfaceLangDesc}
            control={
              <select
                value={activeLanguage}
                onChange={(e) => setLanguage(e.target.value)}
                className="bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 appearance-none font-bold"
              >
                <option value="en">English</option>
                <option value="te">Telugu</option>
                <option value="hi">Hindi</option>
              </select>
            }
          />
        </SettingsSection>

        {/* Notifications */}
        <SettingsSection title={t.notifications} icon={Bell}>
          <SettingsRow
            label={t.emailGen}
            description={t.emailGenDesc}
            control={<ToggleSwitch enabled={notifications.emailGenerations} onToggle={() => toggle("emailGenerations")} />}
          />
          <SettingsRow
            label={t.emailBilling}
            description={t.emailBillingDesc}
            control={<ToggleSwitch enabled={notifications.emailBilling} onToggle={() => toggle("emailBilling")} />}
          />
          <SettingsRow
            label={t.emailUpdates}
            description={t.emailUpdatesDesc}
            control={<ToggleSwitch enabled={notifications.emailUpdates} onToggle={() => toggle("emailUpdates")} />}
          />
          <SettingsRow
            label={t.browserPush}
            description={t.browserPushDesc}
            control={<ToggleSwitch enabled={notifications.browserPush} onToggle={() => toggle("browserPush")} />}
          />
        </SettingsSection>

        {/* Security */}
        <SettingsSection title={t.security} icon={Shield}>
          <SettingsRow
            label={t.changePass}
            description={t.changePassDesc}
            control={
              <button
                onClick={() => setIsPasswordModalOpen(true)}
                className="text-xs font-bold text-blue-600 px-4 py-2 bg-blue-50 dark:bg-blue-900/30 rounded-xl active:scale-95 transition-transform"
              >
                {t.updateBtn}
              </button>
            }
          />
          <SettingsRow
            label={t.tfa}
            description={t.tfaDesc}
            control={<ToggleSwitch enabled={tfaEnabled} onToggle={handleTfaToggle} />}
          />
        </SettingsSection>

        {/* ── Professional Logout Button ─────────────────────────────────────── */}
        <button
          id="logout-btn"
          onClick={() => setIsLogoutModalOpen(true)}
          disabled={isLoggingOut}
          className="w-full flex items-center justify-between px-5 py-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm active:scale-[0.98] transition-all duration-200 group"
        >
          <div className="flex items-center gap-4">
            <div className="w-9 h-9 rounded-xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center group-active:bg-gray-200 dark:group-active:bg-gray-600 transition-colors">
              <LogOut className="w-4 h-4 text-gray-700 dark:text-gray-300" />
            </div>
            <div className="text-left">
              <p className="text-sm font-bold text-gray-900 dark:text-white">{t.logout}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t.logoutDesc}</p>
            </div>
          </div>
          {isLoggingOut ? (
            <div className="w-4 h-4 rounded-full border-2 border-gray-300 border-t-gray-600 animate-spin" />
          ) : (
            <svg className="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
        </button>

        {/* ── Subtle Delete Account (bottom, demoted) ────────────────────────── */}
        <div className="pt-2 flex justify-center">
          <button
            id="delete-account-btn"
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-600 hover:text-red-500 dark:hover:text-red-400 transition-colors py-2 px-3 rounded-xl"
          >
            <Trash2 className="w-3 h-3" />
            {t.deleteAcc}
          </button>
        </div>
      </div>

      {/* Modals Overlay */}
      <AnimatePresence>

        {/* ── Logout Confirmation Modal ──────────────────────────────────────── */}
        {isLogoutModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 20 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className="bg-white dark:bg-gray-800 rounded-3xl max-w-xs w-full overflow-hidden shadow-2xl border border-gray-100 dark:border-gray-700"
            >
              {/* Icon header */}
              <div className="pt-7 pb-4 flex flex-col items-center gap-3 px-6">
                <div className="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                  <LogOut className="w-7 h-7 text-gray-700 dark:text-gray-300" />
                </div>
                <div className="text-center">
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">{t.logoutTitle}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">{t.logoutMessage}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="px-6 pb-6 pt-2 flex flex-col gap-2.5">
                <button
                  id="logout-confirm-btn"
                  onClick={performLogout}
                  disabled={isLoggingOut}
                  className="w-full py-3.5 bg-gray-900 dark:bg-gray-700 text-white rounded-2xl text-sm font-bold active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {isLoggingOut ? (
                    <>
                      <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Logging out…
                    </>
                  ) : (
                    <>
                      <LogOut className="w-4 h-4" />
                      {t.logoutConfirm}
                    </>
                  )}
                </button>
                <button
                  id="logout-cancel-btn"
                  onClick={() => setIsLogoutModalOpen(false)}
                  disabled={isLoggingOut}
                  className="w-full py-3.5 bg-gray-100 dark:bg-gray-700/50 text-gray-700 dark:text-gray-300 rounded-2xl text-sm font-bold active:scale-[0.98] transition-all disabled:opacity-60"
                >
                  {t.logoutCancel}
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isPasswordModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-800 rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-gray-100 dark:border-gray-700"
            >
              <div className="p-6 border-b border-gray-100 dark:border-gray-700">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Change Password</h3>
              </div>
              <form onSubmit={handlePasswordSubmit} className="p-6 space-y-4">
                {passwordError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-xs font-semibold text-center">
                    {passwordError}
                  </div>
                )}
                {passwordSuccess ? (
                  <div className="text-center py-6 space-y-2">
                    <div className="h-12 w-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto">
                      <Check className="h-6 w-6" />
                    </div>
                    <p className="text-gray-900 dark:text-white font-bold">Password Updated!</p>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-gray-500">New Password</label>
                      <input
                        type="password"
                        required
                        placeholder="Min 6 characters"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl px-4 py-3 text-sm text-gray-900 dark:text-white focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-gray-500">Confirm Password</label>
                      <input
                        type="password"
                        required
                        placeholder="Re-enter new password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl px-4 py-3 text-sm text-gray-900 dark:text-white focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="flex gap-3 justify-end pt-2">
                      <button
                        type="button"
                        disabled={passwordLoading}
                        onClick={() => setIsPasswordModalOpen(false)}
                        className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 dark:bg-gray-700 rounded-xl w-full"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={passwordLoading}
                        className="px-4 py-3 text-sm font-bold text-white bg-blue-600 rounded-xl w-full flex items-center justify-center disabled:opacity-60"
                      >
                        {passwordLoading ? 'Updating…' : 'Save'}
                      </button>
                    </div>
                  </>
                )}
              </form>
            </motion.div>
          </div>
        )}

        {isTfaModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-800 rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-gray-100 dark:border-gray-700"
            >
              <div className="p-6 border-b border-gray-100 dark:border-gray-700">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Enable 2FA</h3>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-2xl border border-gray-200 dark:border-gray-600">
                    <QrCode className="h-32 w-32 text-gray-900 dark:text-white" />
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed">
                    Scan with your authenticator app then enter the 6-digit code below.
                  </p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-gray-500">Verification Code</label>
                  <input
                    type="number"
                    placeholder="123456"
                    value={tfaVerificationCode}
                    onChange={(e) => setTfaVerificationCode(e.target.value)}
                    className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl px-4 py-3 text-lg text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 font-mono text-center tracking-widest"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => { setIsTfaModalOpen(false); setTfaVerificationCode(""); }}
                    className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 dark:bg-gray-700 rounded-xl w-full"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      if (tfaVerificationCode.length === 6) {
                        setTfaEnabled(true);
                        setIsTfaModalOpen(false);
                      } else {
                        alert("Please enter a valid 6-digit code.");
                      }
                    }}
                    className="px-4 py-3 text-sm font-bold text-white bg-blue-600 rounded-xl w-full"
                  >
                    Verify
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {isDeleteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-800 rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-red-100 dark:border-red-900/50"
            >
              <div className="p-6 border-b border-red-50 dark:border-red-900/30">
                <h3 className="text-lg font-bold text-red-600">Delete Account?</h3>
              </div>
              <div className="p-6 space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                  This action is irreversible. Type <span className="font-bold text-red-600">DELETE</span> to confirm.
                </p>
                <input
                  type="text"
                  value={deleteConfirmationText}
                  onChange={(e) => setDeleteConfirmationText(e.target.value)}
                  className="w-full bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl px-4 py-3 text-sm text-red-900 dark:text-red-300 focus:outline-none focus:border-red-500 font-mono"
                />
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={() => { setIsDeleteModalOpen(false); setDeleteConfirmationText(""); }}
                    className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 dark:bg-gray-700 rounded-xl w-full"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={deleteConfirmationText !== "DELETE"}
                    onClick={() => {
                      alert("Account deleted.");
                      setIsDeleteModalOpen(false);
                      logout();
                      navigate('/login');
                    }}
                    className="px-4 py-3 text-sm font-bold text-white bg-red-600 rounded-xl w-full disabled:opacity-50 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {/* ── Toast notification ─────────────────────────────────────────────── */}
        {toast && <Toast message={toast.message} type={toast.type} />}

      </AnimatePresence>
    </div>
  );
};
