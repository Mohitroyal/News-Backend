import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    otp_hash = Column(String(255), nullable=False)
    purpose = Column(String(50), default="login", nullable=False, index=True)
    
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False, index=True)
    request_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="otps")

    __table_args__ = (
        Index("idx_otp_phone_purpose_consumed", "phone_number", "purpose", "consumed"),
        Index("idx_otp_phone_created_at", "phone_number", "created_at"),
        Index("idx_otp_expires_consumed", "expires_at", "consumed"),
    )
