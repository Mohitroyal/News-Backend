"""
Migration: Add show_watermark column to clippings table.

Safe database schema migration script. Reads connection parameters
strictly from environment variables or application configuration.
Does not log, store, or expose any credentials.
"""

import os
import sys

# Attempt to load configuration from application settings if available
try:
    from app.core.config import settings
    DATABASE_URL = getattr(settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL")
    SUPABASE_URL = getattr(settings, "SUPABASE_URL", None) or os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None) or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
except Exception:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

SQL = """
ALTER TABLE clippings
ADD COLUMN IF NOT EXISTS show_watermark BOOLEAN DEFAULT TRUE;
"""

def run_migration():
    print("[MIGRATION] Checking database configuration...")
    
    if DATABASE_URL:
        print("[MIGRATION] DATABASE_URL detected — applying migration via PostgreSQL...")
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(SQL)
            print("[MIGRATION] Column 'show_watermark' verified/added successfully!")
            cur.close()
            conn.close()
            return True
        except ImportError:
            print("[MIGRATION] psycopg2 not installed.")
        except Exception as e:
            print(f"[MIGRATION] Direct connection error: {type(e).__name__}")
    
    # Fallback to Supabase Management RPC if service role key is configured
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            import requests
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/exec_sql"
            headers = {
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            }
            res = requests.post(url, headers=headers, json={"query": SQL}, timeout=10)
            if res.status_code in (200, 201, 204):
                print("[MIGRATION] Migration applied via Supabase management endpoint.")
                return True
        except Exception as e:
            print(f"[MIGRATION] Supabase RPC execution error: {type(e).__name__}")

    print("[MIGRATION] Database connection environment variables not set or direct access unavailable.")
    print("[MIGRATION] Please apply SQL in Supabase SQL Editor:")
    print("=" * 60)
    print(SQL.strip())
    print("=" * 60)
    return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
