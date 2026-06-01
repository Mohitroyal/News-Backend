import { useState, useEffect } from 'react';
import { useAuthStore, useUIStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { Bell, Moon, Trash2, Shield, Check, QrCode } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const translations = {
  en: {
    settings: "Settings",
    manageAcc: "Manage your account preferences",
    appearance: "Appearance",
    darkMode: "Dark Mode",
    darkModeDesc: "Use the dark theme across the application",
    interfaceLang: "Interface Language",
    interfaceLangDesc: "Language used for UI labels and prompts",
    notifications: "Notifications",
    emailGen: "Email — Generation Complete",
    emailGenDesc: "Get notified when your newspaper is ready",
    emailBilling: "Email — Billing Alerts",
    emailBillingDesc: "Invoices and payment confirmations",
    emailUpdates: "Email — Product Updates",
    emailUpdatesDesc: "New features and announcements",
    browserPush: "Device Push Notifications",
    browserPushDesc: "Real-time alerts on your device",
    security: "Security",
    changePass: "Change Password",
    changePassDesc: "Update your account password",
    updateBtn: "Update",
    tfa: "Two-Factor Authentication",
    tfaDesc: "Add an extra layer of security",
    dangerZone: "Danger Zone",
    deleteAcc: "Delete Account",
    deleteAccDesc: "Permanently delete your account and all associated data. This cannot be undone.",
    logout: "Log Out"
  },
  te: {
    settings: "సెట్టింగ్‌లు",
    manageAcc: "మీ ఖాతా ప్రాధాన్యతలను నిర్వహించండి",
    appearance: "స్వరూపం",
    darkMode: "డార్క్ మోడ్",
    darkModeDesc: "అప్లికేషన్ అంతటా డార్క్ థీమ్‌ను ఉపయోగించండి",
    interfaceLang: "ఇంటర్‌ఫేస్ భాష",
    interfaceLangDesc: "UI లేబుల్స్ మరియు ప్రాంప్ట్‌ల కోసం ఉపయోగించే భాష",
    notifications: "నోటిఫికేషన్‌లు",
    emailGen: "ఇమెయిల్ — జనరేషన్ పూర్తయింది",
    emailGenDesc: "మీ వార్తాపత్రిక సిద్ధమైనప్పుడు తెలియజేయండి",
    emailBilling: "ఇమెయిల్ — బిల్లింగ్ హెచ్చరికలు",
    emailBillingDesc: "ఇన్‌వాయిస్‌లు మరియు చెల్లింపు నిర్ధారణలు",
    emailUpdates: "ఇమెయిల్ — ఉత్పత్తి నవీకరణలు",
    emailUpdatesDesc: "కొత్త ఫీచర్లు మరియు ప్రకటనలు",
    browserPush: "పరికర పుష్ నోటిఫికేషన్‌లు",
    browserPushDesc: "మీ పరికరంలో రియల్-టైమ్ హెచ్చరికలు",
    security: "భద్రత",
    changePass: "పాస్వర్డ్ మార్చండి",
    changePassDesc: "మీ ఖాతా పాస్‌వర్డ్‌ను నవీకరించండి",
    updateBtn: "నవీకరించండి",
    tfa: "టూ-ఫాక్టర్ అథెంటికేషన్",
    tfaDesc: "భద్రత యొక్క అదనపు పొరను జోడించండి",
    dangerZone: "డేంజర్ జోన్",
    deleteAcc: "ఖాతాను తొలగించండి",
    deleteAccDesc: "మీ ఖాతా మరియు డేటాను శాశ్వతంగా తొలగించండి.",
    logout: "లాగ్ అవుట్"
  },
  hi: {
    settings: "सेटिंग्स",
    manageAcc: "अपनी खाता प्राथमिकताएं प्रबंधित करें",
    appearance: "दिखावट",
    darkMode: "डार्क मोड",
    darkModeDesc: "एप्लिकेशन में डार्क थीम का उपयोग करें",
    interfaceLang: "इंटरफ़ेस भाषा",
    interfaceLangDesc: "UI लेबल और प्रॉम्प्ट के लिए उपयोग की जाने वाली भाषा",
    notifications: "सूचनाएं",
    emailGen: "ईमेल - निर्माण पूर्ण",
    emailGenDesc: "जब आपका अखबार तैयार हो जाए तो सूचना प्राप्त करें",
    emailBilling: "ईमेल - बिलिंग अलर्ट",
    emailBillingDesc: "चालान और भुगतान की पुष्टि",
    emailUpdates: "ईमेल - उत्पाद अपडेट",
    emailUpdatesDesc: "नई सुविधाएँ और घोषणाएँ",
    browserPush: "डिवाइस पुश सूचनाएँ",
    browserPushDesc: "आपके डिवाइस पर वास्तविक समय अलर्ट",
    security: "सुरक्षा",
    changePass: "पासवर्ड बदलें",
    changePassDesc: "अपना खाता पासवर्ड अपडेट करें",
    updateBtn: "अपडेट करें",
    tfa: "दो-कारक प्रमाणीकरण",
    tfaDesc: "सुरक्षा की एक अतिरिक्त परत जोड़ें",
    dangerZone: "डेंजर जोन",
    deleteAcc: "खाता हटाएं",
    deleteAccDesc: "अपना खाता और डेटा स्थायी रूप से हटाएं।",
    logout: "लॉग आउट"
  }
};

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

export const SettingsScreen = () => {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  // Use persistent UI store
  const theme = useUIStore((state) => state.theme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);
  const language = useUIStore((state) => state.language);
  const setLanguage = useUIStore((state) => state.setLanguage);
  
  const activeLanguage = language;
  const t = translations[activeLanguage as keyof typeof translations] || translations.en;

  useEffect(() => {
    // Theme effect moved to App.tsx
  }, [theme]);

  const [notifications, setNotifications] = useState({
    emailGenerations: true,
    emailBilling: true,
    emailUpdates: true,
    browserPush: true,
  });

  const toggle = (key: keyof typeof notifications) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Modals state
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [isTfaModalOpen, setIsTfaModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const [tfaEnabled, setTfaEnabled] = useState(false);
  const [tfaVerificationCode, setTfaVerificationCode] = useState("");
  const [deleteConfirmationText, setDeleteConfirmationText] = useState("");

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      alert("New passwords do not match!");
      return;
    }
    setPasswordSuccess(true);
    setTimeout(() => {
      setPasswordSuccess(false);
      setIsPasswordModalOpen(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    }, 1500);
  };

  const handleTfaToggle = () => {
    if (tfaEnabled) {
      setTfaEnabled(false);
    } else {
      setIsTfaModalOpen(true);
    }
  };

  return (
    <div className="p-6 pb-24 h-full dark:bg-gray-900 transition-colors duration-300">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gray-200 flex items-center justify-center">
            <Shield className="w-5 h-5 text-gray-700" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white transition-colors duration-300">{t.settings}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 transition-colors duration-300">{t.manageAcc}</p>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Appearance */}
        <SettingsSection title={t.appearance} icon={Moon}>
          <SettingsRow
            label={t.darkMode}
            description={t.darkModeDesc}
            control={<ToggleSwitch enabled={theme === "dark"} onToggle={() => toggleTheme()} />}
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
                className="text-xs font-bold text-blue-600 px-4 py-2 bg-blue-50 rounded-xl active:scale-95 transition-transform"
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

        {/* Danger Zone */}
        <div className="bg-red-50 border border-red-100 rounded-3xl overflow-hidden shadow-[0_4px_20px_-10px_rgba(255,0,0,0.1)]">
          <div className="px-5 py-4 border-b border-red-100 flex items-center gap-3">
            <Trash2 className="h-4 w-4 text-red-600" />
            <h2 className="text-sm font-bold text-red-600">{t.dangerZone}</h2>
          </div>
          <div className="px-5 py-5 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-gray-900">{t.deleteAcc}</p>
              <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{t.deleteAccDesc}</p>
            </div>
            <button
              onClick={() => setIsDeleteModalOpen(true)}
              className="shrink-0 text-xs font-bold text-white bg-red-600 px-4 py-2 rounded-xl active:scale-95 transition-transform"
            >
              {t.deleteAcc}
            </button>
          </div>
        </div>

        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className="w-full py-4 bg-gray-900 text-white rounded-2xl font-bold active:scale-[0.98] transition-all"
        >
          {t.logout}
        </button>
      </div>

      {/* Modals Overlay */}
      <AnimatePresence>
        {isPasswordModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-gray-100"
            >
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-bold text-gray-900">Change Password</h3>
              </div>
              <form onSubmit={handlePasswordSubmit} className="p-6 space-y-4">
                {passwordSuccess ? (
                  <div className="text-center py-6 space-y-2">
                    <div className="h-12 w-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto">
                      <Check className="h-6 w-6" />
                    </div>
                    <p className="text-gray-900 font-bold">Password Updated!</p>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-gray-500">Current Password</label>
                      <input
                        type="password"
                        required
                        value={oldPassword}
                        onChange={(e) => setOldPassword(e.target.value)}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-gray-500">New Password</label>
                      <input
                        type="password"
                        required
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-gray-500">Confirm Password</label>
                      <input
                        type="password"
                        required
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-900 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="flex gap-3 justify-end pt-2">
                      <button
                        type="button"
                        onClick={() => setIsPasswordModalOpen(false)}
                        className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 rounded-xl w-full"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-3 text-sm font-bold text-white bg-blue-600 rounded-xl w-full"
                      >
                        Save
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
              className="bg-white rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-gray-100"
            >
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-bold text-gray-900">Enable 2FA</h3>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="bg-gray-50 p-4 rounded-2xl border border-gray-200">
                    <QrCode className="h-32 w-32 text-gray-900" />
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
                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-lg text-gray-900 focus:outline-none focus:border-blue-500 font-mono text-center tracking-widest"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => { setIsTfaModalOpen(false); setTfaVerificationCode(""); }}
                    className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 rounded-xl w-full"
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
              className="bg-white rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl border border-red-100"
            >
              <div className="p-6 border-b border-red-50">
                <h3 className="text-lg font-bold text-red-600">Delete Account?</h3>
              </div>
              <div className="p-6 space-y-4">
                <p className="text-sm text-gray-600 leading-relaxed">
                  This action is irreversible. Type <span className="font-bold text-red-600">DELETE</span> to confirm.
                </p>
                <input
                  type="text"
                  value={deleteConfirmationText}
                  onChange={(e) => setDeleteConfirmationText(e.target.value)}
                  className="w-full bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-900 focus:outline-none focus:border-red-500 font-mono"
                />
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={() => { setIsDeleteModalOpen(false); setDeleteConfirmationText(""); }}
                    className="px-4 py-3 text-sm font-bold text-gray-500 bg-gray-100 rounded-xl w-full"
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
      </AnimatePresence>
    </div>
  );
};
