import { History } from 'lucide-react';
import { useGenerationStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '@/lib/i18n';

export const HistoryScreen = () => {
  const generations = useGenerationStore((state) => state.generations);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const safeGenerations = Array.isArray(generations) ? generations.filter(Boolean) : [];

  return (
    <div className="p-6 pb-6 dark:bg-gray-900 transition-colors duration-300">
      <div className="mb-6 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
          <History className="w-5 h-5 text-orange-600 dark:text-orange-400" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white transition-colors duration-300">{t.history}</h2>
      </div>

      <div className="flex flex-col gap-4">
        {safeGenerations.length === 0 ? (
          <div className="bg-gray-50 dark:bg-gray-800 rounded-3xl p-8 text-center border border-dashed border-gray-200 dark:border-gray-700 transition-colors duration-300">
            <p className="text-gray-500 dark:text-gray-400">{t.noClippingsFound}</p>
          </div>
        ) : (
          safeGenerations.map((gen: any, i: number) => {
            const key = gen?.id || `fallback-key-${i}`;
            return (
              <div 
                key={key} 
                onClick={() => gen?.id && navigate(`/preview/${gen.id}`)}
                className="bg-white dark:bg-gray-800 p-4 rounded-3xl shadow-[0_2px_10px_-4px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 flex gap-4 active:scale-[0.98] transition-all cursor-pointer hover:border-gray-200 dark:hover:border-gray-600"
              >
                <img 
                  src={gen?.png_url || "https://placehold.co/100x120/png?text=Processing"} 
                  alt="preview" 
                  className="w-20 h-24 rounded-2xl object-cover bg-gray-100 dark:bg-gray-900 shadow-sm"
                />
                <div className="flex-1 flex flex-col justify-center">
                  <h4 className="font-bold text-gray-800 dark:text-white text-lg leading-tight line-clamp-2 mb-2">
                    {gen?.config?.headline || gen?.config?.publicationName || t.untitled}
                  </h4>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg transition-colors duration-300">
                      {gen?.config?.templateId ? String(gen.config.templateId).replace('_', ' ') : "DEFAULT"}
                    </span>
                    <span className="text-xs text-gray-400">
                      {gen?.createdAt ? new Date(gen.createdAt).toLocaleDateString() : t.processing}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
