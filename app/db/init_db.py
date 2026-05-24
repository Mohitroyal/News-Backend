import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine, Base
from app.models.user import User
from app.models.clipping import Clipping, Usage, Payment

def init_db():
    print("Connecting to Supabase PostgreSQL...")
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        print("[SUCCESS] Database tables created successfully!")
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")

if __name__ == "__main__":
    init_db()
