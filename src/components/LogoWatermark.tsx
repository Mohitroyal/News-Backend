/**
 * LogoWatermark — RTI Express logo watermark
 *
 * Uses the actual RTI Express logo JPEG as the watermark source.
 *
 * Why mix-blend-mode: multiply:
 *   The logo is blue-on-white. `multiply` makes white pixels fully
 *   transparent (white × background = background), so only the blue
 *   branding shows through as a faint tint. No image editing needed.
 *
 * Stacking:
 *   z-index: 5 → above scrollable content (z:auto),
 *                below sticky header (z-10) and bottom-nav (z-20).
 *
 * Interaction:
 *   pointer-events: none → never blocks taps, scrolls, or gestures.
 *
 * Scrolling:
 *   position: fixed → viewport-anchored, never scrolls with content.
 */

import watermarkLogo from '@/assets/rti_express_watermark.png';

interface LogoWatermarkProps {
  /**
   * Overall opacity of the watermark.
   * Default 0.12 (12 %) — visible but non-distracting on real devices.
   */
  opacity?: number;
  /**
   * Set to true on dark-background screens (e.g. Login).
   * Disables multiply blend (which darkens on dark bg) and uses
   * a screen blend instead so the logo stays subtle and light.
   */
  darkBackground?: boolean;
}

export const LogoWatermark = ({
  opacity = 0.12,
  darkBackground = false,
}: LogoWatermarkProps) => {
  return (
    <div
      aria-hidden="true"
      style={{
        /* ── Position ── */
        position: 'fixed',
        inset: 0,

        /* ── Layout: centred ── */
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',

        /* ── Stacking ── */
        zIndex: 5,

        /* ── Interaction ── */
        pointerEvents: 'none',

        /* ── Display mode ── */
        mixBlendMode: darkBackground ? 'screen' : 'multiply',
        opacity: opacity,
      }}
    >
      <img
        src={watermarkLogo}
        alt=""
        draggable={false}
        style={{
          width: '75%', // Shrink slightly to fit screen nicely
          maxWidth: '450px',
          height: 'auto',
          display: 'block',
          userSelect: 'none',
          WebkitUserSelect: 'none',
          transform: 'rotate(-30deg)',
          filter: darkBackground ? 'invert(1)' : 'none',
        }}
      />
    </div>
  );
};
