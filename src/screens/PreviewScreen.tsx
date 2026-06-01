import { useParams, useNavigate } from 'react-router-dom';
import { useGenerationStore } from '@/store';
import { ArrowLeft, Download, FileDown, Share2, MoreHorizontal } from 'lucide-react';
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
  const [serverWaking, setServerWaking] = useState(false);
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
    setServerWaking(false);

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
          setServerWaking(false);

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
          setServerWaking(true);
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
  const currentStage    = liveStage || generation.stage || generation.status || 'Processing';
  const progressPercent = generation.progress ?? getProgress(liveStage || generation.stage);
  const timeLeft        = Math.max(0, MAX_POLL_MS - elapsedMs);

  return (
    <div className="h-screen bg-neutral-900 flex flex-col fixed inset-0 z-50">
      {/* ── Top Bar ──────────────────────────────────────────────────────── */}
      <div className="h-16 bg-neutral-950/80 border-b border-white/10 flex items-center justify-between px-4 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex flex-col items-center">
          <span className="text-white font-semibold">Preview</span>
          <span className="text-[10px] font-mono text-gray-500">clipping_{generation.id.slice(0, 8)}.png</span>
        </div>
        <div className="w-9" />
      </div>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto bg-neutral-800 p-4 flex items-center justify-center">

        {/* ── Completed: show image ─────────────────────────────────────── */}
        {generation.png_url ? (
          <img
            src={generation.png_url}
            alt="Newspaper Preview"
            className="max-w-full max-h-full object-contain shadow-2xl rounded-sm"
          />

        /* ── Failed: show full debug card ─────────────────────────────── */
        ) : generation.status === 'failed' || (generation.status === 'completed' && !generation.png_url) ? (
          <div className="flex flex-col items-center text-red-400 gap-4 text-center max-w-md w-full px-6 py-8 bg-neutral-950/70 border border-red-500/20 rounded-2xl mx-auto shadow-2xl overflow-y-auto max-h-[75vh]">
            <span className="font-bold text-xl text-red-500 tracking-wide">Generation Failed</span>

            {/* Stage */}
            <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
              <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Stage</span>
              <span className="text-sm text-white font-semibold">
                {(generation.stage || generation.custom_layout?.stage || 'Unknown — check Render logs')
                  .replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
              </span>
            </div>

            {/* Exception Type */}
            {(generation.error_type || generation.custom_layout?.error_type) && (
              <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Exception Type</span>
                <span className="text-xs text-yellow-300 font-mono break-words">
                  {generation.error_type || generation.custom_layout?.error_type}
                </span>
              </div>
            )}

            {/* Message */}
            <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
              <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Message</span>
              <span className="text-xs text-red-300 font-mono break-words leading-relaxed">
                {generation.message || generation.error ||
                  generation.custom_layout?.message || generation.custom_layout?.error ||
                  'No message — check Render logs'}
              </span>
            </div>

            {/* Technical Details */}
            {(generation.details || generation.custom_layout?.details) && (
              <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Technical Details</span>
                <span className="text-[11px] text-gray-300 font-mono break-all leading-normal max-h-36 overflow-y-auto bg-black/45 p-2 rounded-lg border border-white/5">
                  {generation.details || generation.custom_layout?.details}
                </span>
              </div>
            )}

            {/* Stack Trace */}
            {(generation.traceback || generation.custom_layout?.traceback) && (
              <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Stack Trace</span>
                <pre className="text-[10px] text-gray-400 font-mono break-all leading-normal max-h-48 overflow-y-auto bg-black/60 p-2 rounded-lg border border-white/5 whitespace-pre-wrap">
                  {generation.traceback || generation.custom_layout?.traceback}
                </pre>
              </div>
            )}

            {/* Raw dump last resort */}
            {!generation.stage && !generation.message && !generation.details && generation.custom_layout && (
              <div className="flex flex-col gap-1 w-full border-t border-white/5 pt-3 text-left">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Raw Debug Data</span>
                <pre className="text-[10px] text-gray-400 font-mono break-all leading-normal max-h-48 overflow-y-auto bg-black/60 p-2 rounded-lg border border-white/5 whitespace-pre-wrap">
                  {JSON.stringify(generation.custom_layout, null, 2)}
                </pre>
              </div>
            )}
          </div>

        /* ── Processing: live progress card ───────────────────────────── */
        ) : (
          <div className="flex flex-col items-center gap-6 w-full max-w-sm px-4">

            {/* Server waking banner */}
            {serverWaking && (
              <div className="w-full bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3 text-center">
                <span className="text-amber-300 text-sm font-semibold">⏳ Server is starting up…</span>
                <p className="text-amber-400/70 text-xs mt-1">Render free instances take ~30s to wake. Please wait.</p>
              </div>
            )}

            {/* Animated newspaper icon */}
            <div className="relative w-20 h-20 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-white/5" />
              <div
                className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-500 animate-spin"
                style={{ animationDuration: '1.2s' }}
              />
              <span className="text-3xl">📰</span>
            </div>

            {/* Stage label */}
            <div className="text-center">
              <p className="text-white font-semibold text-lg">Generating clipping…</p>
              <p className="text-blue-300 text-sm mt-1 font-mono">
                {currentStage.replace(/_/g, ' ')}
              </p>
            </div>

            {/* Progress bar */}
            <div className="w-full">
              <div className="flex justify-between text-xs text-gray-400 mb-2">
                <span>Progress</span>
                <span className="font-mono text-white font-bold">{progressPercent}%</span>
              </div>
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-700 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>

            {/* Stats row */}
            <div className="flex w-full justify-between text-xs text-gray-500">
              <span>Poll #{pollAttempt}</span>
              <span>Elapsed: <span className="text-gray-300 font-mono">{fmtElapsed(elapsedMs)}</span></span>
              <span>Timeout: <span className="text-gray-300 font-mono">{fmtElapsed(timeLeft)}</span></span>
            </div>

            <p className="text-gray-500 text-xs text-center leading-relaxed">
              Checking every 3 seconds · Up to 10 minutes · Do not close this screen
            </p>
          </div>
        )}
      </div>

      {/* ── Bottom Action Bar ─────────────────────────────────────────────── */}
      <div className="h-24 bg-neutral-950/90 border-t border-white/10 flex items-center justify-between px-4 gap-3 shrink-0 pb-safe">
        <button
          onClick={() => handleDownload('png')}
          disabled={downloading || !generation.png_url}
          className="flex-1 py-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold text-xs tracking-wider uppercase active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 shadow-md shadow-blue-900/30"
        >
          <Download className="w-4 h-4" />
          <span>Save PNG</span>
        </button>

        <button
          onClick={() => handleDownload('pdf')}
          disabled={downloading || !generation.png_url}
          className="flex-1 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold text-xs tracking-wider uppercase active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 shadow-md shadow-indigo-900/30"
        >
          <FileDown className="w-4 h-4" />
          <span>Save PDF</span>
        </button>

        <button
          onClick={() => setIsShareSheetOpen(true)}
          disabled={downloading || !generation.png_url}
          className="flex-1 py-3.5 bg-neutral-800 hover:bg-neutral-700 text-white rounded-2xl font-bold text-xs tracking-wider uppercase active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 shadow-md shadow-black/30 border border-white/5"
        >
          <Share2 className="w-4 h-4" />
          <span>Share</span>
        </button>
      </div>

      {/* ── Share Bottom Sheet ───────────────────────────────────────────── */}
      {isShareSheetOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-opacity duration-300"
          onClick={() => setIsShareSheetOpen(false)}
        >
          <div 
            className="fixed bottom-0 left-0 right-0 bg-neutral-950 border-t border-white/10 rounded-t-3xl p-6 pb-10 z-50 transform transition-transform duration-300 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drag Handle */}
            <div className="w-12 h-1 bg-white/20 rounded-full mx-auto mb-6" />
            
            {/* Title */}
            <h3 className="text-white font-bold text-lg mb-6 text-center">Share Newspaper Clipping</h3>
            
            {/* Options Grid */}
            <div className="grid grid-cols-4 gap-y-6 gap-x-2 justify-items-center">
              {/* WhatsApp */}
              <button
                onClick={() => handleShareOptionClick('WhatsApp')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-[#25D366] flex items-center justify-center shadow-lg shadow-[#25D366]/20">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946C.06 5.348 5.397.01 12.008.01c3.202.001 6.212 1.246 8.477 3.514 2.266 2.268 3.507 5.28 3.505 8.484-.004 6.657-5.34 11.997-11.953 11.997-2.005-.001-3.973-.502-5.713-1.455L0 24zm6.59-11.597c-.279-.314-.555-.262-.773-.272-.2-.008-.428-.008-.656-.008-.228 0-.6-.086-.913-.429-.314-.343-1.198-1.172-1.198-2.859 0-1.687 1.226-3.314 1.398-3.543.171-.228 2.413-3.685 5.845-5.17.816-.353 1.453-.564 1.948-.72.822-.262 1.572-.225 2.164-.137.66.099 2.03.83 2.314 1.632.285.803.285 1.49.201 1.632-.083.14-.308.228-.651.4l-2.102 1.03c-.342.166-.591.248-.846.634-.255.38-.973 1.226-1.195 1.48-.222.254-.443.286-.786.114-.343-.171-1.447-.533-2.755-1.7c-1.018-.908-1.704-2.03-1.902-2.372-.199-.343-.021-.528.15-.699.153-.153.343-.4.514-.6.171-.2.228-.343.343-.571.114-.229.057-.429-.028-.6-.086-.171-.773-1.857-1.059-2.543-.278-.669-.561-.578-.773-.589z"/>
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">WhatsApp</span>
              </button>

              {/* Facebook */}
              <button
                onClick={() => handleShareOptionClick('Facebook')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-[#1877F2] flex items-center justify-center shadow-lg shadow-[#1877F2]/20">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">Facebook</span>
              </button>

              {/* Instagram */}
              <button
                onClick={() => handleShareOptionClick('Instagram')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-yellow-500 via-pink-500 to-purple-600 flex items-center justify-center shadow-lg">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                    <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                    <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">Instagram</span>
              </button>

              {/* X (Twitter) */}
              <button
                onClick={() => handleShareOptionClick('X (Twitter)')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-neutral-900 border border-white/10 flex items-center justify-center shadow-lg">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">X (Twitter)</span>
              </button>

              {/* Telegram */}
              <button
                onClick={() => handleShareOptionClick('Telegram')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-[#24A1DE] flex items-center justify-center shadow-lg shadow-[#24A1DE]/20">
                  <svg className="w-5 h-5 text-white mr-0.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 24c6.627 0 12-5.373 12-12S18.627 0 12 0 0 5.373 0 12s5.373 12 12 12z" fill="none"/>
                    <path d="M18.35 6.002a.85.85 0 0 0-.69.043L3.102 11.75c-.65.25-.65.61-.12.77l3.8 1.18 8.8-5.55c.41-.25.8-.12.49.15l-7.12 6.42-.28 3.96c.39 0 .56-.18.78-.39l1.88-1.83 3.9 2.88c.72.4 1.24.2 1.42-.65l2.56-12.06c.26-.95-.36-1.37-1.02-1.17z" fill="currentColor"/>
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">Telegram</span>
              </button>

              {/* Gmail */}
              <button
                onClick={() => handleShareOptionClick('Gmail')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-[#EA4335] flex items-center justify-center shadow-lg shadow-[#EA4335]/20">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                    <polyline points="22,6 12,13 2,6"/>
                  </svg>
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">Gmail</span>
              </button>

              {/* More Apps */}
              <button
                onClick={() => handleShareOptionClick('More Apps')}
                className="flex flex-col items-center gap-2 text-white active:scale-95 transition-transform"
              >
                <div className="w-12 h-12 rounded-full bg-neutral-700 flex items-center justify-center shadow-lg">
                  <MoreHorizontal className="w-5 h-5 text-white" />
                </div>
                <span className="text-[10px] text-gray-400 font-semibold text-center leading-tight">More Apps</span>
              </button>
            </div>
            
            {/* Cancel Button */}
            <button
              onClick={() => setIsShareSheetOpen(false)}
              className="w-full mt-8 py-3.5 bg-neutral-800 hover:bg-neutral-700 text-white font-bold rounded-2xl text-xs tracking-wider uppercase transition-colors border border-white/5 active:scale-[0.98]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
