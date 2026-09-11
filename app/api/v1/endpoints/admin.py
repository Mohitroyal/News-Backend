from typing import Any, List, Optional
from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user import User
from app.models.clipping import Clipping
from app.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    get_supabase_admin_client,
    _get_or_create_supabase_user,
)

router = APIRouter()

ADMIN_EMAILS = [
    "mohithroyal16450@gmail.com",
    "admin@newscraft.ai",
]


def verify_admin_access(current_user: User):
    email = (current_user.email or "").lower().strip()
    is_admin_email = email in [e.lower() for e in ADMIN_EMAILS]
    is_admin_plan = (current_user.subscription_plan or "").lower() == "admin"
    if not (is_admin_email or is_admin_plan):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )


class UpdateRoleRequest(BaseModel):
    role: str


class UpdatePlanRequest(BaseModel):
    plan: str


class BanRequest(BaseModel):
    duration: str = "24h"  # e.g. "24h", "48h", "none" to unban


# ── NEW: Supabase Auth-aware endpoints ────────────────────────────────────────

@router.get("/auth-users")
def get_auth_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    List ALL users from Supabase auth.users (Layer 1), merged with local
    public.users data (plan, generation count). Shows users even if they have
    never called any backend endpoint yet.
    """
    verify_admin_access(current_user)

    admin_sb = get_supabase_admin_client()

    # 1. Fetch all users from Supabase auth.users (paginate up to 1000)
    try:
        auth_response = admin_sb.auth.admin.list_users()
        auth_users = auth_response if isinstance(auth_response, list) else list(auth_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Supabase auth users: {e}")

    # 2. Pull local DB data keyed by UUID string
    local_users = {str(u.id): u for u in db.query(User).all()}

    # 3. Generation counts keyed by UUID string
    gen_counts = db.query(
        Clipping.user_id,
        func.count(Clipping.id).label("total")
    ).group_by(Clipping.user_id).all()
    gen_map = {str(r[0]): r[1] for r in gen_counts if r[0]}

    result = []
    for au in auth_users:
        # Normalise Supabase user object → plain dict
        if hasattr(au, "model_dump"):
            au_data = au.model_dump()
        elif isinstance(au, dict):
            au_data = au
        else:
            au_data = {k: v for k, v in vars(au).items() if not k.startswith("_")}

        uid = str(au_data.get("id", ""))
        email = au_data.get("email") or ""

        # Provider (email, google, etc.)
        identities = au_data.get("identities") or []
        provider = identities[0].get("provider", "email") if identities else "email"

        # User metadata (Google name / avatar)
        raw_meta = au_data.get("user_metadata") or {}
        if hasattr(raw_meta, "model_dump"):
            meta = raw_meta.model_dump()
        elif isinstance(raw_meta, dict):
            meta = raw_meta
        else:
            meta = {}

        avatar_url = meta.get("avatar_url") or meta.get("picture") or ""
        auth_name = meta.get("full_name") or meta.get("name") or ""

        # Merge with local DB row if it exists
        local = local_users.get(uid)
        plan = (local.subscription_plan or "free") if local else "free"
        full_name = (local.full_name or auth_name) if local else auth_name
        is_active = local.is_active if local else True

        # Admin role check
        user_role = "admin" if email.lower() in [e.lower() for e in ADMIN_EMAILS] else "user"
        if local and (local.subscription_plan or "").lower() == "admin":
            user_role = "admin"

        # Ban status
        banned_until = au_data.get("banned_until")

        result.append({
            "id": uid,
            "email": email,
            "full_name": full_name,
            "role": user_role,
            "plan": plan,
            "provider": provider,
            "avatar_url": avatar_url,
            "is_active": is_active,
            "banned_until": banned_until.isoformat() if banned_until and hasattr(banned_until, "isoformat") else banned_until,
            "created_at": au_data.get("created_at", ""),
            "last_sign_in_at": au_data.get("last_sign_in_at", ""),
            "email_confirmed_at": au_data.get("email_confirmed_at"),
            "in_local_db": local is not None,
            "total_generations": gen_map.get(uid, 0),
        })

    # Sort by created_at descending
    result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return result


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: str,
    req: BanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Ban or unban a user in Supabase Auth.
    Pass duration="none" to unban. Example: "24h", "72h", "876600h" (100 years).
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()

    try:
        if req.duration.lower() == "none":
            # Unban: clear ban_duration
            admin_sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})
            action = "unbanned"
        else:
            admin_sb.auth.admin.update_user_by_id(user_id, {"ban_duration": req.duration})
            action = f"banned for {req.duration}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ban status: {e}")

    return {"success": True, "detail": f"User {user_id} {action}"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Permanently delete a user from Supabase Auth (Layer 1) and the local
    public.users table (Layer 2).
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # 1. Delete from local DB first (FK safety)
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    local_user = db.query(User).filter(User.id == u_uuid).first()
    if local_user:
        db.delete(local_user)
        db.commit()

    # 2. Delete from Supabase auth.users
    try:
        admin_sb.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user from Supabase Auth: {e}")

    return {"success": True, "detail": f"User {user_id} deleted from auth and local DB"}


@router.post("/users/{user_id}/sync")
def sync_auth_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Force-sync a Supabase Auth user into the local public.users table.
    Useful for Google / OAuth users who signed up but never called any API.
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # Fetch user from Supabase auth
    try:
        auth_user = admin_sb.auth.admin.get_user_by_id(user_id)
        supa_user = auth_user.user if hasattr(auth_user, "user") else auth_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user from Supabase Auth: {e}")

    if not supa_user:
        raise HTTPException(status_code=404, detail="User not found in Supabase Auth")

    # Upsert into local public.users
    local_user = _get_or_create_supabase_user(db, supa_user)

    return {
        "success": True,
        "detail": f"User {user_id} synced to local DB",
        "user": {
            "id": str(local_user.id),
            "email": local_user.email,
            "full_name": local_user.full_name,
            "plan": local_user.subscription_plan,
        },
    }


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    verify_admin_access(current_user)

    # 1. Total users
    total_users = db.query(User).count()

    # 2. Start of today (UTC & Local tolerance — start of current UTC day)
    now = datetime.utcnow()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 3. Total generations today (clippings created today)
    gen_today_count = db.query(Clipping).filter(
        Clipping.created_at >= start_of_today
    ).count()

    # 4. Total generations all time
    gen_all_count = db.query(Clipping).count()

    # 5. Active users today (distinct users who created clippings today)
    active_today_count = db.query(func.count(func.distinct(Clipping.user_id))).filter(
        Clipping.created_at >= start_of_today
    ).scalar() or 0

    return {
        "totalUsers": total_users,
        "totalGenerationsToday": gen_today_count,
        "totalGenerationsAllTime": gen_all_count,
        "activeUsersToday": active_today_count,
        "totalLogos": 0,
    }


@router.get("/users")
def get_admin_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    verify_admin_access(current_user)

    users = db.query(User).order_by(User.created_at.desc()).all()

    # Subquery / Map for user generation counts
    gen_counts = db.query(
        Clipping.user_id,
        func.count(Clipping.id).label("total")
    ).group_by(Clipping.user_id).all()

    gen_map = {str(r[0]): r[1] for r in gen_counts if r[0]}

    result = []
    for u in users:
        email = (u.email or "").lower()
        user_role = "admin" if email in [e.lower() for e in ADMIN_EMAILS] else "user"
        if (u.subscription_plan or "").lower() == "admin":
            user_role = "admin"

        user_id_str = str(u.id)
        result.append({
            "id": user_id_str,
            "email": u.email or "",
            "full_name": u.full_name or "",
            "role": user_role,
            "plan": u.subscription_plan or "free",
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "last_sign_in_at": None,
            "total_generations": gen_map.get(user_id_str, 0),
            "avatar_url": getattr(u, "avatar_url", "") or "",
            "preferred_language": "English",
        })

    return result


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    verify_admin_access(current_user)
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == u_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.role == "admin":
        user.subscription_plan = "admin"
    db.commit()
    return {"success": True}


@router.put("/users/{user_id}/plan")
def update_user_plan(
    user_id: str,
    req: UpdatePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    verify_admin_access(current_user)
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == u_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.subscription_plan = req.plan
    db.commit()
    return {"success": True}
