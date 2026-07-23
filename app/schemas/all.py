from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, model_validator
from uuid import UUID
from datetime import datetime
import re

# ─── User Schemas ────────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    full_name: Optional[str] = None

class User(UserBase):
    id: UUID
    is_active: bool
    subscription_plan: str
    subscription_status: str
    created_at: Optional[datetime] = None
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
    logo_id: Optional[str] = Field(None, alias="logoId")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    image_urls: List[str] = Field(default=[], alias="imageUrls")
    publication_name: str = Field(alias="publicationName")
    publication_date: str = Field(alias="publicationDate")
    layout_columns: int = Field(3, alias="layoutColumns")
    font_family: str = Field("playfair", alias="fontFamily")
    show_watermark: bool = Field(True, alias="showWatermark")
    image_layout: Optional[str] = Field("default", alias="imageLayout")
    heading_bg: Optional[str] = Field(None, alias="headingBg")
    border_color: Optional[str] = Field(None, alias="borderColor")
    primary_color: Optional[str] = Field(None, alias="primaryColor")
    show_inner_borders: bool = Field(True, alias="showInnerBorders")

    @model_validator(mode="before")
    @classmethod
    def populate_boolean_toggles(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Check all possible alias keys for watermark / logo mode toggles
            keys_to_check = [
                "showWatermark",
                "show_watermark",
                "logoMode",
                "logo_mode",
                "showLogo",
                "show_logo"
            ]
            for key in keys_to_check:
                if key in data:
                    val = data[key]
                    if isinstance(val, str):
                        if val.lower() in ("false", "0", "off", "no"):
                            data["show_watermark"] = False
                            break
                        elif val.lower() in ("true", "1", "on", "yes"):
                            data["show_watermark"] = True
                            break
                    elif isinstance(val, bool):
                        data["show_watermark"] = val
                        break
                        
            # Check for inner borders toggles
            border_keys = [
                "showInnerBorders",
                "show_inner_borders",
                "innerBorders",
                "inner_borders"
            ]
            for key in border_keys:
                if key in data:
                    val = data[key]
                    if isinstance(val, str):
                        if val.lower() in ("false", "0", "off", "no"):
                            data["show_inner_borders"] = False
                            break
                        elif val.lower() in ("true", "1", "on", "yes"):
                            data["show_inner_borders"] = True
                            break
                    elif isinstance(val, bool):
                        data["show_inner_borders"] = val
                        break

        return data

    @model_validator(mode="before")
    @classmethod
    def extract_custom_layout(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If the frontend passes these fields nested under customLayout or custom_layout
            custom = data.get("customLayout") or data.get("custom_layout")
            if isinstance(custom, dict):
                if "imageLayout" in custom and "image_layout" not in data and "imageLayout" not in data:
                    data["imageLayout"] = custom["imageLayout"]
                elif "image_layout" in custom and "image_layout" not in data and "imageLayout" not in data:
                    data["image_layout"] = custom["image_layout"]
                    
                if "headingBg" in custom and "headingBg" not in data and "heading_bg" not in data:
                    data["headingBg"] = custom["headingBg"]
                elif "heading_bg" in custom and "headingBg" not in data and "heading_bg" not in data:
                    data["headingBg"] = custom["heading_bg"]
                    
                if "borderColor" in custom and "borderColor" not in data and "border_color" not in data:
                    data["borderColor"] = custom["borderColor"]
                elif "border_color" in custom and "borderColor" not in data and "border_color" not in data:
                    data["borderColor"] = custom["border_color"]
                    
                if "primaryColor" in custom and "primaryColor" not in data and "primary_color" not in data:
                    data["primaryColor"] = custom["primaryColor"]
                elif "primary_color" in custom and "primaryColor" not in data and "primary_color" not in data:
                    data["primaryColor"] = custom["primary_color"]
        return data

    @model_validator(mode="before")
    @classmethod
    def clean_human_readable_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Extract Hex codes from color strings (e.g., "Classic Red #CC2222")
            def extract_hex(val: Any) -> Any:
                if isinstance(val, str):
                    match = re.search(r'#(?:[0-9a-fA-F]{3}){1,2}', val)
                    if match:
                        return match.group(0)
                return val

            # Normalize template/logo strings to snake_case (e.g., "Bharath Reporter" -> "bharath_reporter")
            def normalize_slug(val: Any) -> Any:
                if isinstance(val, str):
                    if " " in val or val != val.lower():
                        return val.lower().replace(" ", "_")
                return val

            # Aggressively extract colors from ANY possible key the frontend might be sending
            heading_keys = ["headingBg", "heading_bg", "headlineBg", "headline_bg", "headingColor", "headlineColor", "bg_color", "bgColor"]
            for key in heading_keys:
                if key in data and data[key]:
                    val = extract_hex(data[key])
                    data["headingBg"] = val
                    data["heading_bg"] = val
                    break
                    
            border_keys = ["borderColor", "border_color", "borderBg"]
            for key in border_keys:
                if key in data and data[key]:
                    val = extract_hex(data[key])
                    data["borderColor"] = val
                    data["border_color"] = val
                    break

            primary_keys = ["primaryColor", "primary_color", "textColor", "text_color"]
            for key in primary_keys:
                if key in data and data[key]:
                    val = extract_hex(data[key])
                    data["primaryColor"] = val
                    data["primary_color"] = val
                    break

            # Process customLayout just in case it is nested
            custom = data.get("customLayout") or data.get("custom_layout")
            if isinstance(custom, dict):
                for key in heading_keys:
                    if key in custom and custom[key]:
                        val = extract_hex(custom[key])
                        custom["headingBg"] = val
                        custom["heading_bg"] = val
                        data["headingBg"] = val
                        data["heading_bg"] = val
                        break
                for key in border_keys:
                    if key in custom and custom[key]:
                        val = extract_hex(custom[key])
                        custom["borderColor"] = val
                        custom["border_color"] = val
                        data["borderColor"] = val
                        data["border_color"] = val
                        break
                for key in primary_keys:
                    if key in custom and custom[key]:
                        val = extract_hex(custom[key])
                        custom["primaryColor"] = val
                        custom["primary_color"] = val
                        data["primaryColor"] = val
                        data["primary_color"] = val
                        break

        return data

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
    user_id: UUID = Field(alias="userId")
    headline: str
    article_content: str = Field(alias="articleContent")
    language: str
    tone: str
    template_id: str = Field(alias="templateId")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    image_urls: List[str] = Field(default=[], alias="imageUrls")
    png_url: Optional[str] = Field(None, alias="previewUrl")
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

# ─── Login/Signup (local) — kept for backward compat ─────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
