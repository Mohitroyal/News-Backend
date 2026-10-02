import React from 'react';
import { AlertTriangle, X, Check, FileWarning, Sparkles, Loader2 } from 'lucide-react';

export interface ImageWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  errorMessage: string;
  canCompress?: boolean;
  onProceedCompress?: () => void;
  isCompressing?: boolean;
}

export const ImageWarningModal: React.FC<ImageWarningModalProps> = ({
  isOpen,
  onClose,
  title = 'Image Limit Warning',
  errorMessage,
  canCompress = false,
  onProceedCompress,
  isCompressing = false,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        background: 'rgba(10, 25, 47, 0.75)',
        backdropFilter: 'blur(5px)',
        WebkitBackdropFilter: 'blur(5px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        animation: 'fadeIn 0.2s ease-out',
      }}
      onClick={isCompressing ? undefined : onClose}
    >
      <div
        style={{
          background: '#ffffff',
          width: '100%',
          maxWidth: '430px',
          borderRadius: '20px',
          overflow: 'hidden',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(0, 0, 0, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          animation: 'scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Red/Amber Alert Accent */}
        <div
          style={{
            background: 'linear-gradient(135deg, #FFF5F5 0%, #FED7D7 100%)',
            padding: '18px 20px',
            borderBottom: '1px solid #FEB2B2',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '42px',
                height: '42px',
                borderRadius: '12px',
                background: '#CC1E1E',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                boxShadow: '0 4px 10px rgba(204, 30, 30, 0.35)',
                flexShrink: 0,
              }}
            >
              <AlertTriangle size={22} strokeWidth={2.5} />
            </div>
            <div>
              <h3
                style={{
                  margin: 0,
                  fontSize: '17px',
                  fontWeight: 800,
                  color: '#9B1C1C',
                  fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                }}
              >
                {title}
              </h3>
              <span style={{ fontSize: '11px', color: '#C53030', fontWeight: 600 }}>
                {canCompress ? '10 MB Limit Exceeded' : 'Upload Constraint Violation'}
              </span>
            </div>
          </div>
          {!isCompressing && (
            <button
              onClick={onClose}
              style={{
                background: 'rgba(0,0,0,0.06)',
                border: 'none',
                borderRadius: '50%',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#4A5568',
                cursor: 'pointer',
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Specific Error Box */}
          <div
            style={{
              background: '#FFF5F5',
              border: '1.5px solid #FC8181',
              borderRadius: '12px',
              padding: '12px 14px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <FileWarning size={20} color="#E53E3E" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ color: '#9B1C1C', fontSize: '13.5px', fontWeight: 700, lineHeight: 1.45 }}>
              {errorMessage}
            </div>
          </div>

          {/* Caution Box for Compression */}
          {canCompress && (
            <div
              style={{
                background: 'linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)',
                border: '1.5px solid #F59E0B',
                borderRadius: '12px',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                boxShadow: '0 2px 6px rgba(245, 158, 11, 0.12)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    background: '#D97706',
                    color: '#ffffff',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    fontSize: '10.5px',
                    fontWeight: 800,
                    letterSpacing: '0.6px',
                    textTransform: 'uppercase',
                  }}
                >
                  Caution
                </span>
                <span style={{ fontSize: '13px', fontWeight: 800, color: '#92400E' }}>
                  Auto-Compression Notice
                </span>
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: '12.5px',
                  color: '#78350F',
                  lineHeight: 1.5,
                  fontWeight: 500,
                }}
              >
                We are going to compress it to a suitable size so image quality may be reduced (Caution).
              </p>
              <div
                style={{
                  fontSize: '11.5px',
                  color: '#B45309',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginTop: '2px',
                }}
              >
                <Sparkles size={14} color="#D97706" />
                <span>Target: High-resolution &lt; 10MB JPEG format</span>
              </div>
            </div>
          )}

          {/* Specifications Checklist */}
          <div
            style={{
              background: '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '12px',
              padding: '12px 14px',
            }}
          >
            <div
              style={{
                fontSize: '11px',
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: '0.8px',
                color: '#64748B',
                marginBottom: '8px',
              }}
            >
              Image Specifications:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px', color: '#334155' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span>
                <span>
                  <strong>Maximum File Size:</strong> 10 MB (10MB is the limit)
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span>
                <span>
                  <strong>Minimum File Size:</strong> Must be greater than 0 bytes
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span>
                <span>
                  <strong>Max Dimensions:</strong> 4096 × 4096 px (Max 16 Megapixels)
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span>
                <span>
                  <strong>Supported Formats:</strong> JPEG, PNG, WEBP
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ padding: '0 20px 20px 20px' }}>
          {canCompress ? (
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={onClose}
                disabled={isCompressing}
                style={{
                  flex: 1,
                  background: '#F1F5F9',
                  color: '#475569',
                  border: '1px solid #CBD5E1',
                  borderRadius: '12px',
                  padding: '12px 14px',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: isCompressing ? 'not-allowed' : 'pointer',
                  opacity: isCompressing ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  transition: 'background 0.15s ease',
                }}
              >
                <X size={15} />
                <span>Cancel</span>
              </button>

              <button
                onClick={onProceedCompress}
                disabled={isCompressing}
                style={{
                  flex: 1.6,
                  background: isCompressing
                    ? '#64748B'
                    : 'linear-gradient(135deg, #0F487F 0%, #1E3A8A 100%)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '12px 16px',
                  fontSize: '13.5px',
                  fontWeight: 700,
                  cursor: isCompressing ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 14px rgba(15, 72, 127, 0.3)',
                  transition: 'transform 0.15s ease, opacity 0.15s ease',
                }}
              >
                {isCompressing ? (
                  <>
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                    <span>Compressing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    <span>Proceed &amp; Compress</span>
                  </>
                )}
              </button>
            </div>
          ) : (
            <button
              onClick={onClose}
              style={{
                width: '100%',
                background: '#0F487F',
                color: '#ffffff',
                border: 'none',
                borderRadius: '12px',
                padding: '13px',
                fontSize: '14px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 12px rgba(15, 72, 127, 0.25)',
              }}
            >
              <Check size={16} strokeWidth={3} />
              <span>OK, I Understand</span>
            </button>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { opacity: 0; transform: scale(0.92); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
