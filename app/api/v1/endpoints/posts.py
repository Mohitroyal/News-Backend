import uuid
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User
from app.models.clipping import Clipping
from app.models.post import Post, PostLike, PostComment
from app.schemas.post import (
    PostPublishRequest,
    PostResponse,
    FeedResponse,
    CommentCreateRequest,
    CommentResponse,
    LikeToggleResponse,
    ViewIncrementResponse,
    ShareIncrementResponse,
)
from app.auth.dependencies import get_current_active_user, get_current_user, _get_or_create_supabase_user

router = APIRouter()


def _format_time_ago(dt: Optional[datetime]) -> str:
    """Format datetime into a clean relative time string (e.g., 'Just now', '5m ago', '2h ago', '3d ago')."""
    if not dt:
        return ""
    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days}d ago"
    else:
        return dt.strftime("%d %b %Y")


async def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Optional auth for public feed: returns User if valid Bearer token provided, else None."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    try:
        from app.auth.dependencies import supabase
        token = auth.removeprefix("Bearer ").strip()
        if not supabase or not token:
            return None
        res = supabase.auth.get_user(token)
        if res and res.user:
            return _get_or_create_supabase_user(db, res.user)
    except Exception:
        pass
    return None


def _build_post_response(post: Post, current_user_id: Optional[uuid.UUID] = None, is_liked: Optional[bool] = None) -> PostResponse:
    """Helper to convert SQLAlchemy Post model to PostResponse schema."""
    if is_liked is None and current_user_id and post.likes:
        is_liked = any(like.user_id == current_user_id for like in post.likes)
    elif is_liked is None:
        is_liked = False

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        clipping_id=post.clipping_id,
        headline=post.headline,
        content=post.content,
        language=post.language or "te",
        category=post.category or "General",
        location=post.location,
        png_url=post.png_url,
        pdf_url=post.pdf_url,
        image_url=post.image_url,
        image_urls=post.image_urls or [],
        reporter_name=post.reporter_name or (post.author.full_name if post.author else "Reporter"),
        reporter_avatar=post.reporter_avatar,
        publication_name=post.publication_name or "RTI Express",
        views_count=post.views_count or 0,
        likes_count=post.likes_count or 0,
        comments_count=post.comments_count or 0,
        shares_count=post.shares_count or 0,
        is_liked_by_me=bool(is_liked),
        is_published=post.is_published,
        is_pinned=post.is_pinned,
        created_at=post.created_at,
        time_ago=_format_time_ago(post.created_at),
    )


# ── [1] POST ON SPOT (PUBLISH CLIPPING) ──────────────────────────────────────
@router.post("/publish", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def publish_to_spot(
    payload: PostPublishRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Publish a newspaper clipping to the public 'Spot News' community feed.
    Triggered when the user/reporter clicks 'Post on Spot'.
    """
    # If clipping_id provided, verify ownership or fallback image data
    png_url = payload.png_url
    pdf_url = payload.pdf_url
    image_url = payload.image_url
    image_urls = payload.image_urls or []

    if payload.clipping_id:
        clipping = db.query(Clipping).filter(Clipping.id == payload.clipping_id).first()
        if clipping:
            png_url = png_url or clipping.png_url
            pdf_url = pdf_url or clipping.pdf_url
            image_url = image_url or clipping.image_url
            image_urls = image_urls or (clipping.image_urls if isinstance(clipping.image_urls, list) else [])

    new_post = Post(
        id=uuid.uuid4(),
        user_id=current_user.id,
        clipping_id=payload.clipping_id,
        headline=payload.headline,
        content=payload.content,
        language=payload.language or "te",
        category=payload.category or "General",
        location=payload.location,
        png_url=png_url,
        pdf_url=pdf_url,
        image_url=image_url,
        image_urls=image_urls,
        reporter_name=payload.reporter_name or current_user.full_name or "Reporter",
        reporter_avatar=payload.reporter_avatar,
        publication_name=payload.publication_name or "RTI Express",
        views_count=0,
        likes_count=0,
        comments_count=0,
        shares_count=0,
        is_published=True,
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return _build_post_response(new_post, current_user_id=current_user.id, is_liked=False)


# ── [2] SOCIAL MEDIA FEED STREAM ─────────────────────────────────────────────
@router.get("/feed", response_model=FeedResponse)
def get_spot_feed(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category (e.g. Breaking, Politics, Crime, Sports)"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    location: Optional[str] = Query(None, description="Filter by district/city"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by reporter user ID"),
    optional_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Get the public 'Spot News' social media community feed.
    Returns posts with realtime likes/comments counts and personalized is_liked status.
    """
    query = db.query(Post).filter(Post.is_published == True)

    if category and category.lower() != "all":
        query = query.filter(Post.category.ilike(category))
    if language:
        query = query.filter(Post.language == language)
    if location:
        query = query.filter(Post.location.ilike(f"%{location}%"))
    if user_id:
        query = query.filter(Post.user_id == user_id)

    total = query.count()
    offset = (page - 1) * limit
    posts = query.order_by(Post.is_pinned.desc(), desc(Post.created_at)).offset(offset).limit(limit).all()

    # Pre-fetch user's liked post IDs in one query to avoid N+1 queries
    liked_post_ids = set()
    if optional_user and posts:
        post_ids = [p.id for p in posts]
        likes = db.query(PostLike.post_id).filter(
            PostLike.user_id == optional_user.id,
            PostLike.post_id.in_(post_ids)
        ).all()
        liked_post_ids = {like[0] for like in likes}

    current_uid = optional_user.id if optional_user else None
    items = [
        _build_post_response(p, current_user_id=current_uid, is_liked=(p.id in liked_post_ids))
        for p in posts
    ]

    has_more = (offset + limit) < total

    return FeedResponse(
        posts=items,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more,
    )


# ── [3] GET SINGLE POST ──────────────────────────────────────────────────────
@router.get("/{post_id}", response_model=PostResponse)
def get_post_detail(
    post_id: uuid.UUID,
    optional_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get single spot post with full engagement details."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    is_liked = False
    if optional_user:
        is_liked = db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == optional_user.id
        ).first() is not None

    return _build_post_response(post, current_user_id=(optional_user.id if optional_user else None), is_liked=is_liked)


# ── [4] TOGGLE LIKE / UNLIKE ─────────────────────────────────────────────────
@router.post("/{post_id}/like", response_model=LikeToggleResponse)
def toggle_like_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Toggle like/unlike on a post (Instagram style).
    If liked -> unlikes and decrements counter.
    If not liked -> likes and increments counter.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_like = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == current_user.id
    ).first()

    if existing_like:
        db.delete(existing_like)
        post.likes_count = max(0, (post.likes_count or 1) - 1)
        db.commit()
        return LikeToggleResponse(liked=False, likes_count=post.likes_count)
    else:
        new_like = PostLike(
            id=uuid.uuid4(),
            post_id=post_id,
            user_id=current_user.id,
        )
        db.add(new_like)
        post.likes_count = (post.likes_count or 0) + 1
        db.commit()
        return LikeToggleResponse(liked=True, likes_count=post.likes_count)


# ── [5] RECORD VIEW / IMPRESSION ─────────────────────────────────────────────
@router.post("/{post_id}/view", response_model=ViewIncrementResponse)
def record_post_view(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Record an impression / view counter on a post (Way2News style)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.views_count = (post.views_count or 0) + 1
    db.commit()
    return ViewIncrementResponse(views_count=post.views_count)


# ── [6] RECORD SHARE ─────────────────────────────────────────────────────────
@router.post("/{post_id}/share", response_model=ShareIncrementResponse)
def record_post_share(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Record a share event (e.g. WhatsApp share)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.shares_count = (post.shares_count or 0) + 1
    db.commit()
    return ShareIncrementResponse(shares_count=post.shares_count)


# ── [7] GET COMMENTS ─────────────────────────────────────────────────────────
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_post_comments(
    post_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List comments for a post (sorted chronologically)."""
    comments = db.query(PostComment).filter(
        PostComment.post_id == post_id
    ).order_by(PostComment.created_at.asc()).limit(limit).all()

    return [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            user_id=c.user_id,
            content=c.content,
            author_name=c.author_name or (c.user.full_name if c.user else "User"),
            author_avatar=c.author_avatar,
            created_at=c.created_at,
            time_ago=_format_time_ago(c.created_at),
        )
        for c in comments
    ]


# ── [8] ADD COMMENT ──────────────────────────────────────────────────────────
@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment_to_post(
    post_id: uuid.UUID,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Add a new comment to a post."""
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_comment = PostComment(
        id=uuid.uuid4(),
        post_id=post_id,
        user_id=current_user.id,
        content=content,
        author_name=current_user.full_name or "Reporter",
        author_avatar=None,
    )
    db.add(new_comment)

    post.comments_count = (post.comments_count or 0) + 1
    db.commit()
    db.refresh(new_comment)

    return CommentResponse(
        id=new_comment.id,
        post_id=new_comment.post_id,
        user_id=new_comment.user_id,
        content=new_comment.content,
        author_name=new_comment.author_name,
        author_avatar=new_comment.author_avatar,
        created_at=new_comment.created_at,
        time_ago=_format_time_ago(new_comment.created_at),
    )


# ── [9] DELETE POST ──────────────────────────────────────────────────────────
@router.delete("/{post_id}", status_code=status.HTTP_200_OK)
def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a post (only the author can delete their post)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this post")

    db.delete(post)
    db.commit()
    return {"message": "Post successfully deleted", "id": str(post_id)}
