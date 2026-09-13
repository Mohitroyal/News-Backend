import os
import re
import uuid
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.user import User
from app.models.otp import OTPVerification
from app.auth.dependencies import get_current_active_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.schemas.otp import SendOTPRequest, SendOTPResponse, VerifyOTPRequest, VerifyOTPResponse, UserResponseData
from app.services.msg91_service import msg91_service, validate_and_normalize_indian_phone

logger = logging.getLogger("app.api.auth")
router = APIRouter()


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request headers or connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


@router.post("/send-otp", response_model=SendOTPResponse, status_code=status.HTTP_200_OK)
async def send_otp(
    payload: SendOTPRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """
    Send a 6-digit OTP to an Indian mobile number via MSG91 Flow API.
    - Validates Indian phone number format.
    - Rate limits: Max 3 sends per 15 minutes, 60-second cooldown between requests.
    - Generates cryptographically secure 6-digit OTP.
    - Hashes OTP with bcrypt before storing.
    - Dispatches SMS using approved template FOUZIA_OTP (Sender ID: FOUZIA).
    """
    is_valid, e164_phone, msg91_phone = validate_and_normalize_indian_phone(payload.phone)
    if not is_valid or not e164_phone or not msg91_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Indian mobile number. Must be a valid 10-digit number starting with 6, 7, 8, or 9.",
        )

    now = datetime.now(timezone.utc)
    client_ip = _get_client_ip(request)

    # 1. Rate Limiting: Max OTP_SEND_LIMIT requests within OTP_SEND_WINDOW_MINUTES
    window_start = now - timedelta(minutes=settings.OTP_SEND_WINDOW_MINUTES)
    recent_count = (
        db.query(func.count(OTPVerification.id))
        .filter(
            OTPVerification.phone_number == e164_phone,
            OTPVerification.created_at >= window_start,
        )
        .scalar()
        or 0
    )

    if recent_count >= settings.OTP_SEND_LIMIT:
        logger.warning(f"[RATE_LIMIT] Phone {e164_phone[:5]}*** exceeded send limit ({recent_count}/{settings.OTP_SEND_LIMIT})")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "message": f"Too many OTP requests. Maximum {settings.OTP_SEND_LIMIT} requests allowed per {settings.OTP_SEND_WINDOW_MINUTES} minutes. Please try again later.",
            },
        )

    # 2. Cooldown Enforcement: Wait OTP_COOLDOWN_SECONDS between resends
    latest_otp = (
        db.query(OTPVerification)
        .filter(OTPVerification.phone_number == e164_phone)
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if latest_otp and latest_otp.created_at:
        # Normalize latest_otp.created_at to UTC
        created_at_utc = latest_otp.created_at if latest_otp.created_at.tzinfo else latest_otp.created_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = (now - created_at_utc).total_seconds()
        if elapsed_seconds < settings.OTP_COOLDOWN_SECONDS:
            remaining = int(settings.OTP_COOLDOWN_SECONDS - elapsed_seconds)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": f"Please wait {remaining} second(s) before requesting a new OTP.",
                },
            )

    # 3. Invalidate previous active unconsumed OTPs for this phone and purpose
    try:
        db.query(OTPVerification).filter(
            OTPVerification.phone_number == e164_phone,
            OTPVerification.purpose == "login",
            OTPVerification.consumed == False,
        ).update({"consumed": True}, synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[OTP_DB_ERROR] Failed to invalidate old OTPs: {e}")

    # 4. Generate cryptographically secure 6-digit OTP
    plain_otp = "".join(secrets.choice("0123456789") for _ in range(6))

    # 5. Hash OTP with bcrypt (never store plaintext)
    otp_hash = get_password_hash(plain_otp)

    # Check if user already exists
    existing_user = db.query(User).filter(User.phone_number == e164_phone).first()

    expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number=e164_phone,
        user_id=existing_user.id if existing_user else None,
        otp_hash=otp_hash,
        purpose="login",
        attempts=0,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
        consumed=False,
        ip_address=client_ip,
        created_at=now,
        expires_at=expires_at,
    )

    db.add(otp_record)
    try:
        db.commit()
        db.refresh(otp_record)
    except Exception as e:
        db.rollback()
        logger.error(f"[OTP_DB_ERROR] Failed to save OTP record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OTP request. Please try again.",
        )

    # 6. Dispatch SMS via MSG91 Flow API
    success, error_msg, request_id = await msg91_service.send_otp(msg91_phone, plain_otp)

    if not success:
        # Mark OTP as consumed / failed so it cannot be used
        try:
            otp_record.consumed = True
            db.commit()
        except Exception:
            db.rollback()

        logger.error(f"[SMS_FAILED] MSG91 error for {e164_phone[:5]}***: {error_msg}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "message": error_msg or "Failed to deliver OTP SMS. Please verify your phone number and try again.",
            },
        )

    # Update request_id from MSG91 if returned
    if request_id:
        try:
            otp_record.request_id = str(request_id)[:100]
            db.commit()
        except Exception:
            pass

    return {
        "success": True,
        "message": "OTP sent successfully",
    }


@router.post("/verify-otp", response_model=VerifyOTPResponse, status_code=status.HTTP_200_OK)
async def verify_otp(
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Verify 6-digit OTP and authenticate user.
    - Compares submitted OTP against stored bcrypt hash.
    - Enforces 10-minute expiry and max 5 verification attempts.
    - Marks OTP as consumed on success (single-use, prevents replay).
    - Links/creates User profile in database.
    - Issues JWT access token accepted across all backend endpoints.
    """
    is_valid, e164_phone, _ = validate_and_normalize_indian_phone(payload.phone)
    if not is_valid or not e164_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Indian mobile number format.",
        )

    now = datetime.now(timezone.utc)

    # Find the most recent active unconsumed OTP for this phone and purpose
    otp_record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == e164_phone,
            OTPVerification.purpose == "login",
            OTPVerification.consumed == False,
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "No active OTP found for this phone number. Please request a new OTP.",
            },
        )

    # Check Expiration
    expires_at_utc = otp_record.expires_at if otp_record.expires_at.tzinfo else otp_record.expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at_utc:
        otp_record.consumed = True
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "OTP has expired. Please request a new OTP.",
            },
        )

    # Check Max Attempts
    if otp_record.attempts >= otp_record.max_attempts:
        otp_record.consumed = True
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Maximum verification attempts exceeded. Please request a new OTP.",
            },
        )

    # Verify submitted OTP against stored bcrypt hash
    is_correct = verify_password(payload.otp, otp_record.otp_hash)

    if not is_correct:
        otp_record.attempts += 1
        remaining = otp_record.max_attempts - otp_record.attempts
        if remaining <= 0:
            otp_record.consumed = True
            db.commit()
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Invalid OTP. Maximum verification attempts exceeded. Please request a new OTP.",
                },
            )

        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"Invalid OTP. {remaining} attempt(s) remaining.",
            },
        )

    # OTP is correct! Mark consumed immediately to prevent replay
    otp_record.consumed = True
    otp_record.verified_at = now

    # Find or link User in public.users
    user = db.query(User).filter(User.phone_number == e164_phone).first()

    clean_digits = re.sub(r"\D", "", e164_phone)
    phone_email = f"{clean_digits}@phone.user"

    if not user:
        # Check if user exists by placeholder phone email
        user = db.query(User).filter(User.email == phone_email).first()
        if user:
            user.phone_number = e164_phone
        else:
            # Create a new User record
            user = User(
                id=uuid.uuid4(),
                phone_number=e164_phone,
                email=phone_email,
                full_name=f"User {clean_digits[-4:]}",
                is_active=True,
                subscription_plan="free",
                subscription_status="active",
            )
            db.add(user)

    otp_record.user_id = user.id

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"[AUTH_USER_SAVE_ERROR] Failed to persist user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete authentication. Please try again.",
        )

    # Generate JWT authentication token
    token = create_access_token(subject=str(user.id))

    user_data = UserResponseData(
        id=str(user.id),
        phone_number=user.phone_number,
        email=user.email,
        full_name=user.full_name,
        plan=user.plan,
        is_active=user.is_active if user.is_active is not None else True,
    )

    return {
        "success": True,
        "message": "OTP verified successfully",
        "token": token,
        "token_type": "bearer",
        "user": user_data,
    }


# ── Existing Profile Endpoints (Preserved 100% Non-Breaking) ───────────────────

@router.get("/me", response_model=dict)
def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current user profile."""
    return jsonable_encoder({
        "success": True,
        "data": current_user,
        "message": "User retrieved successfully",
    })


@router.patch("/me", response_model=dict)
def update_user_me(
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update current user profile fields."""
    allowed_fields = {"full_name"}
    for field, value in update_data.items():
        if field in allowed_fields:
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return jsonable_encoder({
        "success": True,
        "data": current_user,
        "message": "Profile updated successfully",
    })
