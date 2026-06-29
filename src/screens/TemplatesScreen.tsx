import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGenerationStore } from '@/store';
import { LayoutTemplate, Image as ImageIcon, Images, ChevronRight, ChevronLeft, Check } from 'lucide-react';
import { TemplateCard, THUMBNAILS } from '@/components/TemplateCard';

// ─── Pattern data ──────────────────────────────────────────────────────────────
const PATTERN_GROUPS = [
  {
    id: 'single',
    label: 'Single Image',
    description: 'One featured photo per article',
    icon: <ImageIcon className="w-3.5 h-3.5" />,
    patterns: [
      {
        patternId: 'A',
        title: 'Pattern A',
        description: 'Full headline · dual image row',
      },
      {
        patternId: 'B',
        title: 'Pattern B',
        description: 'Tall left photo · right headline',
      },
    ],
  },
  {
    id: 'double',
    label: 'Double Image',
    description: 'Two photos in one layout',
    icon: <Images className="w-3.5 h-3.5" />,
    patterns: [
      {
        patternId: 'C',
        title: 'Pattern C',
        description: 'Side by side images · text below',
      },
      {
        patternId: 'D',
        title: 'Pattern D',
        description: 'Full image top · small inline image on right',
      },
    ],
  },
  {
    id: 'multi',
    label: 'Multi Image',
    description: '3 or more photos in the layout',
    icon: <LayoutTemplate className="w-3.5 h-3.5" />,
    patterns: [
      {
        patternId: 'E',
        title: 'Pattern E',
        description: '1 full image top + 2 images at bottom',
      },
      {
        patternId: 'F',
        title: 'Pattern F',
        description: '3 images wrapped within text columns',
      },
    ],
  },
  {
    id: 'custom',
    label: 'Custom',
    description: 'Special layout featuring a summary and bullet points',
    icon: <LayoutTemplate className="w-3.5 h-3.5" />,
    patterns: [
      {
        patternId: 'G',
        title: 'Pattern G',
        description: 'Auto-generates summary and bullet points',
      },
    ],
  },
];

// ─── Screen ────────────────────────────────────────────────────────────────────
export const TemplatesScreen = () => {
  const setConfig = useGenerationStore((state) => state.setConfig);
  const navigate = useNavigate();

  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedPatternId, setSelectedPatternId] = useState<string | null>(null);

  const handleSelectPattern = (patternId: string) => {
    setSelectedPatternId((prev) => (prev === patternId ? null : patternId));
  };

  const handleApply = () => {
    if (!selectedPatternId) return;
    setConfig({ layoutPattern: selectedPatternId as any });
    navigate('/generate');
  };

  if (!selectedCategory) {
    // ─── Category Selection View ───
    return (
      <div className="relative pb-24">
        {/* Page header */}
        <div className="px-4 pt-5 pb-2">
          <h1 className="text-[28px] font-serif font-bold text-[#0D1B2A] leading-tight tracking-tight">
            Templates
          </h1>
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">
            CHOOSE IMAGE LAYOUT TYPE
          </p>
          <div className="w-full h-px bg-[#cc2222] mt-3" />
        </div>

        <div className="px-4 pb-4 space-y-4 mt-2">
          {PATTERN_GROUPS.map((group) => (
            <div
              key={group.id}
              onClick={() => setSelectedCategory(group.id)}
              className="bg-white rounded-[14px] overflow-hidden cursor-pointer transition-transform active:scale-[0.98] shadow-sm border border-slate-100"
            >
              {/* Previews container */}
              <div className="bg-[#eef3f8] p-3 pb-0 border-b border-slate-100 relative">
                <div className="absolute top-3 left-3 bg-[#cc2222] text-white text-[9px] font-bold px-2 py-1 rounded-md z-10 shadow-sm uppercase tracking-wide">
                  {group.patterns.length} PATTERNS
                </div>
                <div className="flex gap-2 mt-9 mb-3 px-1">
                  {group.patterns.map((p) => {
                    const Thumbnail = THUMBNAILS[p.patternId] ?? THUMBNAILS.A;
                    return (
                      <div key={p.patternId} className="flex-1 bg-white rounded-md border border-[#cc2222] overflow-hidden relative shadow-sm">
                         {/* Mini red dot at top right */}
                         <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#cc2222] rounded-full z-10" />
                         {/* Pattern label */}
                         <div className="absolute top-1 left-1.5 text-[5.5px] font-bold text-slate-400 uppercase tracking-widest z-10">PATTERN {p.patternId}</div>
                         <div className="w-full aspect-[3/2] pt-3 px-1 pb-1">
                           <Thumbnail />
                         </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              {/* Category Info */}
              <div className="p-4 flex items-center justify-between">
                <div>
                  <h2 className="font-serif font-bold text-[17px] text-[#0D1B2A]">{group.label}</h2>
                  <p className="text-slate-500 text-[11px] mt-0.5">{group.description}</p>
                </div>
                <div className="w-8 h-8 rounded-lg bg-[#0D1B2A] text-white flex items-center justify-center shadow-sm">
                  <ChevronRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ─── Pattern Selection View ───
  const activeGroup = PATTERN_GROUPS.find((g) => g.id === selectedCategory)!;

  return (
    <div className="relative pb-32">
      {/* Page header */}
      <div className="px-4 pt-5 pb-2 flex items-center gap-3">
        <button
          onClick={() => { setSelectedCategory(null); setSelectedPatternId(null); }}
          className="w-9 h-9 bg-[#0D1B2A] rounded-[10px] flex items-center justify-center text-white flex-shrink-0"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-xl font-serif font-extrabold text-[#0D1B2A] leading-tight tracking-tight">
            {activeGroup.label}
          </h1>
          <p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mt-0.5">
            PICK A {activeGroup.label.toUpperCase()} PATTERN
          </p>
        </div>
      </div>
      <div className="px-4">
        <div className="w-full h-[2px] bg-[#cc2222] mt-1 mb-4" />
      </div>

      <div className="px-4 pb-4">
        {/* 2-column card grid */}
        <div className="grid grid-cols-2 gap-3">
          {activeGroup.patterns.map((p) => (
            <div key={p.patternId} className="relative">
              <TemplateCard
                patternId={p.patternId}
                title={`Pattern ${p.patternId}`}
                description={p.description}
                isSelected={selectedPatternId === p.patternId}
                onSelect={handleSelectPattern}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Fixed "Apply Pattern" button */}
      <div
        className="fixed left-0 w-full px-4 pt-3 pb-3 z-30"
        style={{
          bottom: 'calc(4.5rem + env(safe-area-inset-bottom))',
          background: 'linear-gradient(to top, #EEF3F8 60%, transparent)',
        }}
      >
        <button
          onClick={handleApply}
          disabled={!selectedPatternId}
          className={[
            'w-full py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2',
            'transition-all duration-200 active:scale-[0.98]',
            selectedPatternId
              ? 'bg-[#899ba8] text-white' // the screenshot shows a gray-ish button, we use a nice gray-blue
              : 'bg-slate-300 text-slate-100 cursor-not-allowed opacity-50',
          ].join(' ')}
        >
          <Check className="w-4 h-4 mr-1" />
          <span>Use This Pattern</span>
        </button>
      </div>
    </div>
  );
};
