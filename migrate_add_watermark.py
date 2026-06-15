"""
Migration: Add show_watermark column to clippings table.

Run this script to add the show_watermark boolean column to your Supabase
PostgreSQL database. It uses the Supabase Management API (SQL endpoint).

Usage:
    python migrate_add_watermark.py

Requires environment variables:
    SUPABASE_URL         - Your Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Your Supabase service role key (NOT anon key)
"""

import os
import sys
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    print("Set them before running:")
    print('  $env:SUPABASE_URL = "https://your-project.supabase.co"')
    print('  $env:SUPABASE_SERVICE_ROLE_KEY = "eyJ..."')
    sys.exit(1)

SQL = """
ALTER TABLE clippings
ADD COLUMN IF NOT EXISTS show_watermark BOOLEAN DEFAULT TRUE;
"""

print(f"[MIGRATION] Connecting to Supabase: {SUPABASE_URL}")
print(f"[MIGRATION] Running SQL: {SQL.strip()}")

url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

# Try the direct PostgREST approach first - run via pg raw SQL
# Supabase doesn't expose exec_sql by default, so we use the SQL Editor endpoint
url_sql = f"{SUPABASE_URL}/rest/v1/"

# Alternative: use psycopg2 via DATABASE_URL if available
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    print("[MIGRATION] DATABASE_URL found — using direct PostgreSQL connection...")
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        print("[MIGRATION] ✅ Column 'show_watermark' added successfully!")
        cur.close()
        conn.close()
        sys.exit(0)
    except ImportError:
        print("[MIGRATION] psycopg2 not installed. Trying pip install...")
        os.system(f"{sys.executable} -m pip install psycopg2-binary")
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        print("[MIGRATION] ✅ Column 'show_watermark' added successfully!")
        cur.close()
        conn.close()
        sys.exit(0)
    except Exception as e:
        print(f"[MIGRATION] Direct connection failed: {e}")
        print("[MIGRATION] Please run the SQL manually in Supabase SQL Editor:")
        print()
        print(SQL)
        sys.exit(1)
else:
    print("[MIGRATION] No DATABASE_URL found.")
    print("[MIGRATION] Please run this SQL in your Supabase SQL Editor:")
    print()
    print("=" * 60)
    print(SQL.strip())
    print("=" * 60)
    print()
    print("Go to: https://supabase.com/dashboard → SQL Editor → New Query → Paste & Run")
    sys.exit(0)
