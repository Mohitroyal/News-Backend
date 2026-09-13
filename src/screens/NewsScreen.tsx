import React, { useState } from 'react';
import { Newspaper, Calendar, ChevronRight, X, Plus, RefreshCw, Eye, FileText, Pencil, Image as ImageIcon } from 'lucide-react';
import { useGenerationStore } from '@/store';
import { useNavigate } from 'react-router-dom';

export const NewsScreen: React.FC = () => {
  const generations = useGenerationStore((state) => state.generations);
  const navigate = useNavigate();
  const [selectedGen, setSelectedGen] = useState<any | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const safeGenerations = Array.isArray(generations) ? generations.filter(Boolean) : [];

  // Sort by date descending (newest first)
  const sortedGenerations = [...safeGenerations].sort((a, b) => {
    const dateA = new Date(a?.createdAt || 0).getTime();
    const dateB = new Date(b?.createdAt || 0).getTime();
    return dateB - dateA;
  });

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const formatDate = (isoStr?: string) => {
    if (!isoStr) return new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="min-h-full bg-[#EAF1FB] pb-24">
      {/* ── HEADER ── */}
      <div style={{ background: '#EAF1FB', paddingTop: '16px', paddingBottom: '14px', marginBottom: '10px' }}>
        <div className="flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <Newspaper style={{ width: '22px', height: '22px', color: '#123A66' }} />
            <h1 style={{ color: '#123A66', fontSize: '20px', fontWeight: 700, fontFamily: "'Georgia', serif", margin: 0, letterSpacing: '0.3px' }}>
              News
            </h1>
          </div>
          <button
            onClick={handleRefresh}
            style={{ background: '#145AB1', color: '#ffffff', border: 'none', borderRadius: '20px', padding: '6px 16px', fontWeight: 700, fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            title="Refresh feed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <div className="px-3">
        {/* ── EMPTY STATE ── */}
        {sortedGenerations.length === 0 ? (
          <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-8 text-center my-6 flex flex-col items-center justify-center shadow-sm">
            <div className="w-16 h-16 rounded-full bg-[#0d4a8f]/10 flex items-center justify-center mb-4">
              <Newspaper className="w-8 h-8 text-[#0d4a8f]" />
            </div>
            <h3 className="text-lg font-bold text-[#0A2540] mb-2">No clippings published yet</h3>
            <p className="text-xs text-[#6B7A90] max-w-xs mb-6 leading-relaxed">
              Create your first newspaper clipping and publish it to see it listed here in your news feed.
            </p>
            <button
              onClick={() => navigate('/generate')}
              className="flex items-center gap-2 px-6 py-3 rounded-full bg-[#0d4a8f] active:bg-[#145AB1] text-white font-bold text-sm shadow-md transition-transform active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>Create your first clipping</span>
            </button>
          </div>
        ) : (
          /* ── SCROLLABLE LIST OF CARDS ── */
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between px-1 mb-1">
              <span className="text-xs font-extrabold uppercase tracking-wider text-[#0d4a8f]">
                Published History ({sortedGenerations.length})
              </span>
              <span className="text-[11px] text-[#6B7A90]">Newest First</span>
            </div>

            {sortedGenerations.map((gen: any, idx: number) => {
              const key = gen?.id || `gen-${idx}`;
              const headline = gen?.config?.headline || gen?.config?.publicationName || 'Untitled Clipping';
              const activeLogo = gen?.config?.publicationName || 'RTI Express';
              const pubDate = formatDate(gen?.createdAt || gen?.config?.publicationDate);
              const thumbUrl =
                gen?.png_url ||
                gen?.imageUrl ||
                (gen?.config?.imageUrls && gen?.config?.imageUrls[0]) ||
                null;

              return (
                <div
                  key={key}
                  onClick={() => setSelectedGen(gen)}
                  className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-4 shadow-sm flex gap-3 active:scale-[0.98] transition-all cursor-pointer hover:border-[#0d4a8f]/40"
                >
                  {/* Thumbnail */}
                  <div className="w-20 h-24 rounded-xl bg-white border border-[#D0E2F7] overflow-hidden shrink-0 flex items-center justify-center shadow-inner">
                    {thumbUrl ? (
                      <img src={thumbUrl} alt="Thumbnail" className="w-full h-full object-cover" />
                    ) : (
                      <div className="flex flex-col items-center justify-center p-2 text-center text-[#0d4a8f]">
                        <Newspaper className="w-6 h-6 opacity-60 mb-1" />
                        <span className="text-[9px] font-bold">RTI Express</span>
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                    <div>
                      {/* Active Logo Tag */}
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="px-2 py-0.5 rounded-md bg-[#0d4a8f] text-white text-[10px] font-extrabold uppercase tracking-wider">
                          {activeLogo}
                        </span>
                      </div>

                      {/* Headline */}
                      <h3 className="font-bold text-[#0A2540] text-sm leading-snug line-clamp-2">
                        {headline}
                      </h3>
                    </div>

                    {/* Footer Date */}
                    <div className="flex items-center justify-between text-[11px] text-[#6B7A90] mt-2 pt-2 border-t border-[#D0E2F7]/60">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-[#0d4a8f]" />
                        <span>{pubDate}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-[#0d4a8f]" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── READ-ONLY DETAIL MODAL ── */}
      {selectedGen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-lg w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl border border-[#D0E2F7]">
            {/* Modal Header */}
            <div className="bg-[#0d4a8f] px-5 py-4 flex items-center justify-between text-white">
              <div className="flex items-center gap-2 min-w-0">
                <span className="px-2.5 py-1 rounded-full bg-white/20 text-white text-xs font-bold uppercase tracking-wider">
                  {selectedGen?.config?.publicationName || 'RTI Express'}
                </span>
                <span className="text-xs text-white/70 truncate">
                  {formatDate(selectedGen?.createdAt)}
                </span>
              </div>
              <button
                onClick={() => setSelectedGen(null)}
                className="w-8 h-8 rounded-full bg-white/10 active:bg-white/20 flex items-center justify-center text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-5 overflow-y-auto flex-1 space-y-4">
              {/* Full Headline */}
              <div>
                <span className="text-[11px] font-bold text-[#4A90E2] flex items-center gap-1.5 mb-1">
                  <FileText className="w-4 h-4" />
                  Headline
                </span>
                <h2 className="text-lg font-bold text-[#0A2540] leading-snug">
                  {selectedGen?.config?.headline || selectedGen?.config?.publicationName || 'Untitled Clipping'}
                </h2>
              </div>

              {/* Featured Image / Preview */}
              {(selectedGen?.png_url || selectedGen?.imageUrl || (selectedGen?.config?.imageUrls && selectedGen?.config?.imageUrls[0])) && (
                <div>
                  <span className="text-[11px] font-bold text-[#4A90E2] flex items-center gap-1.5 mb-1.5">
                    <ImageIcon className="w-4 h-4" />
                    Featured Image / Clipping
                  </span>
                  <div className="rounded-2xl border border-[#D0E2F7] overflow-hidden bg-[#EEF3F8]">
                    <img
                      src={selectedGen?.png_url || selectedGen?.imageUrl || selectedGen?.config?.imageUrls[0]}
                      alt="Clipping preview"
                      className="w-full h-auto max-h-72 object-contain bg-black/5"
                    />
                  </div>
                </div>
              )}

              {/* Full Article Content */}
              <div>
                <span className="text-[11px] font-bold text-[#4A90E2] flex items-center gap-1.5 mb-1">
                  <Pencil className="w-4 h-4" />
                  Article Content
                </span>
                <div className="bg-[#E8F2FC] border border-[#D0E2F7] rounded-2xl p-4 text-xs leading-relaxed text-[#0A2540] whitespace-pre-wrap font-sans">
                  {selectedGen?.config?.articleContent || selectedGen?.config?.content || 'No article text content available for this clipping.'}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-[#E8F2FC] border-t border-[#D0E2F7] flex items-center justify-between gap-3">
              <button
                onClick={() => setSelectedGen(null)}
                className="flex-1 py-2.5 px-4 rounded-xl border border-[#D0E2F7] bg-white text-[#0A2540] font-bold text-xs active:bg-gray-100 transition-colors"
              >
                Close
              </button>
              {selectedGen?.id && (
                <button
                  onClick={() => {
                    const id = selectedGen.id;
                    setSelectedGen(null);
                    navigate(`/preview/${id}`);
                  }}
                  className="flex-1 py-2.5 px-4 rounded-xl bg-[#0d4a8f] text-white font-bold text-xs flex items-center justify-center gap-1.5 active:bg-[#145AB1] shadow-sm transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Full Clipping</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
