import { useState, useEffect, useRef } from 'react';
import { useGenerationStore, useUIStore, useAuthStore, getReporterPhoto, getReporterName } from '@/store';
import { useNavigate } from 'react-router-dom';
import { Loader2, Image as ImageIcon, X, Newspaper, CheckCircle2, Globe, Type, SlidersHorizontal, ChevronDown } from 'lucide-react';
import { generationService, compressImage } from '@/services/generation.service';
import { TEMPLATES_LIST } from '@/lib/constants';
import { ImageCropModal } from '@/components/ImageCropModal';
import type { Language } from '@/types';
import { LiveNewspaperPreview } from '@/components/LiveNewspaperPreview';
import { PatternSelectionModal } from '@/components/PatternSelectionModal';
import { BORDER_COLOURS, HEADING_BG_COLOURS } from '@/constants/colours';
import { useTranslation } from '@/lib/i18n';

// ─── Generation stage labels + progress ──────────────────────────────────────
const GEN_STAGES = [
  { id: 'uploadingImages',           pct: 10 },
  { id: 'generatingArticle',         pct: 30 },
  { id: 'creatingLayout',  pct: 55 },
  { id: 'renderingClipping',         pct: 75 },
  { id: 'finalizing',                 pct: 92 },
];

const LANGUAGES = [
  { id: 'te', label: 'Telugu (తెలుగు)' },
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
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const currentConfig   = useGenerationStore((state) => state.currentConfig);
  const addGeneration   = useGenerationStore((state) => state.addGeneration);
  const setConfig       = useGenerationStore((state) => state.setConfig);
  const resetConfig     = useGenerationStore((state) => state.resetConfig);
  const logoMode        = useUIStore((state) => state.logoMode);
  const showInnerBorders = useUIStore((state) => state.showInnerBorders);
  const pendingCropImageSrc = useUIStore((state) => state.pendingCropImageSrc);
  const setPendingCropImageSrc = useUIStore((state) => state.setPendingCropImageSrc);
  const navigate        = useNavigate();

  const [headline,      setHeadline]      = useState(currentConfig.headline || '');
  const [content,       setContent]       = useState(currentConfig.articleContent || '');
  const [language,      setLanguage]      = useState<Language>((currentConfig.language as Language) || 'te');
  const [fontFamily,    setFontFamily]    = useState(currentConfig.fontFamily || 'playfair');
  const [layoutColumns, setLayoutColumns] = useState(currentConfig.layoutColumns || 3);
  const [imageUrls,     setImageUrls]     = useState<string[]>(currentConfig.imageUrls || []);

  const [isPatternModalOpen, setIsPatternModalOpen] = useState(false);
  const [isLogoModalOpen,    setIsLogoModalOpen]    = useState(false);
  const [activeColourTab,    setActiveColourTab]    = useState<'border' | 'heading'>('border');
  const [showLangPicker,     setShowLangPicker]     = useState(false);
  const [showColPicker,      setShowColPicker]      = useState(false);

  const [isAdvanceOpen,      setIsAdvanceOpen]      = useState(false);

  const [loading,    setLoading]    = useState(false);
  const [stageIndex, setStageIndex] = useState(-1);
  const [cropImageSrc, setCropImageSrc] = useState<string | null>(null);
  const [cropImageMime, setCropImageMime] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check for restored image on mount
  useEffect(() => {
    if (pendingCropImageSrc) {
      setCropImageMime('image/jpeg'); // Default since format isn't stored in pending
      setCropImageSrc(pendingCropImageSrc);
      setPendingCropImageSrc(null);
    }
  }, [pendingCropImageSrc, setPendingCropImageSrc]);

  const currentStage = stageIndex >= 0 ? GEN_STAGES[Math.min(stageIndex, GEN_STAGES.length - 1)] : null;

  const selectedPattern          = currentConfig.layoutPattern   || 'A';
  const selectedBorderColour     = currentConfig.borderColour    || '#cc2222';
  const selectedHeadingBgColour  = currentConfig.headingBgColour || '#fff3f3';
  const selectedTemplateId       = currentConfig.templateId      || 'rti_express';
  const selectedTemplateDetails  = TEMPLATES_LIST.find(t => t.id === selectedTemplateId) || TEMPLATES_LIST[0];

  useEffect(() => {
    if (selectedTemplateId === 'rti_express') {
      useUIStore.getState().setLogoMode(true);
      setConfig({
        borderColour: '#cc2222',
        headingBgColour: '#cc2222'
      });
    }
  }, [selectedTemplateId, setConfig]);

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
    
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Ensure it's an image even though we accept */*
    if (!file.type.startsWith('image/')) {
      alert('Please select a valid image file (jpeg, png, etc).');
      return;
    }
    
    const mimeType = file.type;
    const url = URL.createObjectURL(file);
    setCropImageMime(mimeType);
    setCropImageSrc(url);
    
    // Reset input value so same file can be selected again
    e.target.value = '';
  };

  const handleCropComplete = async (croppedBlob: Blob) => {
    setCropImageSrc(null);
    setLoading(true);
    try {
      const mimeType = cropImageMime || 'image/jpeg';
      const extension = mimeType === 'image/png' ? 'png' : 'jpeg';
      const rawFile = new File([croppedBlob], `upload.${extension}`, { type: mimeType });
      const compressed = await compressImage(rawFile, 1600, 0.82);
      const uploadRes  = await generationService.uploadImage(compressed);

      if (uploadRes.success && uploadRes.data?.url) {
        let finalUrl = uploadRes.data.url;
        if (finalUrl.includes('onrender.com')) finalUrl = 'https://corsproxy.io/?' + encodeURIComponent(finalUrl);
        setImageUrls(prev => [...prev, finalUrl].slice(0, maxImages));
      } else {
        alert(`Upload Failed: ${(uploadRes as any).error || 'Unknown error'}`);
      }
    } catch (err: any) {
      alert(`Upload Error\n\n${err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!headline || !content) return;
    setLoading(true); setStageIndex(0);
    try {
      const reporterName = getReporterName(user?.email) || (user as any)?.user_metadata?.full_name || (user as any)?.user_metadata?.name || user?.full_name || user?.firstName || 'Reporter';
      const reporterImage = getReporterPhoto(user?.email) || user?.avatarUrl || (user as any)?.user_metadata?.avatar_url || (user as any)?.user_metadata?.picture || '';

      const configToSave = {
        ...currentConfig, headline, articleContent: content, language, fontFamily,
        layoutColumns, imageUrls, imageUrl: imageUrls[0] || '',
        templateId: selectedTemplateId,
        publicationName: selectedTemplateDetails.name,
        logoId: logoMode ? selectedTemplateId : undefined,
        showWatermark: logoMode,
        showInnerBorders: showInnerBorders ?? true,
        publicationDate: new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }),
        reporterName,
        reporterImage,
      };
      setConfig(configToSave); setStageIndex(1);

      const payload: any = { 
        ...configToSave, 
        language, 
        articleContent: content, 
        imageUrls, 
        imageUrl: imageUrls[0] || '', 
        generateHeadline: false, 
        generate_headline: false, 
        autoGenerateHeadline: false,
        showInnerBorders: showInnerBorders ?? true,
        columnMode: layoutColumns === 0 ? 'auto' : 'manual',
        layoutColumns,
        borderColor: currentConfig.borderColour || undefined,
        headingBg: currentConfig.headingBgColour || undefined,
        imageLayout: selectedPattern ? `pattern_${selectedPattern.toLowerCase()}` : undefined,
        reporterName,
        reporterImage,
        reporter_name: reporterName,
        reporter_image: reporterImage
      };
      setStageIndex(2);
      const renderTimer = setTimeout(() => setStageIndex(3), 8_000);
      const finalTimer  = setTimeout(() => setStageIndex(4), 60_000);
      let res: any;
      try { res = await generationService.generate(payload as any); }
      finally { clearTimeout(renderTimer); clearTimeout(finalTimer); }

      const generation = res?.data?.id ? res.data : (res?.id ? res : null);
      if (generation) { 
        generation.config = configToSave; 
        addGeneration(generation); 
        
        // Reset form for next generation
        resetConfig();
        setHeadline('');
        setContent('');
        setLanguage('te');
        setFontFamily('playfair');
        setLayoutColumns(3);
        setImageUrls([]);
        setIsAdvanceOpen(false);
        
        navigate(`/preview/${generation.id}`); 
      }
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

      {cropImageSrc && (
        <ImageCropModal
          imageSrc={cropImageSrc}
          onCropComplete={handleCropComplete}
          onCancel={() => setCropImageSrc(null)}
        />
      )}


      {/* ── Page title banner ── */}
      <div style={{ background: '#0D1B2A', paddingTop: '14px', paddingBottom: '16px', marginBottom: '12px', borderBottom: '3px solid #CC1E1E' }}>
        <h1 style={{ color: '#fff', fontSize: '20px', fontWeight: 800, fontFamily: "'Georgia', serif", margin: 0, textAlign: 'center', letterSpacing: '0.3px', paddingLeft: '16px', paddingRight: '16px' }}>
          {t.newClippingTitle}
        </h1>
      </div>

      <div style={{ padding: '0 12px' }}>

        {/* ── SECTION 1: ACTIVE LOGO ── */}
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={labelStyle}>
                <Newspaper style={{ width: 10, height: 10 }} /> {t.activeLogo}
              </div>
              <span style={{ color: '#fff', fontSize: '16px', fontWeight: 700 }}>{selectedTemplateDetails.name}</span>
            </div>
            <button
              onClick={() => setIsLogoModalOpen(true)}
              style={{ background: '#CC1E1E', color: '#fff', border: 'none', borderRadius: '20px', padding: '8px 20px', fontWeight: 700, fontSize: '13px', cursor: 'pointer', letterSpacing: '0.2px' }}
            >
              {t.change}
            </button>
          </div>
        </div>

        {/* ── SECTION 2: STYLE & COLOURS ── */}
        <div style={cardStyle}>
          {/* Advance Toggle Button */}
          <button
            onClick={() => setIsAdvanceOpen(prev => !prev)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'transparent',
              border: '1px dashed rgba(255,255,255,0.2)',
              borderRadius: '8px',
              padding: '10px 14px',
              color: '#ffffff',
              cursor: 'pointer',
              outline: 'none',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600 }}>
              <SlidersHorizontal style={{ width: '15px', height: '15px', color: 'rgba(255,255,255,0.7)' }} />
              <span>{t.advanced}</span>
            </div>
            <ChevronDown
              style={{
                width: '16px',
                height: '16px',
                color: 'rgba(255,255,255,0.7)',
                transform: isAdvanceOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 200ms ease',
              }}
            />
          </button>

          {/* Collapsible Panel */}
          <div
            style={{
              maxHeight: isAdvanceOpen ? '1200px' : '0px',
              opacity: isAdvanceOpen ? 1 : 0,
              overflow: 'hidden',
              transition: 'max-height 250ms ease, opacity 250ms ease, margin-top 250ms ease',
              marginTop: isAdvanceOpen ? '14px' : '0px',
              pointerEvents: isAdvanceOpen ? 'auto' : 'none',
            }}
          >
            <div style={labelStyle}>🎨 {t.styleAndColours}</div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
              {[
                { key: 'border',  label: `▦  ${t.border}` },
                { key: 'heading', label: `abc  ${t.headingBg}` },
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
              <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '9px', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase' }}>{t.livePreview}</span>
              <button
                onClick={() => navigate('/templates')}
                style={{ background: 'none', border: '1px solid #CC1E1E', borderRadius: '6px', color: '#CC1E1E', fontSize: '9px', fontWeight: 800, letterSpacing: '1px', padding: '4px 10px', cursor: 'pointer', textTransform: 'uppercase' }}
              >
                {t.changePattern}
              </button>
            </div>

            {/* Pattern Preview */}
            <div style={{ marginBottom: '14px' }}>
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
                    {activeColourTab === 'border' ? t.border : t.headingBg}
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
                    {group === 'classic' ? t.classicColours : t.lightSoftColours}
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

            {/* Font + Columns section inside Advance panel */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '14px' }}>
              {/* Font */}
              <div>
                <div style={labelStyle}>{t.font}</div>
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
              <div>
                <div style={labelStyle}>{t.columns}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  {[{ label: t.auto, val: 0 }, { label: t.oneColumn, val: 1 }, { label: t.twoColumns, val: 2 }, { label: t.threeColumns, val: 3 }]
                    .filter(({ val }) => showColPicker || layoutColumns === val)
                    .map(({ label, val }) => {
                    const isActive = layoutColumns === val;
                    return (
                      <button
                        key={label}
                        onClick={() => {
                          if (!showColPicker) {
                            setShowColPicker(true);
                          } else {
                            setLayoutColumns(val);
                            setShowColPicker(false);
                          }
                        }}
                        style={{
                          padding: '9px 12px', borderRadius: '8px',
                          background: isActive && showColPicker ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.05)',
                          border: isActive && showColPicker ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent',
                          color: isActive ? '#fff' : 'rgba(255,255,255,0.45)',
                          fontSize: '12px', fontWeight: isActive ? 700 : 400,
                          textAlign: 'left', cursor: 'pointer',
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}
                      >
                        <span>{label}</span>
                        {!showColPicker && (
                          <span style={{ opacity: 0.5, fontSize: '10px' }}>▼</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── SECTION 3: INTERFACE LANGUAGE ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <Globe style={{ width: 10, height: 10 }} /> {t.interfaceLanguageLabel}
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
          <div style={labelStyle}>{t.headlineLabel}</div>
          <input
            type="text"
            placeholder={t.enterHeadline}
            value={headline}
            onChange={e => setHeadline(e.target.value)}
            style={{ ...inputStyle, caretColor: '#fff' }}
          />
        </div>

        {/* ── SECTION 5: ARTICLE CONTENT ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <Type style={{ width: 10, height: 10 }} /> {t.articleContentLabel}
          </div>
          <textarea
            placeholder={t.enterArticleContent}
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={5}
            style={{ ...inputStyle, resize: 'none', lineHeight: 1.6, caretColor: '#fff' }}
          />
        </div>

        {/* ── SECTION 6: FEATURED IMAGES ── */}
        <div style={cardStyle}>
          <div style={labelStyle}>
            <ImageIcon style={{ width: 10, height: 10 }} /> {t.featuredImagesMax.replace('{max}', maxImages.toString())}
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
              <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '13px', fontWeight: 600 }}>{t.tapToUpload}</span>
              <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: '11px' }}>
                {maxImages - imageUrls.length} {t.remainingAutoCompressed}
              </span>
            </button>
          )}
        </div>

      </div>

      {/* ── Sticky bottom: Generate button ── */}
      <div style={{ position: 'fixed', left: 0, right: 0, bottom: 'calc(70px + env(safe-area-inset-bottom))', zIndex: 40, padding: '0 0' }}>
        {loading && currentStage && (
          <div style={{ background: '#0D1B2A', borderTop: '1px solid rgba(255,255,255,0.08)', padding: '10px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ color: '#fff', fontSize: '11px', fontWeight: 600 }}>{(t as any)[currentStage.id]}</span>
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
            <><Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} /><span>{currentStage ? (t as any)[currentStage.id] : t.publishLoading}</span></>
          ) : (
            <span>{t.publish}</span>
          )}
        </button>
      </div>

      {/* ── Modals ── */}
      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        accept="*/*" 
        onChange={handleFileChange} 
      />
        
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
              <h2 style={{ color: '#fff', fontSize: '18px', fontWeight: 800, fontFamily: "'Georgia', serif", margin: 0 }}>{t.selectLogo}</h2>
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
