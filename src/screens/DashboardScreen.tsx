import { FileText, Clock, Plus, Zap } from 'lucide-react';
import { useGenerationStore, useAuthStore } from '@/store';
import { useNavigate } from 'react-router-dom';

export const DashboardScreen = () => {
  const generations = useGenerationStore((state) => state.generations);
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();

  const recentGenerations = generations.slice(0, 3);

  return (
    <div className="p-6 pb-24 h-full dark:bg-gray-900 transition-colors duration-300">
      {/* Welcome Section */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Welcome back</h2>
          <h1 className="text-3xl font-extrabold text-gray-900 dark:text-white mt-1">
            {user?.full_name || user?.firstName || 'Journalist'}
          </h1>
        </div>
        <div className="w-12 h-12 bg-gradient-to-tr from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-500/30">
          {(user?.full_name || user?.firstName || 'J')[0]}
        </div>
      </div>

      {/* Quick Actions */}
      <h3 className="text-lg font-bold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
        <Zap className="w-5 h-5 text-yellow-500 fill-yellow-500" />
        Quick Actions
      </h3>
      <div className="grid grid-cols-2 gap-4 mb-10">
        <button 
          onClick={() => navigate('/generate')}
          className="bg-white dark:bg-gray-800 p-5 rounded-[24px] shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col items-center justify-center gap-3 aspect-square active:scale-95 transition-transform relative overflow-hidden group"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-14 h-14 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center relative z-10">
            <Plus className="text-blue-600 dark:text-blue-400 w-8 h-8" />
          </div>
          <span className="font-semibold text-gray-700 dark:text-gray-200 relative z-10">New Clipping</span>
        </button>
        
        <button 
          onClick={() => navigate('/templates')}
          className="bg-white dark:bg-gray-800 p-5 rounded-[24px] shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col items-center justify-center gap-3 aspect-square active:scale-95 transition-transform relative overflow-hidden group"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-14 h-14 bg-indigo-100 dark:bg-indigo-900/50 rounded-full flex items-center justify-center relative z-10">
            <FileText className="text-indigo-600 dark:text-indigo-400 w-7 h-7" />
          </div>
          <span className="font-semibold text-gray-700 dark:text-gray-200 relative z-10">Templates</span>
        </button>
      </div>

      {/* Recent Activity */}
      <div className="flex justify-between items-end mb-4">
        <h3 className="text-lg font-bold text-gray-800 dark:text-white flex items-center gap-2">
          <Clock className="w-5 h-5 text-gray-400" />
          Recent Clippings
        </h3>
        <button 
          onClick={() => navigate('/history')}
          className="text-sm font-semibold text-blue-600 dark:text-blue-400 active:opacity-70"
        >
          View All
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {recentGenerations.length === 0 ? (
          <div className="bg-gray-50 dark:bg-gray-800 rounded-2xl p-8 text-center border border-dashed border-gray-200 dark:border-gray-700">
            <p className="text-gray-500 dark:text-gray-400">No clippings generated yet.</p>
          </div>
        ) : (
          recentGenerations.map((gen) => (
            <div 
              key={gen.id} 
              onClick={() => gen?.id && navigate(`/preview/${gen.id}`)}
              className="bg-white dark:bg-gray-800 p-4 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 flex gap-4 items-center active:bg-gray-50 dark:active:bg-gray-700 transition-colors cursor-pointer"
            >
              <img 
                src={gen?.png_url || "https://placehold.co/100x120/png?text=Processing"} 
                alt="preview" 
                className="w-16 h-16 rounded-xl object-cover bg-gray-100 dark:bg-gray-900 shadow-inner"
              />
              <div className="flex-1">
                <h4 className="font-bold text-gray-800 dark:text-white line-clamp-1">{gen?.config?.headline || 'Untitled'}</h4>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs font-medium px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-md">
                    {gen?.config?.templateId ? String(gen.config.templateId).replace('_', ' ') : 'DEFAULT'}
                  </span>
                  <span className="text-xs text-gray-400">
                    {new Date(gen.createdAt).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
