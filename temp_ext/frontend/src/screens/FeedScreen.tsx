import { useState, useEffect } from 'react';
import { 
  Heart, 
  MessageCircle, 
  Share2, 
  Bookmark, 
  Search, 
  Radio, 
  Send, 
  X, 
  CheckCircle2, 
  MapPin, 
  Clock, 
  RefreshCw,
  PlusCircle
} from 'lucide-react';
import { useAuthStore, getReporterPhoto } from '@/store';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/axios';

const NAVY = '#0D1B2A';

const CATEGORIES = [
  'All',
  '🔥 Trending',
  '🚨 Breaking',
  '🏛️ Politics',
  '⚖️ Crime',
  '📍 Local',
  '🏏 Sports',
  '🎬 Cinema'
];

interface FeedPost {
  id: string;
  headline: string;
  article_content: string;
  summary?: string;
  image_url?: string;
  png_url?: string;
  reporter_name: string;
  reporter_image?: string;
  publication_name: string;
  location?: string;
  category?: string;
  likes_count: number;
  comments_count: number;
  shares_count: number;
  views_count?: number;
  created_at: string;
  is_verified_reporter?: boolean;
}

interface CommentItem {
  id: string;
  user_name: string;
  user_avatar?: string;
  comment_text: string;
  created_at: string;
}

export const FeedScreen = () => {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();

  const [posts, setPosts] = useState<FeedPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Likes local state for instant responsive UI
  const [likedPosts, setLikedPosts] = useState<Record<string, boolean>>({});
  const [savedPosts, setSavedPosts] = useState<Record<string, boolean>>({});

  // Comments Modal / Drawer State
  const [activeCommentPost, setActiveCommentPost] = useState<FeedPost | null>(null);
  const [commentsList, setCommentsList] = useState<CommentItem[]>([]);
  const [commentInput, setCommentInput] = useState('');
  const [loadingComments, setLoadingComments] = useState(false);

  // Full Image Modal State
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const displayName =
    (user as any)?.user_metadata?.full_name ||
    user?.full_name ||
    user?.firstName ||
    'Journalist';
  const userPhoto = user?.avatarUrl || getReporterPhoto(user?.email);

  const fetchFeed = async (cat?: string, q?: string) => {
    setLoading(true);
    try {
      const activeCat = cat !== undefined ? cat : selectedCategory;
      const activeQ = q !== undefined ? q : searchQuery;
      let url = '/api/v1/feed?page=1&limit=30';
      if (activeCat && activeCat !== 'All') {
        url += `&category=${encodeURIComponent(activeCat)}`;
      }
      if (activeQ.trim()) {
        url += `&query=${encodeURIComponent(activeQ.trim())}`;
      }
      const res = await api.get(url);
      if (res.data?.posts) {
        setPosts(res.data.posts);
      }
    } catch (err) {
      console.error('Error fetching feed from backend:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed();
  }, [selectedCategory]);

  const handleLike = async (postId: string) => {
    const isCurrentlyLiked = !!likedPosts[postId];
    
    // Instant optimistic update
    setLikedPosts((prev) => ({ ...prev, [postId]: !isCurrentlyLiked }));
    setPosts((prev) =>
      prev.map((p) => {
        if (p.id === postId) {
          return {
            ...p,
            likes_count: isCurrentlyLiked ? Math.max(0, p.likes_count - 1) : p.likes_count + 1,
          };
        }
        return p;
      })
    );

    try {
      await api.post(`/api/v1/feed/${postId}/like`);
    } catch (err) {
      console.error('Like toggle error:', err);
    }
  };

  const handleOpenComments = async (post: FeedPost) => {
    setActiveCommentPost(post);
    setLoadingComments(true);
    try {
      const res = await api.get(`/api/v1/feed/${post.id}/comments`);
      if (res.data?.comments) {
        setCommentsList(res.data.comments);
      }
    } catch (err) {
      console.error('Error loading comments:', err);
    } finally {
      setLoadingComments(false);
    }
  };

  const handlePostComment = async () => {
    if (!activeCommentPost || !commentInput.trim()) return;

    const text = commentInput.trim();
    setCommentInput('');

    const newComment: CommentItem = {
      id: `local-${Date.now()}`,
      user_name: displayName,
      user_avatar: userPhoto || '',
      comment_text: text,
      created_at: new Date().toISOString(),
    };

    setCommentsList((prev) => [newComment, ...prev]);
    setPosts((prev) =>
      prev.map((p) => (p.id === activeCommentPost.id ? { ...p, comments_count: p.comments_count + 1 } : p))
    );

    try {
      await api.post(`/api/v1/feed/${activeCommentPost.id}/comments`, {
        user_name: displayName,
        user_avatar: userPhoto || '',
        comment_text: text,
      });
    } catch (err) {
      console.error('Error adding comment:', err);
    }
  };

  const handleWhatsAppShare = (post: FeedPost) => {
    const text = `🚨 *${post.publication_name || 'RTI EXPRESS'} BREAKING NEWS*\n\n📌 *${post.headline}*\n\n${post.summary || post.article_content}\n\n👤 *Reporter:* ${post.reporter_name}\n📲 *Read full story on RTI News App:* https://rtiexpress.in/news/${post.id}`;
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
    window.open(url, '_blank');
  };

  const formatTimeAgo = (dateStr: string) => {
    try {
      const diffMs = Date.now() - new Date(dateStr).getTime();
      const mins = Math.floor(diffMs / 60000);
      if (mins < 1) return 'Just now';
      if (mins < 60) return `${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      return `${Math.floor(hrs / 24)}d ago`;
    } catch {
      return 'Today';
    }
  };

  return (
    <div className="w-full min-h-screen bg-[#F0F2F5] pb-[90px]">
      
      {/* ── STICKY TOP APP HEADER ── */}
      <div 
        className="sticky top-0 z-40 px-4 py-3 shadow-md"
        style={{ background: NAVY }}
      >
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#CC1E1E] flex items-center justify-center text-white shadow-sm">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-white text-[16px] font-bold tracking-wide flex items-center gap-1.5 leading-none">
                RTI Community Feed
                <span className="text-[9px] bg-red-600/90 text-white font-semibold px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                  Live
                </span>
              </h1>
              <span className="text-[#8A99A8] text-[10px]">Breaking news from accredited reporters</span>
            </div>
          </div>

          <button 
            onClick={() => navigate('/generate')}
            className="flex items-center gap-1 bg-[#CC1E1E] hover:bg-red-700 text-white text-[11px] font-semibold px-2.5 py-1.5 rounded-full shadow-md active:scale-95 transition-all"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>Post News</span>
          </button>
        </div>

        {/* ── SEARCH INPUT ── */}
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search breaking news, locations, topics..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              fetchFeed(selectedCategory, e.target.value);
            }}
            className="w-full bg-white/10 text-white placeholder-gray-400 text-[13px] rounded-xl pl-9 pr-8 py-2 border border-white/10 focus:outline-none focus:border-red-500 transition-all"
          />
          {searchQuery && (
            <button 
              onClick={() => { setSearchQuery(''); fetchFeed(selectedCategory, ''); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* ── CATEGORY PILLS BAR ── */}
      <div className="bg-white border-b border-gray-200 px-3 py-2.5 overflow-x-auto flex items-center gap-2 no-scrollbar shadow-xs">
        {CATEGORIES.map((cat) => {
          const isActive = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3.5 py-1.5 rounded-full text-[12px] font-semibold whitespace-nowrap transition-all duration-200 shadow-xs ${
                isActive
                  ? 'bg-[#CC1E1E] text-white shadow-md scale-[1.02]'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* ── MAIN FEED STREAM ── */}
      <div className="max-w-[540px] mx-auto px-3 py-4 space-y-4">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-500">
            <RefreshCw className="w-8 h-8 animate-spin text-[#CC1E1E]" />
            <p className="text-[13px] font-medium">Loading live community feed...</p>
          </div>
        ) : posts.length === 0 ? (
          <div className="bg-white rounded-2xl p-8 text-center border border-gray-200 shadow-sm">
            <Radio className="w-12 h-12 text-gray-300 mx-auto mb-2" />
            <h3 className="text-gray-800 font-bold text-[16px]">No news articles found</h3>
            <p className="text-gray-500 text-[12px] mt-1 mb-4">Be the first to share breaking news with all community members.</p>
            <button
              onClick={() => navigate('/generate')}
              className="bg-[#CC1E1E] text-white px-4 py-2 rounded-xl text-[12px] font-semibold shadow-md active:scale-95 transition-all"
            >
              Create News Clipping
            </button>
          </div>
        ) : (
          posts.map((post) => {
            const isLiked = !!likedPosts[post.id];
            const isSaved = !!savedPosts[post.id];

            return (
              <article
                key={post.id}
                className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow"
              >
                {/* Post Author Bar */}
                <div className="px-4 py-3 flex items-center justify-between bg-white border-b border-gray-100">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-[#0D1B2A] text-white font-bold flex items-center justify-center flex-shrink-0 border border-gray-200 overflow-hidden shadow-xs">
                      {post.reporter_image ? (
                        <img src={post.reporter_image} alt={post.reporter_name} className="w-full h-full object-cover" />
                      ) : (
                        <span>{(post.reporter_name || 'R')[0]?.toUpperCase()}</span>
                      )}
                    </div>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13.5px] font-bold text-gray-900 truncate leading-tight">
                          {post.reporter_name}
                        </span>
                        {post.is_verified_reporter && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 fill-blue-100 flex-shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-[10.5px] text-gray-500">
                        {post.location && (
                          <span className="flex items-center gap-0.5 truncate">
                            <MapPin className="w-3 h-3 text-red-500 flex-shrink-0" />
                            {post.location}
                          </span>
                        )}
                        <span>•</span>
                        <span className="flex items-center gap-0.5">
                          <Clock className="w-3 h-3 text-gray-400 flex-shrink-0" />
                          {formatTimeAgo(post.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <span className="text-[10px] font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded-md border border-gray-200">
                    {post.publication_name || 'RTI EXPRESS'}
                  </span>
                </div>

                {/* News Image Preview */}
                {(post.image_url || post.png_url) && (
                  <div 
                    className="relative w-full h-[280px] bg-gray-900 overflow-hidden cursor-pointer group"
                    onClick={() => setPreviewImage(post.png_url || post.image_url || null)}
                  >
                    <img
                      src={post.image_url || post.png_url}
                      alt={post.headline}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-3">
                      <span className="text-white text-[11px] font-medium bg-black/70 px-2 py-1 rounded-md backdrop-blur-xs">
                        Tap to view full clipping
                      </span>
                    </div>
                  </div>
                )}

                {/* News Content Area */}
                <div className="p-4">
                  <h2 className="text-[17px] font-bold text-gray-900 leading-snug mb-2 font-serif">
                    {post.headline}
                  </h2>
                  <p className="text-[13.5px] text-gray-700 leading-relaxed line-clamp-3">
                    {post.summary || post.article_content}
                  </p>
                </div>

                {/* Engagement Interaction Bar */}
                <div className="px-4 py-3 bg-[#F8FAFC] border-t border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* Like Button */}
                    <button
                      onClick={() => handleLike(post.id)}
                      className={`flex items-center gap-1.5 text-[12.5px] font-semibold transition-all active:scale-90 ${
                        isLiked ? 'text-red-600' : 'text-gray-600 hover:text-red-600'
                      }`}
                    >
                      <Heart className={`w-[19px] h-[19px] ${isLiked ? 'fill-red-600 text-red-600' : ''}`} />
                      <span>{post.likes_count}</span>
                    </button>

                    {/* Comments Button */}
                    <button
                      onClick={() => handleOpenComments(post)}
                      className="flex items-center gap-1.5 text-[12.5px] font-semibold text-gray-600 hover:text-blue-600 active:scale-90 transition-all"
                    >
                      <MessageCircle className="w-[19px] h-[19px]" />
                      <span>{post.comments_count}</span>
                    </button>

                    {/* WhatsApp Share Button */}
                    <button
                      onClick={() => handleWhatsAppShare(post)}
                      className="flex items-center gap-1.5 text-[12.5px] font-semibold text-emerald-600 hover:text-emerald-700 active:scale-90 transition-all"
                    >
                      <Share2 className="w-[19px] h-[19px]" />
                      <span>Share</span>
                    </button>
                  </div>

                  {/* Bookmark Button */}
                  <button
                    onClick={() => setSavedPosts((prev) => ({ ...prev, [post.id]: !isSaved }))}
                    className={`text-gray-400 hover:text-gray-700 active:scale-90 transition-all ${
                      isSaved ? 'text-[#0D1B2A]' : ''
                    }`}
                  >
                    <Bookmark className={`w-5 h-5 ${isSaved ? 'fill-[#0D1B2A] text-[#0D1B2A]' : ''}`} />
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>

      {/* ── COMMENTS DRAWER / MODAL ── */}
      {activeCommentPost && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex flex-col justify-end">
          <div className="bg-white rounded-t-3xl max-h-[80vh] flex flex-col w-full max-w-[540px] mx-auto shadow-2xl animate-in slide-in-from-bottom duration-200">
            
            {/* Drawer Header */}
            <div className="px-4 py-3.5 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="text-gray-900 font-bold text-[15px]">Discussion & Comments</h3>
                <span className="text-gray-500 text-[11px]">{commentsList.length} public responses</span>
              </div>
              <button
                onClick={() => setActiveCommentPost(null)}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Comments List */}
            <div className="p-4 overflow-y-auto flex-1 space-y-3 max-h-[360px]">
              {loadingComments ? (
                <div className="text-center py-8 text-gray-400 text-[12px]">Loading comments...</div>
              ) : commentsList.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-[12px]">No comments yet. Start the conversation!</div>
              ) : (
                commentsList.map((c) => (
                  <div key={c.id} className="flex gap-2.5 items-start bg-gray-50 p-3 rounded-xl border border-gray-100">
                    <div className="w-7 h-7 rounded-full bg-[#0D1B2A] text-white font-bold text-[11px] flex items-center justify-center flex-shrink-0">
                      {c.user_name[0]?.toUpperCase() || 'U'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] font-bold text-gray-900">{c.user_name}</span>
                        <span className="text-[10px] text-gray-400">{formatTimeAgo(c.created_at)}</span>
                      </div>
                      <p className="text-[12.5px] text-gray-700 mt-0.5 leading-snug">{c.comment_text}</p>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Comment Input Box */}
            <div className="p-3 border-t border-gray-200 bg-gray-50 flex items-center gap-2">
              <input
                type="text"
                placeholder="Write a comment..."
                value={commentInput}
                onChange={(e) => setCommentInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handlePostComment();
                }}
                className="flex-1 bg-white border border-gray-300 rounded-full px-4 py-2 text-[13px] focus:outline-none focus:border-red-500"
              />
              <button
                onClick={handlePostComment}
                disabled={!commentInput.trim()}
                className="w-9 h-9 rounded-full bg-[#CC1E1E] disabled:bg-gray-300 text-white flex items-center justify-center shadow-sm active:scale-95 transition-all"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── FULL IMAGE PREVIEW MODAL ── */}
      {previewImage && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4">
          <button
            onClick={() => setPreviewImage(null)}
            className="absolute top-4 right-4 text-white bg-white/20 p-2 rounded-full hover:bg-white/30"
          >
            <X className="w-6 h-6" />
          </button>
          <img
            src={previewImage}
            alt="Full Preview"
            className="max-w-full max-h-[90vh] object-contain rounded-xl shadow-2xl"
          />
        </div>
      )}

    </div>
  );
};
