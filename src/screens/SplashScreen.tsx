import rtiLogo from '@/assets/rti_express_logo.png';

export const SplashScreen = () => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        minHeight: '100dvh',
        backgroundColor: '#0d1b3e',
        padding: '48px 24px 32px',
        fontFamily: "'Georgia', 'Times New Roman', serif",
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Subtle horizontal stripe overlay (matches the image) */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 1px, transparent 1px, transparent 28px)',
          pointerEvents: 'none',
        }}
      />

      {/* ── Top spacer ── */}
      <div style={{ flex: 1 }} />

      {/* ── Centre content ── */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '18px',
          zIndex: 1,
        }}
      >
        {/* EST. 2024 | INDIA */}
        <p
          style={{
            color: '#a8b8d8',
            fontSize: '11px',
            letterSpacing: '3px',
            fontFamily: "'Arial', sans-serif",
            fontWeight: 600,
            textTransform: 'uppercase',
            margin: 0,
          }}
        >
          EST. 2024&nbsp;&nbsp;|&nbsp;&nbsp;INDIA
        </p>

        {/* Logo box */}
        <div
          style={{
            border: '2.5px solid #cc2222',
            borderRadius: '6px',
            backgroundColor: '#ffffff',
            padding: '10px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 0 1px rgba(204,34,34,0.15), 0 8px 24px rgba(0,0,0,0.4)',
          }}
        >
          <img
            src={rtiLogo}
            alt="RTI Express Logo"
            draggable={false}
            style={{
              width: '160px',
              height: 'auto',
              display: 'block',
            }}
          />
        </div>

        {/* RTI EXPRESS large title */}
        <div style={{ textAlign: 'center', lineHeight: 1.05, marginTop: '6px' }}>
          <h1
            style={{
              color: '#ffffff',
              fontSize: 'clamp(40px, 12vw, 56px)',
              fontWeight: 800,
              fontFamily: "'Georgia', 'Times New Roman', serif",
              letterSpacing: '4px',
              margin: 0,
              textShadow: '0 2px 12px rgba(0,0,0,0.5)',
            }}
          >
            RTI
            <br />
            EXPRESS
          </h1>
        </div>

        {/* RIGHT TO KNOW */}
        <p
          style={{
            color: '#a8b8d8',
            fontSize: '11px',
            letterSpacing: '4px',
            fontFamily: "'Arial', sans-serif",
            fontWeight: 600,
            textTransform: 'uppercase',
            margin: 0,
          }}
        >
          RIGHT TO KNOW
        </p>

        {/* Red divider */}
        <div
          style={{
            width: '36px',
            height: '2.5px',
            backgroundColor: '#cc2222',
            borderRadius: '2px',
          }}
        />

        {/* Spinner */}
        <div
          style={{
            position: 'relative',
            width: '32px',
            height: '32px',
            marginTop: '8px',
          }}
        >
          {/* Track */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '2.5px solid rgba(168,184,216,0.25)',
            }}
          />
          {/* Spinning arc */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '2.5px solid transparent',
              borderTopColor: '#a8b8d8',
              borderRightColor: '#a8b8d8',
              animation: 'rti-spin 1.2s linear infinite',
            }}
          />
        </div>
      </div>

      {/* ── Bottom spacer ── */}
      <div style={{ flex: 1 }} />

      {/* ── Footer ── */}
      <p
        style={{
          color: '#5a6e90',
          fontSize: '11px',
          letterSpacing: '0.5px',
          fontFamily: "'Arial', sans-serif",
          margin: 0,
          zIndex: 1,
          textAlign: 'center',
        }}
      >
        RTI EXPRESS © 2024 &nbsp;·&nbsp; All Rights Reserved
      </p>

      {/* Keyframe for spinner */}
      <style>{`
        @keyframes rti-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
