import uuid
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def _get_or_create_supabase_user(db: Session, supabase_user) -> User:
    """Find existing user by supabase_id or email, or auto-create a new one."""
    # Extract fields safely from supabase user object or dict
    if hasattr(supabase_user, '__dict__'):
        data = supabase_user.__dict__
    else:
        data = supabase_user

    supabase_id = data.get("id") or getattr(supabase_user, "id", None)
    email = data.get("email") or getattr(supabase_user, "email", "") or ""
    user_metadata = data.get("user_metadata") or getattr(supabase_user, "user_metadata", {}) or {}

    # Try by supabase_id first
    if supabase_id:
        user = db.query(User).filter(User.supabase_id == str(supabase_id)).first()
        if user:
            return user

    # Try by email
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if supabase_id and not user.supabase_id:
                user.supabase_id = str(supabase_id)
                db.commit()
                db.refresh(user)
            return user

    # Auto-create a new user from Supabase profile
    full_name = (
        user_metadata.get("full_name")
        or user_metadata.get("name")
        or (email.split("@")[0] if email else "User")
    )
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=full_name,
        supabase_id=str(supabase_id) if supabase_id else None,
        hashed_password=None,
        is_active=True,
        is_superuser=False,
        subscription_plan="free",
        subscription_status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


from supabase import create_client
from fastapi import Request

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

async def get_current_user(request: Request):
    auth = request.headers.get("Authorization")

    if not auth:
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth.replace("Bearer ", "")

    try:
        response = supabase.auth.get_user(token)
    except Exception as e:
        print("[AUTH ERROR] Supabase auth.get_user failed:", e)
        raise HTTPException(status_code=401, detail="Invalid token")

    if not response.user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return response.user


def get_current_active_user(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    local_user = _get_or_create_supabase_user(db, current_user)
    if not local_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return local_user


def get_current_active_superuser(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    local_user = _get_or_create_supabase_user(db, current_user)
    if not local_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return local_user
