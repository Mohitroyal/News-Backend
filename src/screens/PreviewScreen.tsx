import { useParams, useNavigate } from 'react-router-dom';
import { useGenerationStore } from '@/store';
import { ArrowLeft, Download, FileDown, Share2, MoreHorizontal, FileText } from 'lucide-react';
import { generationService } from '@/services/generation.service';
import { useState, useEffect, useRef } from 'react';
import { Capacitor } from '@capacitor/core';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';

// ─── Stage → Progress mapping ───────────────────────────────────────────────
const STAGE_PROGRESS: Record<string, number> = {
  'initialization':           5,
  'Image Processing':         15,
  'Content Generation':       30,
  'Translation':              35,
  'Database Save (rendering)':40,
  'Template Selection':       45,
  'HTML Generation':          55,
  'Screenshot Generation':    70,
  'Font Loading':             72,
  'Playwright Launch':        74,
  'PNG Screenshot Creation':  80,
  'Supabase Upload (PNG)':    85,
  'PDF Generation':           88,
  'PDF Creation':             90,
  'Supabase Upload (PDF)':    93,
  'Database Save (completed)':97,
  'Email Notification':       99,
  'Final Response':           100,
};

const MAX_POLL_MS     = 10 * 60 * 1000; // 10 minutes
const POLL_INTERVAL   = 3000;           // 3 seconds
const MAX_CONSEC_FAIL = 30;             // 30 consecutive network failures before stopping

function getProgress(stage?: string): number {
  if (!stage) return 10;
  return STAGE_PROGRESS[stage] ?? 10;
}

function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export const PreviewScreen = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const generations = useGenerationStore((state) => state.generations);
  const generation = generations.find(g => g.id === id);
  const updateGeneration = useGenerationStore((state) => state.updateGeneration);

  const [downloading, setDownloading] = useState(false);
  const [isShareSheetOpen, setIsShareSheetOpen] = useState(false);
  const [pollAttempt, setPollAttempt]   = useState(0);
  const [elapsedMs,  setElapsedMs]      = useState(0);
  const [liveStage, setLiveStage]       = useState<string>('');

  const startTimeRef    = useRef<number>(Date.now());
  const consecFailRef   = useRef<number>(0);
  const intervalRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (
      !generation ||
      generation.status === 'completed' ||
      generation.status === 'failed' ||
      generation.png_url
    ) return;

    startTimeRef.current  = Date.now();
    consecFailRef.current = 0;
    setPollAttempt(0);
    setElapsedMs(0);

    // ── Elapsed-time ticker ──────────────────────────────────────────────────
    elapsedTimerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 1000);

    // ── Main polling loop ────────────────────────────────────────────────────
    intervalRef.current = setInterval(async () => {
      const elapsed = Date.now() - startTimeRef.current;

      // Hard 10-minute timeout
      if (elapsed >= MAX_POLL_MS) {
        console.warn(`[POLL] 10-minute timeout reached. Stopping.`);
        clearInterval(intervalRef.current!);
        clearInterval(elapsedTimerRef.current!);
        updateGeneration(generation.id, {
          status:  'failed',
          stage:   'Polling Timeout',
          message: `Generation did not complete within 10 minutes (${fmtElapsed(elapsed)}). The backend may still be running — check Render logs.`,
          error:   'Frontend polling timeout after 10 minutes.',
        } as any);
        return;
      }

      setPollAttempt(n => n + 1);
      const attempt = pollAttempt + 1;
      const ts = new Date().toISOString();
      console.log(`[POLL] #${attempt} | elapsed=${fmtElapsed(elapsed)} | ${ts}`);

      try {
        const pollRes = await generationService.getById(generation.id) as any;
        const generationData = pollRes?.data || pollRes;

        if (generationData && generationData.id) {
          // Successful response — reset consecutive-failure counter
          consecFailRef.current = 0;

          // Track live stage for progress bar
          const stage = generationData.stage || generationData.current_stage || liveStage;
          if (stage) setLiveStage(stage);

          // Compute progress from stage map
          const progress = generationData.progress ?? getProgress(stage);

          updateGeneration(generation.id, { ...generationData, progress });

          console.log(`[POLL] #${attempt} | status=${generationData.status} | stage=${stage} | progress=${progress}%`);

          if (generationData.status === 'completed' || generationData.status === 'failed') {
            clearInterval(intervalRef.current!);
            clearInterval(elapsedTimerRef.current!);
          }
        }
      } catch (e: any) {
        consecFailRef.current += 1;
        const cf = consecFailRef.current;

        console.warn(`[POLL] #${attempt} NETWORK ERROR (consecutive=${cf}):`, e?.message || e);

        // If server returns 503/502 → likely Render waking up
        const status = e?.response?.status;
        if (status === 503 || status === 502 || status === 0 || !status) {
          // setServerWaking(true);
        }

        if (cf >= MAX_CONSEC_FAIL) {
          console.warn(`[POLL] Too many consecutive network failures (${cf}). Stopping.`);
          clearInterval(intervalRef.current!);
          clearInterval(elapsedTimerRef.current!);
          updateGeneration(generation.id, {
            status:  'failed',
            stage:   'Polling Network Failures',
            message: `Polling stopped after ${cf} consecutive network errors. Please check your network connection.`,
            error:   'Too many consecutive polling network failures.',
          } as any);
        }
      }
    }, POLL_INTERVAL);

    return () => {
      clearInterval(intervalRef.current!);
      clearInterval(elapsedTimerRef.current!);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generation?.id, generation?.status]);

  if (!generation) {
    return (
      <div className="flex flex-col items-center justify-center h-full pt-20">
        <p className="text-gray-500">Clipping not found.</p>
        <button onClick={() => navigate(-1)} className="mt-4 text-blue-600 font-medium">Go Back</button>
      </div>
    );
  }

  const handleDownload = async (format: 'png' | 'pdf') => {
    setDownloading(true);
    try {
      let blob;
      if (format === 'png') {
        if (!generation.png_url) throw new Error("PNG URL not available");
        const res = await fetch(generation.png_url);
        blob = await res.blob();
      } else {
        if (generation.pdf_url) {
          const res = await fetch(generation.pdf_url);
          blob = await res.blob();
        } else {
          blob = await generationService.exportPdf(generation.id);
        }
      }

      const fileName = `newscraft-${generation.id}.${format}`;

      if (Capacitor.isNativePlatform()) {
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = async () => {
          let base64data = reader.result as string;
          if (base64data.includes(',')) base64data = base64data.split(',')[1];
          try {
            if (Capacitor.getPlatform() === 'android') {
              await Filesystem.requestPermissions();
            }
            await Filesystem.writeFile({ path: fileName, data: base64data, directory: Directory.Documents });
            alert(`${format.toUpperCase()} Downloaded successfully to your Documents!`);
          } catch (e) {
            console.error("Filesystem write error", e);
            alert(`Failed to save to device storage: ${e}`);
          } finally {
            setDownloading(false);
          }
        };
      } else {
        const blobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(blobUrl);
        alert(`${format.toUpperCase()} Downloaded successfully to your device!`);
        setDownloading(false);
      }
    } catch (err) {
      console.error(err);
      alert(`Failed to download ${format.toUpperCase()}`);
      setDownloading(false);
    }
  };

  const handleShareOptionClick = async (optionName: string) => {
    if (!generation.png_url) return;

    setDownloading(true);
    setIsShareSheetOpen(false);

    try {
      const title = 'Share Newspaper Clipping';
      const text = 'Check out this newspaper clipping generated by NewsCraft!';

      // Fetch image blob
      const res = await fetch(generation.png_url);
      const blob = await res.blob();

      if (Capacitor.isNativePlatform()) {
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = async () => {
          let base64data = reader.result as string;
          if (base64data.includes(',')) base64data = base64data.split(',')[1];
          try {
            const tempFileName = `newscraft-share-${generation.id}.png`;
            const writeResult = await Filesystem.writeFile({
              path: tempFileName,
              data: base64data,
              directory: Directory.Cache
            });

            await Share.share({
              title,
              text,
              url: writeResult.uri,
              dialogTitle: 'Share Newspaper Clipping'
            });
          } catch (e) {
            console.error("Filesystem share error", e);
            alert(`Failed to share: ${e}`);
          } finally {
            setDownloading(false);
          }
        };
      } else {
        const shareUrl = generation.png_url;

        // Try Web Share API if supported
        if (navigator.share) {
          try {
            const file = new File([blob], `newscraft-${generation.id}.png`, { type: blob.type });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
              await navigator.share({
                title,
                text,
                files: [file]
              });
              setDownloading(false);
              return;
            }
          } catch (e) {
            console.log("Web file sharing failed, falling back to URL sharing", e);
          }
        }

        // Web Social Share Fallbacks
        let url = '';
        switch (optionName) {
          case 'WhatsApp':
            url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text + '\n' + shareUrl)}`;
            break;
          case 'Facebook':
            url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
            break;
          case 'Instagram':
            await navigator.clipboard.writeText(shareUrl);
            alert('Image link copied to clipboard! Share it on Instagram.');
            setDownloading(false);
            return;
          case 'X (Twitter)':
            url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl)}`;
            break;
          case 'Telegram':
            url = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(text)}`;
            break;
          case 'Gmail':
            url = `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(text + '\n\n' + shareUrl)}`;
            break;
          default:
            if (navigator.share) {
              await navigator.share({ title, text, url: shareUrl });
            } else {
              await navigator.clipboard.writeText(shareUrl);
              alert('Image link copied to clipboard!');
            }
            setDownloading(false);
            return;
        }

        if (url) {
          window.open(url, '_blank');
        }
        setDownloading(false);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to share clipping');
      setDownloading(false);
    }
  };

  // ── Derived state for the progress UI ────────────────────────────────────
  const progressPercent = generation.progress ?? getProgress(liveStage || generation.stage);
  const timeLeft        = Math.max(0, MAX_POLL_MS - elapsedMs);

  return (
    <div className="h-screen bg-[#dceef8] flex flex-col fixed inset-0 z-50 font-sans text-[#0a1a2e]">
      {/* ── HEADER ──────────────────────────────────────────────────────── */}
      <div className="h-16 bg-[#0a2540] border-b-[3px] border-[#cc2222] flex items-center px-4 shrink-0 shadow-sm relative z-20">
        <button
          onClick={() => {
            if (generation.status === 'processing' || generation.status === 'pending') {
              if (window.confirm("Cancel generation?")) navigate(-1);
            } else {
              navigate(-1);
            }
          }}
          className="w-10 h-10 bg-[#cc2222] active:bg-[#a01b1b] rounded-full text-white transition-colors flex items-center justify-center shrink-0 mr-4 shadow-sm"
        >
          <ArrowLeft className="w-5 h-5 ml-[-2px]" />
        </button>
        <div className="flex flex-col flex-1 truncate">
          <span className="text-white font-bold text-[17px] tracking-wide" style={{ fontFamily: 'Georgia, serif' }}>Preview</span>
          <span className="text-[10px] text-[#a0c4dc] tracking-wider truncate">
            clipping_{generation.id.slice(0, 8)}.png
          </span>
        </div>
      </div>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col items-center justify-center relative z-10">

        {/* ── STATE 1: GENERATING ────────────────────────────────────────── */}
        {(!generation.png_url && generation.status !== 'failed') && (
          <div className="flex flex-col items-center w-full max-w-sm px-4">
            {/* SPINNER */}
            <div className="relative w-[120px] h-[120px] flex items-center justify-center mb-6">
              {/* Outer glowing ring */}
              <div className="absolute inset-0 rounded-full border-[2px] border-[#cc2222]/20 shadow-[0_0_15px_rgba(204,34,34,0.3)] animate-pulse" style={{ animationDuration: '3s' }} />
              {/* Inner ring */}
              <div className="absolute inset-0 rounded-full border-[4px] border-transparent border-t-[#cc2222] border-r-[#cc2222] animate-spin" style={{ animationDuration: '1.8s', animationTimingFunction: 'linear' }} />
              {/* Orbiting dot */}
              <div className="absolute inset-0 animate-spin" style={{ animationDuration: '3s', animationTimingFunction: 'linear' }}>
                <div className="absolute top-0 left-1/2 w-3 h-3 bg-[#cc2222] rounded-full shadow-[0_0_8px_#cc2222] transform -translate-x-1/2 -translate-y-1/2" />
              </div>
              {/* Center Icon */}
              <div className="w-12 h-12 bg-white rounded-[10px] shadow-[0_0_12px_rgba(204,34,34,0.2)] flex items-center justify-center text-[#0a2540] animate-pulse" style={{ animationDuration: '2s' }}>
                <FileText className="w-6 h-6" />
              </div>
            </div>

            {/* STATUS TEXT */}
            <h2 className="text-[#0a1a2e] font-bold text-[16px] mb-1 text-center" style={{ fontFamily: 'Georgia, serif' }}>Generating Clipping</h2>
            <p className="text-[#a0c4dc] text-[10px] font-medium mb-3 text-center">Processing newspaper layout</p>
            <div className="text-[#cc2222] font-bold text-[28px] mb-6 tracking-tight drop-shadow-sm transition-all duration-300 transform scale-105">{progressPercent}%</div>

            {/* PROGRESS BAR */}
            <div className="w-full mb-6">
              <div className="flex justify-between text-[9px] uppercase font-bold text-[#a0c4dc] mb-1.5">
                <span>Progress</span>
                <span>{progressPercent}/100</span>
              </div>
              <div className="w-full h-[8px] bg-[#b8d4e8] rounded-[4px] overflow-hidden shadow-inner relative">
                {/* Liquid / Shimmer Progress Fill */}
                <div
                  className="absolute top-0 left-0 h-full rounded-[4px] transition-all duration-500 ease-out"
                  style={{ 
                    width: `${progressPercent}%`,
                    background: 'linear-gradient(90deg, #cc2222, #ff6666, #cc2222)',
                    backgroundSize: '200% 100%',
                    animation: 'shimmer 2s infinite linear'
                  }}
                />
              </div>
            </div>

            {/* INFO CARD */}
            <div className="w-full bg-white border border-[#b8d4e8] rounded-lg p-3.5 mb-6 shadow-sm">
              <div className="flex justify-between items-center mb-2.5 animate-in slide-in-from-right-4 duration-300 fade-in fill-mode-both" style={{ animationDelay: '0ms' }}>
                <span className="text-[#0a1a2e] text-[10px] font-semibold">Poll #</span>
                <span className="text-[#0a1a2e] text-[10px] font-mono font-medium">{pollAttempt}</span>
              </div>
              <div className="flex justify-between items-center mb-2.5 animate-in slide-in-from-right-4 duration-300 fade-in fill-mode-both" style={{ animationDelay: '100ms' }}>
                <span className="text-[#0a1a2e] text-[10px] font-semibold">Elapsed</span>
                <span className="text-[#0a1a2e] text-[10px] font-mono font-medium">{(elapsedMs / 1000).toFixed(1)}s</span>
              </div>
              <div className="flex justify-between items-center mb-2.5 animate-in slide-in-from-right-4 duration-300 fade-in fill-mode-both" style={{ animationDelay: '200ms' }}>
                <span className="text-[#0a1a2e] text-[10px] font-semibold">Timeout in</span>
                <span className="text-[#0a1a2e] text-[10px] font-mono font-medium">{(timeLeft / 1000).toFixed(1)}s</span>
              </div>
              <div className="flex justify-between items-center animate-in slide-in-from-right-4 duration-300 fade-in fill-mode-both" style={{ animationDelay: '300ms' }}>
                <span className="text-[#0a1a2e] text-[10px] font-semibold">Pattern</span>
                <span className="text-[#0a1a2e] text-[10px] font-mono font-medium">Pattern {generation.config?.layoutPattern || 'A'}</span>
              </div>
            </div>

            {/* HINT BAR */}
            <div className="w-full bg-[#0a2540] rounded-[6px] py-[10px] px-[14px] flex items-center justify-center gap-2 shadow-sm animate-in zoom-in-95 duration-500 fill-mode-both" style={{ animationDelay: '400ms' }}>
              <div className="w-3.5 h-3.5 rounded-full bg-[#a0c4dc]/20 flex items-center justify-center shrink-0">
                <span className="text-[#a0c4dc] text-[9px] font-bold font-serif italic">i</span>
              </div>
              <span className="text-[#a0c4dc] text-[10px] font-medium tracking-wide">Checking every 3 seconds &middot; Do not close this screen</span>
            </div>
          </div>
        )}

        {/* ── STATE 3: ERROR ─────────────────────────────────────────────── */}
        {(!generation.png_url && generation.status === 'failed') && (
           <div className="flex flex-col items-center w-full max-w-sm px-4">
              <div className="w-[120px] h-[120px] rounded-full bg-[#cc2222] flex items-center justify-center mb-6 shadow-lg animate-in fade-in zoom-in duration-300" style={{ animation: 'shake 0.3s cubic-bezier(.36,.07,.19,.97) both' }}>
                <span className="text-white text-[60px] font-bold leading-none mt-[-4px]">!</span>
              </div>
              <h2 className="text-[#cc2222] font-bold text-[18px] mb-2 text-center" style={{ fontFamily: 'Georgia, serif' }}>Generation Failed</h2>
              <div className="bg-white border border-[#b8d4e8] p-4 rounded-lg w-full mb-8 shadow-sm">
                <p className="text-[#0a1a2e] text-[12px] text-center font-medium leading-relaxed">
                  {generation.message || generation.error || 'An unexpected error occurred during clipping generation.'}
                </p>
              </div>
              
              <button 
                onClick={() => navigate(-1)}
                className="w-full bg-[#cc2222] active:bg-[#a01b1b] text-white py-[14px] rounded-[8px] font-bold text-xs tracking-wider uppercase transition-colors shadow-sm flex justify-center items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Retry</span>
              </button>
           </div>
        )}

        {/* ── STATE 2: COMPLETE ───────────────────────────────────────────── */}
        {(generation.png_url) && (
          <div className="flex flex-col items-center w-full h-full relative animate-in fade-in duration-500 pb-2">
             <div className="flex flex-col items-center mb-4 shrink-0 relative">
               <div className="absolute inset-0 bg-[#0a2540] rounded-full opacity-0 animate-ping" style={{ animationDuration: '1.5s', animationDelay: '0.4s' }} />
               <div className="w-12 h-12 rounded-full bg-[#0a2540] flex items-center justify-center mb-2 shadow-sm animate-in zoom-in duration-500" style={{ animationTimingFunction: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)' }}>
                 <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" style={{ strokeDasharray: 24, strokeDashoffset: 24, animation: 'draw 0.4s ease-out 0.3s forwards' }} />
                 </svg>
               </div>
               <h2 className="text-[#0a1a2e] font-bold text-[18px] animate-in slide-in-from-bottom-2 duration-300" style={{ fontFamily: 'Georgia, serif' }}>Clipping Ready</h2>
             </div>

             <div className="flex-1 w-full min-h-0 flex justify-center mb-5 bg-white border-[2px] border-[#cc2222] p-1 shadow-sm relative overflow-hidden group animate-in slide-in-from-bottom-4 duration-500 delay-100 fill-mode-both">
               {/* This box contains the actual clipping. No watermarks inside here! */}
               <img
                  src={generation.png_url}
                  alt="Newspaper Preview"
                  className="w-full h-full object-contain bg-white transition-transform duration-700 ease-out hover:scale-[1.02]"
                />
             </div>

             <div className="w-full shrink-0 flex flex-col gap-2">
                <div className="flex w-full gap-2">
                  <button
                    onClick={() => handleDownload('png')}
                    disabled={downloading}
                    className="flex-1 py-[14px] bg-[#cc2222] hover:bg-[#ff3333] active:bg-[#a01b1b] text-white rounded-[8px] font-bold text-xs tracking-wider uppercase transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-[0_4px_12px_rgba(204,34,34,0.3)] animate-in slide-in-from-bottom-2 duration-300 delay-200 fill-mode-both relative overflow-hidden group"
                  >
                    <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:animate-[shimmerSweep_1s_ease-out]" />
                    <Download className="w-4 h-4 shrink-0" />
                    <span>Save PNG</span>
                  </button>

                  <button
                    onClick={() => handleDownload('pdf')}
                    disabled={downloading}
                    className="flex-1 py-[14px] bg-[#0a2540] hover:bg-[#071a2d] active:bg-[#071a2d] text-[#7bbce0] rounded-[8px] font-bold text-xs tracking-wider uppercase transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-[0_4px_12px_rgba(10,37,64,0.3)] animate-in slide-in-from-bottom-2 duration-300 delay-300 fill-mode-both relative overflow-hidden group"
                  >
                    <div className="absolute inset-0 bg-white/10 translate-x-[-100%] group-hover:animate-[shimmerSweep_1s_ease-out]" />
                    <FileDown className="w-4 h-4 shrink-0" />
                    <span>Save PDF</span>
                  </button>
                </div>

                <button
                  onClick={() => setIsShareSheetOpen(true)}
                  disabled={downloading}
                  className="w-full py-[14px] bg-[#dceef8] hover:bg-[#b8d4e8] active:bg-[#b8d4e8] text-[#0a2540] border-[1px] border-[#b8d4e8] rounded-[8px] font-bold text-xs tracking-wider uppercase transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-md animate-in slide-in-from-bottom-2 duration-300 delay-400 fill-mode-both relative overflow-hidden group"
                >
                  <div className="absolute inset-0 bg-white/40 translate-x-[-100%] group-hover:animate-[shimmerSweep_1s_ease-out]" />
                  <Share2 className="w-4 h-4 shrink-0" />
                  <span>Share</span>
                </button>
             </div>
          </div>
        )}
      </div>

      {/* ── Share Bottom Sheet (styled to match palette) ─────────────────── */}
      {isShareSheetOpen && (
        <div 
          className="fixed inset-0 bg-[#0a2540]/60 backdrop-blur-sm z-[60] transition-opacity duration-300"
          onClick={() => setIsShareSheetOpen(false)}
        >
          <div 
            className="fixed bottom-0 left-0 right-0 bg-white border-t-[3px] border-[#cc2222] rounded-t-[20px] p-6 pb-safe z-[60] transform transition-transform duration-300 shadow-2xl animate-in slide-in-from-bottom-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-12 h-1 bg-[#b8d4e8] rounded-full mx-auto mb-6" />
            <h3 className="text-[#0a2540] font-bold text-lg mb-6 text-center" style={{ fontFamily: 'Georgia, serif' }}>Share Newspaper Clipping</h3>
            
            <div className="grid grid-cols-4 gap-y-6 gap-x-2 justify-items-center mb-6">
              {/* WhatsApp */}
              <button onClick={() => handleShareOptionClick('WhatsApp')} className="flex flex-col items-center gap-2 text-[#0a1a2e] hover:scale-105 active:scale-95 transition-transform">
                <div className="w-12 h-12 rounded-full bg-[#25D366] flex items-center justify-center shadow-sm">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946C.06 5.348 5.397.01 12.008.01c3.202.001 6.212 1.246 8.477 3.514 2.266 2.268 3.507 5.28 3.505 8.484-.004 6.657-5.34 11.997-11.953 11.997-2.005-.001-3.973-.502-5.713-1.455L0 24zm6.59-11.597c-.279-.314-.555-.262-.773-.272-.2-.008-.428-.008-.656-.008-.228 0-.6-.086-.913-.429-.314-.343-1.198-1.172-1.198-2.859 0-1.687 1.226-3.314 1.398-3.543.171-.228 2.413-3.685 5.845-5.17.816-.353 1.453-.564 1.948-.72.822-.262 1.572-.225 2.164-.137.66.099 2.03.83 2.314 1.632.285.803.285 1.49.201 1.632-.083.14-.308.228-.651.4l-2.102 1.03c-.342.166-.591.248-.846.634-.255.38-.973 1.226-1.195 1.48-.222.254-.443.286-.786.114-.343-.171-1.447-.533-2.755-1.7c-1.018-.908-1.704-2.03-1.902-2.372-.199-.343-.021-.528.15-.699.153-.153.343-.4.514-.6.171-.2.228-.343.343-.571.114-.229.057-.429-.028-.6-.086-.171-.773-1.857-1.059-2.543-.278-.669-.561-.578-.773-.589z"/>
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-center leading-tight">WhatsApp</span>
              </button>

              {/* Facebook */}
              <button onClick={() => handleShareOptionClick('Facebook')} className="flex flex-col items-center gap-2 text-[#0a1a2e] hover:scale-105 active:scale-95 transition-transform">
                <div className="w-12 h-12 rounded-full bg-[#1877F2] flex items-center justify-center shadow-sm">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-center leading-tight">Facebook</span>
              </button>

              {/* X (Twitter) */}
              <button onClick={() => handleShareOptionClick('X (Twitter)')} className="flex flex-col items-center gap-2 text-[#0a1a2e] hover:scale-105 active:scale-95 transition-transform">
                <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center shadow-sm">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                </div>
                <span className="text-[10px] font-semibold text-center leading-tight">X (Twitter)</span>
              </button>

              {/* More Apps */}
              <button onClick={() => handleShareOptionClick('More Apps')} className="flex flex-col items-center gap-2 text-[#0a1a2e] hover:scale-105 active:scale-95 transition-transform">
                <div className="w-12 h-12 rounded-full bg-[#b8d4e8] flex items-center justify-center shadow-sm text-[#0a2540]">
                  <MoreHorizontal className="w-5 h-5" />
                </div>
                <span className="text-[10px] font-semibold text-center leading-tight">More Apps</span>
              </button>
            </div>
            
            <button
              onClick={() => setIsShareSheetOpen(false)}
              className="w-full py-[14px] bg-[#dceef8] hover:bg-[#b8d4e8] active:bg-[#a0c4dc] text-[#0a2540] font-bold rounded-[8px] text-xs tracking-wider uppercase transition-colors border border-[#b8d4e8]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* CSS Animations */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes draw {
          from { stroke-dashoffset: 24; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes shake {
          10%, 90% { transform: translate3d(-1px, 0, 0); }
          20%, 80% { transform: translate3d(2px, 0, 0); }
          30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
          40%, 60% { transform: translate3d(4px, 0, 0); }
        }
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        @keyframes shimmerSweep {
          100% { transform: translateX(100%); }
        }
      `}} />
    </div>
  );
};

