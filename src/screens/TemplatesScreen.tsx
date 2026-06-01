import { useGenerationStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { LayoutTemplate, Check } from 'lucide-react';
import { TEMPLATES_LIST } from '@/lib/constants';

export const TemplatesScreen = () => {
  const currentConfig = useGenerationStore((state) => state.currentConfig);
  const setConfig = useGenerationStore((state) => state.setConfig);
  const navigate = useNavigate();

  const handleSelect = (templateId: string) => {
    setConfig({ templateId });
    navigate('/generate');
  };

  return (
    <div className="p-6 pb-24 max-w-md mx-auto h-full dark:bg-gray-900 transition-colors duration-300">
      <div className="mb-6 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <LayoutTemplate className="w-5 h-5 text-purple-600 dark:text-purple-400" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white transition-colors duration-300">Templates</h2>
      </div>

      <div className="space-y-4">
        {TEMPLATES_LIST.map((tpl) => {
          const isSelected = currentConfig.templateId === tpl.id;
          
          return (
            <div
              key={tpl.id}
              onClick={() => handleSelect(tpl.id)}
              className={`bg-white dark:bg-gray-800 p-4 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border transition-all cursor-pointer relative overflow-hidden ${
                isSelected ? 'border-purple-500 ring-2 ring-purple-500/20' : 'border-gray-100 dark:border-gray-700 hover:border-purple-200 dark:hover:border-purple-800'
              }`}
            >
              {isSelected && (
                <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center z-10">
                  <Check className="w-3.5 h-3.5 text-white stroke-[3px]" />
                </div>
              )}
              
              <div className="flex items-center gap-4">
                <div className={`w-24 h-12 rounded-xl ${tpl.bgColor} border ${tpl.borderColor} p-1.5 flex items-center justify-center shrink-0`}>
                  {tpl.icon}
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 dark:text-white transition-colors duration-300">{tpl.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 transition-colors duration-300">{tpl.description}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
