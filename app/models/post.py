import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Text, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Post(Base):
    """
    Spot Post / Social Media Feed Item.
    Created when a reporter clicks 'Post on Spot'.
    """
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    clipping_id = Column(UUID(as_uuid=True), ForeignKey("clippings.id"), nullable=True, index=True)

    # Post content & metadata
    headline = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String, default="te")
    category = Column(String, default="General", index=True)  # Breaking, Politics, Crime, Sports, Local, etc.
    location = Column(String, nullable=True)  # e.g., Hyderabad, Vijayawada, Guntur

    # Visual assets
    png_url = Column(String, nullable=True)  # Rendered clipping card image URL
    pdf_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)  # Featured image
    image_urls = Column(JSON, default=list)  # Attached images

    # Author / Reporter snapshot for instant feed rendering
    reporter_name = Column(String, nullable=True)
    reporter_avatar = Column(String, nullable=True)
    publication_name = Column(String, nullable=True)

    # Social engagement counters (denormalized for high performance feeds)
    views_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)

    is_published = Column(Boolean, default=True, index=True)
    is_pinned = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    author = relationship("User", backref="posts")
    clipping = relationship("Clipping", backref="spot_posts")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan")


class PostLike(Base):
    """Tracks likes per user and post."""
    __tablename__ = "post_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_user_like"),
    )

    post = relationship("Post", back_populates="likes")
    user = relationship("User")


class PostComment(Base):
    """User comments on a post."""
    __tablename__ = "post_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    author_name = Column(String, nullable=True)
    author_avatar = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    post = relationship("Post", back_populates="comments")
    user = relationship("User")
