import { supabase } from '@/lib/supabase';
import api from '@/lib/axios';

// ─── Types ────────────────────────────────────────────────────────────────────
export interface AdminUserProfile {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'reporter' | 'user';
  plan: string;
  created_at: string;
  last_sign_in_at?: string;
  total_generations: number;
  avatar_url?: string;
  preferred_language?: string;
}

export interface PublicationLogo {
  id: string;
  name: string;
  logo_url: string;
  publication_code: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminStats {
  totalUsers: number;
  totalGenerationsToday: number;
  totalGenerationsAllTime: number;
  activeUsersToday: number;
  totalLogos: number;
}

// ─── Role Check ───────────────────────────────────────────────────────────────
export const getUserRole = async (userId: string): Promise<string | null> => {
  try {
    // Check profiles table first (has role column)
    const { data, error } = await supabase
      .from('profiles')
      .select('role')
      .eq('id', userId)
      .single();
    if (!error && data?.role) return data.role;

    // Fallback: check users table
    const { data: userData } = await supabase
      .from('users')
      .select('id')
      .eq('id', userId)
      .single();
    return userData ? 'user' : null;
  } catch {
    return null;
  }
};

// ─── Stats ────────────────────────────────────────────────────────────────────
export const getAdminStats = async (): Promise<AdminStats> => {
  // 1. Try Backend API first for full database accurate stats
  try {
    const res = await api.get('/api/v1/admin/stats');
    if (res.data && typeof res.data.totalUsers === 'number') {
      const logosRes = await supabase.from('publication_logos').select('id', { count: 'exact', head: true });
      return {
        totalUsers: res.data.totalUsers,
        totalGenerationsToday: res.data.totalGenerationsToday ?? 0,
        totalGenerationsAllTime: res.data.totalGenerationsAllTime ?? 0,
        activeUsersToday: res.data.activeUsersToday ?? 0,
        totalLogos: logosRes.count ?? res.data.totalLogos ?? 0,
      };
    }
  } catch (err) {
    console.warn('[AdminService] Backend stats endpoint unavailable, falling back to Supabase client query:', err);
  }

  // 2. Fallback: Supabase Client Query
  try {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
    const todayISO = todayStart.toISOString();

    const [
      usersRes,
      profilesRes,
      logosRes,
      genTodayRes,
      genAllRes,
    ] = await Promise.all([
      supabase.from('users').select('id', { count: 'exact', head: true }),
      supabase.from('profiles').select('id', { count: 'exact', head: true }),
      supabase.from('publication_logos').select('id', { count: 'exact', head: true }),
      supabase
        .from('clippings')
        .select('id', { count: 'exact', head: true })
        .gte('created_at', todayISO),
      supabase
        .from('clippings')
        .select('id', { count: 'exact', head: true }),
    ]);

    const { data: activeTodayData } = await supabase
      .from('clippings')
      .select('user_id')
      .gte('created_at', todayISO);

    const uniqueActiveToday = new Set(
      (activeTodayData ?? []).map((r: any) => r.user_id).filter(Boolean)
    ).size;

    const totalUsersCount = Math.max(usersRes.count ?? 0, profilesRes.count ?? 0);

    return {
      totalUsers: totalUsersCount,
      totalGenerationsToday: genTodayRes.count ?? 0,
      totalGenerationsAllTime: genAllRes.count ?? 0,
      activeUsersToday: uniqueActiveToday,
      totalLogos: logosRes.count ?? 0,
    };
  } catch {
    return {
      totalUsers: 0,
      totalGenerationsToday: 0,
      totalGenerationsAllTime: 0,
      activeUsersToday: 0,
      totalLogos: 0,
    };
  }
};

// ─── Users ────────────────────────────────────────────────────────────────────
export const getAdminUsers = async (): Promise<AdminUserProfile[]> => {
  // 1. Try Backend API first
  try {
    const res = await api.get('/api/v1/admin/users');
    if (Array.isArray(res.data) && res.data.length > 0) {
      return res.data;
    }
  } catch (err) {
    console.warn('[AdminService] Backend users endpoint unavailable, falling back to Supabase client query:', err);
  }

  // 2. Fallback: Supabase Client Query
  try {
    const [{ data: users }, { data: profiles }, { data: genData }] = await Promise.all([
      supabase.from('users').select('id, email, full_name, avatar_url, created_at, preferred_language').order('created_at', { ascending: false }),
      supabase.from('profiles').select('id, role, plan, last_sign_in_at'),
      supabase.from('clippings').select('user_id'),
    ]);

    const profileMap: Record<string, any> = {};
    (profiles ?? []).forEach((p: any) => { profileMap[p.id] = p; });

    const genCountMap: Record<string, number> = {};
    (genData ?? []).forEach((row: any) => {
      if (row.user_id) genCountMap[row.user_id] = (genCountMap[row.user_id] ?? 0) + 1;
    });

    const userMap = new Map<string, AdminUserProfile>();

    (users ?? []).forEach((u: any) => {
      userMap.set(u.id, {
        id: u.id,
        email: u.email ?? '',
        full_name: u.full_name ?? '',
        avatar_url: u.avatar_url ?? '',
        created_at: u.created_at ?? '',
        preferred_language: u.preferred_language ?? 'English',
        role: profileMap[u.id]?.role ?? 'user',
        plan: profileMap[u.id]?.plan ?? 'free',
        last_sign_in_at: profileMap[u.id]?.last_sign_in_at,
        total_generations: genCountMap[u.id] ?? 0,
      });
    });

    // Also include any profiles not in users table
    (profiles ?? []).forEach((p: any) => {
      if (!userMap.has(p.id)) {
        userMap.set(p.id, {
          id: p.id,
          email: p.email ?? '',
          full_name: p.full_name ?? 'User',
          avatar_url: '',
          created_at: p.created_at ?? '',
          preferred_language: 'English',
          role: p.role ?? 'user',
          plan: p.plan ?? 'free',
          last_sign_in_at: p.last_sign_in_at,
          total_generations: genCountMap[p.id] ?? 0,
        });
      }
    });

    return Array.from(userMap.values());
  } catch {
    return [];
  }
};

// ─── Edit User Role / Plan ────────────────────────────────────────────────────
export const updateUserRole = async (
  userId: string,
  role: 'admin' | 'reporter' | 'user'
): Promise<{ success: boolean; error?: string }> => {
  try {
    await api.put(`/api/v1/admin/users/${userId}/role`, { role });
  } catch {
    /* backend optional */
  }

  try {
    const { error } = await supabase
      .from('profiles')
      .upsert({ id: userId, role }, { onConflict: 'id' });
    if (error) return { success: false, error: error.message };
    return { success: true };
  } catch (e: any) {
    return { success: false, error: e?.message ?? 'Unknown error' };
  }
};

export const updateUserPlan = async (
  userId: string,
  plan: string
): Promise<{ success: boolean; error?: string }> => {
  try {
    await api.put(`/api/v1/admin/users/${userId}/plan`, { plan });
  } catch {
    /* backend optional */
  }

  try {
    const { error } = await supabase
      .from('profiles')
      .upsert({ id: userId, plan }, { onConflict: 'id' });
    if (error) return { success: false, error: error.message };
    return { success: true };
  } catch (e: any) {
    return { success: false, error: e?.message ?? 'Unknown error' };
  }
};

// ─── Publication Logos ────────────────────────────────────────────────────────
export const getPublicationLogos = async (): Promise<PublicationLogo[]> => {
  try {
    const { data, error } = await supabase
      .from('publication_logos')
      .select('*')
      .order('created_at', { ascending: true });
    if (error) return [];
    return data ?? [];
  } catch {
    return [];
  }
};

export const addPublicationLogo = async (
  name: string,
  logo_url: string,
  publication_code: string
): Promise<{ success: boolean; error?: string }> => {
  try {
    const { error } = await supabase.from('publication_logos').insert([
      {
        name: name.trim(),
        logo_url: logo_url.trim(),
        publication_code: publication_code.trim().toLowerCase().replace(/\s+/g, '_'),
      },
    ]);
    if (error) return { success: false, error: error.message };
    return { success: true };
  } catch (e: any) {
    return { success: false, error: e?.message ?? 'Unknown error' };
  }
};

export const toggleLogoActive = async (
  id: string,
  is_active: boolean
): Promise<{ success: boolean }> => {
  try {
    const { error } = await supabase
      .from('publication_logos')
      .update({ is_active })
      .eq('id', id);
    return { success: !error };
  } catch {
    return { success: false };
  }
};

export const removePublicationLogo = async (id: string): Promise<{ success: boolean }> => {
  try {
    const { error } = await supabase.from('publication_logos').delete().eq('id', id);
    return { success: !error };
  } catch {
    return { success: false };
  }
};

// ─── Activity Logger ──────────────────────────────────────────────────────────
export const logUserActivity = async (
  userId: string,
  email: string,
  name: string,
  action: 'login' | 'generate' | 'export'
): Promise<void> => {
  try {
    await supabase.from('user_activity').insert([
      { user_id: userId, user_email: email, user_name: name, action },
    ]);
  } catch {
    /* silent */
  }
};
