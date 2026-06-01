import { Loader2 } from 'lucide-react';

export const SplashScreen = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 relative overflow-hidden">
      {/* Background blobs */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-blue-600 rounded-full mix-blend-multiply filter blur-[120px] opacity-50 animate-pulse"></div>
      <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-indigo-600 rounded-full mix-blend-multiply filter blur-[120px] opacity-50 animate-pulse" style={{ animationDelay: '1s' }}></div>
      
      <div className="z-10 flex flex-col items-center">
        <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-br from-white via-gray-200 to-gray-500 bg-clip-text text-transparent mb-6 drop-shadow-lg">
          NewsCraft
        </h1>
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    </div>
  );
};
