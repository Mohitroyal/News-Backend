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
    "baba.journilist@gmail.com",
    "admin@newscraft.ai",
]

SUPER_ADMIN_EMAILS = [
    "mohithroyal16450@gmail.com",
    "baba.journilist@gmail.com",
]
SUPER_ADMIN_PHONES = [
    "9346843889",
    "7668886666",
]
SUPER_ADMIN_EMAIL = "mohithroyal16450@gmail.com"  # backward compatibility reference


def is_superadmin(user_or_email_or_phone: Any) -> bool:
    if not user_or_email_or_phone:
        return False
    email = ""
    phone = ""
    if isinstance(user_or_email_or_phone, str):
        val = user_or_email_or_phone.strip().lower()
        if "@" in val:
            email = val
        else:
            phone = re.sub(r"\D", "", val)
    else:
        email = (getattr(user_or_email_or_phone, "email", "") or "").strip().lower()
        phone = re.sub(r"\D", "", getattr(user_or_email_or_phone, "phone_number", "") or "")

    if email and any(email == e.lower() for e in SUPER_ADMIN_EMAILS):
        return True
    if phone and any(phone.endswith(p) for p in SUPER_ADMIN_PHONES):
        return True
    if email and any(p in email for p in SUPER_ADMIN_PHONES):
        return True
    return False


def verify_superadmin_access(current_user: User):
    if not is_superadmin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required"
        )


def verify_admin_access(current_user: User):
    if is_superadmin(current_user):
        return
    email = (current_user.email or "").lower().strip()
    is_admin_email = email in [e.lower() for e in ADMIN_EMAILS]
    is_admin_plan = (current_user.subscription_plan or "").lower() == "admin"
    if is_admin_email or is_admin_plan:
        return
    # Fallback check: Supabase profiles table
    try:
        admin_sb = get_supabase_admin_client()
        prof = admin_sb.from_("profiles").select("role").eq("id", str(current_user.id)).execute()
        if prof and prof.data and len(prof.data) > 0 and prof.data[0].get("role") == "admin":
            current_user.subscription_plan = "admin"
            return
    except Exception:
        pass
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

    # 1. Fetch ALL users from Supabase auth.users using pagination.
    # Supabase defaults to 50 users per page — must loop to get all users.
    try:
        auth_users = []
        page = 1
        per_page = 1000  # max allowed per request
        while True:
            response = admin_sb.auth.admin.list_users(page=page, per_page=per_page)
            batch = response if isinstance(response, list) else list(response)
            if not batch:
                break
            auth_users.extend(batch)
            if len(batch) < per_page:
                # Last page — no more users
                break
            page += 1
        print(f"[ADMIN] Fetched {len(auth_users)} users from Supabase Auth (pages={page})")
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

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_counts = db.query(
        Clipping.user_id,
        func.count(Clipping.id).label("total_today")
    ).filter(Clipping.created_at >= today_start).group_by(Clipping.user_id).all()
    today_gen_map = {str(r[0]): r[1] for r in today_counts if r[0]}

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
        user_role = "user"
        app_meta = au_data.get("app_metadata") or {}
        if hasattr(app_meta, "model_dump"):
            app_meta = app_meta.model_dump()
        elif not isinstance(app_meta, dict):
            app_meta = {}

        meta_role = (meta.get("role") or app_meta.get("role") or "").lower()

        if email.lower() in [e.lower() for e in ADMIN_EMAILS]:
            user_role = "admin"
        elif (local and (local.subscription_plan or "").lower() == "admin"):
            user_role = "admin"
        elif meta_role in ("admin", "reporter", "user"):
            user_role = meta_role

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
            "generations_today": today_gen_map.get(uid, 0),
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
    Ban or unban a user in Supabase Auth and local DB.
    Only superadmin can perform this action.
    Pass duration="none" to unban. Example: "24h", "72h", "876600h" (100 years).
    """
    verify_superadmin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # Safety check: prevent banning superadmin
    try:
        target_user = admin_sb.auth.admin.get_user_by_id(user_id)
        target_email = getattr(target_raw, "email", "").lower().strip() if target_raw else ""
        if is_superadmin(target_email):
            raise HTTPException(status_code=400, detail="Cannot ban a Superadmin")
    except HTTPException:
        raise
    except Exception:
        pass

    is_unban = req.duration.lower() == "none"
    try:
        if is_unban:
            admin_sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})
            action = "unbanned"
        else:
            admin_sb.auth.admin.update_user_by_id(user_id, {"ban_duration": req.duration})
            action = f"banned for {req.duration}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ban status in Auth: {e}")

    # Also sync is_banned to profiles table
    try:
        admin_sb.from_("profiles").upsert(
            {"id": user_id, "is_banned": not is_unban},
            on_conflict="id"
        ).execute()
    except Exception as e:
        print(f"[ADMIN] Profile ban status update warning: {e}")

    # Also update local db
    try:
        u_uuid = uuid.UUID(user_id)
        loc = db.query(User).filter(User.id == u_uuid).first()
        if loc:
            loc.is_active = is_unban
            db.commit()
    except Exception:
        pass

    return {"success": True, "detail": f"User {user_id} {action}"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Permanently delete a user from Supabase Auth (Layer 1) and the local
    public.users table (Layer 2). Only superadmin can perform this action.
    """
    verify_superadmin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # Safety check: prevent deleting superadmin
    try:
        target_user = admin_sb.auth.admin.get_user_by_id(user_id)
        target_email = getattr(target_raw, "email", "").lower().strip() if target_raw else ""
        if is_superadmin(target_email):
            raise HTTPException(status_code=400, detail="Cannot delete a Superadmin")
    except HTTPException:
        raise
    except Exception:
        pass

    # 1. Delete clippings / foreign key records from local DB first
    try:
        u_uuid = uuid.UUID(user_id)
        db.query(Clipping).filter(Clipping.user_id == u_uuid).delete()
        local_user = db.query(User).filter(User.id == u_uuid).first()
        if local_user:
            db.delete(local_user)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[ADMIN] Local DB user delete warning: {e}")

    # 2. Delete from Supabase profiles and clippings table
    try:
        admin_sb.from_("clippings").delete().eq("user_id", user_id).execute()
        admin_sb.from_("profiles").delete().eq("id", user_id).execute()
    except Exception as e:
        print(f"[ADMIN] Supabase profile delete warning: {e}")

    # 3. Delete from Supabase auth.users
    try:
        admin_sb.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user from Supabase Auth: {e}")

    return {"success": True, "detail": f"User {user_id} deleted permanently"}


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
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    verify_admin_access(current_user)

    # 1. Total users — read from Supabase Auth (Layer 1) for accurate count.
    try:
        admin_sb = get_supabase_admin_client()
        auth_users_page = admin_sb.auth.admin.list_users(page=1, per_page=1)
        total_users = None
        if hasattr(auth_users_page, "total"):
            total_users = auth_users_page.total
        if total_users is None:
            all_users = []
            page = 1
            per_page = 1000
            while True:
                batch = admin_sb.auth.admin.list_users(page=page, per_page=per_page)
                batch_list = batch if isinstance(batch, list) else list(batch)
                if not batch_list:
                    break
                all_users.extend(batch_list)
                if len(batch_list) < per_page:
                    break
                page += 1
            total_users = len(all_users)
    except Exception:
        total_users = db.query(User).count()

    # 2. Start of today (UTC)
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

    # 6. Optional range calculations
    range_gen_count = None
    range_active_users = None
    if from_date or to_date:
        range_q = db.query(Clipping)
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                range_q = range_q.filter(Clipping.created_at >= from_dt)
            except ValueError:
                pass
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
                range_q = range_q.filter(Clipping.created_at < to_dt)
            except ValueError:
                pass
        range_gen_count = range_q.count()
        range_active_users = range_q.with_entities(func.count(func.distinct(Clipping.user_id))).scalar() or 0

    return {
        "totalUsers": total_users,
        "totalGenerationsToday": gen_today_count,
        "totalGenerationsAllTime": gen_all_count,
        "activeUsersToday": active_today_count,
        "rangeGenerations": range_gen_count,
        "rangeActiveUsers": range_active_users,
        "fromDate": from_date,
        "toDate": to_date,
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

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_counts = db.query(
        Clipping.user_id,
        func.count(Clipping.id).label("total_today")
    ).filter(Clipping.created_at >= today_start).group_by(Clipping.user_id).all()
    today_gen_map = {str(r[0]): r[1] for r in today_counts if r[0]}

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
            "generations_today": today_gen_map.get(user_id_str, 0),
            "avatar_url": getattr(u, "avatar_url", "") or "",
            "preferred_language": "English",
            "is_banned": not getattr(u, "is_active", True) if hasattr(u, "is_active") and u.is_active is not None else False,
        })

    return result


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a user's role across all layers:
    1. Supabase Auth user metadata (app_metadata & user_metadata)
    2. Supabase `profiles` table (via service role client — completely bypasses RLS)
    3. Local `public.users` table
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # 1. Fetch existing metadata first so we don't wipe other fields
    existing_app_metadata = {}
    existing_user_metadata = {}
    user_email = ""
    try:
        existing_auth_user = admin_sb.auth.admin.get_user_by_id(user_id)
        raw_user = existing_auth_user.user if hasattr(existing_auth_user, "user") else existing_auth_user
        if raw_user:
            user_email = getattr(raw_user, "email", "") or ""
            raw_app = getattr(raw_user, "app_metadata", None)
            if hasattr(raw_app, "model_dump"):
                existing_app_metadata = raw_app.model_dump() or {}
            elif isinstance(raw_app, dict):
                existing_app_metadata = raw_app
            raw_usr = getattr(raw_user, "user_metadata", None)
            if hasattr(raw_usr, "model_dump"):
                existing_user_metadata = raw_usr.model_dump() or {}
            elif isinstance(raw_usr, dict):
                existing_user_metadata = raw_usr
    except Exception as e:
        print(f"[ADMIN] Warning fetching existing metadata: {e}")

    # 2. Update Supabase Auth user metadata — merge role into existing metadata
    try:
        merged_app_metadata = {**existing_app_metadata, "role": req.role, "plan": req.role if req.role == "admin" else existing_app_metadata.get("plan", "free")}
        merged_user_metadata = {**existing_user_metadata, "role": req.role}
        admin_sb.auth.admin.update_user_by_id(
            user_id,
            {
                "user_metadata": merged_user_metadata,
                "app_metadata": merged_app_metadata,
            },
        )
    except Exception as e:
        print(f"[ADMIN] Warning updating Supabase Auth metadata: {e}")

    # 3. Update Supabase public.profiles table using service role (bypasses RLS)
    try:
        profile_data = {"id": user_id, "role": req.role}
        if user_email:
            profile_data["email"] = user_email
        admin_sb.from_("profiles").upsert(
            profile_data,
            on_conflict="id",
        ).execute()
    except Exception as e:
        print(f"[ADMIN] Warning updating Supabase profiles table: {e}")

    # 4. Update local DB (auto-syncing if user not in public.users yet)
    try:
        u_uuid = uuid.UUID(user_id)
        user = db.query(User).filter(User.id == u_uuid).first()
        if not user:
            try:
                auth_user = admin_sb.auth.admin.get_user_by_id(user_id)
                supa_user = auth_user.user if hasattr(auth_user, "user") else auth_user
                if supa_user:
                    user = _get_or_create_supabase_user(db, supa_user)
            except Exception as e:
                print(f"[ADMIN] Error syncing user to local DB: {e}")

        if user:
            if req.role == "admin":
                user.subscription_plan = "admin"
            elif req.role in ("reporter", "user"):
                # Demote: clear the admin plan back to free if it was admin
                if (user.subscription_plan or "").lower() == "admin":
                    user.subscription_plan = "free"
            db.commit()
    except Exception as e:
        print(f"[ADMIN] Error updating local user: {e}")

    return {"success": True, "detail": f"User {user_id} role updated to {req.role}"}


@router.put("/users/{user_id}/plan")
def update_user_plan(
    user_id: str,
    req: UpdatePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a user's subscription plan across all layers:
    1. Supabase Auth user metadata (app_metadata & user_metadata)
    2. Supabase `profiles` table (via service role client — completely bypasses RLS)
    3. Local `public.users` table
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()

    # 1. Update Supabase Auth user metadata
    try:
        admin_sb.auth.admin.update_user_by_id(
            user_id,
            {
                "user_metadata": {"plan": req.plan},
                "app_metadata": {"plan": req.plan},
            },
        )
    except Exception as e:
        print(f"[ADMIN] Warning updating Supabase Auth metadata: {e}")

    # 2. Update Supabase public.profiles table using service role (bypasses RLS)
    try:
        admin_sb.from_("profiles").upsert(
            {"id": user_id, "plan": req.plan},
            on_conflict="id",
        ).execute()
    except Exception as e:
        print(f"[ADMIN] Warning updating Supabase profiles table: {e}")

    # 3. Update local DB (auto-syncing if user not in public.users yet)
    try:
        u_uuid = uuid.UUID(user_id)
        user = db.query(User).filter(User.id == u_uuid).first()
        if not user:
            try:
                auth_user = admin_sb.auth.admin.get_user_by_id(user_id)
                supa_user = auth_user.user if hasattr(auth_user, "user") else auth_user
                if supa_user:
                    user = _get_or_create_supabase_user(db, supa_user)
            except Exception as e:
                print(f"[ADMIN] Error syncing user to local DB: {e}")

        if user:
            if (user.subscription_plan or "").lower() == "admin" and req.plan != "admin":
                pass  # Keep admin status intact
            else:
                user.subscription_plan = req.plan
                db.commit()
    except Exception as e:
        print(f"[ADMIN] Error updating local user: {e}")

    return {"success": True, "detail": f"User {user_id} plan updated to {req.plan}"}



# ── Generation Logs ───────────────────────────────────────────────────────────

@router.get("/generations")
def get_generation_logs(
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[str] = None,       # filter by specific user
    status: Optional[str] = None,        # filter: completed, failed, processing
    template_id: Optional[str] = None,   # filter by template
    from_date: Optional[str] = None,     # YYYY-MM-DD
    to_date: Optional[str] = None,       # YYYY-MM-DD
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Admin view of ALL clippings across ALL users.
    Shows: who generated it, what headline, which template, when, status, PNG/PDF links.
    Supports pagination and optional filters by user_id, status, template_id, from_date, to_date.
    """
    verify_admin_access(current_user)

    query = db.query(Clipping, User).join(User, Clipping.user_id == User.id)

    # Optional filters
    if user_id:
        try:
            u_uuid = uuid.UUID(user_id)
            query = query.filter(Clipping.user_id == u_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

    if status:
        query = query.filter(Clipping.status == status)

    if template_id:
        query = query.filter(Clipping.template_id == template_id)

    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(Clipping.created_at >= from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Clipping.created_at < to_dt)
        except ValueError:
            pass

    # Total count for pagination
    total = query.count()

    # Paginate, newest first
    skip = (page - 1) * page_size
    rows = query.order_by(Clipping.created_at.desc()).offset(skip).limit(page_size).all()

    results = []
    for clipping, user in rows:
        results.append({
            # Clipping identity
            "id": str(clipping.id),
            "status": clipping.status or "unknown",
            "created_at": clipping.created_at.isoformat() if clipping.created_at else "",

            # Who generated it
            "user_id": str(user.id),
            "user_email": user.email or "",
            "user_name": user.full_name or "",
            "user_plan": user.subscription_plan or "free",

            # What was generated
            "headline": clipping.headline or "",
            "template_id": clipping.template_id or "",
            "language": clipping.language or "en",
            "tone": clipping.tone or "formal",
            "publication_name": clipping.publication_name or "",
            "publication_date": clipping.publication_date or "",
            "layout_columns": clipping.layout_columns,
            "font_family": clipping.font_family or "",
            "image_count": len(clipping.image_urls or []) + (1 if clipping.image_url else 0),

            # Output files
            "png_url": clipping.png_url or "",
            "pdf_url": clipping.pdf_url or "",
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "results": results,
    }


# ── Publication Logos Management ──────────────────────────────────────────────

class CreateLogoRequest(BaseModel):
    name: str
    publication_code: str
    logo_url: str = ""
    is_active: bool = True


class UpdateLogoRequest(BaseModel):
    name: Optional[str] = None
    publication_code: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


DEFAULT_SEEDED_LOGOS = [
    {"name": "Spot News 24x7", "publication_code": "spot_news_24x7", "logo_url": "", "is_active": True},
    {"name": "RTI Express", "publication_code": "rti_express", "logo_url": "", "is_active": True},
    {"name": "Bharath Reporter", "publication_code": "bharath_reporter", "logo_url": "", "is_active": True},
    {"name": "National News 24x7", "publication_code": "national_news", "logo_url": "", "is_active": True},
]


def _seed_logos_if_needed(admin_sb):
    """Seed standard brand publication logos if table is empty"""
    try:
        check = admin_sb.from_("publication_logos").select("id").limit(1).execute()
        if not check.data:
            print("[LOGOS] Seeding initial publication logos...")
            for item in DEFAULT_SEEDED_LOGOS:
                try:
                    admin_sb.from_("publication_logos").insert([item]).execute()
                except Exception as se:
                    print(f"[LOGOS] Seed item warning: {se}")
    except Exception as e:
        print(f"[LOGOS] Auto-seed check warning: {e}")


@router.get("/logos/active")
def get_active_logos() -> Any:
    """
    Public endpoint for reporters and client app:
    Returns only currently ACTIVE publication logos.
    """
    try:
        admin_sb = get_supabase_admin_client()
        _seed_logos_if_needed(admin_sb)
        res = admin_sb.from_("publication_logos").select("*").eq("is_active", True).order("created_at", desc=False).execute()
        return res.data or []
    except Exception as e:
        print(f"[LOGOS] Warning reading active logos: {e}")
        return [l for l in DEFAULT_SEEDED_LOGOS if l.get("is_active")]


@router.get("/logos")
def get_all_logos(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Admin endpoint: Returns all publication logos with their active/inactive status.
    """
    verify_admin_access(current_user)
    try:
        admin_sb = get_supabase_admin_client()
        _seed_logos_if_needed(admin_sb)
        res = admin_sb.from_("publication_logos").select("*").order("created_at", desc=False).execute()
        return res.data or []
    except Exception as e:
        print(f"[LOGOS] Warning reading all logos: {e}")
        return DEFAULT_SEEDED_LOGOS


@router.post("/logos")
def create_logo(
    req: CreateLogoRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Admin endpoint: Create a new publication brand logo.
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()
    clean_code = req.publication_code.strip().lower().replace(" ", "_")
    clean_name = req.name.strip()
    payload = {
        "name": clean_name,
        "publication_code": clean_code,
        "logo_url": req.logo_url.strip(),
        "is_active": req.is_active,
    }
    try:
        res = admin_sb.from_("publication_logos").insert([payload]).execute()
        return {"success": True, "data": res.data[0] if res.data else payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create publication logo: {e}")


@router.put("/logos/{logo_id}")
def update_logo(
    logo_id: str,
    req: UpdateLogoRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Admin endpoint: Update or toggle active/inactive status of a publication logo.
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()
    payload = {}
    if req.name is not None:
        payload["name"] = req.name.strip()
    if req.publication_code is not None:
        payload["publication_code"] = req.publication_code.strip().lower().replace(" ", "_")
    if req.logo_url is not None:
        payload["logo_url"] = req.logo_url.strip()
    if req.is_active is not None:
        payload["is_active"] = req.is_active

    if not payload:
        return {"success": True, "detail": "No fields to update"}

    try:
        # 1. Try update by id
        up_res = admin_sb.from_("publication_logos").update(payload).eq("id", logo_id).execute()
        if up_res.data:
            return {"success": True, "data": up_res.data[0]}

        # 2. Try update by publication_code
        up_res = admin_sb.from_("publication_logos").update(payload).eq("publication_code", logo_id).execute()
        if up_res.data:
            return {"success": True, "data": up_res.data[0]}

        # 3. Try stripped code (e.g. 'pub_rti_express' -> 'rti_express')
        clean_code = logo_id.replace("pub_", "")
        up_res = admin_sb.from_("publication_logos").update(payload).eq("publication_code", clean_code).execute()
        if up_res.data:
            return {"success": True, "data": up_res.data[0]}

        # 4. If not found in database, insert it with the desired active status
        insert_data = {
            "name": req.name or clean_code.replace("_", " ").title(),
            "publication_code": clean_code,
            "logo_url": req.logo_url or "",
            "is_active": req.is_active if req.is_active is not None else True,
        }
        ins_res = admin_sb.from_("publication_logos").insert([insert_data]).execute()
        return {"success": True, "data": ins_res.data[0] if ins_res.data else insert_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update publication logo: {e}")


@router.delete("/logos/{logo_id}")
def delete_logo(
    logo_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Admin endpoint: Delete a publication logo.
    """
    verify_admin_access(current_user)
    admin_sb = get_supabase_admin_client()
    try:
        del_res = admin_sb.from_("publication_logos").delete().eq("id", logo_id).execute()
        if not del_res.data:
            clean_code = logo_id.replace("pub_", "")
            del_res = admin_sb.from_("publication_logos").delete().eq("publication_code", clean_code).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete publication logo: {e}")

