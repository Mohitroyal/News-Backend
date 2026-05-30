import uuid
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from supabase import create_client

# ── Supabase client (uses anon key to call get_user) ──────────────────────────
if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
else:
    supabase = None


def _get_or_create_supabase_user(db: Session, supabase_user) -> User:
    """
    Given a Supabase user object (or dict), sync it to the local public.users table.
    The local user.id is set to the same UUID as the Supabase auth user.id so that
    all foreign-key references (clippings.user_id, etc.) are stable.
    """
    # Normalise — Supabase SDK returns an object; we may also call this with a dict
    if hasattr(supabase_user, "__dict__"):
        data = supabase_user.__dict__
    else:
        data = supabase_user

    supabase_id_str = data.get("id") or getattr(supabase_user, "id", None)
    email = data.get("email") or getattr(supabase_user, "email", "") or ""
    user_metadata = (
        data.get("user_metadata")
        or getattr(supabase_user, "user_metadata", {})
        or {}
    )

    if not supabase_id_str:
        raise HTTPException(status_code=401, detail="Invalid Supabase user: missing id")

    # Parse UUID
    try:
        supabase_uuid = uuid.UUID(str(supabase_id_str))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Supabase user id format")

    # 1. Look up by primary key (same UUID as Supabase auth)
    user = db.query(User).filter(User.id == supabase_uuid).first()
    if user:
        return user

    # 2. Look up by email (handles case where row was created before UUID sync)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Align the local id with Supabase auth id if they differ
            if user.id != supabase_uuid:
                print(f"[AUTH] Updating local user id {user.id} → {supabase_uuid} for {email}")
                # Update PK — only safe if no FK rows exist yet; otherwise skip
                try:
                    user.id = supabase_uuid
                    db.commit()
                    db.refresh(user)
                except Exception:
                    db.rollback()
            return user

    # 3. Auto-create new user
    full_name = (
        user_metadata.get("full_name")
        or user_metadata.get("name")
        or (email.split("@")[0] if email else "User")
    )
    new_user = User(
        id=supabase_uuid,
        email=email,
        full_name=full_name,
        is_active=True,
        subscription_plan="free",
        subscription_status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"[AUTH] Auto-created local user for {email} (id={supabase_uuid})")
    return new_user


async def get_current_user(request: Request):
    """
    Validate the Supabase JWT from the Authorization header.
    Returns the raw Supabase user object.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    if not supabase:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase client is not configured on the server")
    try:
        response = supabase.auth.get_user(token)
    except Exception as e:
        print(f"[AUTH ERROR] supabase.auth.get_user failed: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")

    if not response or not response.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return response.user


def get_current_active_user(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Convert the Supabase user object into the local SQLAlchemy User model.
    Auto-creates the row in public.users on first login.
    """
    local_user = _get_or_create_supabase_user(db, current_user)
    if not local_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return local_user


def get_current_active_superuser(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    local_user = _get_or_create_supabase_user(db, current_user)
    # No is_superuser column — check subscription plan or email allow-list
    admin_emails = ["admin@newscraft.ai"]
    if local_user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    return local_user
