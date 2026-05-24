import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.all import TokenPayload

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


def _try_supabase_token(token: str, db: Session):
    """Attempt to verify token as a Supabase JWT using the service role."""
    try:
        from supabase import create_client
        supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
        response = supabase_client.auth.get_user(token)
        if response and response.user:
            return _get_or_create_supabase_user(db, response.user)
    except Exception as e:
        print(f"[AUTH ERROR] _try_supabase_token failed: {e}")
        import traceback; traceback.print_exc()
    return None


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    # ── Path 1: Supabase Google OAuth token ──────────────────────────────────
    # Supabase tokens are significantly longer than local JWTs (~200+ chars)
    if len(token) > 150:
        user = _try_supabase_token(token, db)
        if user:
            return user

    # ── Path 2: Local JWT (email/password login) ──────────────────────────────
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        token_data = TokenPayload(**payload)
        user_uuid = uuid.UUID(token_data.sub)
        user = db.query(User).filter(User.id == user_uuid).first()
        if user:
            return user
    except (JWTError, ValidationError, ValueError, TypeError):
        pass

    # ── Path 3: Short token fallback — still try Supabase ────────────────────
    user = _try_supabase_token(token, db)
    if user:
        return user

    # ── All paths failed ──────────────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user
