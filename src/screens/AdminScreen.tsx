import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users, BarChart3, Image as ImageIcon, Shield, LogOut,
  Plus, Trash2, Eye, EyeOff, RefreshCw, X, Check,
  AlertTriangle, TrendingUp, Newspaper, Activity, Crown,
  ChevronDown, ChevronUp, Search
} from 'lucide-react';
import { useAuthStore, isAdminUser } from '@/store';
import { supabase } from '@/lib/supabase';
import {
  getAdminStats, getAdminUsers, getPublicationLogos,
  addPublicationLogo, removePublicationLogo, toggleLogoActive,
  updateUserRole, updateUserPlan,
  type AdminStats, type AdminUserProfile, type PublicationLogo
} from '@/services/admin.service';


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

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative rounded-2xl overflow-hidden"
      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
    >
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${color}22` }}>
            <Icon className="w-4 h-4" style={{ color }} />
          </div>
          <TrendingUp className="w-3.5 h-3.5 text-green-400 opacity-60" />
        </div>
        <p className="text-white text-2xl font-black tracking-tight">{fmt(Number(value))}</p>
        <p className="text-white/50 text-xs font-semibold uppercase tracking-widest mt-1">{label}</p>
        {sub && <p className="text-white/30 text-[10px] mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  );
}

function PlanBadge({ plan }: { plan: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    admin:      { label: 'ADMIN',      color: '#f59e0b', bg: '#f59e0b22' },
    pro:        { label: 'PRO',        color: '#6366f1', bg: '#6366f122' },
    enterprise: { label: 'ENTERPRISE', color: '#10b981', bg: '#10b98122' },
    free:       { label: 'FREE',       color: '#94a3b8', bg: '#94a3b822' },
    reporter:   { label: 'REPORTER',   color: '#38bdf8', bg: '#38bdf822' },
  };
  const s = map[plan?.toLowerCase()] ?? map.free;
  return (
    <span className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider"
      style={{ color: s.color, background: s.bg }}>
      {s.label}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  const isAdmin = role === 'admin';
  return (
    <span className="flex items-center gap-1 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider"
      style={{ color: isAdmin ? '#f59e0b' : '#38bdf8', background: isAdmin ? '#f59e0b22' : '#38bdf822' }}>
      {isAdmin ? <Crown className="w-2.5 h-2.5" /> : <Shield className="w-2.5 h-2.5" />}
      {role || 'user'}
    </span>
  );
}

function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] flex items-center gap-3 px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold"
      style={{ background: type === 'success' ? '#10b981' : '#ef4444', color: '#fff', whiteSpace: 'nowrap' }}
    >
      {type === 'success' ? <Check className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
      {message}
    </motion.div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export const AdminScreen = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  // ── Access guard ──────────────────────────────────────────────────────────
  const [accessChecked, setAccessChecked] = useState(false);
  const [hasAccess, setHasAccess] = useState(false);

  useEffect(() => {
    const checkAccess = async () => {
      if (!user) return false;

      // 1. Immediate sync check via store role or email list
      if (isAdminUser(user)) {
        setHasAccess(true);
        setAccessChecked(true);
        return true;
      }

      // 2. Dynamic check: query profiles table in case role was recently updated
      try {
        const { data } = await supabase
          .from('profiles')
          .select('role')
          .eq('id', user.id)
          .single();

        if (data?.role === 'admin') {
          setHasAccess(true);
          setAccessChecked(true);
          return true;
        }
      } catch {
        /* silent */
      }

      setHasAccess(false);
      setAccessChecked(true);
      return true;
    };

    if (user) {
      checkAccess();
      return;
    }

    // user was null — wait one tick for store hydration then try again
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
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'logos'>('overview');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserProfile[]>([]);
  const [logos, setLogos] = useState<PublicationLogo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<keyof AdminUserProfile>('created_at');
  const [sortAsc, setSortAsc] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Edit user state
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<string>('');
  const [editPlan, setEditPlan] = useState<string>('');
  const [editSaving, setEditSaving] = useState(false);

  // Logo form
  const [showLogoForm, setShowLogoForm] = useState(false);
  const [logoName, setLogoName] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoCode, setLogoCode] = useState('');
  const [logoFormLoading, setLogoFormLoading] = useState(false);
  const [logoFormError, setLogoFormError] = useState('');

  const showToast = (message: string, type: 'success' | 'error') => setToast({ message, type });

  // ── Data fetching ─────────────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, u, l] = await Promise.all([getAdminStats(), getAdminUsers(), getPublicationLogos()]);
      setStats(s);
      setUsers(u);
      setLogos(l);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (hasAccess) fetchAll();
  }, [hasAccess, fetchAll]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleSort = (field: keyof AdminUserProfile) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(true); }
  };

  const filteredUsers = users
    .filter(u =>
      u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      const av = a[sortField] as any;
      const bv = b[sortField] as any;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortAsc ? cmp : -cmp;
    });

  const handleAddLogo = async (e: React.FormEvent) => {
    e.preventDefault();
    setLogoFormError('');
    if (!logoName.trim() || !logoUrl.trim() || !logoCode.trim()) {
      setLogoFormError('All fields are required.');
      return;
    }
    setLogoFormLoading(true);
    const result = await addPublicationLogo(logoName, logoUrl, logoCode);
    setLogoFormLoading(false);
    if (result.success) {
      showToast('Logo added successfully!', 'success');
      setShowLogoForm(false);
      setLogoName(''); setLogoUrl(''); setLogoCode('');
      fetchAll();
    } else {
      setLogoFormError(result.error ?? 'Failed to add logo.');
    }
  };

  const handleToggleLogo = async (id: string, current: boolean) => {
    await toggleLogoActive(id, !current);
    showToast(`Logo ${!current ? 'enabled' : 'disabled'}`, 'success');
    fetchAll();
  };

  const handleDeleteLogo = async (id: string, name: string) => {
    if (!window.confirm(`Delete logo "${name}"? This cannot be undone.`)) return;
    const result = await removePublicationLogo(id);
    if (result.success) {
      showToast('Logo removed.', 'success');
      fetchAll();
    } else {
      showToast('Failed to remove logo.', 'error');
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    logout();
    navigate('/login', { replace: true });
  };

  // ── Edit User ─────────────────────────────────────────────────────────────
  const startEdit = (u: AdminUserProfile) => {
    setEditingUserId(u.id);
    setEditRole(u.role ?? 'user');
    setEditPlan(u.plan ?? 'free');
  };

  const cancelEdit = () => { setEditingUserId(null); };

  const saveEdit = async (u: AdminUserProfile) => {
    setEditSaving(true);
    const [r1, r2] = await Promise.all([
      updateUserRole(u.id, editRole as any),
      updateUserPlan(u.id, editPlan),
    ]);
    setEditSaving(false);
    if (r1.success && r2.success) {
      showToast('User updated!', 'success');
      setEditingUserId(null);
      fetchAll();
    } else {
      showToast(r1.error ?? r2.error ?? 'Failed to update user.', 'error');
    }
  };

  // ── Access Denied ─────────────────────────────────────────────────────────
  if (!accessChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0D1B2A' }}>
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-amber-400 border-t-transparent animate-spin" />
          <p className="text-white/50 text-sm font-semibold">Verifying access…</p>
        </div>
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: '#0D1B2A' }}>
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-center max-w-xs"
        >
          <div className="w-20 h-20 rounded-3xl bg-red-500/10 flex items-center justify-center mx-auto mb-5">
            <Shield className="w-10 h-10 text-red-400" />
          </div>
          <h2 className="text-white text-2xl font-black mb-2">Access Denied</h2>
          <p className="text-white/50 text-sm leading-relaxed mb-6">
            You do not have administrator privileges to access this panel.
          </p>
          <button
            onClick={() => navigate('/', { replace: true })}
            className="w-full py-3 rounded-2xl text-sm font-bold text-white"
            style={{ background: '#CC1E1E' }}
          >
            Go Back to App
          </button>
        </motion.div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ background: '#0D1B2A', fontFamily: "'Inter', sans-serif" }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: '#f59e0b22' }}>
              <Crown className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h1 className="text-white font-black text-lg leading-none">Admin Panel</h1>
              <p className="text-white/40 text-[11px] mt-0.5 font-semibold uppercase tracking-widest">NewsCraft Control Center</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchAll}
              disabled={loading}
              className="w-9 h-9 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
              style={{ background: 'rgba(255,255,255,0.07)' }}
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-white/60 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => navigate('/')}
              className="px-3 py-1.5 rounded-xl text-xs font-bold text-white/60 active:scale-95 transition-transform"
              style={{ background: 'rgba(255,255,255,0.07)' }}
            >
              ← App
            </button>
            <button
              onClick={handleLogout}
              className="w-9 h-9 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
              style={{ background: 'rgba(204,30,30,0.15)' }}
              title="Logout"
            >
              <LogOut className="w-4 h-4 text-red-400" />
            </button>
          </div>
        </div>

        {/* Admin badge */}
        <div className="max-w-5xl mx-auto px-4 pb-3">
          <div className="flex items-center gap-2 text-xs text-white/40">
            <Crown className="w-3 h-3 text-amber-400" />
            <span>Logged in as <span className="text-amber-400 font-bold">{user?.email}</span></span>
            <RoleBadge role="admin" />
          </div>
        </div>
      </header>

      {/* ── Tab Bar ────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="flex gap-2 rounded-2xl p-1" style={{ background: 'rgba(255,255,255,0.04)' }}>
          {([
            { id: 'overview', label: 'Overview', icon: BarChart3 },
            { id: 'users',    label: 'Users',    icon: Users },
            { id: 'logos',    label: 'Logos',    icon: ImageIcon },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all`}
              style={activeTab === tab.id
                ? { background: '#CC1E1E', color: '#fff' }
                : { color: 'rgba(255,255,255,0.45)' }
              }
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content ────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 pb-12">
        <AnimatePresence mode="wait">

          {/* ══ Overview Tab ══════════════════════════════════════════ */}
          {activeTab === 'overview' && (
            <motion.div key="overview" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              {loading ? (
                <div className="grid grid-cols-2 gap-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-28 rounded-2xl animate-pulse" style={{ background: 'rgba(255,255,255,0.05)' }} />
                  ))}
                </div>
              ) : stats ? (
                <>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <StatCard icon={Users}     label="Total Users"       value={stats.totalUsers}              color="#38bdf8" />
                    <StatCard icon={Activity}  label="Active Today"      value={stats.activeUsersToday}        color="#10b981" />
                    <StatCard icon={Newspaper} label="Generated Today"   value={stats.totalGenerationsToday}   color="#f59e0b" />
                    <StatCard icon={BarChart3} label="All-time Gens"     value={stats.totalGenerationsAllTime} color="#a78bfa" />
                  </div>
                  <StatCard icon={ImageIcon}   label="Publication Logos" value={stats.totalLogos}              color="#fb7185" sub="Available in app logo picker" />

                  {/* Quick actions */}
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <button
                      onClick={() => setActiveTab('users')}
                      className="flex items-center gap-2 px-4 py-3 rounded-2xl text-sm font-bold text-white active:scale-95 transition-transform"
                      style={{ background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.2)' }}
                    >
                      <Users className="w-4 h-4 text-sky-400" />
                      Manage Users
                    </button>
                    <button
                      onClick={() => setActiveTab('logos')}
                      className="flex items-center gap-2 px-4 py-3 rounded-2xl text-sm font-bold text-white active:scale-95 transition-transform"
                      style={{ background: 'rgba(251,113,133,0.1)', border: '1px solid rgba(251,113,133,0.2)' }}
                    >
                      <ImageIcon className="w-4 h-4 text-rose-400" />
                      Manage Logos
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-center py-16 text-white/40 text-sm">Failed to load stats.</div>
              )}
            </motion.div>
          )}

          {/* ══ Users Tab ══════════════════════════════════════════════ */}
          {activeTab === 'users' && (
            <motion.div key="users" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              {/* Search bar */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                <input
                  type="text"
                  placeholder="Search by name or email…"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-3 rounded-2xl text-sm text-white placeholder-white/30 outline-none"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2">
                    <X className="w-4 h-4 text-white/40" />
                  </button>
                )}
              </div>

              {loading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-20 rounded-2xl animate-pulse" style={{ background: 'rgba(255,255,255,0.05)' }} />
                  ))}
                </div>
              ) : filteredUsers.length === 0 ? (
                <div className="text-center py-16 text-white/40 text-sm">No users found.</div>
              ) : (
                <div className="space-y-3">
                  {/* Sort row */}
                  <div className="flex items-center gap-3 px-1 mb-1">
                    <span className="text-white/30 text-[10px] font-bold uppercase tracking-widest">Sort by:</span>
                    {(['full_name', 'created_at', 'total_generations'] as const).map(f => (
                      <button
                        key={f}
                        onClick={() => handleSort(f)}
                        className="flex items-center gap-0.5 text-[10px] font-bold uppercase tracking-wider"
                        style={{ color: sortField === f ? '#38bdf8' : 'rgba(255,255,255,0.3)' }}
                      >
                        {f === 'full_name' ? 'Name' : f === 'created_at' ? 'Joined' : 'Gens'}
                        {sortField === f ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : null}
                      </button>
                    ))}
                    <span className="ml-auto text-white/30 text-[10px]">{filteredUsers.length} users</span>
                  </div>

                  {filteredUsers.map((u, idx) => (
                    <motion.div
                      key={u.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      className="rounded-2xl p-4"
                      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}
                    >
                      <div className="flex items-start gap-3">
                        {/* Avatar */}
                        <div className="w-10 h-10 rounded-xl shrink-0 overflow-hidden flex items-center justify-center"
                          style={{ background: 'rgba(255,255,255,0.08)' }}>
                          {u.avatar_url ? (
                            <img src={u.avatar_url} alt={u.full_name} className="w-full h-full object-cover" />
                          ) : (
                            <span className="text-white font-black text-sm">
                              {(u.full_name || u.email || 'U').charAt(0).toUpperCase()}
                            </span>
                          )}
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-white font-bold text-sm truncate">
                              {u.full_name || 'No Name'}
                            </span>
                            <RoleBadge role={u.role ?? 'user'} />
                            <PlanBadge plan={u.plan ?? 'free'} />
                          </div>
                          <p className="text-white/40 text-xs truncate mt-0.5">{u.email}</p>
                          <div className="flex items-center gap-4 mt-2">
                            <div className="flex items-center gap-1">
                              <Newspaper className="w-3 h-3 text-amber-400" />
                              <span className="text-white/60 text-[11px] font-semibold">{u.total_generations} news</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Activity className="w-3 h-3 text-green-400" />
                              <span className="text-white/60 text-[11px] font-semibold">{timeAgo(u.last_sign_in_at)}</span>
                            </div>
                            <div className="flex items-center gap-1 ml-auto">
                              <span className="text-white/30 text-[10px]">Joined {formatDate(u.created_at)}</span>
                            </div>
                          </div>

                          {/* Edit row */}
                          {editingUserId === u.id ? (
                            <div className="mt-3 space-y-2">
                              <div className="flex gap-2">
                                <div className="flex-1">
                                  <label className="block text-[9px] font-bold text-white/40 uppercase tracking-widest mb-1">Role</label>
                                  <select
                                    value={editRole}
                                    onChange={e => setEditRole(e.target.value)}
                                    className="w-full px-2 py-1.5 rounded-lg text-xs text-white outline-none"
                                    style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)' }}
                                  >
                                    <option value="user">User</option>
                                    <option value="reporter">Reporter</option>
                                    <option value="admin">Admin</option>
                                  </select>
                                </div>
                                <div className="flex-1">
                                  <label className="block text-[9px] font-bold text-white/40 uppercase tracking-widest mb-1">Plan</label>
                                  <select
                                    value={editPlan}
                                    onChange={e => setEditPlan(e.target.value)}
                                    className="w-full px-2 py-1.5 rounded-lg text-xs text-white outline-none"
                                    style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)' }}
                                  >
                                    <option value="free">Free</option>
                                    <option value="pro">Pro</option>
                                    <option value="enterprise">Enterprise</option>
                                  </select>
                                </div>
                              </div>
                              <div className="flex gap-2">
                                <button
                                  onClick={() => saveEdit(u)}
                                  disabled={editSaving}
                                  className="flex-1 py-1.5 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1 active:scale-95"
                                  style={{ background: '#10b981' }}
                                >
                                  {editSaving ? <div className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" /> : <><Check className="w-3 h-3" /> Save</>}
                                </button>
                                <button
                                  onClick={cancelEdit}
                                  className="flex-1 py-1.5 rounded-lg text-xs font-bold active:scale-95"
                                  style={{ background: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.5)' }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => startEdit(u)}
                              className="mt-2 px-3 py-1 rounded-lg text-[10px] font-bold active:scale-95 transition-transform"
                              style={{ background: 'rgba(255,255,255,0.07)', color: 'rgba(255,255,255,0.4)' }}
                            >
                              ✏️ Edit Role / Plan
                            </button>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ══ Logos Tab ══════════════════════════════════════════════ */}
          {activeTab === 'logos' && (
            <motion.div key="logos" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>

              {/* Add logo button */}
              <div className="mb-4">
                <button
                  onClick={() => { setShowLogoForm(!showLogoForm); setLogoFormError(''); }}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold text-white active:scale-95 transition-transform"
                  style={{ background: showLogoForm ? 'rgba(255,255,255,0.06)' : '#CC1E1E' }}
                >
                  {showLogoForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                  {showLogoForm ? 'Cancel' : 'Add Publication Logo'}
                </button>
              </div>

              {/* Add logo form */}
              <AnimatePresence>
                {showLogoForm && (
                  <motion.form
                    onSubmit={handleAddLogo}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-4 rounded-2xl overflow-hidden"
                    style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}
                  >
                    <div className="p-4 space-y-3">
                      <p className="text-white/60 text-xs font-bold uppercase tracking-widest mb-1">New Publication Logo</p>

                      {logoFormError && (
                        <div className="flex items-center gap-2 text-xs font-semibold text-red-400 bg-red-500/10 rounded-xl px-3 py-2.5">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          {logoFormError}
                        </div>
                      )}

                      {[
                        { label: 'Publication Name', value: logoName, set: setLogoName, placeholder: 'e.g. Spot News 24x7' },
                        { label: 'Logo Image URL', value: logoUrl, set: setLogoUrl, placeholder: 'https://example.com/logo.png' },
                        { label: 'Unique Code (slug)', value: logoCode, set: setLogoCode, placeholder: 'e.g. spot_news_24x7' },
                      ].map(f => (
                        <div key={f.label}>
                          <label className="block text-[10px] font-bold text-white/40 uppercase tracking-widest mb-1.5">{f.label}</label>
                          <input
                            type="text"
                            value={f.value}
                            onChange={e => f.set(e.target.value)}
                            placeholder={f.placeholder}
                            className="w-full px-4 py-3 rounded-xl text-sm text-white placeholder-white/20 outline-none"
                            style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)' }}
                          />
                        </div>
                      ))}

                      {/* Logo preview */}
                      {logoUrl && (
                        <div className="flex items-center gap-3 p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)' }}>
                          <img
                            src={logoUrl}
                            alt="Preview"
                            className="h-10 w-auto object-contain rounded"
                            onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                          />
                          <span className="text-white/50 text-xs">Logo preview</span>
                        </div>
                      )}

                      <button
                        type="submit"
                        disabled={logoFormLoading}
                        className="w-full py-3 rounded-xl text-sm font-bold text-white flex items-center justify-center gap-2 active:scale-95 transition-transform disabled:opacity-60"
                        style={{ background: '#CC1E1E' }}
                      >
                        {logoFormLoading ? (
                          <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                        ) : (
                          <><Check className="w-4 h-4" /> Save Logo</>
                        )}
                      </button>
                    </div>
                  </motion.form>
                )}
              </AnimatePresence>

              {/* Logo list */}
              {loading ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-20 rounded-2xl animate-pulse" style={{ background: 'rgba(255,255,255,0.05)' }} />
                  ))}
                </div>
              ) : logos.length === 0 ? (
                <div className="text-center py-16">
                  <ImageIcon className="w-10 h-10 text-white/20 mx-auto mb-3" />
                  <p className="text-white/40 text-sm">No logos yet. Add a publication logo above.</p>
                  <p className="text-white/20 text-xs mt-1">Logos added here will appear in the app's logo selector for all users.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-white/30 text-[10px] font-bold uppercase tracking-widest mb-2">{logos.length} Publication{logos.length !== 1 ? 's' : ''}</p>
                  {logos.map((logo, idx) => (
                    <motion.div
                      key={logo.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      className="flex items-center gap-3 p-4 rounded-2xl"
                      style={{
                        background: logo.is_active ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                        border: `1px solid ${logo.is_active ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.04)'}`,
                        opacity: logo.is_active ? 1 : 0.6,
                      }}
                    >
                      {/* Logo thumbnail */}
                      <div className="w-14 h-10 rounded-xl overflow-hidden shrink-0 flex items-center justify-center"
                        style={{ background: 'rgba(255,255,255,0.08)' }}>
                        <img
                          src={logo.logo_url}
                          alt={logo.name}
                          className="h-full w-auto object-contain p-1"
                          onError={e => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-white font-bold text-sm truncate">{logo.name}</p>
                        <p className="text-white/40 text-[10px] font-mono">{logo.publication_code}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${logo.is_active ? 'text-green-400 bg-green-400/10' : 'text-white/30 bg-white/5'}`}>
                            {logo.is_active ? '● Active' : '○ Inactive'}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleToggleLogo(logo.id, logo.is_active)}
                          className="w-8 h-8 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
                          style={{ background: logo.is_active ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.07)' }}
                          title={logo.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {logo.is_active
                            ? <Eye className="w-3.5 h-3.5 text-green-400" />
                            : <EyeOff className="w-3.5 h-3.5 text-white/40" />
                          }
                        </button>
                        <button
                          onClick={() => handleDeleteLogo(logo.id, logo.name)}
                          className="w-8 h-8 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
                          style={{ background: 'rgba(239,68,68,0.12)' }}
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-red-400" />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Info note */}
              <div className="mt-6 rounded-2xl p-4" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)' }}>
                <p className="text-amber-400/80 text-xs font-semibold leading-relaxed">
                  💡 Logos added here appear in the logo selector on the Generate screen for all users.
                  When a publication pays for access, add their logo here to activate it.
                  Toggle active/inactive without deleting.
                </p>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>

      {/* Toast */}
      <AnimatePresence>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </AnimatePresence>
    </div>
  );
};
