import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.clipping import Clipping
from app.models.user import User

router = APIRouter()

# In-memory social state cache (likes, comments, published feed overrides)
_SOCIAL_FEED_STORE: Dict[str, Dict[str, Any]] = {}
_COMMENTS_STORE: Dict[str, List[Dict[str, Any]]] = {}
_LIKES_STORE: Dict[str, set] = {}

# Default seed posts for community showcase
_SEED_COMMUNITY_POSTS = [
    {
        "id": "feed-seed-1",
        "headline": "మల్లంపల్లి పల్లె దవాఖానలో బాలికలకు ప్రత్యేక హెచ్‌పీవీ టీకా కార్యక్రమం",
        "article_content": "మల్లంపల్లి, సెప్టెంబర్ 5 (ఆర్టిఐ ఎక్స్‌ప్రెస్ న్యూస్): గర్భాశయ ముఖద్వార క్యాన్సర్ నివారణకు ముందస్తు చర్యల్లో భాగంగా మల్లంపల్లి పల్లె దవాఖానలో 9 నుంచి 14 ఏళ్ల లోపు బాలికలకు ఉచితంగా హెచ్‌పీవీ టీకా వేసే కార్యక్రమం ప్రారంభించారు.",
        "summary": "బాలికల ఆరోగ్య పరిరక్షణకు ఉచిత హెచ్‌పీవీ వ్యాక్సినేషన్ విజయవంతంగా ప్రారంభం.",
        "image_url": "https://picsum.photos/id/1025/600/700",
        "reporter_name": "Mohithroyal Pokkala",
        "reporter_image": "",
        "publication_name": "RTI EXPRESS",
        "location": "Mallampalli, Telangana",
        "category": "Healthcare",
        "likes_count": 142,
        "comments_count": 18,
        "shares_count": 35,
        "views_count": 1240,
        "created_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(hours=2)).isoformat(),
        "is_verified_reporter": True,
    },
    {
        "id": "feed-seed-2",
        "headline": "దెందులూరు మండలం గోపన్నపాలెం సెంటర్ లో ఘోర రోడ్డు ప్రమాదం",
        "article_content": "దెందులూరు, సెప్టెంబర్ 5 (ఆర్టిఐ ఎక్స్‌ప్రెస్ న్యూస్): ఏలూరు జిల్లా దెందులూరు మండలం గోపన్నపాలెం సెంటర్‌లో శుక్రవారం సాయంత్రం విషాదకర ఘటన చోటుచేసుకుంది. స్థానిక పోలీసులు కేసు నమోదు చేసి దర్యాప్తు చేస్తున్నారు.",
        "summary": "గోపన్నపాలెం జాతీయ రహదారి వద్ద ట్రాఫిక్ జామ్, సంఘటనా స్థలానికి చేరుకున్న పోలీసులు.",
        "image_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800&auto=format&fit=crop&q=80",
        "reporter_name": "K. Venkatesh (Bureau Chief)",
        "reporter_image": "",
        "publication_name": "RTI EXPRESS",
        "location": "Denduluru, Eluru District",
        "category": "Breaking",
        "likes_count": 98,
        "comments_count": 12,
        "shares_count": 41,
        "views_count": 980,
        "created_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(hours=4)).isoformat(),
        "is_verified_reporter": True,
    },
    {
        "id": "feed-seed-3",
        "headline": "రైతులకు నూతన సాగు పద్ధతులపై వ్యవసాయ శాస్త్రవేత్తల ప్రత్యేక అవగాహన సదస్సు",
        "article_content": "విజయవాడ: ఆధునిక పద్ధతులతో అధిక దిగుబడులు సాధించేందుకు రైతులకు వ్యవసాయ శాఖ ఆధ్వర్యంలో ఉచిత సాంకేతిక శిక్షణ మరియు విత్తనాల పంపిణీ నిర్వహించారు.",
        "summary": "ఖరీఫ్ సీజన్ నేపథ్యంలో రైతులకు డ్రోన్ స్ప్రేయింగ్ మరియు సేంద్రీయ ఎరువులపై శిక్షణ.",
        "image_url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=800&auto=format&fit=crop&q=80",
        "reporter_name": "S. Rajesh Kumar",
        "reporter_image": "",
        "publication_name": "Bharath Reporter",
        "location": "Vijayawada, Andhra Pradesh",
        "category": "Agriculture",
        "likes_count": 76,
        "comments_count": 9,
        "shares_count": 22,
        "views_count": 650,
        "created_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(hours=6)).isoformat(),
        "is_verified_reporter": False,
    }
]


class CommentCreateRequest(BaseModel):
    user_name: str = Field(default="RTI User")
    user_avatar: Optional[str] = None
    comment_text: str


class PublishNewsRequest(BaseModel):
    clipping_id: Optional[str] = None
    headline: str
    article_content: str
    image_url: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_image: Optional[str] = None
    publication_name: Optional[str] = "RTI EXPRESS"
    category: Optional[str] = "Local"
    location: Optional[str] = "Andhra Pradesh"


@router.get("")
async def get_community_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    query: Optional[str] = None,
    trending: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns public news feed posts with engagement statistics, reporter profiles, and categories.
    """
    posts = []

    # 1. Fetch from live database completed clippings
    try:
        db_clippings = (
            db.query(Clipping)
            .filter(Clipping.status == "completed")
            .order_by(Clipping.created_at.desc())
            .limit(limit)
            .all()
        )
        for c in db_clippings:
            post_id = str(c.id)
            social_data = _SOCIAL_FEED_STORE.get(post_id, {})
            likes = social_data.get("likes_count", 0)
            comments = len(_COMMENTS_STORE.get(post_id, []))
            
            author_name = "Mohithroyal Pokkala"
            author_img = None
            if c.owner:
                author_name = c.owner.full_name or author_name
                author_img = getattr(c.owner, "avatar_url", None)

            posts.append({
                "id": post_id,
                "headline": c.headline,
                "article_content": c.article_content,
                "summary": c.article_content[:180] + "..." if len(c.article_content) > 180 else c.article_content,
                "image_url": c.image_url or (c.image_urls[0] if c.image_urls and len(c.image_urls) > 0 else None),
                "png_url": c.png_url,
                "reporter_name": author_name,
                "reporter_image": author_img,
                "publication_name": c.publication_name or "RTI EXPRESS",
                "location": "Local",
                "category": "News",
                "likes_count": likes,
                "comments_count": comments,
                "shares_count": social_data.get("shares_count", 0),
                "views_count": social_data.get("views_count", 15),
                "created_at": c.created_at.isoformat() if c.created_at else datetime.utcnow().isoformat(),
                "is_verified_reporter": True,
            })
    except Exception as e:
        print(f"[FEED] DB query notice: {e}")

    # 2. Combine with seed community items
    for seed in _SEED_COMMUNITY_POSTS:
        post_id = seed["id"]
        social_data = _SOCIAL_FEED_STORE.get(post_id, {})
        post_copy = dict(seed)
        if "likes_count" in social_data:
            post_copy["likes_count"] = social_data["likes_count"]
        if post_id in _COMMENTS_STORE:
            post_copy["comments_count"] = len(_COMMENTS_STORE[post_id])
        posts.append(post_copy)

    # Filter by category if specified
    if category and category.lower() not in ["all", "🔥 trending"]:
        clean_cat = category.lower().replace("🚨", "").replace("🏛️", "").replace("⚖️", "").replace("📍", "").replace("🏏", "").replace("🎬", "").strip()
        posts = [p for p in posts if clean_cat in p.get("category", "").lower() or clean_cat in p.get("headline", "").lower()]

    # Search query filter
    if query and query.strip():
        q = query.strip().lower()
        posts = [p for p in posts if q in p.get("headline", "").lower() or q in p.get("article_content", "").lower() or q in p.get("reporter_name", "").lower()]

    # Sort if trending requested
    if trending or (category and "trending" in category.lower()):
        posts = sorted(posts, key=lambda p: (p.get("likes_count", 0) * 2 + p.get("comments_count", 0) * 3 + p.get("shares_count", 0) * 4), reverse=True)

    # Paginate
    start_idx = (page - 1) * limit
    paged_posts = posts[start_idx : start_idx + limit]

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total_posts": len(posts),
        "posts": paged_posts,
    }


@router.post("/{post_id}/like")
async def toggle_like(post_id: str, user_id: str = Query("user_anon")) -> Dict[str, Any]:
    """
    Toggle like on a community news post.
    """
    if post_id not in _LIKES_STORE:
        _LIKES_STORE[post_id] = set()

    user_liked = user_id in _LIKES_STORE[post_id]
    if user_liked:
        _LIKES_STORE[post_id].remove(user_id)
        is_liked = False
    else:
        _LIKES_STORE[post_id].add(user_id)
        is_liked = True

    # Update count
    if post_id not in _SOCIAL_FEED_STORE:
        _SOCIAL_FEED_STORE[post_id] = {"likes_count": 0, "shares_count": 0, "views_count": 0}

    # Find base count
    base_likes = 0
    for s in _SEED_COMMUNITY_POSTS:
        if s["id"] == post_id:
            base_likes = s["likes_count"]
            break

    total_likes = max(0, base_likes + len(_LIKES_STORE[post_id]))
    _SOCIAL_FEED_STORE[post_id]["likes_count"] = total_likes

    return {
        "success": True,
        "post_id": post_id,
        "is_liked": is_liked,
        "likes_count": total_likes,
    }


@router.get("/{post_id}/comments")
async def get_comments(post_id: str) -> Dict[str, Any]:
    """
    Fetch all user comments for a specific news card.
    """
    comments = _COMMENTS_STORE.get(post_id, [])
    # Default seed comments if empty
    if not comments:
        comments = [
            {
                "id": "c-1",
                "user_name": "Ravi Kumar",
                "user_avatar": "",
                "comment_text": "చాలా మంచి వార్త. ప్రజలకు ఎంతో ఉపయోగపడుతుంది.",
                "created_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(minutes=45)).isoformat(),
            },
            {
                "id": "c-2",
                "user_name": "Anitha Reddy",
                "user_avatar": "",
                "comment_text": "ధన్యవాదాలు రిపోర్టర్ గారు, పూర్తి వివరాలు స్పష్టంగా ఇచ్చారు.",
                "created_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(minutes=20)).isoformat(),
            }
        ]
        _COMMENTS_STORE[post_id] = comments

    return {
        "success": True,
        "post_id": post_id,
        "total_comments": len(comments),
        "comments": comments,
    }


@router.post("/{post_id}/comments")
async def add_comment(post_id: str, req: CommentCreateRequest) -> Dict[str, Any]:
    """
    Add a new comment on a community news post.
    """
    if not req.comment_text.strip():
        raise HTTPException(status_code=400, detail="Comment text cannot be empty")

    new_comment = {
        "id": f"comment-{uuid.uuid4().hex[:8]}",
        "user_name": req.user_name or "RTI Community Member",
        "user_avatar": req.user_avatar or "",
        "comment_text": req.comment_text.strip(),
        "created_at": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
    }

    if post_id not in _COMMENTS_STORE:
        _COMMENTS_STORE[post_id] = []

    _COMMENTS_STORE[post_id].insert(0, new_comment)

    return {
        "success": True,
        "post_id": post_id,
        "comment": new_comment,
        "total_comments": len(_COMMENTS_STORE[post_id]),
    }


@router.post("/publish")
async def publish_to_community(req: PublishNewsRequest) -> Dict[str, Any]:
    """
    Publish a newly generated news clipping to the public social feed.
    """
    post_id = req.clipping_id or f"feed-{uuid.uuid4().hex[:8]}"
    new_post = {
        "id": post_id,
        "headline": req.headline,
        "article_content": req.article_content,
        "summary": req.article_content[:180] + "..." if len(req.article_content) > 180 else req.article_content,
        "image_url": req.image_url,
        "reporter_name": req.reporter_name or "Mohithroyal Pokkala",
        "reporter_image": req.reporter_image or "",
        "publication_name": req.publication_name or "RTI EXPRESS",
        "location": req.location or "Andhra Pradesh",
        "category": req.category or "Local",
        "likes_count": 1,
        "comments_count": 0,
        "shares_count": 0,
        "views_count": 1,
        "created_at": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        "is_verified_reporter": True,
    }

    _SEED_COMMUNITY_POSTS.insert(0, new_post)

    return {
        "success": True,
        "message": "News published to Community Feed successfully!",
        "post": new_post,
    }
