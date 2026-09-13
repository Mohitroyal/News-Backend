from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class SendOTPRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian phone number (with or without +91/91/0)")

    @field_validator("phone")
    def clean_phone(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Phone number is required")
        cleaned = re.sub(r"[\s\-\(\)\.]+", "", v.strip())
        if not cleaned:
            raise ValueError("Phone number cannot be empty")
        return cleaned


class SendOTPResponse(BaseModel):
    success: bool = True
    message: str = "OTP sent successfully"


class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., description="10-digit Indian phone number")
    otp: str = Field(..., description="6-digit verification code")

    @field_validator("otp")
    def validate_otp(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("OTP is required")
        cleaned = v.strip()
        if not re.match(r"^\d{6}$", cleaned):
            raise ValueError("OTP must be exactly 6 digits")
        return cleaned


class UserResponseData(BaseModel):
    id: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    plan: str = "free"
    is_active: bool = True


class VerifyOTPResponse(BaseModel):
    success: bool = True
    message: str = "OTP verified successfully"
    token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    user: Optional[UserResponseData] = None
