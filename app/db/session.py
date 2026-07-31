import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

db_url = settings.DATABASE_URL or ""
is_testing = "pytest" in sys.modules or "unittest" in sys.modules or os.environ.get("TESTING") == "1"

if is_testing:
    db_url = "sqlite:///./test_temp.db"
else:
    # Normalize postgres schema for SQLAlchemy compatibility
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Supabase Connection Pooler optimization:
    # Auto-switch pooler.supabase.com port 5432 (Session Mode, max 15 clients) to 6543 (Transaction Mode)
    if "pooler.supabase.com" in db_url and ":5432/" in db_url:
        db_url = db_url.replace(":5432/", ":6543/", 1)

    if not db_url:
        print("[WARNING] DATABASE_URL is empty or not set. Falling back to local SQLite.")
        db_url = "sqlite:///./newscraft.db"
    elif "sqlite" not in db_url:
        host = "unknown"
        port = 5432
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            # Test socket connectivity with a short timeout
            socket.create_connection((host, port), timeout=3)
        except Exception as e:
            print(f"[WARNING] PostgreSQL host {host}:{port} is unreachable ({e}). Falling back to local SQLite.")
            db_url = "sqlite:///./newscraft.db"


if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    # Strict connection pool configuration for Supabase / PostgreSQL:
    # pool_size=3, max_overflow=3 keeps max connections per worker <= 6 to avoid EMAXCONNSESSION errors.
    engine = create_engine(
        db_url,
        pool_size=3,
        max_overflow=3,
        pool_recycle=300,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
