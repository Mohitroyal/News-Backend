import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any
from fastapi.responses import RedirectResponse

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.auth.dependencies import get_current_active_user
from app.schemas.all import User as UserSchema, UserCreate, Token, LoginRequest

router = APIRouter()


@router.post("/login", response_model=dict)
def login_access_token(
    db: Session = Depends(get_db), login_data: LoginRequest = None
) -> Any:
    """JSON login — returns a JWT for future requests."""
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Please verify your email address before logging in.",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(user.id, expires_delta=access_token_expires)
    return jsonable_encoder({
        "success": True,
        "data": {
            "token": token,
            "access_token": token,
            "token_type": "bearer",
            "user": user,
        },
        "message": "Login successful",
    })


@router.post("/signup", response_model=dict)
def create_user_signup(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """Create new user with email verification."""
    user = db.query(User).filter(User.email == user_in.email).first()

    full_name = user_in.full_name
    if not full_name and (user_in.firstName or user_in.lastName):
        full_name = f"{user_in.firstName or ''} {user_in.lastName or ''}".strip()

    if user:
        if user.is_active:
            raise HTTPException(
                status_code=400,
                detail="The user with this username already exists in the system",
            )
        else:
            user.hashed_password = security.get_password_hash(user_in.password)
            user.full_name = full_name
            db.commit()
            db_user = user
    else:
        db_user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            full_name=full_name,
            is_active=False,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    token = security.create_access_token(
        subject=f"verify:{db_user.email}",
        expires_delta=timedelta(hours=24),
    )

    try:
        from app.services.email_service import email_service
        email_service.send_verification_email(db_user.email, token)
    except Exception as e:
        print(f"Failed to send verification email: {e}")

    return jsonable_encoder({
        "success": True,
        "data": None,
        "message": "Verification link sent! Please check your email.",
    })


@router.get("/verify", response_model=dict)
def verify_email(
    *,
    db: Session = Depends(get_db),
    token: str,
) -> Any:
    """Verify email link and redirect to production frontend."""
    from jose import jwt, JWTError

    # Use the production frontend URL or fall back to localhost
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    frontend_login_url = f"{frontend_url.rstrip('/')}/login"

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub", "")
        if not sub.startswith("verify:"):
            return RedirectResponse(url=f"{frontend_login_url}?error=invalid_token")
        email = sub.split("verify:")[-1]
    except JWTError:
        return RedirectResponse(url=f"{frontend_login_url}?error=invalid_token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return RedirectResponse(url=f"{frontend_login_url}?error=user_not_found")

    if not user.is_active:
        user.is_active = True
        db.commit()

    return RedirectResponse(url=f"{frontend_login_url}?verified=true")


@router.get("/me", response_model=dict)
def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current user."""
    return jsonable_encoder({
        "success": True,
        "data": current_user,
        "message": "User retrieved successfully",
    })
