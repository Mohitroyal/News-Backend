import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
from app.models.user import User


class Clipping(Base):
    __tablename__ = "clippings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    headline = Column(String, nullable=False)
    article_content = Column(Text, nullable=False)
    content_formatted = Column(JSON)  # AI formatted JSON

    language = Column(String, default="en")
    tone = Column(String, default="formal")
    template_id = Column(String, nullable=False)
    logo_id = Column(String, nullable=True)  # brand identity

    publication_name = Column(String)
    publication_date = Column(String)

    image_url = Column(String)  # Featured image
    image_urls = Column(JSON, default=list)  # Multiple images list
    layout_columns = Column(Integer, default=3)
    font_family = Column(String, default="playfair")
    show_watermark = Column(Boolean, default=True)  # Toggle watermark/logo overlay

    # Custom Editor Layout Data
    custom_layout = Column(JSON, nullable=True)

    # Exported files (Supabase Storage URLs)
    png_url = Column(String)
    pdf_url = Column(String)

    status = Column(String, default="pending")  # pending, processing, completed, failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="clippings")


class CustomTemplate(Base):
    __tablename__ = "custom_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    layout_data = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User")


class Usage(Base):
    __tablename__ = "usage_analytics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    action = Column(String)  # generate, download_png, download_pdf
    meta = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="usage")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    stripe_invoice_id = Column(String, unique=True)
    amount = Column(Integer)
    currency = Column(String, default="usd")
    status = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="payments")
