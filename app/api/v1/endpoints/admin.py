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
from app.auth.dependencies import get_current_user, get_current_active_user

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
