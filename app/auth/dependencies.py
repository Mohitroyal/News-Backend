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


def get_supabase_admin_client():
    """
    Returns a Supabase client initialised with the service role key.
    This client has full admin access to auth.users and should only be
    used inside admin-protected endpoints.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase admin client is not configured (missing SUPABASE_SERVICE_ROLE_KEY)",
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def _get_or_create_supabase_user(db: Session, supabase_user) -> User:
    """
    Given a Supabase user object (or dict), sync it to the local public.users table.
    The local user.id is set to the same UUID as the Supabase auth user.id so that
    all foreign-key references (clippings.user_id, etc.) are stable.
    """
    if isinstance(supabase_user, User):
        return supabase_user

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
    app_metadata = (
        data.get("app_metadata")
        or getattr(supabase_user, "app_metadata", {})
        or {}
    )
    meta_role = (
        user_metadata.get("role")
        or app_metadata.get("role")
        or ""
    ).lower()

    phone = (
        data.get("phone")
        or getattr(supabase_user, "phone", None)
        or user_metadata.get("phone_number")
        or user_metadata.get("phone")
        or app_metadata.get("phone_number")
        or app_metadata.get("phone")
        or None
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
        modified = False
        if meta_role == "admin" and (user.subscription_plan or "").lower() != "admin":
            user.subscription_plan = "admin"
            modified = True
        if phone and not user.phone_number:
            user.phone_number = phone
            modified = True
        if modified:
            try:
                db.commit()
                db.refresh(user)
            except Exception:
                db.rollback()
        return user

    # 2. Look up by email (handles case where row was created before UUID sync)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            modified = False
            if meta_role == "admin" and (user.subscription_plan or "").lower() != "admin":
                user.subscription_plan = "admin"
                modified = True
            if phone and not user.phone_number:
                user.phone_number = phone
                modified = True
            # Align the local id with Supabase auth id if they differ
            if user.id != supabase_uuid:
                print(f"[AUTH] Updating local user id {user.id} → {supabase_uuid} for {email}")
                user.id = supabase_uuid
                modified = True
            if modified:
                try:
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
    init_plan = "admin" if meta_role == "admin" else "free"
    new_user = User(
        id=supabase_uuid,
        email=email,
        phone_number=phone,
        full_name=full_name,
        is_active=True,
        subscription_plan=init_plan,
        subscription_status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"[AUTH] Auto-created local user for {email} (id={supabase_uuid}, plan={init_plan}, phone={phone})")
    return new_user



async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Validate either an internal application JWT or a Supabase JWT from Authorization header.
    Returns User instance or Supabase user object.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # 1. Check if token is an internal application JWT (issued by verify-otp)
    if settings.SECRET_KEY:
        try:
            from jose import jwt
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            sub = payload.get("sub")
            if sub:
                try:
                    user_uuid = uuid.UUID(str(sub))
                    user = db.query(User).filter(User.id == user_uuid).first()
                    if user:
                        return user
                except Exception:
                    user = db.query(User).filter((User.phone_number == str(sub)) | (User.email == str(sub))).first()
                    if user:
                        return user
        except Exception:
            # Fall through to Supabase JWT verification
            pass

    # 2. Structural JWT validation (header.payload.signature)
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid JWT format")

    if not supabase:
        raise HTTPException(status_code=401, detail="Token verification failed (Auth service unavailable)")

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
