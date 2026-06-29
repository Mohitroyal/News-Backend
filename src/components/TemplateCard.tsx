import { Check } from 'lucide-react';

// ─── Layout thumbnail SVGs ────────────────────────────────────────────────────

const PatternAThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    {/* Background */}
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Headline box at top */}
    <rect x="4" y="4" width="112" height="14" fill="#0D1B2A" rx="2" />
    <rect x="8" y="8" width="60" height="5" fill="#ffffff" rx="1" opacity="0.8" />
    {/* Left: 2-column text */}
    <rect x="4" y="22" width="53" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="28" width="50" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="34" width="53" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="40" width="48" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="46" width="53" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="52" width="45" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="58" width="50" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="64" width="53" height="4" fill="#cbd5e1" rx="1" />
    <rect x="4" y="70" width="40" height="4" fill="#cbd5e1" rx="1" />
    {/* Right: image placeholder */}
    <rect x="62" y="22" width="54" height="52" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <rect x="76" y="38" width="26" height="18" fill="#bfdbfe" rx="1" opacity="0.6" />
    <text x="89" y="50" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">IMG</text>
  </svg>
);

const PatternBThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Red left bar + headline */}
    <rect x="4" y="4" width="5" height="16" fill="#CC1E1E" rx="1" />
    <rect x="12" y="6" width="70" height="5" fill="#0D1B2A" rx="1" />
    <rect x="12" y="13" width="55" height="4" fill="#64748b" rx="1" opacity="0.5" />
    {/* Full-width center image */}
    <rect x="4" y="24" width="112" height="26" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="60" y="40" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">FULL WIDTH IMAGE</text>
    {/* 2-col text below */}
    <rect x="4" y="54" width="52" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="59" width="49" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="64" width="52" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="69" width="45" height="3" fill="#cbd5e1" rx="1" />
    <rect x="64" y="54" width="52" height="3" fill="#cbd5e1" rx="1" />
    <rect x="64" y="59" width="48" height="3" fill="#cbd5e1" rx="1" />
    <rect x="64" y="64" width="52" height="3" fill="#cbd5e1" rx="1" />
    <rect x="64" y="69" width="40" height="3" fill="#cbd5e1" rx="1" />
  </svg>
);

const PatternCThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Headline */}
    <rect x="4" y="4" width="112" height="8" fill="#0D1B2A" rx="2" />
    <rect x="8" y="7" width="55" height="3" fill="#ffffff" rx="1" opacity="0.7" />
    {/* Side-by-side images */}
    <rect x="4" y="16" width="54" height="36" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="31" y="37" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">IMG 1</text>
    <rect x="62" y="16" width="54" height="36" fill="#dcfce7" rx="2" stroke="#86efac" strokeWidth="0.5" />
    <text x="89" y="37" fontSize="6" fill="#16a34a" textAnchor="middle" fontFamily="sans-serif">IMG 2</text>
    {/* Text below */}
    <rect x="4" y="56" width="112" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="61" width="100" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="66" width="112" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="71" width="88" height="3" fill="#cbd5e1" rx="1" />
  </svg>
);

const PatternDThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Full-width top image */}
    <rect x="4" y="4" width="112" height="26" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="60" y="20" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">FULL WIDTH IMAGE</text>
    {/* Body text with inline small image on right */}
    <rect x="4" y="34" width="72" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="39" width="70" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="44" width="72" height="3" fill="#cbd5e1" rx="1" />
    {/* Small inline image floated right */}
    <rect x="80" y="34" width="36" height="28" fill="#fef9c3" rx="2" stroke="#fde047" strokeWidth="0.5" />
    <text x="98" y="51" fontSize="5" fill="#a16207" textAnchor="middle" fontFamily="sans-serif">IMG</text>
    {/* More wrapped text */}
    <rect x="4" y="49" width="72" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="54" width="65" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="66" width="112" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="71" width="98" height="3" fill="#cbd5e1" rx="1" />
  </svg>
);

const PatternEThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Headline */}
    <rect x="4" y="4" width="112" height="8" fill="#0D1B2A" rx="2" />
    <rect x="8" y="7" width="55" height="3" fill="#ffffff" rx="1" opacity="0.7" />
    {/* 1 full image top */}
    <rect x="4" y="16" width="112" height="28" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="60" y="33" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">MAIN IMAGE</text>
    {/* 2 images bottom */}
    <rect x="4" y="48" width="54" height="28" fill="#dcfce7" rx="2" stroke="#86efac" strokeWidth="0.5" />
    <text x="31" y="64" fontSize="5.5" fill="#16a34a" textAnchor="middle" fontFamily="sans-serif">IMG 2</text>
    <rect x="62" y="48" width="54" height="28" fill="#fae8ff" rx="2" stroke="#d8b4fe" strokeWidth="0.5" />
    <text x="89" y="64" fontSize="5.5" fill="#9333ea" textAnchor="middle" fontFamily="sans-serif">IMG 3</text>
  </svg>
);

const PatternFThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    {/* Headline */}
    <rect x="4" y="4" width="112" height="8" fill="#0D1B2A" rx="2" />
    <rect x="8" y="7" width="55" height="3" fill="#ffffff" rx="1" opacity="0.7" />
    {/* 3-column layout with images wrapped in text */}
    {/* Col 1 */}
    <rect x="4" y="16" width="34" height="20" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="21" y="28" fontSize="5" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">IMG</text>
    <rect x="4" y="38" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="43" width="30" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="48" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="53" width="28" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="58" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="63" width="30" height="3" fill="#cbd5e1" rx="1" />
    <rect x="4" y="68" width="34" height="3" fill="#cbd5e1" rx="1" />
    {/* Col 2 */}
    <rect x="43" y="16" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="21" width="30" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="26" width="34" height="18" fill="#dcfce7" rx="2" stroke="#86efac" strokeWidth="0.5" />
    <text x="60" y="37" fontSize="5" fill="#16a34a" textAnchor="middle" fontFamily="sans-serif">IMG</text>
    <rect x="43" y="46" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="51" width="28" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="56" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="61" width="30" height="3" fill="#cbd5e1" rx="1" />
    <rect x="43" y="66" width="34" height="3" fill="#cbd5e1" rx="1" />
    {/* Col 3 */}
    <rect x="82" y="16" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="21" width="30" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="26" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="31" width="28" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="36" width="34" height="18" fill="#fae8ff" rx="2" stroke="#d8b4fe" strokeWidth="0.5" />
    <text x="99" y="47" fontSize="5" fill="#9333ea" textAnchor="middle" fontFamily="sans-serif">IMG</text>
    <rect x="82" y="56" width="34" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="61" width="28" height="3" fill="#cbd5e1" rx="1" />
    <rect x="82" y="66" width="34" height="3" fill="#cbd5e1" rx="1" />
  </svg>
);

const PatternGThumbnail = () => (
  <svg viewBox="0 0 120 80" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="80" fill="#f8fafc" rx="4" />
    <rect x="4" y="4" width="112" height="8" fill="#0D1B2A" rx="2" />
    <rect x="8" y="7" width="55" height="3" fill="#ffffff" rx="1" opacity="0.7" />
    <rect x="4" y="16" width="112" height="28" fill="#dbeafe" rx="2" stroke="#93c5fd" strokeWidth="0.5" />
    <text x="60" y="33" fontSize="6" fill="#3b82f6" textAnchor="middle" fontFamily="sans-serif">MAIN IMAGE</text>
    <rect x="4" y="48" width="112" height="24" fill="#fef08a" rx="2" stroke="#fde047" strokeWidth="0.5" opacity="0.4" />
    <circle cx="10" cy="54" r="1.5" fill="#ca8a04" />
    <rect x="14" y="53" width="90" height="2" fill="#ca8a04" rx="1" opacity="0.7" />
    <circle cx="10" cy="59" r="1.5" fill="#ca8a04" />
    <rect x="14" y="58" width="80" height="2" fill="#ca8a04" rx="1" opacity="0.7" />
    <circle cx="10" cy="64" r="1.5" fill="#ca8a04" />
    <rect x="14" y="63" width="85" height="2" fill="#ca8a04" rx="1" opacity="0.7" />
  </svg>
);

// ─── Thumbnail map ─────────────────────────────────────────────────────────────
export const THUMBNAILS: Record<string, React.FC> = {
  A: PatternAThumbnail,
  B: PatternBThumbnail,
  C: PatternCThumbnail,
  D: PatternDThumbnail,
  E: PatternEThumbnail,
  F: PatternFThumbnail,
  G: PatternGThumbnail,
};

// ─── Props ─────────────────────────────────────────────────────────────────────
export interface TemplateCardProps {
  patternId: string;   // 'A' | 'B' | 'C' | 'D' | 'E' | 'F'
  title: string;
  description: string;
  isSelected: boolean;
  onSelect: (patternId: string) => void;
}

// ─── Component ─────────────────────────────────────────────────────────────────
export const TemplateCard = ({
  patternId,
  title,
  description,
  isSelected,
  onSelect,
}: TemplateCardProps) => {
  const Thumbnail = THUMBNAILS[patternId] ?? PatternAThumbnail;

  return (
    <div
      role="button"
      aria-pressed={isSelected}
      aria-label={`Select ${title}`}
      onClick={() => onSelect(patternId)}
      className={[
        'relative bg-white rounded-2xl overflow-hidden cursor-pointer select-none',
        'transition-all duration-200 active:scale-[0.97]',
        'shadow-[0_2px_12px_-4px_rgba(0,0,0,0.10)]',
        isSelected
          ? 'border-2 border-[#CC1E1E] shadow-[0_0_0_3px_rgba(204,30,30,0.12)]'
          : 'border-2 border-transparent hover:border-[#CC1E1E]/30 hover:shadow-[0_4px_20px_-6px_rgba(0,0,0,0.15)]',
      ].join(' ')}
    >
      {/* Selected badge */}
      {isSelected && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-[#CC1E1E] text-white text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full shadow-sm">
          <Check className="w-2.5 h-2.5 stroke-[3px]" />
          Selected
        </div>
      )}

      {/* Thumbnail area */}
      <div
        className={[
          'w-full aspect-[3/2] p-1.5 border-b transition-colors duration-200',
          isSelected ? 'bg-[#fff5f5] border-[#CC1E1E]/20' : 'bg-slate-50 border-slate-100',
        ].join(' ')}
      >
        <Thumbnail />
      </div>

      {/* Info area */}
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-1.5 mb-0.5">
          {/* Pattern ID badge */}
          <span
            className={[
              'text-[9px] font-extrabold uppercase tracking-widest px-1.5 py-0.5 rounded',
              isSelected ? 'bg-[#CC1E1E] text-white' : 'bg-slate-100 text-slate-500',
            ].join(' ')}
          >
            {patternId}
          </span>
          <h3 className="text-xs font-bold text-[#0D1B2A] leading-tight">{title}</h3>
        </div>
        <p className="text-[10px] text-slate-500 leading-snug">{description}</p>
      </div>
    </div>
  );
};
