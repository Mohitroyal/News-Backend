import React from 'react';
import watermarkLogo from '@/assets/rti_express_watermark.png';
import { ImageIcon } from 'lucide-react';

interface LiveNewspaperPreviewProps {
  patternId: string;
  borderColour: string;
  headingBgColour: string;
  headlineText: string;
  onPress: () => void;
}

export const LiveNewspaperPreview: React.FC<LiveNewspaperPreviewProps> = ({
  patternId,
  borderColour,
  headingBgColour,
  headlineText,
  onPress,
}) => {
  return (
    <div className="flex flex-col items-center w-full">
      <div 
        onClick={onPress}
        className="w-full bg-white relative cursor-pointer active:scale-[0.98] transition-transform shadow-sm rounded-lg flex flex-col overflow-hidden"
        style={{ border: `2px solid ${borderColour}` }}
      >
        {/* Top header inside the border */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
          <span className="text-[10px] font-bold text-gray-500 tracking-wider">PATTERN {patternId}</span>
          <span className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: borderColour }}></span>
        </div>

        {/* The actual pattern container */}
        <div className="p-2 relative flex-1 flex flex-col h-[150px]">
          {/* Watermark */}
          <div className="absolute inset-0 flex items-center justify-center opacity-10 pointer-events-none overflow-hidden z-0">
             <img src={watermarkLogo} alt="Watermark" className="w-[140px] object-contain -rotate-[30deg] mix-blend-multiply" />
          </div>

          <div className="flex-1 w-full relative z-10 flex flex-col p-1.5 bg-white/80 backdrop-blur-[1px]" style={{ border: `1px solid ${borderColour}` }}>
            {patternId === 'A' && (
              <>
                 <div className="w-full p-1.5" style={{ backgroundColor: headingBgColour }}>
                   <div className="text-[10px] font-bold leading-tight font-serif text-black truncate">
                     {headlineText || 'Headline text...'}
                   </div>
                 </div>
                 <div className="w-full h-1 mt-1 border-y" style={{ borderColor: borderColour }} />
                 <div className="flex gap-2 flex-1 mt-1.5">
                   <div className="flex-1 flex flex-col gap-1.5 pt-0.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-5/6 h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-4/5 h-[3px] bg-gray-300 rounded-full" />
                   </div>
                   <div className="w-[45px] h-[45px] bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-4 h-4 text-blue-300" strokeWidth={1.5} />
                   </div>
                 </div>
              </>
            )}
            
            {patternId === 'B' && (
              <>
                 <div className="flex gap-1.5 items-center mb-1">
                   <div className="w-1.5 h-6" style={{ backgroundColor: borderColour }} />
                   <div className="flex-1 p-1.5" style={{ backgroundColor: headingBgColour }}>
                     <div className="text-[10px] font-bold leading-tight font-serif text-black truncate">
                       {headlineText || 'Headline text...'}
                     </div>
                   </div>
                 </div>
                 <div className="w-full h-[45px] mb-1.5 bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                   <ImageIcon className="w-4 h-4 text-blue-300" strokeWidth={1.5} />
                 </div>
                 <div className="flex gap-2 flex-1">
                   <div className="flex-1 flex flex-col gap-1.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-5/6 h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                   </div>
                   <div className="flex-1 flex flex-col gap-1.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-4/5 h-[3px] bg-gray-300 rounded-full" />
                   </div>
                 </div>
              </>
            )}

            {patternId === 'C' && (
              <>
                 <div className="w-full p-1.5 mb-1.5" style={{ backgroundColor: headingBgColour }}>
                   <div className="text-[10px] font-bold leading-tight font-serif text-black truncate text-center border-y border-dashed py-0.5" style={{ borderColor: borderColour }}>
                     {headlineText || 'Headline text...'}
                   </div>
                 </div>
                 <div className="flex gap-1.5 h-[45px] mb-1.5">
                   <div className="flex-1 bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-4 h-4 text-blue-300" strokeWidth={1.5} />
                   </div>
                   <div className="flex-1 bg-green-50 border border-green-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-4 h-4 text-green-300" strokeWidth={1.5} />
                   </div>
                 </div>
                 <div className="flex-1 flex flex-col gap-1.5">
                   <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                   <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                   <div className="w-3/4 h-[3px] bg-gray-300 rounded-full" />
                 </div>
              </>
            )}

            {patternId === 'D' && (
              <>
                 <div className="w-full h-[35px] mb-1 bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                   <ImageIcon className="w-4 h-4 text-blue-300" strokeWidth={1.5} />
                 </div>
                 <div className="w-full p-1.5 mb-1.5" style={{ backgroundColor: headingBgColour }}>
                   <div className="text-[10px] font-bold leading-tight font-serif text-black truncate flex items-center gap-1">
                     <span style={{ color: borderColour }}>■</span>
                     {headlineText || 'Headline text...'}
                   </div>
                 </div>
                 <div className="flex gap-2 flex-1">
                   <div className="flex-1 flex flex-col gap-1.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-4/5 h-[3px] bg-gray-300 rounded-full" />
                   </div>
                   <div className="w-[35px] h-full bg-yellow-50 border border-yellow-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-yellow-400" strokeWidth={1.5} />
                   </div>
                 </div>
              </>
            )}

            {patternId === 'E' && (
              <>
                 <div className="w-full p-1.5 mb-1.5" style={{ backgroundColor: headingBgColour }}>
                   <div className="text-[10px] font-bold leading-tight font-serif text-black truncate text-center">
                     {headlineText || 'Headline text...'}
                   </div>
                 </div>
                 <div className="w-full h-[40px] mb-1.5 bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                   <ImageIcon className="w-4 h-4 text-blue-300" strokeWidth={1.5} />
                 </div>
                 <div className="flex-1 flex flex-col gap-1.5 mb-1.5 justify-center">
                   <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                   <div className="w-3/4 h-[3px] bg-gray-300 rounded-full mx-auto" />
                 </div>
                 <div className="flex gap-1 h-[25px]">
                   <div className="flex-1 bg-green-50 border border-green-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-green-300" strokeWidth={1.5} />
                   </div>
                   <div className="flex-1 bg-purple-50 border border-purple-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-purple-300" strokeWidth={1.5} />
                   </div>
                 </div>
              </>
            )}

            {patternId === 'F' && (
              <>
                 <div className="flex gap-1.5 items-center mb-1.5">
                   <div className="w-1.5 h-6" style={{ backgroundColor: borderColour }} />
                   <div className="flex-1 p-1.5" style={{ backgroundColor: headingBgColour }}>
                     <div className="text-[10px] font-bold leading-tight font-serif text-black truncate">
                       {headlineText || 'Headline text...'}
                     </div>
                   </div>
                 </div>
                 <div className="flex gap-1 h-[30px] mb-1.5">
                   <div className="flex-1 bg-blue-100/50 border border-blue-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-blue-300" strokeWidth={1.5} />
                   </div>
                   <div className="flex-1 bg-green-50 border border-green-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-green-300" strokeWidth={1.5} />
                   </div>
                   <div className="flex-1 bg-purple-50 border border-purple-200 flex items-center justify-center rounded-sm">
                     <ImageIcon className="w-3 h-3 text-purple-300" strokeWidth={1.5} />
                   </div>
                 </div>
                 <div className="flex gap-2 flex-1">
                   <div className="flex-1 flex flex-col gap-1.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-5/6 h-[3px] bg-gray-300 rounded-full" />
                   </div>
                   <div className="flex-1 flex flex-col gap-1.5">
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                     <div className="w-full h-[3px] bg-gray-300 rounded-full" />
                   </div>
                 </div>
              </>
            )}

          </div>
        </div>
      </div>
    </div>
  );
};
