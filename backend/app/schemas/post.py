from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class PostPublishRequest(BaseModel):
    """Payload sent by mobile client when clicking 'Post on Spot'."""
    clipping_id: Optional[UUID] = None
    headline: str
    content: str
    language: Optional[str] = "te"
    category: Optional[str] = "General"
    location: Optional[str] = None
    png_url: Optional[str] = None
    pdf_url: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = []
    reporter_name: Optional[str] = None
    reporter_avatar: Optional[str] = None
    publication_name: Optional[str] = None


class CommentCreateRequest(BaseModel):
    """Payload to post a comment."""
    content: str


class CommentResponse(BaseModel):
    """Comment item response."""
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    author_name: Optional[str] = "Anonymous"
    author_avatar: Optional[str] = None
    created_at: datetime
    time_ago: Optional[str] = None

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    """Spot Post item with social counters & interaction states."""
    id: UUID
    user_id: UUID
    clipping_id: Optional[UUID] = None
    headline: str
    content: str
    language: str = "te"
    category: str = "General"
    location: Optional[str] = None
    png_url: Optional[str] = None
    pdf_url: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: List[str] = []
    reporter_name: Optional[str] = None
    reporter_avatar: Optional[str] = None
    publication_name: Optional[str] = None

    views_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0

    is_liked_by_me: bool = False
    is_published: bool = True
    is_pinned: bool = False

    created_at: datetime
    time_ago: Optional[str] = None

    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    """Paginated Social Media Feed."""
    posts: List[PostResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class LikeToggleResponse(BaseModel):
    """Response after toggling like on a post."""
    liked: bool
    likes_count: int


class ViewIncrementResponse(BaseModel):
    """Response after recording a post view/impression."""
    views_count: int


class ShareIncrementResponse(BaseModel):
    """Response after recording a share."""
    shares_count: int
