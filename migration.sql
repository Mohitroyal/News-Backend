-- ============================================================
-- NewsCraft AI — Production-Safe Supabase Migration Script
-- Run this in the Supabase SQL Editor (Project → SQL Editor)
-- NEVER drops existing tables or columns
-- Uses ADD COLUMN IF NOT EXISTS for safe idempotency
-- ============================================================

-- ── USERS TABLE ───────────────────────────────────────────────
-- Ensure public.users exists and matches the backend model.
-- NOTE: Supabase auth users are in auth.users. This is your
--       application's public.users profile table.

CREATE TABLE IF NOT EXISTS public.users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    full_name   TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    stripe_customer_id  TEXT UNIQUE,
    subscription_id     TEXT,
    subscription_plan   TEXT DEFAULT 'free',
    subscription_status TEXT DEFAULT 'active',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

-- Add missing columns if users table already exists
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS subscription_id TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS subscription_plan TEXT DEFAULT 'free';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Drop deprecated columns (only if safe — remove comment to enable)
-- ALTER TABLE public.users DROP COLUMN IF EXISTS hashed_password;
-- ALTER TABLE public.users DROP COLUMN IF EXISTS is_superuser;
-- ALTER TABLE public.users DROP COLUMN IF EXISTS supabase_id;


-- ── CLIPPINGS TABLE ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.clippings (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES public.users(id) NOT NULL,
    headline          TEXT NOT NULL,
    article_content   TEXT NOT NULL,
    content_formatted JSONB,
    language          TEXT DEFAULT 'en',
    tone              TEXT DEFAULT 'formal',
    template_id       TEXT NOT NULL,
    logo_id           TEXT,
    publication_name  TEXT,
    publication_date  TEXT,
    image_url         TEXT,
    image_urls        JSONB DEFAULT '[]',
    layout_columns    INTEGER DEFAULT 3,
    font_family       TEXT DEFAULT 'playfair',
    custom_layout     JSONB,
    png_url           TEXT,
    pdf_url           TEXT,
    status            TEXT DEFAULT 'pending',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- If clippings table existed with owner_id, rename it safely:
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'clippings'
          AND column_name = 'owner_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'clippings'
          AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.clippings RENAME COLUMN owner_id TO user_id;
        RAISE NOTICE 'Renamed clippings.owner_id → user_id';
    ELSE
        RAISE NOTICE 'clippings.owner_id rename skipped (already done or user_id exists)';
    END IF;
END $$;

-- Add any missing columns to clippings
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS headline TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS article_content TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS content_formatted JSONB;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS tone TEXT DEFAULT 'formal';
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS template_id TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS logo_id TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS publication_name TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS publication_date TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS image_urls JSONB DEFAULT '[]';
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS layout_columns INTEGER DEFAULT 3;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS font_family TEXT DEFAULT 'playfair';
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS custom_layout JSONB;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS png_url TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS pdf_url TEXT;
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
ALTER TABLE public.clippings ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();


-- ── CUSTOM TEMPLATES TABLE ────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.custom_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES public.users(id) NOT NULL,
    name        TEXT NOT NULL,
    layout_data JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Rename owner_id if applicable
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'custom_templates'
          AND column_name = 'owner_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'custom_templates'
          AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.custom_templates RENAME COLUMN owner_id TO user_id;
    END IF;
END $$;


-- ── USAGE ANALYTICS TABLE ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.usage_analytics (
    id         SERIAL PRIMARY KEY,
    user_id    UUID REFERENCES public.users(id) NOT NULL,
    action     TEXT,
    meta       JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.usage_analytics ADD COLUMN IF NOT EXISTS action TEXT;
ALTER TABLE public.usage_analytics ADD COLUMN IF NOT EXISTS meta JSONB;
ALTER TABLE public.usage_analytics ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();


-- ── PAYMENTS TABLE ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.payments (
    id                SERIAL PRIMARY KEY,
    user_id           UUID REFERENCES public.users(id) NOT NULL,
    stripe_invoice_id TEXT UNIQUE,
    amount            INTEGER,
    currency          TEXT DEFAULT 'usd',
    status            TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS stripe_invoice_id TEXT;
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS amount INTEGER;
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'usd';
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();


-- ── ROW LEVEL SECURITY (recommended) ─────────────────────────
-- Enable RLS so users can only access their own rows.
-- Uncomment these if you haven't set up RLS yet.

-- ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.clippings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.custom_templates ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.usage_analytics ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

-- ── Verification Query ────────────────────────────────────────
-- Run after migration to confirm columns exist:

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('users', 'clippings', 'custom_templates', 'usage_analytics', 'payments')
ORDER BY table_name, ordinal_position;
