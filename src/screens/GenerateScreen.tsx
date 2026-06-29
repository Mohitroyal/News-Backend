import { useState } from 'react';
import { useGenerationStore, useUIStore } from '@/store';
import { useNavigate } from 'react-router-dom';
import { Loader2, Image as ImageIcon, X, Newspaper, CheckCircle2, Globe, Type } from 'lucide-react';
import { generationService, compressImage } from '@/services/generation.service';
import { TEMPLATES_LIST } from '@/lib/constants';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import type { Language } from '@/types';
import { LiveNewspaperPreview } from '@/components/LiveNewspaperPreview';
import { PatternSelectionModal } from '@/components/PatternSelectionModal';
import { BORDER_COLOURS, HEADING_BG_COLOURS } from '@/constants/colours';

// ─── Generation stage labels + progress ──────────────────────────────────────
const GEN_STAGES = [
  { label: 'Uploading Images…',           pct: 10 },
  { label: 'Generating Article…',         pct: 30 },
  { label: 'Creating Newspaper Layout…',  pct: 55 },
  { label: 'Rendering Clipping…',         pct: 75 },
  { label: 'Finalizing…',                 pct: 92 },
];

const LANGUAGES = [
  { id: 'en', label: 'English' },
  { id: 'te', label: 'Telugu (తెలుగు)' },
  { id: 'hi', label: 'Hindi (हिन्दी)' },
];

// ─── Shared card style ────────────────────────────────────────────────────────
const cardStyle: React.CSSProperties = {
  background: '#0D1B2A',
  borderRadius: '12px',
  padding: '14px',
  marginBottom: '12px',
  border: '1px solid rgba(255,255,255,0.07)',
};

const labelStyle: React.CSSProperties = {
  fontSize: '9px',
  fontWeight: 700,
  letterSpacing: '1.5px',
  textTransform: 'uppercase',
  color: 'rgba(255,255,255,0.45)',
  marginBottom: '8px',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'rgba(255,255,255,0.07)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px',
  padding: '11px 12px',
  color: '#ffffff',
  fontSize: '14px',
  outline: 'none',
  boxSizing: 'border-box',
};

export const GenerateScreen = () => {
  const currentConfig   = useGenerationStore((state) => state.currentConfig);
  const addGeneration   = useGenerationStore((state) => state.addGeneration);
  const setConfig       = useGenerationStore((state) => state.setConfig);
  const logoMode        = useUIStore((state) => state.logoMode);
  const navigate        = useNavigate();

  const [headline,      setHeadline]      = useState(currentConfig.headline || '');
  const [content,       setContent]       = useState(currentConfig.articleContent || '');
  const [language,      setLanguage]      = useState<Language>((currentConfig.language as Language) || 'en');
  const [fontFamily,    setFontFamily]    = useState(currentConfig.fontFamily || 'playfair');
  const [layoutColumns, setLayoutColumns] = useState(currentConfig.layoutColumns || 3);
  const [imageUrls,     setImageUrls]     = useState<string[]>(currentConfig.imageUrls || []);

  const [isPatternModalOpen, setIsPatternModalOpen] = useState(false);
  const [isLogoModalOpen,    setIsLogoModalOpen]    = useState(false);
  const [activeColourTab,    setActiveColourTab]    = useState<'border' | 'heading'>('border');
  const [showLangPicker,     setShowLangPicker]     = useState(false);

  const [loading,    setLoading]    = useState(false);
  const [stageIndex, setStageIndex] = useState(-1);

  const currentStage = stageIndex >= 0 ? GEN_STAGES[Math.min(stageIndex, GEN_STAGES.length - 1)] : null;

  const selectedPattern          = currentConfig.layoutPattern   || 'A';
  const selectedBorderColour     = currentConfig.borderColour    || '#cc2222';
  const selectedHeadingBgColour  = currentConfig.headingBgColour || '#fff3f3';
  const selectedTemplateId       = currentConfig.templateId      || 'rti_express';
  const selectedTemplateDetails  = TEMPLATES_LIST.find(t => t.id === selectedTemplateId) || TEMPLATES_LIST[0];

  const maxImages = ['A', 'B'].includes(selectedPattern) ? 1 : ['C', 'D'].includes(selectedPattern) ? 2 : 3;

  const getColourDetails = (hex: string, isBorder: boolean) => {
    const palettes  = isBorder ? BORDER_COLOURS : HEADING_BG_COLOURS;
    const allColours = [...palettes.classic, ...palettes.lightAndSoft];
    return allColours.find(c => c.hex.toLowerCase() === hex.toLowerCase()) || { name: 'Custom', hex };
  };

  const activeColourDetails = activeColourTab === 'border'
    ? getColourDetails(selectedBorderColour, true)
    : getColourDetails(selectedHeadingBgColour, false);



  const activeLang = LANGUAGES.find(l => l.id === language) || LANGUAGES[0];

  // ─── Image upload ───────────────────────────────────────────────────────────
  const handleImageUpload = async () => {
    if (imageUrls.length >= maxImages) {
      alert(`Max ${maxImages} image(s) for Pattern ${selectedPattern}.`);
      return;
    }
    try {
      const image = await Camera.getPhoto({
        quality: 85, allowEditing: false,
        resultType: CameraResultType.Base64, source: CameraSource.Photos,
      });
      if (!image.base64String) return;
      setLoading(true);

      const byteCharacters = atob(image.base64String);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
      const byteArray  = new Uint8Array(byteNumbers);
      const mimeType   = image.format === 'png' ? 'image/png' : 'image/jpeg';
      const rawFile    = new File([new Blob([byteArray], { type: mimeType })], `upload.${image.format || 'jpeg'}`, { type: mimeType });
      const compressed = await compressImage(rawFile, 1600, 0.82);
      const uploadRes  = await generationService.uploadImage(compressed);

      if (uploadRes.success && uploadRes.data.url) {
        let finalUrl = uploadRes.data.url;
        if (finalUrl.includes('onrender.com')) finalUrl = 'https://corsproxy.io/?' + encodeURIComponent(finalUrl);
        setImageUrls(prev => [...prev, finalUrl].slice(0, maxImages));
      }
    } catch (err: any) {
      if (err.message !== 'User cancelled photos app') alert(`Upload Error\n\n${err.message || 'Unknown error'}`);
    } finally { setLoading(false); }
  };

  // ─── Generate clipping ──────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!headline || !content) return;
    setLoading(true); setStageIndex(0);
    try {
      const configToSave = {
        ...currentConfig, headline, articleContent: content, language, fontFamily,
        layoutColumns, imageUrls, imageUrl: imageUrls[0] || '',
        templateId: selectedTemplateId,
        publicationName: selectedTemplateDetails.name,
        logoId: logoMode ? selectedTemplateId : undefined,
        showWatermark: logoMode,
        publicationDate: new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }),
      };
      setConfig(configToSave); setStageIndex(1);

      let finalContent = content;
      if (language !== 'en') {
        try {
          const res  = await fetch(`https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${language}&dt=t&q=${encodeURIComponent(content)}`);
          const json = await res.json();
          finalContent = json[0].map((x: any) => x[0]).join('');
        } catch (e) { console.warn('[GEN] Translation failed', e); }
      }

      const payload: any = { 
        ...configToSave, 
        language, 
        articleContent: finalContent, 
        imageUrls, 
        imageUrl: imageUrls[0] || '', 
        generateHeadline: false, 
        generate_headline: false, 
        autoGenerateHeadline: false,
        columnMode: layoutColumns === 0 ? 'auto' : 'manual',
        layoutColumns,
        borderColor: currentConfig.borderColour || undefined,
        headingBg: currentConfig.headingBgColour || undefined,
        imageLayout: selectedPattern ? `pattern_${selectedPattern.toLowerCase()}` : undefined
      };
      setStageIndex(2);
      const renderTimer = setTimeout(() => setStageIndex(3), 8_000);
      const finalTimer  = setTimeout(() => setStageIndex(4), 60_000);
      let res: any;
      try { res = await generationService.generate(payload as any); }
      finally { clearTimeout(renderTimer); clearTimeout(finalTimer); }

      const generation = res?.data?.id ? res.data : (res?.id ? res : null);
      if (generation) { generation.config = configToSave; addGeneration(generation); navigate(`/preview/${generation.id}`); }
      else throw new Error(`Unexpected server response: ${JSON.stringify(res)}`);
    } catch (err: any) {
      let errorTitle = 'Generation Failed';
      let errorMessage = err.response?.data?.message || err.message || JSON.stringify(err);
      if (err.response?.status === 403 || errorMessage.includes('403')) { errorTitle = 'Limit Reached'; errorMessage = 'Free clipping limit reached.'; }
      alert(`${errorTitle}\n\n${errorMessage}`);
    } finally { setLoading(false); setStageIndex(-1); }
  };

  return (
    <div style={{ background: '#EEF3F8', minHeight: '100%', paddingBottom: '130px' }}>

      {/* ── Page title banner ── */}
      <div style={{ background: '#0D1B2A', paddingTop: '14px', paddingBottom: '16px', marginBottom: '12px', borderBottom: '3px solid #CC1E1E' }}>
        <h1 style={{ color: '#fff', fontSize: '20px', fontWeight: 800, fontFamily: "'Georgia', serif", margin: 0, textAlign: 'center', letterSpacing: '0.3px', paddingLeft: '16px', paddingRight: '16px' }}>
          New Newspaper Clipping
        </h1>
      </div>

      <div style={{ padding: '0 12px' }}>

        {/* ── SECTION 1: ACTIVE LOGO ── */}
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={labelStyle}>
                <Newspaper style={{ width: 10, height: 10 }} /> ACTIVE LOGO
              </div>
              <span style={{ color: '#fff', fontSize: '16px', fontWeight: 700 }}>{selectedTemplateDetails.name}</span>
            </div>
            <button
              onClick={() => setIsLogoModalOpen(true)}
              style={{ background: '#CC1E1E', color: '#fff', border: 'none', borderRadius: '20px', padding: '8px 20px', fontWeight: 700, fontSize: '13px', cursor: 'pointer', letterSpacing: '0.2px' }}
            >
              Change
            </button>
          </div>
        </div>

        {/* ── SECTION 2: STYLE & COLOURS ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>🎨 STYLE &amp; COLOURS</div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
            {[
              { key: 'border',  label: '▦  Border' },
              { key: 'heading', label: 'abc  Heading BG' },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveColourTab(tab.key as any)}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: '8px',
                  border: activeColourTab === tab.key ? '1px solid rgba(255,255,255,0.2)' : '1px solid rgba(255,255,255,0.08)',
                  background: activeColourTab === tab.key ? 'rgba(255,255,255,0.13)' : 'transparent',
                  color: activeColourTab === tab.key ? '#fff' : 'rgba(255,255,255,0.38)',
                  fontWeight: activeColourTab === tab.key ? 700 : 500,
                  fontSize: '12px', cursor: 'pointer',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Live Preview header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '9px', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase' }}>LIVE PREVIEW</span>
            <button
              onClick={() => navigate('/templates')}
              style={{ background: 'none', border: '1px solid #CC1E1E', borderRadius: '6px', color: '#CC1E1E', fontSize: '9px', fontWeight: 800, letterSpacing: '1px', padding: '4px 10px', cursor: 'pointer', textTransform: 'uppercase' }}
            >
              CHANGE PATTERN
            </button>
          </div>

          {/* Pattern Preview */}
          <div style={{ marginBottom: '10px' }}>
            <LiveNewspaperPreview
              patternId={selectedPattern}
              borderColour={selectedBorderColour}
              headingBgColour={selectedHeadingBgColour}
              headlineText={headline}
              onPress={() => navigate('/templates')}
            />
          </div>

          {/* Selected colour display */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(255,255,255,0.07)', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: activeColourDetails.hex, flexShrink: 0, border: '1.5px solid rgba(255,255,255,0.15)' }} />
            <div>
              <div style={{ color: '#fff', fontSize: '13px', fontWeight: 700 }}>{activeColourDetails.name}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '10px', fontFamily: 'monospace' }}>{activeColourDetails.hex}</span>
                <span style={{ background: 'rgba(255,255,255,0.12)', color: '#fff', fontSize: '9px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {activeColourTab === 'border' ? 'Border' : 'Heading BG'}
                </span>
              </div>
            </div>
          </div>

          {/* Colour Swatches */}
          {(['classic', 'lightAndSoft'] as const).map(group => {
            const palettes  = activeColourTab === 'border' ? BORDER_COLOURS : HEADING_BG_COLOURS;
            const colours   = palettes[group];
            const activeHex = activeColourTab === 'border' ? selectedBorderColour : selectedHeadingBgColour;
            return (
              <div key={group} style={{ marginBottom: '14px' }}>
                <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '9px', fontWeight: 700, letterSpacing: '1.2px', textTransform: 'uppercase', marginBottom: '8px' }}>
                  {group === 'classic' ? 'CLASSIC COLOURS' : 'LIGHT & SOFT COLOURS'}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '8px' }}>
                  {colours.map(c => {
                    const isSelected = activeHex.toLowerCase() === c.hex.toLowerCase();
                    return (
                      <button
                        key={c.hex}
                        onClick={() => activeColourTab === 'border' ? setConfig({ borderColour: c.hex }) : setConfig({ headingBgColour: c.hex })}
                        style={{
                          width: '100%', aspectRatio: '1', borderRadius: '8px', border: 'none',
                          background: c.hex, cursor: 'pointer', position: 'relative',
                          outline: isSelected ? '2.5px solid #fff' : '2px solid rgba(255,255,255,0.1)',
                          outlineOffset: isSelected ? '2px' : '0px',
                          transform: isSelected ? 'scale(1.08)' : 'scale(1)',
                          transition: 'all 0.15s',
                        }}
                      >
                        {isSelected && (
                          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.15)', borderRadius: '8px' }}>
                            <CheckCircle2 style={{ width: '14px', height: '14px', color: '#fff' }} strokeWidth={3} />
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── SECTION 3: INTERFACE LANGUAGE ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <Globe style={{ width: 10, height: 10 }} /> INTERFACE LANGUAGE
          </div>
          <button
            onClick={() => setShowLangPicker(v => !v)}
            style={{ ...inputStyle, textAlign: 'left', cursor: 'pointer', fontWeight: 500 }}
          >
            {activeLang.label}
          </button>
          {showLangPicker && (
            <div style={{ marginTop: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
              {LANGUAGES.map(lang => (
                <button
                  key={lang.id}
                  onClick={() => { setLanguage(lang.id as Language); setShowLangPicker(false); }}
                  style={{
                    width: '100%', padding: '11px 14px', background: language === lang.id ? 'rgba(204,30,30,0.2)' : 'transparent',
                    color: language === lang.id ? '#fff' : 'rgba(255,255,255,0.6)', border: 'none', borderBottom: '1px solid rgba(255,255,255,0.06)',
                    textAlign: 'left', fontSize: '13px', fontWeight: language === lang.id ? 700 : 400, cursor: 'pointer',
                  }}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── SECTION 4: HEADLINE ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>HEADLINE</div>
          <input
            type="text"
            placeholder="Enter headline"
            value={headline}
            onChange={e => setHeadline(e.target.value)}
            style={{ ...inputStyle, caretColor: '#fff' }}
          />
        </div>

        {/* ── SECTION 5: ARTICLE CONTENT ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <Type style={{ width: 10, height: 10 }} /> ARTICLE CONTENT
          </div>
          <textarea
            placeholder="Enter article content..."
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={5}
            style={{ ...inputStyle, resize: 'none', lineHeight: 1.6, caretColor: '#fff' }}
          />
        </div>

        {/* ── SECTION 6: FEATURED IMAGES ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <ImageIcon style={{ width: 10, height: 10 }} /> FEATURED IMAGES (MAX {maxImages})
          </div>

          {imageUrls.length > 0 && (
            <div style={{ display: 'flex', gap: '10px', marginBottom: '10px', overflowX: 'auto', paddingBottom: '4px' }}>
              {imageUrls.map((url, idx) => (
                <div key={idx} style={{ position: 'relative', flexShrink: 0, width: '90px', height: '90px', borderRadius: '10px', overflow: 'hidden', border: '2px solid rgba(255,255,255,0.1)' }}>
                  <img src={url} alt={`img ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <button
                    onClick={() => setImageUrls(prev => prev.filter((_, i) => i !== idx))}
                    style={{ position: 'absolute', top: '4px', right: '4px', width: '22px', height: '22px', background: '#CC1E1E', border: 'none', borderRadius: '50%', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                  >
                    <X style={{ width: '11px', height: '11px' }} strokeWidth={3} />
                  </button>
                  {/* Radio indicator */}
                  <div style={{ position: 'absolute', bottom: '4px', left: '4px', width: '16px', height: '16px', background: '#CC1E1E', border: '2px solid #fff', borderRadius: '50%' }} />
                </div>
              ))}
            </div>
          )}

          {imageUrls.length < maxImages && (
            <button
              onClick={handleImageUpload}
              disabled={loading}
              style={{
                width: '100%', border: '1.5px dashed rgba(255,255,255,0.2)', borderRadius: '10px',
                background: 'rgba(255,255,255,0.04)', padding: '20px 0', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
              }}
            >
              <ImageIcon style={{ width: '24px', height: '24px', color: 'rgba(255,255,255,0.4)' }} />
              <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '13px', fontWeight: 600 }}>Tap to upload image</span>
              <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: '11px' }}>
                {maxImages - imageUrls.length} remaining · auto-compressed
              </span>
            </button>
          )}
        </div>

        {/* ── SECTION 7: FONT + COLUMNS ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
          {/* Font — shows selected font as a display box, tap to cycle */}
          <div style={{ ...cardStyle, marginBottom: 0 }}>
            <div style={labelStyle}>FONT</div>
            <button
              onClick={() => {
                const fonts = ['playfair', 'merriweather', 'inter', 'courier'];
                const next = fonts[(fonts.indexOf(fontFamily) + 1) % fonts.length];
                setFontFamily(next);
              }}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: '8px',
                background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)',
                color: '#fff', fontSize: '13px', fontWeight: 600,
                textAlign: 'left', cursor: 'pointer',
              }}
            >
              {fontFamily.charAt(0).toUpperCase() + fontFamily.slice(1)}
            </button>
          </div>

          {/* Columns */}
          <div style={{ ...cardStyle, marginBottom: 0 }}>
            <div style={labelStyle}>COLUMNS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
              {[{ label: 'Auto', val: 0 }, { label: '1 Column', val: 1 }, { label: '2 Columns', val: 2 }, { label: '3 Columns', val: 3 }].map(({ label, val }) => {
                const isActive = layoutColumns === val;
                return (
                  <button
                    key={label}
                    onClick={() => setLayoutColumns(val)}
                    style={{
                      padding: '9px 12px', borderRadius: '8px',
                      background: isActive ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.05)',
                      border: isActive ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent',
                      color: isActive ? '#fff' : 'rgba(255,255,255,0.45)',
                      fontSize: '12px', fontWeight: isActive ? 700 : 400,
                      textAlign: 'left', cursor: 'pointer',
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

      </div>

      {/* ── Sticky bottom: Generate button ── */}
      <div style={{ position: 'fixed', left: 0, right: 0, bottom: 'calc(70px + env(safe-area-inset-bottom))', zIndex: 40, padding: '0 0' }}>
        {loading && currentStage && (
          <div style={{ background: '#0D1B2A', borderTop: '1px solid rgba(255,255,255,0.08)', padding: '10px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ color: '#fff', fontSize: '11px', fontWeight: 600 }}>{currentStage.label}</span>
              <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', fontFamily: 'monospace' }}>{currentStage.pct}%</span>
            </div>
            <div style={{ height: '3px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ height: '100%', background: '#CC1E1E', borderRadius: '2px', width: `${currentStage.pct}%`, transition: 'width 0.7s ease-out' }} />
            </div>
          </div>
        )}
        <button
          onClick={handleGenerate}
          disabled={loading || !headline || !content}
          style={{
            width: '100%', padding: '18px 0', background: (loading || !headline || !content) ? '#a01515' : '#CC1E1E',
            color: '#fff', border: 'none', fontWeight: 700, fontSize: '16px',
            fontFamily: "'Georgia', serif", cursor: (loading || !headline || !content) ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
            opacity: (loading || !headline || !content) ? 0.65 : 1,
          }}
        >
          {loading ? (
            <><Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} /><span>{currentStage?.label || 'Processing…'}</span></>
          ) : (
            <span>Generate Clipping →</span>
          )}
        </button>
      </div>

      {/* ── Modals ── */}
      <PatternSelectionModal
        isOpen={isPatternModalOpen}
        onClose={() => setIsPatternModalOpen(false)}
        selectedPattern={selectedPattern}
        onSelectPattern={(patternId) => setConfig({ layoutPattern: patternId as any })}
      />

      {isLogoModalOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}>
          <div
            style={{ width: '100%', maxHeight: '80vh', background: '#0D1B2A', borderRadius: '20px 20px 0 0', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.08)', flexShrink: 0 }}>
              <h2 style={{ color: '#fff', fontSize: '18px', fontWeight: 800, fontFamily: "'Georgia', serif", margin: 0 }}>Select Logo</h2>
              <button onClick={() => setIsLogoModalOpen(false)} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', width: '32px', height: '32px', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <X style={{ width: '16px', height: '16px' }} />
              </button>
            </div>
            <div style={{ overflowY: 'auto', flex: 1, minHeight: 0, padding: '12px', paddingBottom: '100px', display: 'flex', flexDirection: 'column', gap: '8px', WebkitOverflowScrolling: 'touch', touchAction: 'pan-y', overscrollBehavior: 'contain' }}>
              {TEMPLATES_LIST.map(template => {
                const isSelected = selectedTemplateId === template.id;
                return (
                  <button
                    key={template.id}
                    onClick={() => { setConfig({ templateId: template.id }); setIsLogoModalOpen(false); }}
                    style={{
                      background: isSelected ? 'rgba(204,30,30,0.15)' : 'rgba(255,255,255,0.05)',
                      border: `1.5px solid ${isSelected ? '#CC1E1E' : 'rgba(255,255,255,0.08)'}`,
                      borderRadius: '10px', padding: '12px', display: 'flex', alignItems: 'center', gap: '12px',
                      cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <div style={{ width: '40px', height: '40px', background: 'rgba(255,255,255,0.08)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Newspaper style={{ width: '20px', height: '20px', color: 'rgba(255,255,255,0.6)' }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#fff', fontSize: '14px', fontWeight: 700 }}>{template.name}</div>
                      <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>{template.id}</div>
                    </div>
                    {isSelected && <CheckCircle2 style={{ width: '18px', height: '18px', color: '#CC1E1E', flexShrink: 0 }} />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};
