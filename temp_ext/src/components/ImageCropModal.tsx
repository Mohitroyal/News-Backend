import React, { useState, useRef } from 'react';
import ReactCrop from 'react-image-crop';
import type { Crop, PixelCrop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import { X } from 'lucide-react';

interface ImageCropModalProps {
  imageSrc: string;
  onCropComplete: (croppedBlob: Blob) => void;
  onCancel: () => void;
}

export const ImageCropModal: React.FC<ImageCropModalProps> = ({ imageSrc, onCropComplete, onCancel }) => {
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<PixelCrop>();
  const [hasUserDragged, setHasUserDragged] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const [isCropping, setIsCropping] = useState(false);

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    setCrop({ unit: '%', x: 0, y: 0, width: 100, height: 100 });
    const { naturalWidth, naturalHeight } = e.currentTarget;
    const rect = e.currentTarget.getBoundingClientRect();
    const width = rect.width || e.currentTarget.width || naturalWidth;
    const height = rect.height || e.currentTarget.height || naturalHeight;
    setCompletedCrop({
      unit: 'px',
      x: 0,
      y: 0,
      width,
      height
    });
  }

  const handleCropChange = (_: Crop, percentCrop: Crop) => {
    setCrop(percentCrop);
    setHasUserDragged(true);
  };

  const handleConfirm = async (forceFullImage: boolean = false) => {
    if (!imgRef.current) return;
    
    setIsCropping(true);
    try {
      const image = imgRef.current;
      const canvas = document.createElement('canvas');
      
      let cropX = 0;
      let cropY = 0;
      let cropWidth = image.naturalWidth;
      let cropHeight = image.naturalHeight;

      if (!forceFullImage && hasUserDragged && completedCrop && completedCrop.width > 0 && completedCrop.height > 0) {
        if ((completedCrop as any).unit === '%' || (crop && crop.unit === '%')) {
          const cX = completedCrop.x ?? crop?.x ?? 0;
          const cY = completedCrop.y ?? crop?.y ?? 0;
          const cW = completedCrop.width ?? crop?.width ?? 100;
          const cH = completedCrop.height ?? crop?.height ?? 100;

          cropX = Math.round((cX / 100) * image.naturalWidth);
          cropY = Math.round((cY / 100) * image.naturalHeight);
          cropWidth = Math.round((cW / 100) * image.naturalWidth);
          cropHeight = Math.round((cH / 100) * image.naturalHeight);
        } else {
          const rect = image.getBoundingClientRect();
          const dispW = rect.width || image.width || image.naturalWidth;
          const dispH = rect.height || image.height || image.naturalHeight;
          const scaleX = image.naturalWidth / dispW;
          const scaleY = image.naturalHeight / dispH;

          cropX = Math.round(completedCrop.x * scaleX);
          cropY = Math.round(completedCrop.y * scaleY);
          cropWidth = Math.round(completedCrop.width * scaleX);
          cropHeight = Math.round(completedCrop.height * scaleY);
        }
      }

      // Safeguard: If user didn't drag or if selection spans near full width/height (or left near 0 & right near 100%),
      // enforce 100% full uncropped image bounds
      const rightEdge = cropX + cropWidth;
      const bottomEdge = cropY + cropHeight;
      if (
        forceFullImage ||
        !hasUserDragged ||
        (cropWidth >= image.naturalWidth * 0.80 && cropHeight >= image.naturalHeight * 0.80) ||
        (cropX <= image.naturalWidth * 0.15 && rightEdge >= image.naturalWidth * 0.85) ||
        (cropY <= image.naturalHeight * 0.15 && bottomEdge >= image.naturalHeight * 0.85)
      ) {
        cropX = 0;
        cropY = 0;
        cropWidth = image.naturalWidth;
        cropHeight = image.naturalHeight;
      }

      // Bound checks
      cropX = Math.max(0, Math.min(cropX, image.naturalWidth - 1));
      cropY = Math.max(0, Math.min(cropY, image.naturalHeight - 1));
      cropWidth = Math.min(cropWidth, image.naturalWidth - cropX);
      cropHeight = Math.min(cropHeight, image.naturalHeight - cropY);

      canvas.width = cropWidth;
      canvas.height = cropHeight;
      
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('No 2d context');
      
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';

      ctx.drawImage(
        image,
        cropX,
        cropY,
        cropWidth,
        cropHeight,
        0,
        0,
        cropWidth,
        cropHeight
      );
      
      canvas.toBlob((blob) => {
        if (!blob) {
          throw new Error('Canvas is empty');
        }
        onCropComplete(blob);
      }, 'image/png');
      
    } catch (e) {
      console.error(e);
      alert('Failed to crop image');
      setIsCropping(false);
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
        maxWidth: '520px',
        borderRadius: '16px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
      }}>
        {/* Header */}
        <div style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, color: '#fff', fontSize: '20px', fontWeight: 'bold' }}>Crop / Full Image</h2>
          <button onClick={onCancel} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>

        {/* Cropper Body */}
        <div style={{ padding: '0 20px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px', overflow: 'auto' }}>
          <ReactCrop
            crop={crop}
            onChange={handleCropChange}
            onComplete={(c) => setCompletedCrop(c)}
            style={{ maxWidth: '100%', maxHeight: '60vh' }}
          >
            <img 
              ref={imgRef} 
              alt="Crop me" 
              src={imageSrc} 
              onLoad={onImageLoad} 
              style={{ display: 'block', maxWidth: '100%', maxHeight: '60vh', width: 'auto', height: 'auto' }} 
            />
          </ReactCrop>
        </div>

        {/* Footer */}
        <div style={{ padding: '20px', display: 'flex', gap: '10px' }}>
          <button
            onClick={() => handleConfirm(true)}
            disabled={isCropping}
            style={{ 
              flex: 1, 
              background: '#1E293B', 
              color: '#38BDF8', 
              border: '1px solid #38BDF8', 
              padding: '12px 10px', 
              borderRadius: '12px', 
              fontWeight: 'bold',
              fontSize: '14px',
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            Full Image (No Crop)
          </button>
          <button
            onClick={() => handleConfirm(false)}
            disabled={isCropping}
            style={{ 
              flex: 1, 
              background: '#CC1E1E', 
              color: '#fff', 
              border: 'none', 
              padding: '12px 10px', 
              borderRadius: '12px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              fontWeight: 'bold',
              fontSize: '14px',
              cursor: 'pointer',
              opacity: isCropping ? 0.7 : 1,
              whiteSpace: 'nowrap'
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
