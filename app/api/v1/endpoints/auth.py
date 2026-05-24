import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Any

from app.db.session import get_db
from app.models.user import User
from app.auth.dependencies import get_current_active_user
from app.schemas.all import User as UserSchema
from app.core.config import settings

router = APIRouter()


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
