import { useState } from 'react';
import { useGenerationStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { Loader2, ArrowRight, Globe, Type, Image as ImageIcon, X, Newspaper, CheckCircle2 } from 'lucide-react';
import { generationService, compressImage } from '@/services/generation.service';
import { TEMPLATES_LIST } from '@/lib/constants';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import type { Language } from '@/types';

// ─── Generation stage labels + progress ──────────────────────────────────────
const GEN_STAGES = [
  { label: 'Uploading Images…',           pct: 10 },
  { label: 'Generating Article…',         pct: 30 },
  { label: 'Creating Newspaper Layout…',  pct: 55 },
  { label: 'Rendering Clipping…',         pct: 75 },
  { label: 'Finalizing…',                 pct: 92 },
];

export const GenerateScreen = () => {
  const currentConfig   = useGenerationStore((state) => state.currentConfig);
  const addGeneration   = useGenerationStore((state) => state.addGeneration);
  const setConfig       = useGenerationStore((state) => state.setConfig);
  const navigate        = useNavigate();

  const [headline,      setHeadline]      = useState(currentConfig.headline      || '');
  const [content,       setContent]       = useState(currentConfig.articleContent || '');
  const [language,      setLanguage]      = useState<Language>((currentConfig.language as Language) || 'en');
  const [fontFamily,    setFontFamily]    = useState(currentConfig.fontFamily     || 'playfair');
  const [layoutColumns, setLayoutColumns] = useState(currentConfig.layoutColumns  || 3);
  const [imageUrls,     setImageUrls]     = useState<string[]>(currentConfig.imageUrls || []);
  const [loading,       setLoading]       = useState(false);
  const [stageIndex,    setStageIndex]    = useState(-1); // -1 = idle

  const currentStage = stageIndex >= 0 ? GEN_STAGES[Math.min(stageIndex, GEN_STAGES.length - 1)] : null;

  // ─── Image upload ───────────────────────────────────────────────────────────
  const handleImageUpload = async () => {
    if (imageUrls.length >= 3) {
      alert('You can only upload up to 3 images.');
      return;
    }

    try {
      const image = await Camera.getPhoto({
        quality:      85,
        allowEditing: false,
        resultType:   CameraResultType.Base64,
        source:       CameraSource.Photos,
      });

      if (!image.base64String) return;

      setLoading(true);
      console.log('[GEN] Image selected — compressing…');

      // Decode Base64 → Blob → File
      const byteCharacters = atob(image.base64String);
      const byteNumbers    = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const mimeType  = image.format === 'png' ? 'image/png' : 'image/jpeg';
      const extension = image.format || 'jpeg';
      const rawFile   = new File([new Blob([byteArray], { type: mimeType })], `upload.${extension}`, { type: mimeType });

      // Compress before upload (≤1600 px, 82% quality)
      const compressedFile = await compressImage(rawFile, 1600, 0.82);
      console.log(`[GEN] Uploading image (${(compressedFile.size / 1024).toFixed(0)} KB)…`);

      const uploadRes = await generationService.uploadImage(compressedFile);
      if (uploadRes.success && uploadRes.data.url) {
        let finalUrl = uploadRes.data.url;
        // Bypass Render hairpin NAT deadlock when accessed from within Render
        if (finalUrl.includes('onrender.com')) {
          finalUrl = 'https://corsproxy.io/?' + encodeURIComponent(finalUrl);
        }
        setImageUrls(prev => [...prev, finalUrl].slice(0, 3));
        console.log('[GEN] Images Uploaded ✓', finalUrl);
      }
    } catch (err: any) {
      if (err.message !== 'User cancelled photos app') {
        console.error('[GEN] Upload error:', err);
        const stage = err.message?.includes('Upload') ? 'Image Upload Failed' : 'Upload Error';
        alert(`${stage}\n\n${err.message || 'Unknown error'}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // ─── Generate clipping ──────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!headline || !content) return;
    setLoading(true);
    setStageIndex(0); // "Uploading Images…"

    console.log('[GEN] === Generation Started ===');
    console.log(`[GEN] headline="${headline}" lang=${language} images=${imageUrls.length} template=${currentConfig.templateId}`);

    try {
      const selectedTemplateDetails =
        TEMPLATES_LIST.find(t => t.id === currentConfig.templateId) || TEMPLATES_LIST[0];

      const configToSave = {
        ...currentConfig,
        headline,
        articleContent: content,
        language,
        fontFamily,
        layoutColumns,
        imageUrls,
        imageUrl:        imageUrls[0] || '',
        publicationName: selectedTemplateDetails.name,
        logoId:          selectedTemplateDetails.id,
        publicationDate: new Date().toLocaleDateString('en-US', {
          weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        }),
      };

      setConfig(configToSave);

      // ── Stage 1: Images already uploaded — move to article stage ────────
      setStageIndex(1); // "Generating Article…"
      console.log('[GEN] Images Uploaded ✓');

      let finalContent = content;
      if (language !== 'en') {
        console.log(`[GEN] Translating content to ${language}…`);
        try {
          const res = await fetch(
            `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${language}&dt=t&q=${encodeURIComponent(content)}`
          );
          const json = await res.json();
          finalContent = json[0].map((x: any) => x[0]).join('');
          console.log('[GEN] Translation complete ✓');
        } catch (e) {
          console.warn('[GEN] Translation failed — using original content', e);
        }
      }

      const payload = {
        ...configToSave,
        language,
        articleContent: finalContent,
        imageUrls,
        imageUrl: imageUrls[0] || '',
      };

      // ── Stage 2: Layout ──────────────────────────────────────────────────
      setStageIndex(2); // "Creating Newspaper Layout…"
      console.log('[GEN] Article Generated ✓ — sending to backend…');

      // ── Stage 3: Rendering ───────────────────────────────────────────────
      // The generate call can take 2–5 minutes on Render free tier.
      // It has timeout: 0 (no timeout). We advance the UI stage while waiting.
      const renderTimer = setTimeout(() => setStageIndex(3), 8_000);  // "Rendering Clipping…"
      const finalTimer  = setTimeout(() => setStageIndex(4), 60_000); // "Finalizing…"

      let res: any;
      try {
        res = await generationService.generate(payload as any);
      } finally {
        clearTimeout(renderTimer);
        clearTimeout(finalTimer);
      }

      console.log('[GEN] Backend response received ✓');

      const generation = res?.data?.id ? res.data : (res?.id ? res : null);

      if (generation) {
        console.log(`[GEN] PNG Generated ✓ | ID=${generation.id} | status=${generation.status}`);
        if (generation.png_url)  console.log('[GEN] PNG URL ✓', generation.png_url);
        if (generation.pdf_url)  console.log('[GEN] PDF URL ✓', generation.pdf_url);
        console.log('[GEN] Upload Complete ✓ — navigating to preview');

        // Inject config so history/dashboard screens don't crash
        generation.config = configToSave;
        addGeneration(generation);
        navigate(`/preview/${generation.id}`);
      } else {
        throw new Error(`Unexpected server response: ${JSON.stringify(res)}`);
      }
    } catch (err: any) {
      console.error('[GEN] Generation error:', err);

      // ── Map error to a human-readable stage message ───────────────────
      let errorTitle   = 'Generation Failed';
      let errorMessage = err.response?.data?.message || err.message || JSON.stringify(err);

      if (err.response?.status === 403 || errorMessage.includes('403')) {
        errorTitle   = 'Limit Reached';
        errorMessage = 'Free clipping limit reached. Go to Settings → Log Out and sign up with a new email to continue.';
      } else if (errorMessage.toLowerCase().includes('upload') || errorMessage.toLowerCase().includes('image')) {
        errorTitle = 'Image Upload Failed';
      } else if (errorMessage.toLowerCase().includes('playwright') || errorMessage.toLowerCase().includes('browser')) {
        errorTitle = 'Playwright Rendering Failed';
      } else if (errorMessage.toLowerCase().includes('supabase') || errorMessage.toLowerCase().includes('storage')) {
        errorTitle = 'Supabase Upload Failed';
      } else if (errorMessage.toLowerCase().includes('template') || errorMessage.toLowerCase().includes('html')) {
        errorTitle = 'Template Generation Failed';
      } else if (errorMessage.toLowerCase().includes('network') || errorMessage.toLowerCase().includes('connect')) {
        errorTitle = 'Network Error — Check Connection';
      }

      alert(`${errorTitle}\n\n${errorMessage}`);
    } finally {
      setLoading(false);
      setStageIndex(-1);
    }
  };

  const selectedTemplateDetails =
    TEMPLATES_LIST.find(t => t.id === currentConfig.templateId) || TEMPLATES_LIST[0];

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
      <div className="flex-none p-4 pb-2 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-800 transition-colors duration-300">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white transition-colors duration-300">Generate</h1>
      </div>

      <div className="p-6 pb-24 max-w-md mx-auto relative h-full">
        <div className="space-y-6">

          {/* Language Selector */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
            <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              <Globe className="w-4 h-4 text-blue-500" /> Language
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
              className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-2xl p-4 text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium appearance-none"
            >
              <option value="en">English</option>
              <option value="te">Telugu (తెలుగు)</option>
              <option value="hi">Hindi (हिन्दी)</option>
              <option value="kn">Kannada (ಕನ್ನಡ)</option>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="ml">Malayalam (മലയാളം)</option>
            </select>
          </div>

          {/* Headline */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
            <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Headline</label>
            <input
              type="text"
              placeholder="E.g. The Future of AI"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-2xl p-4 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-lg font-medium"
            />
          </div>

          {/* Content Snippet */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
            <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              <Type className="w-4 h-4 text-blue-500" /> Article Content
            </label>
            <textarea
              placeholder="Paste your article text here or let AI generate it..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={5}
              className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-2xl p-4 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none"
            />
          </div>

          {/* Featured Images */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
            <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              <ImageIcon className="w-4 h-4 text-blue-500" /> Featured Images (Max 3)
            </label>

            {imageUrls.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-3">
                {imageUrls.map((url, idx) => (
                  <div key={idx} className="relative rounded-xl overflow-hidden border border-gray-200 dark:border-gray-600 aspect-square group bg-gray-100 dark:bg-gray-700">
                    <img src={url} alt={`Uploaded ${idx + 1}`} className="w-full h-full object-cover" />
                    <div className="absolute bottom-1 left-1 bg-green-500 rounded-full p-0.5">
                      <CheckCircle2 className="h-3 w-3 text-white" />
                    </div>
                    <button
                      onClick={() => setImageUrls(prev => prev.filter((_, i) => i !== idx))}
                      className="absolute top-1 right-1 bg-white/90 dark:bg-black/90 shadow-sm text-red-500 p-1 rounded-full text-xs font-bold active:scale-95 transition-transform"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {imageUrls.length < 3 && (
              <button
                onClick={handleImageUpload}
                disabled={loading}
                className="w-full relative border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-2xl p-6 text-center bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                <div className="flex flex-col items-center justify-center gap-2 pointer-events-none">
                  <ImageIcon className="h-6 w-6 text-gray-400 dark:text-gray-500" />
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Tap to upload image</p>
                  <p className="text-xs text-gray-500 dark:text-gray-500">{3 - imageUrls.length} remaining · auto-compressed</p>
                </div>
              </button>
            )}
          </div>

          {/* Typography & Layout */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">Font</label>
              <select
                value={fontFamily}
                onChange={(e) => setFontFamily(e.target.value)}
                className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl p-3 text-gray-900 dark:text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="playfair">Playfair</option>
                <option value="merriweather">Merriweather</option>
                <option value="inter">Inter</option>
                <option value="courier">Courier</option>
              </select>
            </div>
            <div className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 transition-colors duration-300">
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">Columns</label>
              <select
                value={layoutColumns}
                onChange={(e) => setLayoutColumns(Number(e.target.value))}
                className="w-full bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl p-3 text-gray-900 dark:text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value={1}>1 Column</option>
                <option value={2}>2 Columns</option>
                <option value={3}>3 Columns</option>
              </select>
            </div>
          </div>

          {/* Logo / Template Status */}
          <div
            onClick={() => navigate('/templates')}
            className="bg-white dark:bg-gray-800 p-5 rounded-3xl shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)] border border-gray-100 dark:border-gray-700 flex items-center justify-between cursor-pointer active:scale-[0.98] transition-transform duration-300"
          >
            <div>
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                <Newspaper className="w-4 h-4 text-blue-500" /> Active Logo
              </label>
              <p className="text-gray-900 dark:text-white font-bold">{selectedTemplateDetails.name}</p>
            </div>
            <div className="text-blue-600 dark:text-blue-400 font-medium text-sm bg-blue-50 dark:bg-blue-900/30 px-3 py-1 rounded-full">
              Change
            </div>
          </div>

        </div>
      </div>

      {/* ── Sticky bottom: progress bar + generate button ─────────────────── */}
      <div className="fixed bottom-20 left-0 w-full px-6 pt-4 pb-2 bg-gradient-to-t from-gray-50 via-gray-50 dark:from-gray-900 dark:via-gray-900 to-transparent z-10 transition-colors duration-300">

        {/* Live progress bar shown during generation */}
        {loading && currentStage && (
          <div className="mb-3 bg-white dark:bg-gray-800 rounded-2xl px-4 py-3 shadow-md border border-gray-100 dark:border-gray-700">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">{currentStage.label}</span>
              <span className="text-xs font-mono text-gray-500 dark:text-gray-400">{currentStage.pct}%</span>
            </div>
            <div className="w-full h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-700 ease-out"
                style={{ width: `${currentStage.pct}%` }}
              />
            </div>
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1.5 text-center">
              This can take up to 2–3 minutes. Do not close the app.
            </p>
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={loading || !headline || !content}
          className="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-2xl font-semibold shadow-xl shadow-blue-600/30 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              <span className="text-sm">{currentStage?.label || 'Processing…'}</span>
            </>
          ) : (
            <>
              Generate Clipping
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};
