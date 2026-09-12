-- ====================================================================
-- NewsCraft AI — Production Supabase Row Level Security (RLS) Baseline
-- Enforces SEC-018: Strict multi-tenant isolation across all user tables
-- Run this in Supabase Dashboard -> SQL Editor
-- ====================================================================

-- ── 1. USERS TABLE ──────────────────────────────────────────────────
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;

-- Drop any conflicting older policies
DROP POLICY IF EXISTS "Users can read own profile" ON public.users;
DROP POLICY IF EXISTS "Users can update own profile" ON public.users;
DROP POLICY IF EXISTS "Service role full access on users" ON public.users;

CREATE POLICY "Users can read own profile" ON public.users
    FOR SELECT TO authenticated
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Service role full access on users" ON public.users
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);


-- ── 2. CLIPPINGS TABLE ──────────────────────────────────────────────
ALTER TABLE IF EXISTS public.clippings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can select own clippings" ON public.clippings;
DROP POLICY IF EXISTS "Users can insert own clippings" ON public.clippings;
DROP POLICY IF EXISTS "Users can update own clippings" ON public.clippings;
DROP POLICY IF EXISTS "Users can delete own clippings" ON public.clippings;
DROP POLICY IF EXISTS "Service role full access on clippings" ON public.clippings;

CREATE POLICY "Users can select own clippings" ON public.clippings
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own clippings" ON public.clippings
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own clippings" ON public.clippings
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own clippings" ON public.clippings
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on clippings" ON public.clippings
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);


-- ── 3. CUSTOM TEMPLATES TABLE ───────────────────────────────────────
ALTER TABLE IF EXISTS public.custom_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can select own custom templates" ON public.custom_templates;
DROP POLICY IF EXISTS "Users can insert own custom templates" ON public.custom_templates;
DROP POLICY IF EXISTS "Users can update own custom templates" ON public.custom_templates;
DROP POLICY IF EXISTS "Users can delete own custom templates" ON public.custom_templates;
DROP POLICY IF EXISTS "Service role full access on templates" ON public.custom_templates;

CREATE POLICY "Users can select own custom templates" ON public.custom_templates
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own custom templates" ON public.custom_templates
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own custom templates" ON public.custom_templates
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own custom templates" ON public.custom_templates
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on templates" ON public.custom_templates
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);


-- ── 4. USAGE ANALYTICS & PAYMENTS ───────────────────────────────────
ALTER TABLE IF EXISTS public.usage_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.payments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users select own analytics" ON public.usage_analytics;
DROP POLICY IF EXISTS "Users insert own analytics" ON public.usage_analytics;
DROP POLICY IF EXISTS "Service role full analytics" ON public.usage_analytics;

CREATE POLICY "Users select own analytics" ON public.usage_analytics
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users insert own analytics" ON public.usage_analytics
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full analytics" ON public.usage_analytics
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Users select own payments" ON public.payments;
DROP POLICY IF EXISTS "Service role full payments" ON public.payments;

CREATE POLICY "Users select own payments" ON public.payments
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full payments" ON public.payments
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);


-- ── 5. SPOT COMMUNITY POSTS TABLE ───────────────────────────────────
ALTER TABLE IF EXISTS public.posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view published posts" ON public.posts;
DROP POLICY IF EXISTS "Authors can insert posts" ON public.posts;
DROP POLICY IF EXISTS "Authors can update own posts" ON public.posts;
DROP POLICY IF EXISTS "Authors can delete own posts" ON public.posts;
DROP POLICY IF EXISTS "Service role full access on posts" ON public.posts;

CREATE POLICY "Anyone can view published posts" ON public.posts
    FOR SELECT TO public
    USING (is_published = true OR (auth.uid() IS NOT NULL AND auth.uid() = user_id));

CREATE POLICY "Authors can insert posts" ON public.posts
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Authors can update own posts" ON public.posts
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Authors can delete own posts" ON public.posts
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on posts" ON public.posts
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);


-- ── 6. POST LIKES & COMMENTS ────────────────────────────────────────
ALTER TABLE IF EXISTS public.post_likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.post_comments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public can view likes" ON public.post_likes;
DROP POLICY IF EXISTS "Users can insert own like" ON public.post_likes;
DROP POLICY IF EXISTS "Users can delete own like" ON public.post_likes;
DROP POLICY IF EXISTS "Service role full access likes" ON public.post_likes;

CREATE POLICY "Public can view likes" ON public.post_likes
    FOR SELECT TO public
    USING (true);

CREATE POLICY "Users can insert own like" ON public.post_likes
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own like" ON public.post_likes
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access likes" ON public.post_likes
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Public can view comments" ON public.post_comments;
DROP POLICY IF EXISTS "Users can insert comments" ON public.post_comments;
DROP POLICY IF EXISTS "Authors can delete own comments" ON public.post_comments;
DROP POLICY IF EXISTS "Service role full access comments" ON public.post_comments;

CREATE POLICY "Public can view comments" ON public.post_comments
    FOR SELECT TO public
    USING (true);

CREATE POLICY "Users can insert comments" ON public.post_comments
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Authors can delete own comments" ON public.post_comments
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access comments" ON public.post_comments
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);
