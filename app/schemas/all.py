from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime

# ─── User Schemas ────────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: UUID
    is_active: bool
    subscription_plan: str
    subscription_status: str
    created_at: datetime
    plan: str
    credits: int

    class Config:
        from_attributes = True

# ─── Clipping Schemas ────────────────────────────────────────────
class ClippingBase(BaseModel):
    headline: str
    article_content: str = Field(alias="articleContent")
    language: str = "en"
    tone: str = "formal"
    template_id: str = Field(alias="templateId")
    logo_id: Optional[str] = Field(None, alias="logoId")  # logo/brand identity separate from layout
    image_url: Optional[str] = Field(None, alias="imageUrl")
    image_urls: List[str] = Field(default=[], alias="imageUrls")
    publication_name: str = Field(alias="publicationName")
    publication_date: str = Field(alias="publicationDate")
    layout_columns: int = Field(3, alias="layoutColumns")
    font_family: str = Field("playfair", alias="fontFamily")

    class Config:
        populate_by_name = True

class ClippingCreate(ClippingBase):
    pass

class ClippingUpdate(BaseModel):
    status: Optional[str] = None
    png_url: Optional[str] = None
    pdf_url: Optional[str] = None

class Clipping(BaseModel):
    id: UUID
    owner_id: UUID = Field(alias="userId")
    headline: str
    article_content: str = Field(alias="articleContent")
    language: str
    tone: str
    template_id: str = Field(alias="templateId")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    image_urls: List[str] = Field(default=[], alias="imageUrls")
    png_url: Optional[str] = Field(None, alias="previewUrl") # Map PNG to previewUrl
    pdf_url: Optional[str] = None
    status: str
    layout_columns: int = Field(3, alias="layoutColumns")
    font_family: str = Field("playfair", alias="fontFamily")
    created_at: datetime = Field(alias="createdAt")

    class Config:
        from_attributes = True
        populate_by_name = True

# ─── Auth Schemas ────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
