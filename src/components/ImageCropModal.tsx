import React, { useState, useRef } from 'react';
import ReactCrop, { centerCrop, makeAspectCrop } from 'react-image-crop';
import type { Crop, PixelCrop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import { X } from 'lucide-react';

interface ImageCropModalProps {
  imageSrc: string;
  onCropComplete: (croppedBlob: Blob) => void;
  onCancel: () => void;
}

function centerAspectCrop(mediaWidth: number, mediaHeight: number, aspect: number) {
  return centerCrop(
    makeAspectCrop(
      {
        unit: '%',
        width: 90,
      },
      aspect,
      mediaWidth,
      mediaHeight,
    ),
    mediaWidth,
    mediaHeight,
  )
}

export const ImageCropModal: React.FC<ImageCropModalProps> = ({ imageSrc, onCropComplete, onCancel }) => {
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<PixelCrop>();
  const imgRef = useRef<HTMLImageElement>(null);
  const [isCropping, setIsCropping] = useState(false);

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { width, height } = e.currentTarget;
    setCrop(centerAspectCrop(width, height, 16 / 9));
  }

  const handleConfirm = async () => {
    if (!completedCrop || !imgRef.current) return;
    
    setIsCropping(true);
    try {
      const image = imgRef.current;
      const canvas = document.createElement('canvas');
      const scaleX = image.naturalWidth / image.width;
      const scaleY = image.naturalHeight / image.height;
      
      canvas.width = completedCrop.width;
      canvas.height = completedCrop.height;
      
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('No 2d context');
      
      ctx.drawImage(
        image,
        completedCrop.x * scaleX,
        completedCrop.y * scaleY,
        completedCrop.width * scaleX,
        completedCrop.height * scaleY,
        0,
        0,
        completedCrop.width,
        completedCrop.height,
      );
      
      canvas.toBlob((blob) => {
        if (!blob) {
          throw new Error('Canvas is empty');
        }
        onCropComplete(blob);
      }, 'image/jpeg', 0.95);
      
    } catch (e) {
      console.error(e);
      alert('Failed to crop image');
    }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.85)', zIndex: 9999,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: '#0D1B2A', 
        width: '100%', 
        maxWidth: '500px',
        borderRadius: '16px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
      }}>
        {/* Header */}
        <div style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, color: '#fff', fontSize: '20px', fontWeight: 'bold' }}>Crop Image</h2>
          <button onClick={onCancel} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>

        {/* Cropper Body */}
        <div style={{ padding: '0 20px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
          <ReactCrop
            crop={crop}
            onChange={(_, percentCrop) => setCrop(percentCrop)}
            onComplete={(c) => setCompletedCrop(c)}
            style={{ width: '100%', maxHeight: '60vh' }}
          >
            <img 
              ref={imgRef} 
              alt="Crop me" 
              src={imageSrc} 
              onLoad={onImageLoad} 
              style={{ maxWidth: '100%', maxHeight: '60vh', objectFit: 'contain' }} 
            />
          </ReactCrop>
        </div>

        {/* Footer */}
        <div style={{ padding: '20px' }}>
          <button
            onClick={handleConfirm}
            disabled={isCropping}
            style={{ 
              width: '100%', 
              background: '#CC1E1E', 
              color: '#fff', 
              border: 'none', 
              padding: '16px 20px', 
              borderRadius: '12px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              fontWeight: 'bold',
              fontSize: '18px',
              opacity: isCropping ? 0.7 : 1
            }}
          >
            {isCropping ? 'Processing...' : 'Confirm Crop'}
          </button>
        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        .ReactCrop__crop-selection {
          border: 2px dashed rgba(255,255,255,0.8) !important;
          background: transparent !important;
        }
        .ReactCrop__drag-handle {
          width: 24px !important;
          height: 24px !important;
          border: 2px solid #fff !important;
          background: transparent !important;
          border-radius: 0 !important;
        }
        .ReactCrop__drag-handle::after {
          display: none !important;
        }
        .ReactCrop__drag-handle.ord-nw {
          border-right: 0 !important;
          border-bottom: 0 !important;
          margin-top: -2px !important;
          margin-left: -2px !important;
        }
        .ReactCrop__drag-handle.ord-ne {
          border-left: 0 !important;
          border-bottom: 0 !important;
          margin-top: -2px !important;
          margin-right: -2px !important;
        }
        .ReactCrop__drag-handle.ord-sw {
          border-right: 0 !important;
          border-top: 0 !important;
          margin-bottom: -2px !important;
          margin-left: -2px !important;
        }
        .ReactCrop__drag-handle.ord-se {
          border-left: 0 !important;
          border-top: 0 !important;
          margin-bottom: -2px !important;
          margin-right: -2px !important;
        }
        .ReactCrop__drag-handle.ord-n, .ReactCrop__drag-handle.ord-s, .ReactCrop__drag-handle.ord-e, .ReactCrop__drag-handle.ord-w {
          display: none !important;
        }
      `}} />
    </div>
  );
};
