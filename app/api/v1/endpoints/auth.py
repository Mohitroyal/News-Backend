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
from app.auth.dependencies import get_current_active_user, get_supabase_admin_client
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
    except Exception as e:
        db.rollback()
        logger.error(f"[OTP_DB_ERROR] Failed to save OTP record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OTP request. Please try again.",
        )

    # Extract ID before network call to avoid lazy-loading checkout
    otp_record_id = otp_record.id

    # 6. Dispatch SMS via MSG91 Flow API
    success, error_msg, request_id = await msg91_service.send_otp(msg91_phone, plain_otp)

    if not success:
        # Mark OTP as consumed / failed so it cannot be used
        try:
            db.query(OTPVerification).filter(OTPVerification.id == otp_record_id).update({"consumed": True})
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
            db.query(OTPVerification).filter(OTPVerification.id == otp_record_id).update({"request_id": str(request_id)[:100]})
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

    SUPER_ADMIN_PHONES = ["9346843889", "7668886666"]
    is_super_admin = any(clean_digits.endswith(p) for p in SUPER_ADMIN_PHONES)

    if not user:
        # Check if user exists by placeholder phone email
        user = db.query(User).filter(User.email == phone_email).first()
        if user:
            user.phone_number = e164_phone
            if is_super_admin:
                user.subscription_plan = "admin"
        else:
            # Create a new User record
            user = User(
                id=uuid.uuid4(),
                phone_number=e164_phone,
                email=phone_email,
                full_name="Super Admin" if is_super_admin else f"User {clean_digits[-4:]}",
                is_active=True,
                subscription_plan="admin" if is_super_admin else "free",
                subscription_status="active",
            )
            db.add(user)
    else:
        if is_super_admin:
            user.subscription_plan = "admin"
            if not user.full_name or user.full_name.startswith("User "):
                user.full_name = "Super Admin"

    user.updated_at = now
    otp_record.user_id = user.id

    # Extract data before commit to prevent lazy-loading DB queries during network calls
    user_id_str = str(user.id)
    user_phone = user.phone_number
    user_email = user.email or phone_email
    user_full_name = user.full_name
    user_plan = getattr(user, 'plan', getattr(user, 'subscription_plan', 'free'))
    user_sub_plan = user.subscription_plan or "free"
    user_is_active = user.is_active if user.is_active is not None else True

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[AUTH_USER_SAVE_ERROR] Failed to persist user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete authentication. Please try again.",
        )

    # Sync mobile OTP user to Supabase Auth (auth.users) so they appear in Supabase Dashboard -> Authentication -> Users
    try:
        admin_sb = get_supabase_admin_client()

        # 1. Check if user already exists in Supabase Auth by ID
        existing_auth_user = None
        try:
            get_res = admin_sb.auth.admin.get_user_by_id(user_id_str)
            existing_auth_user = get_res.user if hasattr(get_res, "user") else get_res
        except Exception:
            existing_auth_user = None

        if not existing_auth_user:
            # Register user directly in Supabase auth.users
            user_attrs = {
                "id": user_id_str,
                "phone": e164_phone,
                "phone_confirm": True,
                "email": user_email,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": user_full_name,
                    "name": user_full_name,
                    "phone_number": e164_phone,
                    "phone": e164_phone,
                },
                "app_metadata": {
                    "provider": "phone",
                    "providers": ["phone"],
                },
            }
            try:
                admin_sb.auth.admin.create_user(user_attrs)
                logger.info(f"[SUPABASE_AUTH_SYNC] Successfully registered mobile user {e164_phone} in Supabase auth.users")
            except Exception as e_create:
                logger.warning(f"[SUPABASE_AUTH_CREATE_WARN] Failed to create in auth.users: {e_create}")
        else:
            # Update user in Supabase auth.users
            try:
                admin_sb.auth.admin.update_user_by_id(
                    user_id_str,
                    {
                        "phone": e164_phone,
                        "phone_confirm": True,
                        "user_metadata": {
                            "full_name": user_full_name,
                            "name": user_full_name,
                            "phone_number": e164_phone,
                            "phone": e164_phone,
                        },
                    },
                )
            except Exception as e_up:
                logger.warning(f"[SUPABASE_AUTH_UPDATE_WARN] Failed to update auth.users: {e_up}")

        # 2. Upsert into public.profiles table
        admin_sb.from_("profiles").upsert(
            {
                "id": user_id_str,
                "email": user_email,
                "full_name": user_full_name,
                "phone_number": user_phone,
                "role": "admin" if is_super_admin else user_sub_plan,
                "plan": user_sub_plan,
                "last_sign_in_at": now.isoformat(),
            },
            on_conflict="id",
        ).execute()
    except Exception as ep:
        logger.warning(f"[SUPABASE_PROFILE_SYNC_WARNING] {ep}")

    # Generate JWT authentication token
    token = create_access_token(subject=user_id_str)

    user_data = UserResponseData(
        id=user_id_str,
        phone_number=user_phone,
        email=user_email,
        full_name=user_full_name,
        plan=user_plan,
        is_active=user_is_active,
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


@router.delete("/me", response_model=dict, status_code=status.HTTP_200_OK)
@router.delete("/me/", response_model=dict, status_code=status.HTTP_200_OK)
@router.post("/delete-account", response_model=dict, status_code=status.HTTP_200_OK)
@router.delete("/delete-account", response_model=dict, status_code=status.HTTP_200_OK)
@router.post("/me/delete", response_model=dict, status_code=status.HTTP_200_OK)
def delete_user_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Permanently delete the current user's account and all their generated content:
    1. Social posts, post likes, comments, and post images.
    2. Newspaper clippings, exported PNG/PDF assets, and custom templates.
    3. Usage analytics, payment references, and OTP verifications.
    4. Local user record from public.users.
    5. Supabase profiles and auth.users entry.
    """
    # Prevent deletion of superadmin accounts
    from app.api.v1.endpoints.admin import is_superadmin
    if is_superadmin(current_user.email) or (current_user.phone_number and is_superadmin(current_user.phone_number)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Superadmin accounts cannot be deleted via self-service deletion."
        )

    user_id_str = str(current_user.id)
    user_uuid = current_user.id

    # 1. Delete all generated content and related records from local database
    try:
        from app.models.post import Post, PostLike, PostComment
        from app.models.clipping import Clipping, CustomTemplate, Usage, Payment
        from app.models.otp import OTPVerification

        # A. Delete user's likes & comments on any posts
        db.query(PostLike).filter(PostLike.user_id == user_uuid).delete(synchronize_session=False)
        db.query(PostComment).filter(PostComment.user_id == user_uuid).delete(synchronize_session=False)

        # B. Delete user's own posts (cascade removes likes & comments on their posts)
        user_posts = db.query(Post).filter(Post.user_id == user_uuid).all()
        for p in user_posts:
            db.delete(p)

        # C. Delete clippings generated by this user
        db.query(Clipping).filter(Clipping.user_id == user_uuid).delete(synchronize_session=False)

        # D. Delete custom templates, usage analytics, OTP verifications
        db.query(CustomTemplate).filter(CustomTemplate.user_id == user_uuid).delete(synchronize_session=False)
        db.query(Usage).filter(Usage.user_id == user_uuid).delete(synchronize_session=False)
        db.query(Payment).filter(Payment.user_id == user_uuid).delete(synchronize_session=False)
        db.query(OTPVerification).filter(OTPVerification.user_id == user_uuid).delete(synchronize_session=False)
        if current_user.phone_number:
            db.query(OTPVerification).filter(OTPVerification.phone_number == current_user.phone_number).delete(synchronize_session=False)

        # E. Delete local user account
        db.delete(current_user)
        db.commit()
        logger.info(f"[ACCOUNT_DELETION] Successfully purged local DB records for user {user_id_str}")
    except Exception as e:
        db.rollback()
        logger.error(f"[ACCOUNT_DELETION_ERROR] Failed to purge local DB records for user {user_id_str}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user content: {str(e)}"
        )

    # 2. Delete from Supabase profiles, posts, clippings tables
    try:
        admin_sb = get_supabase_admin_client()
        try:
            admin_sb.from_("posts").delete().eq("user_id", user_id_str).execute()
        except Exception as ep:
            logger.warning(f"[SUPABASE_POSTS_DELETE_WARN] {ep}")

        try:
            admin_sb.from_("clippings").delete().eq("user_id", user_id_str).execute()
        except Exception as ec:
            logger.warning(f"[SUPABASE_CLIPPINGS_DELETE_WARN] {ec}")

        try:
            admin_sb.from_("profiles").delete().eq("id", user_id_str).execute()
        except Exception as epr:
            logger.warning(f"[SUPABASE_PROFILES_DELETE_WARN] {epr}")

        # 3. Delete from Supabase auth.users
        try:
            admin_sb.auth.admin.delete_user(user_id_str)
            logger.info(f"[ACCOUNT_DELETION] Successfully deleted Supabase Auth user {user_id_str}")
        except Exception as ea:
            logger.warning(f"[SUPABASE_AUTH_DELETE_WARN] {ea}")
    except Exception as esb:
        logger.warning(f"[SUPABASE_ADMIN_CLIENT_WARN] {esb}")

    return {
        "success": True,
        "message": "Your account and all generated content have been permanently deleted.",
        "user_id": user_id_str,
    }
