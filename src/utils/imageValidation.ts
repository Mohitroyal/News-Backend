/**
 * Image Validation Utility
 *
 * Enforces strict constraints on image uploads in the frontend matching backend security rules:
 * 1. File Size Limit: Max 10 MB (10 * 1024 * 1024 bytes), Min > 0 bytes.
 * 2. Dimension Limit: Max 4096 px width / height.
 * 3. Resolution / Pixel Limit: Max 16,000,000 pixels (16 Megapixels, decompression bomb protection).
 * 4. Allowed Formats: JPEG, PNG, WEBP (image/jpeg, image/png, image/webp).
 */

export const IMAGE_CONSTRAINTS = {
  MAX_UPLOAD_SIZE: 10 * 1024 * 1024, // 10 MB limit
  MIN_UPLOAD_SIZE: 1,                 // Must be > 0 bytes
  MAX_DIMENSION: 4096,                // Max width/height in px
  MAX_PIXELS: 16_000_000,             // Max total pixels (16 Megapixels)
  ALLOWED_MIME_TYPES: ['image/jpeg', 'image/png', 'image/webp'],
  ALLOWED_EXTENSIONS: ['jpeg', 'jpg', 'png', 'webp'],
} as const;

export interface ValidationOptions {
  allowSvg?: boolean;
  maxSizeBytes?: number;
  maxDimension?: number;
  maxPixels?: number;
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
  width?: number;
  height?: number;
  size?: number;
}

/**
 * Validate an image File or Blob against size, MIME type, dimensions, and pixel limits.
 */
export async function validateImageFile(
  file: File | Blob,
  options: ValidationOptions = {}
): Promise<ValidationResult> {
  const maxSize = options.maxSizeBytes ?? IMAGE_CONSTRAINTS.MAX_UPLOAD_SIZE;
  const maxDim = options.maxDimension ?? IMAGE_CONSTRAINTS.MAX_DIMENSION;
  const maxPix = options.maxPixels ?? IMAGE_CONSTRAINTS.MAX_PIXELS;

  // 1. Check minimum file size
  if (file.size === 0) {
    return {
      valid: false,
      error: 'Empty file uploaded. File must be greater than 0 bytes.',
    };
  }

  // 2. Check maximum file size (10 MB limit)
  if (file.size > maxSize) {
    const sizeMb = (maxSize / (1024 * 1024)).toFixed(0);
    return {
      valid: false,
      error: `File exceeds maximum allowed size of ${sizeMb}MB. 10MB is the limit.`,
    };
  }

  // 3. Format / MIME type check
  const mimeType = (file.type || '').toLowerCase().split(';')[0].trim();
  const fileName = 'name' in file ? (file as File).name.toLowerCase() : '';
  const isSvg = mimeType === 'image/svg+xml' || fileName.endsWith('.svg');

  if (isSvg) {
    if (options.allowSvg) {
      return { valid: true, size: file.size };
    }
    return {
      valid: false,
      error: "Unsupported image format: 'image/svg+xml'. Allowed formats: JPEG, PNG, WEBP.",
    };
  }

  if (mimeType && !IMAGE_CONSTRAINTS.ALLOWED_MIME_TYPES.includes(mimeType as any)) {
    return {
      valid: false,
      error: `Unsupported content type: '${mimeType}'. Allowed formats: JPEG, PNG, WEBP.`,
    };
  }

  if (fileName) {
    const ext = fileName.split('.').pop() || '';
    if (ext && !IMAGE_CONSTRAINTS.ALLOWED_EXTENSIONS.includes(ext as any)) {
      return {
        valid: false,
        error: `Unsupported image extension: '.${ext}'. Allowed formats: JPEG, PNG, WEBP.`,
      };
    }
  }

  // 4. Validate dimensions and total pixel count asynchronously
  return new Promise((resolve) => {
    const objectUrl = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const width = img.naturalWidth || img.width;
      const height = img.naturalHeight || img.height;
      const pixels = width * height;

      if (width > maxDim || height > maxDim) {
        resolve({
          valid: false,
          error: `Image dimensions (${width}x${height}) exceed maximum allowed limit of ${maxDim}x${maxDim}.`,
          width,
          height,
          size: file.size,
        });
        return;
      }

      if (pixels > maxPix) {
        resolve({
          valid: false,
          error: `Image pixel density too high (${(pixels / 1_000_000).toFixed(1)}MP). Maximum allowed limit is 16 Megapixels (decompression bomb protection).`,
          width,
          height,
          size: file.size,
        });
        return;
      }

      resolve({
        valid: true,
        width,
        height,
        size: file.size,
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      resolve({
        valid: false,
        error: 'Unable to read image. The file may be corrupt or not a valid JPEG, PNG, or WEBP image.',
      });
    };

    img.src = objectUrl;
  });
}
