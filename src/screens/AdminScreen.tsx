import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users, BarChart3, Image as ImageIcon, Shield, LogOut,
  Plus, Trash2, Eye, EyeOff, RefreshCw, X, Check,
  AlertTriangle, TrendingUp, Newspaper, Activity, Crown,
  ChevronDown, ChevronUp, Search, ArrowLeft, Ban,
  Calendar, FileText, ExternalLink,
  UploadCloud, Edit2, CheckCircle2
} from 'lucide-react';
import { useAuthStore, isAdminUser, isSuperAdminUser } from '@/store';
import { supabase } from '@/lib/supabase';
import {
  getAdminStats, getAdminUsers, getPublicationLogos,
  addPublicationLogo, updatePublicationLogo, uploadLogoImage,
  removePublicationLogo, toggleLogoActive,
  updateUserRole, updateUserPlan, banUser, deleteUser,
  getAdminClippings,
  type AdminStats, type AdminUserProfile, type PublicationLogo, type AdminClippingLog
} from '@/services/admin.service';
import mastheadLogo from '../assets/rti_express_logo.png';

function fmt(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function timeAgo(dateStr?: string) {
  if (!dateStr) return 'Never';
  const d = new Date(dateStr);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatDateTime(dateStr?: string) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

function getTodayStr() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getYesterdayStr() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getDaysAgoStr(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color, bg }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string; bg: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-2xl p-4 border border-[#D0E2F7] shadow-sm flex flex-col justify-between"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: bg }}>
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase" style={{ background: bg, color }}>
          Live
        </span>
      </div>
      <div>
        <p className="text-[#0A2540] text-2xl font-black tracking-tight">{fmt(Number(value))}</p>
        <p className="text-[#6B7A90] text-xs font-bold uppercase tracking-wider mt-1">{label}</p>
        {sub && <p className="text-[#8FA3B8] text-[11px] mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  );
}

function PlanBadge({ plan }: { plan: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    admin:      { label: 'ADMIN',      color: '#B45309', bg: '#FEF3C7' },
    pro:        { label: 'PRO',        color: '#4338CA', bg: '#EEF2FF' },
    enterprise: { label: 'ENTERPRISE', color: '#047857', bg: '#ECFDF5' },
    free:       { label: 'FREE',       color: '#475569', bg: '#F1F5F9' },
    reporter:   { label: 'REPORTER',   color: '#0369A1', bg: '#E0F2FE' },
  };
  const s = map[plan?.toLowerCase()] ?? map.free;
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider border border-current/20"
      style={{ color: s.color, background: s.bg }}>
      {s.label}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  const isSuper = role === 'superadmin';
  const isAdmin = role === 'admin' || isSuper;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider"
      style={{
        color: isSuper ? '#92400E' : isAdmin ? '#0369A1' : '#475569',
        background: isSuper ? '#FEF3C7' : isAdmin ? '#E0F2FE' : '#F1F5F9',
        border: isSuper ? '1px solid #FCD34D' : isAdmin ? '1px solid #BAE6FD' : '1px solid #E2E8F0',
      }}>
      {isSuper ? <Crown className="w-2.5 h-2.5" /> : isAdmin ? <Shield className="w-2.5 h-2.5" /> : null}
      {role || 'user'}
    </span>
  );
}

function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] flex items-center gap-2.5 px-5 py-3 rounded-2xl shadow-xl text-sm font-bold text-white"
      style={{ background: type === 'success' ? '#059669' : '#DC2626' }}
    >
      {type === 'success' ? <Check className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
      <span>{message}</span>
    </motion.div>
  );
}

// ─── Main AdminScreen Component ───────────────────────────────────────────────
export const AdminScreen = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  // ── Access guard ──────────────────────────────────────────────────────────
  const [accessChecked, setAccessChecked] = useState(false);
  const [hasAccess, setHasAccess] = useState(false);

  useEffect(() => {
    const checkAccess = async () => {
      // 1. Superadmin fast-path
      if (isSuperAdminUser(user)) {
        setHasAccess(true);
        setAccessChecked(true);
        return true;
      }

      // 2. AdminUser helper
      if (isAdminUser(user)) {
        setHasAccess(true);
        setAccessChecked(true);
        return true;
      }

      // 3. Supabase profiles check
      if (user?.id) {
        try {
          const { data: prof } = await supabase
            .from('profiles')
            .select('role')
            .eq('id', user.id)
            .single();
          if (prof?.role === 'admin') {
            setHasAccess(true);
            setAccessChecked(true);
            return true;
          }
        } catch { /* silent */ }
      }

      // 4. Backend API check (real ground truth)
      try {
        const raw = localStorage.getItem('newscraft-auth');
        const token = raw ? JSON.parse(raw)?.state?.token : null;
        if (token) {
          const res = await fetch(
            'https://news-backend-sjw6.onrender.com/api/v1/admin/stats',
            { headers: { Authorization: 'Bearer ' + token } }
          );
          if (res.status === 200) {
            setHasAccess(true);
            setAccessChecked(true);
            return true;
          }
        }
      } catch { /* silent */ }

      setHasAccess(false);
      setAccessChecked(true);
      return false;
    };

    if (user) {
      checkAccess();
      return;
    }

    const timer = setTimeout(() => {
      if (!user) {
        navigate('/login', { replace: true });
        return;
      }
      checkAccess();
    }, 300);

    return () => clearTimeout(timer);
  }, [user, navigate]);

  // ── State ─────────────────────────────────────────────────────────────────
  const isSuperAdmin = isSuperAdminUser(user);
  const [activeTab, setActiveTab] = useState<'overview' | 'clippings' | 'users' | 'logos'>('overview');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserProfile[]>([]);
  const [logos, setLogos] = useState<PublicationLogo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [userFilter, setUserFilter] = useState<'all' | 'active_today' | 'admin' | 'reporter' | 'banned'>('all');
  const [sortField, setSortField] = useState<keyof AdminUserProfile>('created_at');
  const [sortAsc, setSortAsc] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Date filtering state
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [activeDatePreset, setActiveDatePreset] = useState<'all' | 'today' | 'yesterday' | 'week' | 'month' | 'custom'>('all');

  // Clippings state
  const [clippings, setClippings] = useState<AdminClippingLog[]>([]);
  const [clippingsLoading, setClippingsLoading] = useState(false);
  const [clippingsTotal, setClippingsTotal] = useState(0);
  const [clippingsSearch, setClippingsSearch] = useState('');
  const [selectedClippingModal, setSelectedClippingModal] = useState<AdminClippingLog | null>(null);

  // Guard tab for non-superadmin
  useEffect(() => {
    if (!isSuperAdmin && activeTab === 'logos') {
      setActiveTab('overview');
    }
  }, [isSuperAdmin, activeTab]);

  // Edit user state
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<string>('');
  const [editPlan, setEditPlan] = useState<string>('');
  const [editPhone, setEditPhone] = useState<string>('');
  const [editSaving, setEditSaving] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  // Logo form and editing state
  const [showLogoForm, setShowLogoForm] = useState(false);
  const [editingLogoId, setEditingLogoId] = useState<string | null>(null);
  const [logoName, setLogoName] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoCode, setLogoCode] = useState('');
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string>('');
  const [showManualUrl, setShowManualUrl] = useState(false);
  const [logoFormLoading, setLogoFormLoading] = useState(false);
  const [logoFormError, setLogoFormError] = useState('');
  const logoFileInputRef = useRef<HTMLInputElement>(null);

  const showToast = (message: string, type: 'success' | 'error') => setToast({ message, type });

  // ── Data fetching ─────────────────────────────────────────────────────────
  const fetchAll = useCallback(async (fDate?: string, tDate?: string) => {
    setLoading(true);
    try {
      const [statsData, usersData, logosData] = await Promise.all([
        getAdminStats(fDate, tDate),
        getAdminUsers(),
        getPublicationLogos(),
      ]);
      setStats(statsData);
      setUsers(usersData);
      setLogos(logosData);
    } catch {
      showToast('Error loading admin dashboard data', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchClippings = useCallback(async (fDate?: string, tDate?: string) => {
    setClippingsLoading(true);
    try {
      const res = await getAdminClippings({ fromDate: fDate, toDate: tDate, page: 1, pageSize: 60 });
      setClippings(res.results);
      setClippingsTotal(res.total);
    } catch {
      showToast('Failed to load clippings history', 'error');
    } finally {
      setClippingsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (hasAccess) {
      fetchAll(fromDate || undefined, toDate || undefined);
    }
  }, [hasAccess, fetchAll, fromDate, toDate]);

  useEffect(() => {
    if (hasAccess && activeTab === 'clippings') {
      fetchClippings(fromDate || undefined, toDate || undefined);
    }
  }, [hasAccess, activeTab, fetchClippings, fromDate, toDate]);

  // ── Date presets ──────────────────────────────────────────────────────────
  const handleDatePreset = (preset: 'all' | 'today' | 'yesterday' | 'week' | 'month' | 'custom') => {
    setActiveDatePreset(preset);
    let f = '';
    let t = '';
    if (preset === 'today') {
      f = getTodayStr();
      t = getTodayStr();
    } else if (preset === 'yesterday') {
      f = getYesterdayStr();
      t = getYesterdayStr();
    } else if (preset === 'week') {
      f = getDaysAgoStr(7);
      t = getTodayStr();
    } else if (preset === 'month') {
      f = getDaysAgoStr(30);
      t = getTodayStr();
    }
    setFromDate(f);
    setToDate(t);
  };

  const handleClippingsTodayClick = () => {
    handleDatePreset('today');
    setClippingsSearch('');
    setActiveTab('clippings');
    fetchClippings(getTodayStr(), getTodayStr());
  };

  const handleAllClippingsClick = () => {
    handleDatePreset('all');
    setClippingsSearch('');
    setActiveTab('clippings');
    fetchClippings();
  };

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleLogout = async () => {
    try { await supabase.auth.signOut(); } catch { /* continue */ }
    logout();
    try {
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.startsWith('newscraft') || key.startsWith('spotnews'))) keysToRemove.push(key);
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));
    } catch { /* continue */ }
    navigate('/login', { replace: true });
  };

  // User Actions
  const startEdit = (u: AdminUserProfile) => {
    if (isSuperAdminUser(u.email)) {
      showToast('Superadmin account is protected.', 'error');
      return;
    }
    setEditingUserId(u.id);
    setEditRole(u.role ?? 'user');
    setEditPlan(u.plan ?? 'free');
    setEditPhone(u.phone_number ?? '');
  };

  const cancelEdit = () => { setEditingUserId(null); };

  const saveEdit = async (u: AdminUserProfile) => {
    if (isSuperAdminUser(u.email)) {
      showToast('Superadmin account cannot be modified.', 'error');
      setEditingUserId(null);
      return;
    }
    if (editRole === 'admin' && !isSuperAdmin) {
      showToast('Only superadmin can grant admin role.', 'error');
      return;
    }
    setEditSaving(true);
    let roleSuccess = true;
    let planSuccess = true;
    let errorMsg: string | undefined;

    if (editRole !== u.role || editPhone !== (u.phone_number ?? '')) {
      const r1 = await updateUserRole(u.id, editRole as any, editPhone.trim() || u.phone_number);
      if (!r1.success) {
        roleSuccess = false;
        errorMsg = r1.error;
      }
    }
    if (editPlan !== u.plan && editRole !== 'admin') {
      const r2 = await updateUserPlan(u.id, editPlan);
      if (!r2.success) {
        planSuccess = false;
        errorMsg = errorMsg ?? r2.error;
      }
    }

    setEditSaving(false);
    setEditingUserId(null);

    if (roleSuccess && planSuccess) {
      showToast(`Updated ${u.email} successfully`, 'success');
      fetchAll(fromDate || undefined, toDate || undefined);
    } else {
      showToast(errorMsg ?? 'Failed to update user', 'error');
    }
  };

  const handleBanToggle = async (u: AdminUserProfile) => {
    if (isSuperAdminUser(u.email)) {
      showToast('Superadmin cannot be blocked.', 'error');
      return;
    }
    setActionLoadingId(u.id);
    const duration = u.is_banned ? 'none' : '876600h';
    const res = await banUser(u.id, duration);
    setActionLoadingId(null);
    if (res.success) {
      showToast(u.is_banned ? `Unblocked ${u.email}` : `Blocked ${u.email}`, 'success');
      fetchAll(fromDate || undefined, toDate || undefined);
    } else {
      showToast(res.error ?? 'Action failed', 'error');
    }
  };

  const handleDeleteUser = async (u: AdminUserProfile) => {
    if (isSuperAdminUser(u.email)) {
      showToast('Superadmin cannot be deleted.', 'error');
      return;
    }
    if (!isSuperAdmin) {
      showToast('Only superadmin can delete users.', 'error');
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete user ${u.email}? This action cannot be undone.`)) {
      return;
    }
    setActionLoadingId(u.id);
    const res = await deleteUser(u.id);
    setActionLoadingId(null);
    if (res.success) {
      showToast(`User ${u.email} deleted successfully.`, 'success');
      fetchAll(fromDate || undefined, toDate || undefined);
    } else {
      showToast(res.error ?? 'Failed to delete user.', 'error');
    }
  };

  // Logo handlers
  const resetLogoForm = () => {
    setLogoName('');
    setLogoUrl('');
    setLogoCode('');
    setLogoFile(null);
    setLogoPreview('');
    setShowManualUrl(false);
    setEditingLogoId(null);
    setShowLogoForm(false);
    setLogoFormError('');
  };

  const handleLogoFileSelect = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setLogoFormError('Please select a valid image file (PNG, JPG, SVG, WebP)');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setLogoFormError('Image size must be less than 5MB');
      return;
    }
    setLogoFile(file);
    setLogoFormError('');
    const reader = new FileReader();
    reader.onload = (e) => setLogoPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleSaveLogo = async () => {
    if (!logoName.trim()) {
      setLogoFormError('Publication name is required');
      return;
    }
    if (!logoCode.trim()) {
      setLogoFormError('Publication code is required');
      return;
    }
    if (!editingLogoId && !logoFile && !logoUrl.trim()) {
      setLogoFormError('Please upload a logo image or provide an image URL');
      return;
    }

    setLogoFormLoading(true);
    setLogoFormError('');

    let finalLogoUrl = logoUrl.trim();
    if (logoFile) {
      const uploadRes = await uploadLogoImage(logoFile);
      if (uploadRes.error || !uploadRes.url) {
        setLogoFormLoading(false);
        setLogoFormError(uploadRes.error ?? 'Failed to upload logo image');
        return;
      }
      finalLogoUrl = uploadRes.url;
    }

    if (editingLogoId) {
      const updates: any = { name: logoName.trim(), publication_code: logoCode.trim() };
      if (finalLogoUrl) updates.logo_url = finalLogoUrl;
      const result = await updatePublicationLogo(editingLogoId, updates);
      setLogoFormLoading(false);
      if (result.success) {
        showToast('Publication logo updated successfully!', 'success');
        resetLogoForm();
        fetchAll();
      } else {
        setLogoFormError(result.error ?? 'Failed to update logo.');
      }
    } else {
      const result = await addPublicationLogo(logoName, finalLogoUrl, logoCode);
      setLogoFormLoading(false);
      if (result.success) {
        showToast('Publication logo added successfully!', 'success');
        resetLogoForm();
        fetchAll();
      } else {
        setLogoFormError(result.error ?? 'Failed to add logo.');
      }
    }
  };

  const handleToggleLogo = async (id: string, current: boolean) => {
    if (!isSuperAdmin) {
      showToast('Only superadmin can manage logos.', 'error');
      return;
    }
    await toggleLogoActive(id, !current);
    showToast(`Logo ${!current ? 'enabled' : 'disabled'}`, 'success');
    fetchAll();
  };

  const handleDeleteLogo = async (id: string, name: string) => {
    if (!isSuperAdmin) {
      showToast('Only superadmin can manage logos.', 'error');
      return;
    }
    if (!window.confirm(`Delete logo "${name}"? This cannot be undone.`)) return;
    const result = await removePublicationLogo(id);
    if (result.success) {
      showToast('Logo removed.', 'success');
      fetchAll();
    } else {
      showToast('Failed to remove logo.', 'error');
    }
  };

  // ── Access Denied / Loading State ─────────────────────────────────────────
  if (!accessChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#EAF1FB]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-3 border-[#015BB3] border-t-transparent animate-spin" />
          <p className="text-[#0A2540] text-sm font-bold">Verifying Administrator Access…</p>
        </div>
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#EAF1FB]">
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="bg-white border border-[#D0E2F7] rounded-3xl p-8 text-center max-w-sm shadow-md"
        >
          <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-4 border border-red-100">
            <Shield className="w-8 h-8 text-[#DC2626]" />
          </div>
          <h2 className="text-[#0A2540] text-xl font-bold mb-2">Access Restricted</h2>
          <p className="text-[#6B7A90] text-xs leading-relaxed mb-6">
            You do not have administrator privileges to view this control panel. If you believe this is an error, please contact support.
          </p>
          <button
            onClick={() => navigate('/', { replace: true })}
            className="w-full py-3 rounded-xl text-sm font-bold text-white bg-[#015BB3] shadow-sm active:scale-95 transition-transform"
          >
            Return to App
          </button>
        </motion.div>
      </div>
    );
  }

  // Counts for user filter tabs
  const activeTodayCount = users.filter((u) => u.is_active_today).length;
  const reportersCount = users.filter((u) => u.role === 'reporter').length;
  const adminsCount = users.filter((u) => u.role === 'admin').length;
  const bannedCount = users.filter((u) => u.is_banned).length;

  // Filtered users
  const filteredUsers = users.filter((u) => {
    const q = searchQuery.toLowerCase().trim();
    const matchesSearch =
      !q ||
      u.email.toLowerCase().includes(q) ||
      (u.phone_number && u.phone_number.toLowerCase().includes(q)) ||
      (u.full_name || '').toLowerCase().includes(q) ||
      (u.role || '').toLowerCase().includes(q) ||
      (u.plan || '').toLowerCase().includes(q);

    if (!matchesSearch) return false;

    if (userFilter === 'active_today') return Boolean(u.is_active_today);
    if (userFilter === 'admin') return u.role === 'admin';
    if (userFilter === 'reporter') return u.role === 'reporter';
    if (userFilter === 'banned') return Boolean(u.is_banned);
    return true;
  }).sort((a, b) => {
    const aVal = a[sortField] ?? '';
    const bVal = b[sortField] ?? '';
    if (aVal < bVal) return sortAsc ? -1 : 1;
    if (aVal > bVal) return sortAsc ? 1 : -1;
    return 0;
  });

  // Filtered clippings
  const filteredClippings = clippings.filter((c) => {
    const q = clippingsSearch.toLowerCase();
    return (
      c.headline.toLowerCase().includes(q) ||
      c.user_email.toLowerCase().includes(q) ||
      (c.publication_name || '').toLowerCase().includes(q) ||
      (c.language || '').toLowerCase().includes(q)
    );
  });

  // ── Render Dashboard ──────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#EAF1FB] pb-24 text-[#0A2540] font-sans">
      {/* ── Spot News Masthead Header ── */}
      <header className="w-full bg-[#015BB3] text-white shadow-md">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-11 w-auto bg-white p-1 rounded-lg border border-white/20 flex items-center justify-center shrink-0">
              <img src={mastheadLogo} alt="Spot News" className="h-full w-auto object-contain max-w-[70px]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-white text-lg font-black tracking-wide leading-tight" style={{ fontFamily: "'Georgia', serif" }}>
                  Spot News 24x7
                </h1>
                <span className="bg-amber-400 text-[#0A2540] text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-xs">
                  {isSuperAdmin ? 'SUPERADMIN' : 'ADMIN'}
                </span>
              </div>
              <p className="text-white/75 text-[11px] font-medium">Control Center & Operations</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/')}
              className="px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 bg-white/15 text-white active:scale-95 transition-transform hover:bg-white/20"
              title="Return to App"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>App</span>
            </button>
            <button
              onClick={() => fetchAll(fromDate || undefined, toDate || undefined)}
              disabled={loading}
              className="w-9 h-9 rounded-xl flex items-center justify-center bg-white/15 text-white active:scale-95 transition-transform hover:bg-white/20"
              title="Refresh Data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleLogout}
              className="w-9 h-9 rounded-xl flex items-center justify-center bg-[#D32F2F] text-white active:scale-95 transition-transform hover:bg-[#B71C1C]"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* User bar */}
        <div className="bg-[#0A2540]/30 border-t border-white/10 px-4 py-2">
          <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-white/80">
            <div className="flex items-center gap-2 truncate">
              <Crown className="w-3.5 h-3.5 text-amber-300 shrink-0" />
              <span className="truncate">
                Admin: <strong className="text-white font-bold">{user?.email}</strong>
              </span>
            </div>
            <span className="text-[11px] text-white/60 shrink-0">
              {new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          </div>
        </div>
      </header>

      {/* ── Segmented Navigation Tabs ── */}
      <div className="max-w-5xl mx-auto px-4 pt-4">
        <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-1 flex items-center gap-1 shadow-xs">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'overview'
                ? 'bg-[#015BB3] text-white shadow-sm'
                : 'text-[#415A77] hover:bg-white/50'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab('clippings')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'clippings'
                ? 'bg-[#015BB3] text-white shadow-sm'
                : 'text-[#415A77] hover:bg-white/50'
            }`}
          >
            <Newspaper className="w-4 h-4" />
            <span>Clippings</span>
          </button>

          <button
            onClick={() => setActiveTab('users')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'users'
                ? 'bg-[#015BB3] text-white shadow-sm'
                : 'text-[#415A77] hover:bg-white/50'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Users ({users.length})</span>
          </button>

          {isSuperAdmin && (
            <button
              onClick={() => setActiveTab('logos')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'logos'
                  ? 'bg-[#015BB3] text-white shadow-sm'
                  : 'text-[#415A77] hover:bg-white/50'
              }`}
            >
              <ImageIcon className="w-4 h-4" />
              <span>Logos ({logos.length})</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Main Tab Content ── */}
      <main className="max-w-5xl mx-auto px-4 pt-4">

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 1: OVERVIEW                                                      */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Date Preset Filter Bar */}
            <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-3 shadow-xs">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#0A2540]">
                  <Calendar className="w-3.5 h-3.5 text-[#015BB3]" />
                  <span>Filter Statistics by Period</span>
                </div>
                {stats?.rangeGenerations !== null && stats?.rangeGenerations !== undefined && (
                  <span className="text-[11px] font-bold text-[#015BB3] bg-[#D6E9FF] px-2 py-0.5 rounded-full">
                    {stats.rangeGenerations} clippings in range
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {(['all', 'today', 'yesterday', 'week', 'month', 'custom'] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => handleDatePreset(p)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold capitalize transition-all ${
                      activeDatePreset === p
                        ? 'bg-[#015BB3] text-white shadow-xs'
                        : 'bg-white text-[#415A77] border border-[#D0E2F7] hover:bg-white/80'
                    }`}
                  >
                    {p === 'all' ? 'All Time' : p === 'week' ? 'Last 7D' : p === 'month' ? 'Last 30D' : p}
                  </button>
                ))}
              </div>

              {activeDatePreset === 'custom' && (
                <div className="mt-3 pt-3 border-t border-[#D0E2F7] flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="text-[#6B7A90] font-semibold">From:</span>
                    <input
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                      className="bg-white border border-[#D0E2F7] rounded-lg px-2 py-1 text-xs text-[#0A2540]"
                    />
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="text-[#6B7A90] font-semibold">To:</span>
                    <input
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                      className="bg-white border border-[#D0E2F7] rounded-lg px-2 py-1 text-xs text-[#0A2540]"
                    />
                  </div>
                  <button
                    onClick={() => fetchAll(fromDate, toDate)}
                    className="px-3 py-1 rounded-lg text-xs font-bold bg-[#015BB3] text-white"
                  >
                    Apply
                  </button>
                </div>
              )}
            </div>

            {/* Stat Cards Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                icon={Users}
                label="Total Users"
                value={stats?.totalUsers ?? 0}
                sub="Registered accounts"
                color="#015BB3"
                bg="#E0F2FE"
              />
              <div
                onClick={handleClippingsTodayClick}
                className="cursor-pointer active:scale-95 transition-transform"
                title="Tap to view clippings generated today"
              >
                <StatCard
                  icon={TrendingUp}
                  label="Clippings Today"
                  value={stats?.totalGenerationsToday ?? 0}
                  sub="Published today · Tap to view →"
                  color="#059669"
                  bg="#ECFDF5"
                />
              </div>
              <div
                onClick={handleAllClippingsClick}
                className="cursor-pointer active:scale-95 transition-transform"
                title="Tap to view all clippings"
              >
                <StatCard
                  icon={Newspaper}
                  label="Total Clippings"
                  value={stats?.totalGenerationsAllTime ?? 0}
                  sub="All-time created · Tap to view →"
                  color="#D97706"
                  bg="#FEF3C7"
                />
              </div>
              <div
                onClick={() => {
                  setUserFilter('active_today');
                  setActiveTab('users');
                }}
                className="cursor-pointer active:scale-95 transition-transform"
                title="Tap to see users active today"
              >
                <StatCard
                  icon={Activity}
                  label="Active Reporters"
                  value={Math.max(stats?.activeUsersToday ?? 0, activeTodayCount)}
                  sub="Active today · Tap to view →"
                  color="#059669"
                  bg="#ECFDF5"
                />
              </div>
            </div>

            {/* Range highlight if filtered */}
            {stats?.rangeGenerations !== null && stats?.rangeGenerations !== undefined && (
              <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-4 shadow-xs flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-bold text-[#6B7A90] uppercase tracking-wider">Filtered Period Metric</span>
                  <h4 className="text-xl font-black text-[#015BB3] mt-0.5">
                    {stats.rangeGenerations} Clippings · {stats.rangeActiveUsers ?? 0} Active Users
                  </h4>
                  <p className="text-xs text-[#6B7A90] mt-0.5">
                    From {formatDate(stats.fromDate || fromDate)} to {formatDate(stats.toDate || toDate)}
                  </p>
                </div>
                <button
                  onClick={() => handleDatePreset('all')}
                  className="text-xs font-bold text-[#015BB3] underline active:opacity-70"
                >
                  Clear Filter
                </button>
              </div>
            )}

            {/* Quick Actions Card */}
            <div className="bg-white border border-[#D0E2F7] rounded-2xl p-4 shadow-sm">
              <h3 className="text-sm font-bold text-[#0A2540] mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#015BB3]" />
                <span>Quick Operations</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
                <button
                  onClick={() => {
                    setUserFilter('active_today');
                    setActiveTab('users');
                  }}
                  className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200 text-left hover:bg-emerald-100/60 transition-all flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-1.5">
                      <p className="text-xs font-bold text-emerald-950">Active Reporters</p>
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    </div>
                    <p className="text-[11px] text-emerald-800 mt-0.5 font-medium">
                      {activeTodayCount} online / generating today
                    </p>
                  </div>
                  <Activity className="w-4 h-4 text-emerald-600" />
                </button>

                <button
                  onClick={() => {
                    setUserFilter('all');
                    setActiveTab('users');
                  }}
                  className="p-3 rounded-xl bg-[#E8F2FC] border border-[#D0E2F7] text-left hover:bg-[#D6E9FF] transition-all flex items-center justify-between"
                >
                  <div>
                    <p className="text-xs font-bold text-[#0A2540]">Manage Users & Roles</p>
                    <p className="text-[11px] text-[#6B7A90] mt-0.5">Promote, demote or ban users</p>
                  </div>
                  <Users className="w-4 h-4 text-[#015BB3]" />
                </button>

                <button
                  onClick={() => setActiveTab('clippings')}
                  className="p-3 rounded-xl bg-[#E8F2FC] border border-[#D0E2F7] text-left hover:bg-[#D6E9FF] transition-all flex items-center justify-between"
                >
                  <div>
                    <p className="text-xs font-bold text-[#0A2540]">Review Clippings</p>
                    <p className="text-[11px] text-[#6B7A90] mt-0.5">Browse news generation feed</p>
                  </div>
                  <Newspaper className="w-4 h-4 text-[#015BB3]" />
                </button>

                {isSuperAdmin && (
                  <button
                    onClick={() => { setActiveTab('logos'); setShowLogoForm(true); }}
                    className="p-3 rounded-xl bg-[#E8F2FC] border border-[#D0E2F7] text-left hover:bg-[#D6E9FF] transition-all flex items-center justify-between"
                  >
                    <div>
                      <p className="text-xs font-bold text-[#0A2540]">Add Publication Logo</p>
                      <p className="text-[11px] text-[#6B7A90] mt-0.5">Upload new masthead logo</p>
                    </div>
                    <Plus className="w-4 h-4 text-[#015BB3]" />
                  </button>
                )}
              </div>
            </div>

            {/* System Status */}
            <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-4 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-bold text-[#0A2540]">Production Engine Active</span>
              </div>
              <span className="text-[#6B7A90]">Backend v1.0 · Supabase Secure RLS</span>
            </div>
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 2: CLIPPINGS                                                     */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'clippings' && (
          <div className="space-y-4">
            {/* Search & Actions Header */}
            <div className="bg-white border border-[#D0E2F7] rounded-2xl p-3 shadow-sm flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-[#8FA3B8] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search clippings by headline, user email, publication..."
                  value={clippingsSearch}
                  onChange={(e) => setClippingsSearch(e.target.value)}
                  className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl pl-9 pr-3 py-2 text-xs text-[#0A2540] placeholder-[#8FA3B8] focus:outline-none focus:border-[#015BB3]"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchClippings(fromDate || undefined, toDate || undefined)}
                  disabled={clippingsLoading}
                  className="px-3 py-2 rounded-xl bg-[#015BB3] text-white text-xs font-bold flex items-center gap-1.5 shadow-xs"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${clippingsLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh ({clippingsTotal})</span>
                </button>
              </div>
            </div>

            {/* Today's Filter Banner */}
            {activeDatePreset === 'today' && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-2xs">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-emerald-950">
                        Clippings Generated Today ({filteredClippings.length})
                      </h4>
                      <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-emerald-200 text-emerald-800 uppercase tracking-wider">
                        Today
                      </span>
                    </div>
                    <p className="text-[11px] text-emerald-700 mt-0.5">
                      Review all clippings published today and see which reporter generated each one.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    handleDatePreset('all');
                    fetchClippings();
                  }}
                  className="text-xs font-bold text-emerald-800 bg-white hover:bg-emerald-100 border border-emerald-300 rounded-xl px-3 py-1.5 transition-colors shrink-0 self-start sm:self-center"
                >
                  Show All Clippings
                </button>
              </div>
            )}

            {/* Clippings List */}
            {clippingsLoading ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 rounded-full border-2 border-[#015BB3] border-t-transparent animate-spin mx-auto mb-2" />
                <p className="text-xs text-[#6B7A90] font-bold">Loading clippings…</p>
              </div>
            ) : filteredClippings.length === 0 ? (
              <div className="bg-white border border-[#D0E2F7] rounded-2xl p-10 text-center shadow-sm">
                <Newspaper className="w-12 h-12 text-[#8FA3B8] mx-auto mb-2 opacity-50" />
                <p className="text-sm font-bold text-[#0A2540]">
                  {activeDatePreset === 'today' ? 'No Clippings Generated Today Yet' : 'No clippings found'}
                </p>
                <p className="text-xs text-[#6B7A90] mt-1">
                  {activeDatePreset === 'today'
                    ? 'When reporters create clippings today, they will appear here with author details and links.'
                    : 'Try clearing search filters or selecting another date preset.'}
                </p>
                {activeDatePreset === 'today' && (
                  <button
                    onClick={() => {
                      handleDatePreset('all');
                      fetchClippings();
                    }}
                    className="mt-3 px-3.5 py-1.5 rounded-xl bg-[#015BB3] text-white text-xs font-bold shadow-xs inline-flex items-center gap-1.5"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View All Past Clippings</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredClippings.map((clip) => (
                  <div
                    key={clip.id}
                    onClick={() => setSelectedClippingModal(clip)}
                    className="bg-white border border-[#D0E2F7] rounded-2xl p-4 shadow-sm hover:border-[#015BB3] transition-all cursor-pointer flex flex-col justify-between group"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#E0F2FE] text-[#0369A1] uppercase tracking-wider">
                          {clip.publication_name || 'Spot News'}
                        </span>
                        <span className="text-[11px] text-[#8FA3B8] font-medium">
                          {timeAgo(clip.created_at)}
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-[#0A2540] line-clamp-2 leading-snug mb-2 group-hover:text-[#015BB3] transition-colors">
                        {clip.headline || 'Untitled Clipping'}
                      </h4>

                      {/* Who Generated It: Reporter Card */}
                      <div className="flex items-center gap-2.5 p-2 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] mb-3">
                        <div className="w-8 h-8 rounded-full bg-[#E0F2FE] border border-[#015BB3]/30 text-[#015BB3] font-bold text-xs flex items-center justify-center shrink-0">
                          {(clip.user_name || clip.user_email || 'R').substring(0, 1).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-[#0A2540] truncate">
                            {clip.user_name || 'Reporter'}
                          </p>
                          <p className="text-[10px] text-[#6B7A90] truncate">
                            {clip.user_email}
                          </p>
                        </div>
                        {clip.user_plan && (
                          <PlanBadge plan={clip.user_plan} />
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-[#6B7A90] mb-1">
                        <span className="uppercase font-semibold">{clip.language}</span>
                        <span>·</span>
                        <span>{clip.layout_columns} Cols</span>
                        <span>·</span>
                        <span className="capitalize">{clip.template_id?.replace(/_/g, ' ')}</span>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#E8F2FC] flex items-center justify-between">
                      <span className="text-[11px] text-[#8FA3B8]">{formatDateTime(clip.created_at)}</span>
                      <span className="text-xs font-bold text-[#015BB3] flex items-center gap-1">
                        <Eye className="w-3.5 h-3.5" />
                        <span>View Details</span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 3: USERS                                                         */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'users' && (
          <div className="space-y-4">
            {/* Search and Sort Bar */}
            <div className="bg-white border border-[#D0E2F7] rounded-2xl p-3 shadow-sm flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-[#8FA3B8] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by email, name, role or plan..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl pl-9 pr-3 py-2 text-xs text-[#0A2540] placeholder-[#8FA3B8] focus:outline-none focus:border-[#015BB3]"
                />
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value as any)}
                  className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl px-2.5 py-2 text-xs text-[#0A2540] font-bold focus:outline-none"
                >
                  <option value="created_at">Joined Date</option>
                  <option value="email">Email</option>
                  <option value="role">Role</option>
                  <option value="total_generations">Most Clippings</option>
                </select>

                <button
                  onClick={() => setSortAsc(!sortAsc)}
                  className="p-2 rounded-xl bg-[#E8F2FC] border border-[#D0E2F7] text-[#0A2540] hover:bg-[#D6E9FF]"
                  title="Toggle sort direction"
                >
                  {sortAsc ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
              <button
                onClick={() => setUserFilter('all')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 transition-all ${
                  userFilter === 'all'
                    ? 'bg-[#015BB3] text-white shadow-xs'
                    : 'bg-white text-[#415A77] border border-[#D0E2F7] hover:bg-[#E8F2FC]'
                }`}
              >
                All Users ({users.length})
              </button>

              <button
                onClick={() => setUserFilter('active_today')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 flex items-center gap-1.5 transition-all ${
                  userFilter === 'active_today'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'bg-white text-emerald-700 border border-emerald-300 hover:bg-emerald-50'
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Active Today ({activeTodayCount})</span>
              </button>

              <button
                onClick={() => setUserFilter('reporter')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 transition-all ${
                  userFilter === 'reporter'
                    ? 'bg-[#015BB3] text-white shadow-xs'
                    : 'bg-white text-[#415A77] border border-[#D0E2F7] hover:bg-[#E8F2FC]'
                }`}
              >
                Reporters ({reportersCount})
              </button>

              <button
                onClick={() => setUserFilter('admin')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 transition-all ${
                  userFilter === 'admin'
                    ? 'bg-[#015BB3] text-white shadow-xs'
                    : 'bg-white text-[#415A77] border border-[#D0E2F7] hover:bg-[#E8F2FC]'
                }`}
              >
                Admins ({adminsCount})
              </button>

              {bannedCount > 0 && (
                <button
                  onClick={() => setUserFilter('banned')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 transition-all ${
                    userFilter === 'banned'
                      ? 'bg-red-600 text-white shadow-xs'
                      : 'bg-white text-red-700 border border-red-200 hover:bg-red-50'
                  }`}
                >
                  Blocked ({bannedCount})
                </button>
              )}
            </div>

            {/* Empty State if no users match */}
            {filteredUsers.length === 0 && (
              <div className="bg-white border border-[#D0E2F7] rounded-2xl p-8 text-center">
                <Users className="w-8 h-8 text-[#8FA3B8] mx-auto mb-2" />
                <h4 className="text-sm font-bold text-[#0A2540]">No users found</h4>
                <p className="text-xs text-[#6B7A90] mt-1">
                  {userFilter === 'active_today'
                    ? 'No reporters have logged in or generated clippings today yet.'
                    : 'Try changing your search query or filter.'}
                </p>
                {userFilter !== 'all' && (
                  <button
                    onClick={() => setUserFilter('all')}
                    className="mt-3 px-4 py-1.5 rounded-xl bg-[#015BB3] text-white text-xs font-bold shadow-xs active:scale-95"
                  >
                    View All Users ({users.length})
                  </button>
                )}
              </div>
            )}

            {/* Users List */}
            <div className="space-y-2.5">
              {filteredUsers.map((u) => {
                const isSuper = isSuperAdminUser(u.email);
                const isSelf = user?.email?.toLowerCase() === u.email?.toLowerCase();
                return (
                  <div
                    key={u.id}
                    className="bg-white border border-[#D0E2F7] rounded-2xl p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-full bg-[#D6E9FF] border border-[#015BB3]/30 flex items-center justify-center font-bold text-[#015BB3] shrink-0 text-sm relative">
                        {u.avatar_url ? (
                          <img src={u.avatar_url} alt="" className="w-full h-full rounded-full object-cover" />
                        ) : (
                          (u.full_name || u.email || 'U').substring(0, 2).toUpperCase()
                        )}
                        {u.is_active_today && (
                          <span
                            className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-emerald-500 border-2 border-white rounded-full shadow-xs"
                            title="Active Today"
                          />
                        )}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-sm font-bold text-[#0A2540] truncate">
                            {u.full_name || 'Reporter'}
                          </h4>
                          <RoleBadge role={isSuper ? 'superadmin' : u.role} />
                          <PlanBadge plan={u.plan} />

                          {u.is_active_today && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1 border border-emerald-300">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                              Active Today
                            </span>
                          )}

                          {Boolean((u.generations_today ?? 0) > 0) && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                              ⚡ {u.generations_today} clipping{(u.generations_today ?? 0) > 1 ? 's' : ''} today
                            </span>
                          )}

                          {u.is_banned && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 uppercase">
                              Blocked
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-wrap mt-0.5">
                          <p className="text-xs text-[#6B7A90] truncate">{u.email}</p>
                          {u.phone_number && (
                            <span className="text-[11px] font-semibold text-[#015BB3] bg-[#E8F2FC] border border-[#D0E2F7] px-2 py-0.5 rounded-md">
                              📞 {u.phone_number}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-[#8FA3B8] mt-0.5 flex-wrap">
                          <span>Joined {formatDate(u.created_at)}</span>
                          {u.last_sign_in_at && (
                            <span className="text-[#015BB3] font-medium">
                              · Last active: {formatDate(u.last_sign_in_at)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Clippings Generated Per User Badge */}
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setClippingsSearch(u.email);
                        setActiveTab('clippings');
                      }}
                      className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-sky-50 to-blue-50 border border-sky-200 text-[#015BB3] hover:border-[#015BB3] hover:shadow-xs transition-all cursor-pointer group shrink-0 self-start md:self-center"
                      title={`View clippings generated by ${u.full_name || u.email}`}
                    >
                      <div className="w-8 h-8 rounded-lg bg-[#015BB3] text-white flex items-center justify-center shrink-0 shadow-2xs">
                        <Newspaper className="w-4 h-4" />
                      </div>
                      <div className="text-left">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-black text-[#0A2540]">
                            {u.total_generations ?? 0}
                          </span>
                          <span className="text-xs font-bold text-[#6B7A90]">
                            {(u.total_generations ?? 0) === 1 ? 'Clipping' : 'Clippings'}
                          </span>
                          {(u.generations_today ?? 0) > 0 && (
                            <span className="text-[10px] font-black px-1.5 py-0.5 rounded-full bg-emerald-600 text-white shadow-2xs">
                              +{u.generations_today} today
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] text-[#015BB3] font-semibold group-hover:underline">
                          View clippings →
                        </p>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 self-end md:self-center">
                      {!isSuper && (
                        <>
                          <button
                            onClick={() => startEdit(u)}
                            className="px-3 py-1.5 rounded-xl bg-[#E8F2FC] text-[#015BB3] border border-[#D0E2F7] text-xs font-bold flex items-center gap-1 active:scale-95 transition-transform"
                          >
                            <Edit2 className="w-3 h-3" />
                            <span>Edit</span>
                          </button>

                          <button
                            onClick={() => handleBanToggle(u)}
                            disabled={actionLoadingId === u.id}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1 border active:scale-95 transition-transform ${
                              u.is_banned
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-red-50 text-red-700 border-red-200'
                            }`}
                          >
                            <Ban className="w-3 h-3" />
                            <span>{u.is_banned ? 'Unblock' : 'Block'}</span>
                          </button>

                          {isSuperAdmin && !isSelf && (
                            <button
                              onClick={() => handleDeleteUser(u)}
                              disabled={actionLoadingId === u.id}
                              className="p-2 rounded-xl bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 active:scale-95"
                              title="Delete User"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 4: PUBLICATION LOGOS (Superadmin Only)                           */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'logos' && isSuperAdmin && (
          <div className="space-y-4">
            <div className="bg-white border border-[#D0E2F7] rounded-2xl p-4 shadow-sm flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0A2540]">Brand Publication Logos</h3>
                <p className="text-xs text-[#6B7A90] mt-0.5">Manage masthead logos available to reporters during news generation</p>
              </div>
              <button
                onClick={() => { resetLogoForm(); setShowLogoForm(true); }}
                className="px-4 py-2 rounded-xl bg-[#015BB3] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm active:scale-95"
              >
                <Plus className="w-4 h-4" />
                <span>Add Logo</span>
              </button>
            </div>

            {/* Logo Form (when visible) */}
            {showLogoForm && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-4 shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-[#0A2540]">
                    {editingLogoId ? 'Edit Publication Logo' : 'New Publication Logo'}
                  </h4>
                  <button onClick={resetLogoForm} className="text-[#6B7A90] hover:text-[#0A2540]">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {logoFormError && (
                  <div className="p-2.5 rounded-xl bg-red-100 text-red-800 text-xs font-bold flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{logoFormError}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-[#0A2540] mb-1">Publication Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Spot News 24x7"
                      value={logoName}
                      onChange={(e) => setLogoName(e.target.value)}
                      className="w-full bg-white border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs text-[#0A2540] focus:outline-none focus:border-[#015BB3]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#0A2540] mb-1">Publication Code (Key)</label>
                    <input
                      type="text"
                      placeholder="e.g. spot_news"
                      value={logoCode}
                      onChange={(e) => setLogoCode(e.target.value)}
                      className="w-full bg-white border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs text-[#0A2540] focus:outline-none focus:border-[#015BB3]"
                    />
                  </div>
                </div>

                {/* Upload or URL */}
                <div>
                  <label className="block text-xs font-bold text-[#0A2540] mb-1">Logo Artwork</label>
                  <div className="flex items-center gap-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setShowManualUrl(false)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold ${!showManualUrl ? 'bg-[#015BB3] text-white' : 'bg-white text-[#6B7A90]'}`}
                    >
                      File Upload
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowManualUrl(true)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold ${showManualUrl ? 'bg-[#015BB3] text-white' : 'bg-white text-[#6B7A90]'}`}
                    >
                      Image URL
                    </button>
                  </div>

                  {!showManualUrl ? (
                    <div
                      onClick={() => logoFileInputRef.current?.click()}
                      className="border-2 border-dashed border-[#D0E2F7] rounded-xl p-4 text-center cursor-pointer bg-white hover:border-[#015BB3] transition-all"
                    >
                      <input
                        ref={logoFileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && handleLogoFileSelect(e.target.files[0])}
                      />
                      <UploadCloud className="w-6 h-6 text-[#015BB3] mx-auto mb-1" />
                      <p className="text-xs font-bold text-[#0A2540]">
                        {logoFile ? logoFile.name : 'Click to select logo image'}
                      </p>
                      <p className="text-[10px] text-[#8FA3B8]">PNG, JPG or SVG up to 5MB</p>
                    </div>
                  ) : (
                    <input
                      type="text"
                      placeholder="https://example.com/logo.png"
                      value={logoUrl}
                      onChange={(e) => { setLogoUrl(e.target.value); setLogoPreview(e.target.value); }}
                      className="w-full bg-white border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs text-[#0A2540] focus:outline-none focus:border-[#015BB3]"
                    />
                  )}

                  {logoPreview && (
                    <div className="mt-2 p-2 bg-white rounded-xl border border-[#D0E2F7] inline-block">
                      <img src={logoPreview} alt="Preview" className="h-12 w-auto object-contain max-w-[140px]" />
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    onClick={resetLogoForm}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-white text-[#6B7A90] border border-[#D0E2F7]"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveLogo}
                    disabled={logoFormLoading}
                    className="px-5 py-2 rounded-xl text-xs font-bold bg-[#015BB3] text-white shadow-sm flex items-center gap-1.5"
                  >
                    {logoFormLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>Save Logo</span>
                  </button>
                </div>
              </motion.div>
            )}

            {/* Logos Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {logos.map((logo) => (
                <div
                  key={logo.id}
                  className="bg-white border border-[#D0E2F7] rounded-2xl p-4 shadow-sm flex items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-16 h-12 rounded-xl bg-[#E8F2FC] border border-[#D0E2F7] p-1 flex items-center justify-center shrink-0">
                      <img src={logo.logo_url} alt={logo.name} className="max-h-full max-w-full object-contain" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-[#0A2540]">{logo.name}</h4>
                      <p className="text-xs text-[#6B7A90]">Code: <code>{logo.publication_code}</code></p>
                      <span className={`inline-block mt-1 text-[9px] font-bold px-1.5 py-0.2 rounded ${logo.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'}`}>
                        {logo.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleToggleLogo(logo.id, logo.is_active)}
                      className="p-1.5 rounded-lg bg-[#E8F2FC] text-[#0A2540] hover:bg-[#D6E9FF]"
                      title={logo.is_active ? 'Disable' : 'Enable'}
                    >
                      {logo.is_active ? <Eye className="w-4 h-4 text-emerald-600" /> : <EyeOff className="w-4 h-4 text-gray-400" />}
                    </button>
                    <button
                      onClick={() => handleDeleteLogo(logo.id, logo.name)}
                      className="p-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* MODAL: EDIT USER ROLE / PLAN                                         */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {editingUserId && (
          <div className="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-[#0A2540]/50 backdrop-blur-xs">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white border border-[#D0E2F7] rounded-3xl p-5 w-full max-w-sm shadow-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-[#0A2540]">Modify User Permissions</h3>
                <button onClick={cancelEdit} className="text-[#8FA3B8] hover:text-[#0A2540]">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {(() => {
                const targetUser = users.find((u) => u.id === editingUserId);
                if (!targetUser) return null;
                return (
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-[#6B7A90]">Target Account</p>
                      <p className="text-sm font-bold text-[#0A2540]">{targetUser.email}</p>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-[#0A2540] mb-1">Phone Number</label>
                      <input
                        type="text"
                        value={editPhone}
                        onChange={(e) => setEditPhone(e.target.value)}
                        placeholder="e.g. +919876543210"
                        className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs font-bold text-[#0A2540] focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-[#0A2540] mb-1">Role</label>
                      <select
                        value={editRole}
                        onChange={(e) => setEditRole(e.target.value)}
                        className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs font-bold text-[#0A2540] focus:outline-none"
                      >
                        <option value="user">User</option>
                        <option value="reporter">Reporter</option>
                        {isSuperAdmin && <option value="admin">Administrator</option>}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-[#0A2540] mb-1">Subscription Plan</label>
                      <select
                        value={editPlan}
                        onChange={(e) => setEditPlan(e.target.value)}
                        className="w-full bg-[#E8F2FC] border border-[#D0E2F7] rounded-xl px-3 py-2 text-xs font-bold text-[#0A2540] focus:outline-none"
                      >
                        <option value="free">Free</option>
                        <option value="reporter">Reporter</option>
                        <option value="pro">Pro</option>
                        <option value="enterprise">Enterprise</option>
                        <option value="admin">Admin Plan</option>
                      </select>
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2">
                      <button
                        onClick={cancelEdit}
                        className="px-4 py-2 rounded-xl text-xs font-bold bg-[#E8F2FC] text-[#6B7A90]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => saveEdit(targetUser)}
                        disabled={editSaving}
                        className="px-5 py-2 rounded-xl text-xs font-bold bg-[#015BB3] text-white flex items-center gap-1.5 shadow-sm"
                      >
                        {editSaving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                        <span>Save Changes</span>
                      </button>
                    </div>
                  </div>
                );
              })()}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* MODAL: CLIPPING DETAIL PREVIEW                                       */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {selectedClippingModal && (
          <div className="fixed inset-0 z-[160] flex items-center justify-center p-4 bg-[#0A2540]/60 backdrop-blur-xs">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white border border-[#D0E2F7] rounded-3xl p-5 w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto space-y-4"
            >
              <div className="flex items-start justify-between gap-2 border-b border-[#D0E2F7] pb-3">
                <div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#E0F2FE] text-[#0369A1] uppercase">
                    {selectedClippingModal.publication_name || 'Spot News'}
                  </span>
                  <h3 className="text-base font-bold text-[#0A2540] mt-1 leading-snug">
                    {selectedClippingModal.headline}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedClippingModal(null)}
                  className="p-1 rounded-lg text-[#8FA3B8] hover:text-[#0A2540]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Image preview */}
              {selectedClippingModal.png_url ? (
                <div className="rounded-2xl overflow-hidden border border-[#D0E2F7] bg-[#E8F2FC] max-h-72 flex items-center justify-center">
                  <img
                    src={selectedClippingModal.png_url}
                    alt="Clipping"
                    className="w-full h-auto max-h-72 object-contain"
                  />
                </div>
              ) : (
                <div className="p-8 rounded-2xl bg-[#E8F2FC] text-center text-xs text-[#6B7A90]">
                  No thumbnail image URL recorded for this generation.
                </div>
              )}

              {/* Metadata chips */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded-xl bg-[#E8F2FC]">
                  <p className="text-[10px] text-[#8FA3B8] uppercase font-bold">Author</p>
                  <p className="font-bold text-[#0A2540] truncate">{selectedClippingModal.user_name} ({selectedClippingModal.user_email})</p>
                </div>
                <div className="p-2.5 rounded-xl bg-[#E8F2FC]">
                  <p className="text-[10px] text-[#8FA3B8] uppercase font-bold">Generated At</p>
                  <p className="font-bold text-[#0A2540]">{formatDateTime(selectedClippingModal.created_at)}</p>
                </div>
                <div className="p-2.5 rounded-xl bg-[#E8F2FC]">
                  <p className="text-[10px] text-[#8FA3B8] uppercase font-bold">Language & Tone</p>
                  <p className="font-bold text-[#0A2540] capitalize">{selectedClippingModal.language} · {selectedClippingModal.tone}</p>
                </div>
                <div className="p-2.5 rounded-xl bg-[#E8F2FC]">
                  <p className="text-[10px] text-[#8FA3B8] uppercase font-bold">Layout Columns</p>
                  <p className="font-bold text-[#0A2540]">{selectedClippingModal.layout_columns} Columns</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#D0E2F7]">
                {selectedClippingModal.png_url && (
                  <a
                    href={selectedClippingModal.png_url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-[#E8F2FC] text-[#015BB3] border border-[#D0E2F7] flex items-center gap-1.5"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open Full PNG</span>
                  </a>
                )}
                {selectedClippingModal.pdf_url && (
                  <a
                    href={selectedClippingModal.pdf_url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-[#015BB3] text-white flex items-center gap-1.5 shadow-xs"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Open PDF</span>
                  </a>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Toast ── */}
      <AnimatePresence>
        {toast && (
          <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
        )}
      </AnimatePresence>
    </div>
  );
};
