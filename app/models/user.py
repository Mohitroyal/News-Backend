import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    
    # Supabase Auth Link
    supabase_id = Column(String, unique=True, index=True)
    
    # Subscriptions
    stripe_customer_id = Column(String, unique=True, nullable=True)
    subscription_id = Column(String, nullable=True)
    subscription_plan = Column(String, default="free") # free, pro, enterprise
    subscription_status = Column(String, default="active")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    clippings = relationship("Clipping", back_populates="owner")
    payments = relationship("Payment", back_populates="user")
    usage = relationship("Usage", back_populates="user")

    @property
    def plan(self) -> str:
        return self.subscription_plan or "free"

    @property
    def credits(self) -> int:
        if self.subscription_plan == "pro":
            return 100
        elif self.subscription_plan == "enterprise":
            return 99999
        return 5

