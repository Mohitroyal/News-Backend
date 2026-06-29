import React from 'react';
import { X, ImageIcon, Images, LayoutTemplate } from 'lucide-react';

export const PATTERN_GROUPS = [
  {
    id: 'single',
    label: 'Single Image',
    icon: <ImageIcon className="w-3.5 h-3.5" />,
    patterns: [
      {
        patternId: 'A',
        title: 'Pattern A',
        description: 'Headline box at top · image on right · 2 column text',
      },
      {
        patternId: 'B',
        title: 'Pattern B',
        description: 'Left red bar headline · full width center image · 2 col text',
      },
    ],
  },
  {
    id: 'double',
    label: 'Double Image',
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
        description: 'Full image top · small inline image on right with text wrap',
      },
    ],
  },
  {
    id: 'multi',
    label: 'Multi Image',
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
];

export const PATTERN_TO_TEMPLATE_ID: Record<string, string> = {
  A: 'bharath_reporter',
  B: 'rti_express',
  C: 'national_news',
  D: 'extra_news',
  E: 'bharath_reporter',
  F: 'extra_news',
};

interface PatternSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPattern: string;
  onSelectPattern: (patternId: string) => void;
}

export const PatternSelectionModal: React.FC<PatternSelectionModalProps> = ({
  isOpen,
  onClose,
  selectedPattern,
  onSelectPattern,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div 
        className="w-full max-h-[85vh] bg-white rounded-t-2xl sm:rounded-2xl sm:max-w-md flex flex-col overflow-hidden animate-in slide-in-from-bottom-full sm:slide-in-from-bottom-10"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h2 className="text-[18px] font-bold font-serif text-[#0a1a2e]">Select Layout Pattern</h2>
          <button onClick={onClose} className="p-2 -mr-2 text-gray-500 rounded-full hover:bg-gray-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto space-y-6 bg-[#EEF3F8]">
          {PATTERN_GROUPS.map((group) => (
            <div key={group.id} className="mb-6 last:mb-0">
              <div className="flex items-center gap-2 mb-3 px-1">
                <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center">
                  {group.icon}
                </div>
                <h2 className="text-[#0D1B2A] font-bold text-[14px]">{group.label}</h2>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                {group.patterns.map((pattern) => {
                  const isSelected = selectedPattern === pattern.patternId;
                  return (
                    <button
                      key={pattern.patternId}
                      onClick={() => {
                        onSelectPattern(pattern.patternId);
                        onClose();
                      }}
                      className={`
                        text-left rounded-[12px] p-3 border-[1.5px] transition-all bg-white relative overflow-hidden
                        ${isSelected ? 'border-[#cc2222] shadow-sm' : 'border-[#b8d4e8] hover:border-blue-300'}
                      `}
                    >
                      {/* Mini preview thumbnail placeholder */}
                      <div className={`w-full aspect-[3/4] rounded-md mb-2 flex flex-col gap-1 p-1.5 ${isSelected ? 'bg-red-50' : 'bg-gray-50'}`}>
                        {pattern.patternId === 'A' && (
                          <>
                            <div className="w-full h-3 bg-gray-300 rounded-sm" />
                            <div className="flex gap-1 flex-1">
                              <div className="flex-1 flex flex-col gap-1">
                                <div className="w-full h-1 bg-gray-200" />
                                <div className="w-full h-1 bg-gray-200" />
                                <div className="w-full h-1 bg-gray-200" />
                              </div>
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                            </div>
                          </>
                        )}
                        {pattern.patternId === 'B' && (
                          <>
                            <div className="flex gap-1">
                              <div className="w-1 h-3 bg-[#cc2222]" />
                              <div className="flex-1 h-3 bg-gray-300 rounded-sm" />
                            </div>
                            <div className="w-full flex-1 bg-gray-300 rounded-sm" />
                            <div className="w-full h-2 bg-gray-200 rounded-sm" />
                          </>
                        )}
                        {pattern.patternId === 'C' && (
                          <>
                            <div className="flex gap-1 h-1/2">
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                            </div>
                            <div className="w-full h-1 bg-gray-200" />
                            <div className="w-full h-1 bg-gray-200" />
                          </>
                        )}
                        {pattern.patternId === 'D' && (
                          <>
                            <div className="w-full h-1/3 bg-gray-300 rounded-sm" />
                            <div className="flex gap-1 flex-1">
                              <div className="flex-1 flex flex-col gap-1">
                                <div className="w-full h-1 bg-gray-200" />
                                <div className="w-full h-1 bg-gray-200" />
                              </div>
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                            </div>
                          </>
                        )}
                        {pattern.patternId === 'E' && (
                          <>
                            <div className="w-full h-1/2 bg-gray-300 rounded-sm" />
                            <div className="flex gap-1 flex-1">
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                              <div className="flex-1 bg-gray-300 rounded-sm" />
                            </div>
                          </>
                        )}
                        {pattern.patternId === 'F' && (
                          <>
                            <div className="flex gap-1">
                              <div className="flex-1 aspect-square bg-gray-300 rounded-sm" />
                              <div className="flex-1 aspect-square bg-gray-300 rounded-sm" />
                              <div className="flex-1 aspect-square bg-gray-300 rounded-sm" />
                            </div>
                            <div className="w-full h-1 bg-gray-200" />
                            <div className="w-full h-1 bg-gray-200" />
                          </>
                        )}
                      </div>
                      <div className="font-bold text-[#0a1a2e] text-[12px] leading-tight mb-1">{pattern.title}</div>
                      <div className="text-[#888888] text-[9px] leading-snug">{pattern.description}</div>
                      
                      {isSelected && (
                        <div className="absolute top-2 right-2 w-3 h-3 bg-[#cc2222] rounded-full border border-white" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
