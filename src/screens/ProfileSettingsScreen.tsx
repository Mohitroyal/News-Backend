import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Camera, Check, AlertCircle } from 'lucide-react';
import { useAuthStore, getReporterPhoto, saveReporterPhoto, getReporterName, saveReporterName } from '@/store';
import { supabase } from '@/lib/supabase';

export const ProfileSettingsScreen: React.FC = () => {
  const navigate = useNavigate();
  const { user, updateUser } = useAuthStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Derive initial values from auth user state and local persistence
  const currentEmail = user?.email || 'reporter@rtiexpress.com';
  const initialName =
    getReporterName(currentEmail) ||
    (user as any)?.user_metadata?.full_name ||
    (user as any)?.user_metadata?.name ||
    user?.full_name ||
    user?.firstName ||
    'Reporter';
  const initialPhoto =
    getReporterPhoto(currentEmail) ||
    user?.avatarUrl ||
    (user as any)?.user_metadata?.avatar_url ||
    (user as any)?.user_metadata?.picture ||
    '';

  const [name, setName] = useState(initialName);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [error, setError] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Active avatar image URL (local preview or existing photo)
  const activePhoto = photoPreview !== null ? photoPreview : initialPhoto;
  const initialLetter = (name.trim()[0] || 'R').toUpperCase();

  // Handle native image selection and crop to 1:1 circle preview
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const size = Math.min(img.width, img.height);
        const targetSize = 300;
        canvas.width = targetSize;
        canvas.height = targetSize;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          const offsetX = (img.width - size) / 2;
          const offsetY = (img.height - size) / 2;
          ctx.drawImage(img, offsetX, offsetY, size, size, 0, 0, targetSize, targetSize);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
          setPhotoPreview(dataUrl);
        }
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const handleSaveChanges = () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Reporter name is required');
      return;
    }

    setError('');

    const newPhotoUrl = photoPreview !== null ? photoPreview : initialPhoto;

    // 1. Persist name & photo to localStorage helpers
    saveReporterName(currentEmail, trimmedName);
    if (newPhotoUrl) {
      saveReporterPhoto(currentEmail, newPhotoUrl);
    }

    // 2. Sync to Supabase auth metadata if available
    supabase.auth.updateUser({
      data: {
        full_name: trimmedName,
        name: trimmedName,
        ...(newPhotoUrl ? { avatar_url: newPhotoUrl, picture: newPhotoUrl } : {}),
      },
    }).catch((err) => console.warn('[ProfileSettings] Supabase updateUser warning:', err));

    // 3. Update auth store so all screens (including identity card & masthead byline) update immediately
    const existingUserMetadata = (user as any)?.user_metadata || {};
    const updatedUserMetadata = {
      ...existingUserMetadata,
      full_name: trimmedName,
      name: trimmedName,
      ...(newPhotoUrl ? { avatar_url: newPhotoUrl, picture: newPhotoUrl } : {}),
    };

    updateUser({
      full_name: trimmedName,
      firstName: trimmedName,
      ...(newPhotoUrl ? { avatarUrl: newPhotoUrl } : {}),
      user_metadata: updatedUserMetadata,
    } as any);

    // 4. Show brief "Profile updated" confirmation and navigate back to Settings
    setToastMessage('Profile updated');
    setTimeout(() => {
      navigate('/settings');
    }, 900);
  };

  return (
    <div className="min-h-full bg-[#F3F6FB] flex flex-col font-sans">
      {/* ── Header ── */}
      <header className="bg-[#015BB3] px-4 py-3.5 flex items-center gap-3 text-white sticky top-0 z-20 shadow-md">
        <button
          type="button"
          onClick={() => navigate('/settings')}
          className="p-1 rounded-full text-white hover:bg-white/10 active:scale-95 transition-all"
          aria-label="Back to Settings"
        >
          <ChevronLeft className="w-6 h-6 text-white" />
        </button>
        <h1
          className="text-xl font-bold text-white tracking-wide"
          style={{ fontFamily: "'Georgia', serif" }}
        >
          Profile Settings
        </h1>
      </header>

      {/* ── Body ── */}
      <main className="flex-1 p-6 flex flex-col items-center max-w-md mx-auto w-full space-y-6">
        {/* Toast confirmation */}
        {toastMessage && (
          <div className="w-full bg-[#015BB3] text-white px-4 py-3 rounded-xl shadow-lg flex items-center justify-center gap-2 text-sm font-bold animate-fade-in">
            <Check className="w-4 h-4 text-green-400 shrink-0" />
            <span>{toastMessage}</span>
          </div>
        )}

        {/* Avatar & Change photo link */}
        <div className="flex flex-col items-center">
          <div className="w-[88px] h-[88px] rounded-full bg-[#015BB3] border-[3px] border-[#145AB1] flex items-center justify-center overflow-hidden shadow-md shrink-0">
            {activePhoto ? (
              <img
                src={activePhoto}
                alt="Reporter Avatar"
                className="w-full h-full object-cover rounded-full"
              />
            ) : (
              <span className="text-white text-3xl font-bold font-serif">{initialLetter}</span>
            )}
          </div>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="text-[#145AB1] font-bold text-sm hover:underline cursor-pointer flex items-center gap-1.5 mt-3 active:scale-95 transition-transform"
          >
            <Camera className="w-4 h-4 text-[#145AB1]" />
            <span>Change photo</span>
          </button>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handlePhotoSelect}
            accept="image/*"
            className="hidden"
          />
        </div>

        {/* Inputs section */}
        <div className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-5 space-y-5 shadow-sm">
          {/* Reporter Name input */}
          <div>
            <label className="block text-xs font-bold text-[#0A2540] uppercase tracking-wider mb-1.5">
              Reporter Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError('');
              }}
              className={`w-full bg-white text-[#0A2540] border ${
                error
                  ? 'border-red-500 ring-2 ring-red-200'
                  : 'border-[#D0E2F7] focus:border-[#145AB1] focus:ring-2 focus:ring-[#145AB1]/20'
              } rounded-xl px-4 py-3 text-sm font-medium focus:outline-none transition-all shadow-sm`}
              placeholder="Enter reporter name"
            />
            {error && (
              <p className="text-xs text-red-600 font-bold mt-1.5 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{error}</span>
              </p>
            )}
          </div>

          {/* Email input (Disabled) */}
          <div>
            <label className="block text-xs font-bold text-[#0A2540] uppercase tracking-wider mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={currentEmail}
              disabled
              readOnly
              className="w-full bg-[#F3F6FB] text-[#6B7A90] border border-[#D0E2F7] rounded-xl px-4 py-3 text-sm font-medium cursor-not-allowed select-none shadow-inner"
            />
          </div>
        </div>

        {/* Spacer to push button downwards on tall screens */}
        <div className="flex-1 min-h-[20px]" />

        {/* Save changes button */}
        <div className="w-full pt-2">
          <button
            type="button"
            onClick={handleSaveChanges}
            className="w-full bg-[#145AB1] hover:bg-[#015BB3] active:scale-[0.99] text-white font-bold text-base py-3.5 rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>Save changes</span>
          </button>
        </div>
      </main>
    </div>
  );
};
