# Spot News & Social Media Feed Integration Guide

This guide documents the **Spot News Community Feed** (Instagram & Way2News style) with real-time Likes, Comments, View counters, and "Post on Spot" publishing.

---

## 1. Backend REST Endpoints Reference

All endpoints are prefixed with `/api/v1/posts`:

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/posts/publish` | **Yes (Bearer Token)** | Publish a generated clipping to Spot News |
| `GET` | `/api/v1/posts/feed` | Optional (Public) | Fetch paginated feed with live like status |
| `GET` | `/api/v1/posts/{post_id}` | Optional (Public) | Fetch single post with full social stats |
| `POST` | `/api/v1/posts/{post_id}/like` | **Yes (Bearer Token)** | Toggle like/unlike with atomic counter update |
| `POST` | `/api/v1/posts/{post_id}/view` | No (Public) | Record impression/view counter |
| `POST` | `/api/v1/posts/{post_id}/share`| No (Public) | Record share counter (e.g. WhatsApp) |
| `GET` | `/api/v1/posts/{post_id}/comments`| No (Public) | Fetch comments for a post |
| `POST` | `/api/v1/posts/{post_id}/comments`| **Yes (Bearer Token)** | Add a new comment to a post |
| `DELETE`| `/api/v1/posts/{post_id}` | **Yes (Author Only)** | Delete a post |

---

## 2. Frontend TypeScript Service (`services/post.service.ts`)

```typescript
import { api } from '@/services/api'; // Axios instance with Supabase token interceptor

export interface PostItem {
  id: string;
  user_id: string;
  clipping_id?: string;
  headline: string;
  content: string;
  language: string;
  category: string;
  location?: string;
  png_url?: string;
  pdf_url?: string;
  image_url?: string;
  image_urls: string[];
  reporter_name?: string;
  reporter_avatar?: string;
  publication_name?: string;
  views_count: number;
  likes_count: number;
  comments_count: number;
  shares_count: number;
  is_liked_by_me: boolean;
  created_at: string;
  time_ago?: string;
}

export interface FeedResponse {
  posts: PostItem[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface CommentItem {
  id: string;
  post_id: string;
  user_id: string;
  content: string;
  author_name: string;
  author_avatar?: string;
  created_at: string;
  time_ago?: string;
}

export const postService = {
  // 1. Publish to Spot
  publishToSpot: async (data: {
    clipping_id?: string;
    headline: string;
    content: string;
    png_url?: string;
    image_urls?: string[];
    reporter_name?: string;
    publication_name?: string;
    category?: string;
    location?: string;
  }) => {
    const res = await api.post<PostItem>('/posts/publish', data);
    return res.data;
  },

  // 2. Fetch Feed
  getFeed: async (page = 1, limit = 10, category?: string) => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (category && category !== 'All') params.append('category', category);
    const res = await api.get<FeedResponse>(`/posts/feed?${params.toString()}`);
    return res.data;
  },

  // 3. Toggle Like
  toggleLike: async (postId: string) => {
    const res = await api.post<{ liked: boolean; likes_count: number }>(`/posts/${postId}/like`);
    return res.data;
  },

  // 4. Record View
  recordView: async (postId: string) => {
    const res = await api.post<{ views_count: number }>(`/posts/${postId}/view`);
    return res.data;
  },

  // 5. Record Share
  recordShare: async (postId: string) => {
    const res = await api.post<{ shares_count: number }>(`/posts/${postId}/share`);
    return res.data;
  },

  // 6. Comments
  getComments: async (postId: string) => {
    const res = await api.get<CommentItem[]>(`/posts/${postId}/comments`);
    return res.data;
  },

  addComment: async (postId: string, content: string) => {
    const res = await api.post<CommentItem>(`/posts/${postId}/comments`, { content });
    return res.data;
  },
};
```

---

## 3. "Post on Spot" Button for Clipping View (`PostOnSpotButton.tsx`)

```tsx
import React, { useState } from 'react';
import { Send, CheckCircle2, Loader2 } from 'lucide-react';
import { postService } from '@/services/post.service';
import { useNavigate } from 'react-router-dom';

interface PostOnSpotProps {
  clipping: {
    id: string;
    headline: string;
    article_content: string;
    png_url: string;
    image_urls?: string[];
    reporter_name?: string;
    publication_name?: string;
  };
}

export const PostOnSpotButton: React.FC<PostOnSpotProps> = ({ clipping }) => {
  const [loading, setLoading] = useState(false);
  const [posted, setPosted] = useState(false);
  const navigate = useNavigate();

  const handlePost = async () => {
    setLoading(true);
    try {
      await postService.publishToSpot({
        clipping_id: clipping.id,
        headline: clipping.headline,
        content: clipping.article_content,
        png_url: clipping.png_url,
        image_urls: clipping.image_urls,
        reporter_name: clipping.reporter_name,
        publication_name: clipping.publication_name,
        category: 'Breaking',
      });
      setPosted(true);
      setTimeout(() => {
        navigate('/spot-feed');
      }, 1200);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to post on Spot');
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handlePost}
      disabled={loading || posted}
      className={`w-full py-3.5 px-5 rounded-2xl font-bold text-white flex items-center justify-center gap-2 shadow-lg transition-all ${
        posted
          ? 'bg-emerald-600 shadow-emerald-600/30'
          : 'bg-gradient-to-r from-red-600 to-orange-500 shadow-orange-500/30 active:scale-[0.98]'
      }`}
    >
      {loading ? (
        <Loader2 className="w-5 h-5 animate-spin" />
      ) : posted ? (
        <>
          <CheckCircle2 className="w-5 h-5" />
          <span>Posted to Spot News ✓</span>
        </>
      ) : (
        <>
          <Send className="w-5 h-5" />
          <span>Post on Spot (స్పాట్ లో పోస్ట్ చేయండి)</span>
        </>
      )}
    </button>
  );
};
```

---

## 4. Full Instagram + Way2News Style Feed Component (`SpotNewsFeedScreen.tsx`)

```tsx
import React, { useState, useEffect } from 'react';
import { Heart, MessageCircle, Eye, Share2, MapPin, MoreVertical, Send, Loader2 } from 'lucide-react';
import { postService, PostItem, CommentItem } from '@/services/post.service';

export const SpotNewsFeedScreen: React.FC = () => {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [activeCommentsPostId, setActiveCommentsPostId] = useState<string | null>(null);

  const fetchFeed = async (pageNum = 1) => {
    try {
      const data = await postService.getFeed(pageNum, 10);
      setPosts(prev => (pageNum === 1 ? data.posts : [...prev, ...data.posts]));
      setHasMore(data.has_more);
      setPage(pageNum);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed(1);
  }, []);

  const handleLike = async (postId: string) => {
    // Optimistic UI update
    setPosts(prev =>
      prev.map(p => {
        if (p.id === postId) {
          const newLiked = !p.is_liked_by_me;
          return {
            ...p,
            is_liked_by_me: newLiked,
            likes_count: newLiked ? p.likes_count + 1 : Math.max(0, p.likes_count - 1),
          };
        }
        return p;
      })
    );

    try {
      await postService.toggleLike(postId);
    } catch (e) {
      fetchFeed(page);
    }
  };

  const handleShare = async (post: PostItem) => {
    postService.recordShare(post.id);
    const shareText = `*${post.headline}*\n\nRead more on RTI Express: ${post.png_url || ''}`;
    const url = `whatsapp://send?text=${encodeURIComponent(shareText)}`;
    window.open(url, '_blank');
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 pb-20">
      {/* Top App Bar */}
      <header className="sticky top-0 z-30 bg-white/95 dark:bg-gray-800/95 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between">
        <h1 className="text-lg font-black text-red-600 tracking-tight flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse" />
          SPOT NEWS 24x7
        </h1>
        <span className="text-xs font-semibold text-gray-500 bg-gray-100 dark:bg-gray-700 px-2.5 py-1 rounded-full">
          Community Feed
        </span>
      </header>

      {/* Feed Stream */}
      <div className="max-w-md mx-auto py-3 space-y-4 px-3">
        {loading && posts.length === 0 ? (
          <div className="py-20 flex flex-col items-center justify-center text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin mb-2" />
            <p className="text-sm">Loading Spot News...</p>
          </div>
        ) : (
          posts.map(post => (
            <article
              key={post.id}
              className="bg-white dark:bg-gray-800 rounded-3xl overflow-hidden shadow-sm border border-gray-100 dark:border-gray-700/60"
            >
              {/* Card Header */}
              <div className="p-3.5 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md overflow-hidden">
                    {post.reporter_avatar ? (
                      <img src={post.reporter_avatar} alt="" className="w-full h-full object-cover" />
                    ) : (
                      (post.reporter_name?.[0] || 'R').toUpperCase()
                    )}
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-gray-900 dark:text-white leading-snug">
                      {post.reporter_name || 'Reporter'}
                    </h2>
                    <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                      {post.location && (
                        <>
                          <MapPin className="w-3 h-3 text-red-500" />
                          <span>{post.location}</span>
                          <span>•</span>
                        </>
                      )}
                      <span>{post.time_ago || 'Recently'}</span>
                    </div>
                  </div>
                </div>
                <button className="text-gray-400 p-1">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>

              {/* Newspaper Clipping Image */}
              <div
                className="relative bg-gray-950 aspect-[4/5] overflow-hidden cursor-pointer"
                onDoubleClick={() => handleLike(post.id)}
              >
                <img
                  src={post.png_url || post.image_url || ''}
                  alt={post.headline}
                  className="w-full h-full object-contain"
                  loading="lazy"
                />
              </div>

              {/* Social Action Bar */}
              <div className="px-4 py-3 flex items-center justify-between border-b border-gray-50 dark:border-gray-700/40">
                <div className="flex items-center gap-4">
                  {/* Like */}
                  <button
                    onClick={() => handleLike(post.id)}
                    className="flex items-center gap-1.5 group transition-transform active:scale-125"
                  >
                    <Heart
                      className={`w-6 h-6 transition-colors ${
                        post.is_liked_by_me
                          ? 'fill-red-500 text-red-500'
                          : 'text-gray-600 dark:text-gray-300'
                      }`}
                    />
                    <span className="text-xs font-bold text-gray-700 dark:text-gray-300">
                      {post.likes_count}
                    </span>
                  </button>

                  {/* Comment */}
                  <button
                    onClick={() => setActiveCommentsPostId(post.id)}
                    className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300 active:scale-110"
                  >
                    <MessageCircle className="w-6 h-6" />
                    <span className="text-xs font-bold">{post.comments_count}</span>
                  </button>

                  {/* Share */}
                  <button
                    onClick={() => handleShare(post)}
                    className="flex items-center gap-1.5 text-emerald-600 active:scale-110"
                  >
                    <Share2 className="w-6 h-6" />
                    <span className="text-xs font-bold">{post.shares_count || ''}</span>
                  </button>
                </div>

                {/* Views Counter (Way2News style) */}
                <div className="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700/60 px-2.5 py-1 rounded-full">
                  <Eye className="w-3.5 h-3.5 text-blue-500" />
                  <span>{post.views_count} views</span>
                </div>
              </div>

              {/* Headline & Excerpt */}
              <div className="p-4 pt-3">
                <h3 className="text-base font-bold text-gray-900 dark:text-white mb-1.5 leading-snug">
                  {post.headline}
                </h3>
                <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-3 leading-relaxed">
                  {post.content}
                </p>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
};
```
