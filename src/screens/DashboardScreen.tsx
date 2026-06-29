import { FilePlus, LayoutTemplate, Newspaper } from 'lucide-react';
import { useGenerationStore, useAuthStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '@/lib/i18n';

export const DashboardScreen = () => {
  const generations = useGenerationStore((state) => state.generations);
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const recentGenerations = generations.slice(0, 3);

  const displayName =
    (user as any)?.user_metadata?.full_name ||
    (user as any)?.user_metadata?.name ||
    (user as any)?.email?.split('@')[0] ||
    user?.full_name ||
    user?.firstName ||
    'Journalist';

  const avatarLetter = displayName[0]?.toUpperCase() ?? 'J';

  return (
    <div className="w-full px-4 pb-[80px] pt-3">

      {/* ── WELCOME CARD ── */}
      <div
        className="rounded-[14px] p-4 mb-5 flex justify-between items-center shadow-sm"
        style={{
          background: 'linear-gradient(135deg, #e8f0f8 0%, #f4f8fc 100%)',
          border: '1px solid rgba(13,27,42,0.08)',
          borderLeft: '3.5px solid #0D1B2A',
        }}
      >
        <div className="flex flex-col">
          <span className="text-[#7a8fa6] text-[10px] uppercase font-semibold tracking-[1.4px] mb-1">
            {t.welcomeBack}
          </span>
          <h1 className="text-[#0D1B2A] text-[22px] font-bold leading-tight mb-1">
            {displayName}
          </h1>
          <p className="text-[#7a8fa6] text-[12px]">
            {t.readyToCreate}
          </p>
        </div>
        <div
          className="w-[46px] h-[46px] rounded-full flex items-center justify-center text-white font-bold text-[18px] flex-shrink-0 shadow-md"
          style={{ background: '#0D1B2A' }}
        >
          {avatarLetter}
        </div>
      </div>

      {/* ── QUICK ACTIONS ── */}
      <div className="mb-6">
        <h2 className="text-[#888] text-[10px] font-[600] tracking-[1.4px] uppercase mb-[12px] text-center">
          {t.quickActions}
        </h2>

        {/* Button grid */}
        <div className="grid grid-cols-2 gap-[10px]">
          {/* New Clipping */}
          <button
            onClick={() => navigate('/generate')}
            className="bg-[#0D1B2A] rounded-[12px] py-[22px] px-[14px] flex flex-col items-center justify-center gap-2 active:scale-95 transition-all shadow-md"
          >
            <FilePlus className="w-[24px] h-[24px] text-white" strokeWidth={1.5} />
            <span className="text-white text-[12px] font-bold uppercase tracking-wider">
              {t.newClipping}
            </span>
          </button>

          {/* Templates */}
          <button
            onClick={() => navigate('/templates')}
            className="bg-[#0D1B2A] rounded-[12px] py-[22px] px-[14px] flex flex-col items-center justify-center gap-2 active:scale-95 transition-all shadow-md"
          >
            <LayoutTemplate className="w-[24px] h-[24px] text-white" strokeWidth={1.5} />
            <span className="text-white text-[12px] font-bold uppercase tracking-wider">
              {t.templatesBtn}
            </span>
          </button>
        </div>
      </div>

      {/* ── RECENT CLIPPINGS ── */}
      <div>
        <div className="flex justify-between items-center mb-[12px]">
          <div className="flex items-center gap-1.5">
            <span className="text-[#CC1E1E] text-[10px]">⚡</span>
            <h2 className="text-[#444] text-[10px] font-[700] tracking-[1.4px] uppercase m-0">
              {t.recentClippings}
            </h2>
          </div>
          <button
            onClick={() => navigate('/history')}
            className="text-[#CC1E1E] text-[12px] font-semibold"
          >
            {t.viewAll}
          </button>
        </div>

        <div className="flex flex-col gap-3">
          {recentGenerations.length === 0 ? (
            <div className="w-full bg-white rounded-[14px] py-10 px-4 flex flex-col items-center justify-center border border-dashed border-black/10 shadow-sm">
              <Newspaper className="w-8 h-8 text-[#888888] mb-3" strokeWidth={1.5} />
              <p className="text-[#555] text-[14px] mb-1 font-medium text-center">
                {t.noClippings}
              </p>
              <button
                onClick={() => navigate('/generate')}
                className="text-[#CC1E1E] text-[13px] hover:underline"
              >
                {t.createFirst}
              </button>
            </div>
          ) : (
            recentGenerations.map((gen) => (
              <div
                key={gen.id}
                onClick={() => gen?.id && navigate(`/preview/${gen.id}`)}
                className="bg-white p-[14px] rounded-[12px] border border-black/5 flex gap-3 items-center active:bg-gray-50 transition-colors cursor-pointer shadow-sm"
              >
                <img
                  src={gen?.png_url || 'https://placehold.co/54x64/EEF3F8/0D1B2A?text=...'}
                  alt="preview"
                  className="w-[54px] h-[64px] rounded-[6px] object-cover bg-[#EEF3F8] flex-shrink-0"
                />
                <div className="flex-1 flex flex-col justify-center">
                  <h4 className="font-bold text-[#0D1B2A] text-[13px] line-clamp-2 leading-snug mb-2">
                    {gen?.config?.headline || 'Untitled'}
                  </h4>
                  <div className="flex items-center gap-2">
                    <span className="bg-[#E8F5E2] text-[#2D7A1F] text-[10px] px-2.5 py-0.5 rounded-full font-semibold">
                      {t.published}
                    </span>
                    <span className="text-[10px] text-[#aaa]">
                      {t.processing}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
