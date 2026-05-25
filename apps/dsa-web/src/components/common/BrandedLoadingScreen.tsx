import { useEffect, useState } from 'react';
import type React from 'react';
import { BrandLogo } from './BrandLogo';

interface GlobalLoaderProps {
  fading?: boolean;
  text?: string;
  subtext?: string;
}

const BOOT_LINES = [
  'INITIALIZING WOLFY AI CORE...',
  'CONNECTING US/HK/CN FEEDS... [OK]',
  'LOADING QUANTITATIVE MODELS...',
  'SYSTEM READY.',
];

const SEGMENT_COUNT = 10;

export const GlobalLoader: React.FC<GlobalLoaderProps> = ({ fading = false }) => {
  const [visibleLineCount, setVisibleLineCount] = useState(1);
  const [activeSegmentCount, setActiveSegmentCount] = useState(0);

  useEffect(() => {
    const lineTimer = window.setInterval(() => {
      setVisibleLineCount((count) => Math.min(count + 1, BOOT_LINES.length));
    }, 500);

    const segmentTimer = window.setInterval(() => {
      setActiveSegmentCount((count) => Math.min(count + 1, SEGMENT_COUNT));
    }, 170);

    return () => {
      window.clearInterval(lineTimer);
      window.clearInterval(segmentTimer);
    };
  }, []);

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-black px-6 transition-opacity duration-500 ${
        fading ? 'pointer-events-none opacity-0' : 'opacity-100'
      }`}
      role="status"
      aria-live="polite"
      aria-label="WolfyStock quant terminal boot sequence"
    >
      <style>
        {`
          @keyframes quant-grid-rise {
            from { transform: translate3d(0, 0, 0); }
            to { transform: translate3d(0, -40px, 0); }
          }

          @keyframes terminal-caret {
            0%, 45% { opacity: 1; }
            46%, 100% { opacity: 0; }
          }
        `}
      </style>

      <div
        className="absolute inset-[-40px] bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px]"
        style={{
          animation: 'quant-grid-rise 14s linear infinite',
          maskImage: 'radial-gradient(circle, black 40%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(circle, black 40%, transparent 80%)',
        }}
        aria-hidden="true"
      />

      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.12),transparent_28%),radial-gradient(circle_at_center,transparent_0%,rgba(0,0,0,0.88)_74%)]"
        aria-hidden="true"
      />

      <main className="relative z-10 flex w-full max-w-sm flex-col items-center">
        <div className="relative flex size-40 items-center justify-center md:size-48">
          <span
            className="absolute inset-0 rounded-full bg-emerald-400/10 blur-3xl animate-pulse"
            aria-hidden="true"
          />
          <span
            className="absolute inset-[22%] rounded-full bg-emerald-300/10 blur-2xl"
            aria-hidden="true"
          />
          <BrandLogo className="relative z-10 w-full h-full animate-pulse drop-shadow-[0_0_30px_rgba(16,185,129,0.5)]" />
        </div>

        <p className="mt-6 text-center font-mono text-lg font-bold uppercase tracking-[0.6em] text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.3)] md:text-xl">
          WOLFYSTOCK
        </p>

        <div className="mt-6 w-72 md:w-80">
          <div className="min-h-[5.75rem] text-left font-mono text-[10px] leading-relaxed text-emerald-400 md:text-xs">
            {BOOT_LINES.map((line, index) => {
              const isVisible = index < visibleLineCount;
              const isActive = index === visibleLineCount - 1 && visibleLineCount < BOOT_LINES.length;

              return (
                <p
                  key={line}
                  className={`flex gap-2 transition-opacity duration-200 ${
                    isVisible ? 'opacity-100' : 'opacity-0'
                  }`}
                >
                  <span className="text-emerald-300/90">&gt;</span>
                  <span>
                    {line}
                    {isActive ? (
                      <span
                        className="ml-1 inline-block h-3 w-1 translate-y-0.5 bg-emerald-400"
                        style={{ animation: 'terminal-caret 0.8s steps(1) infinite' }}
                        aria-hidden="true"
                      />
                    ) : null}
                  </span>
                </p>
              );
            })}
          </div>

          <div className="mt-4 flex w-full gap-1" aria-hidden="true">
            {Array.from({ length: SEGMENT_COUNT }).map((_, index) => (
              <span
                key={index}
                className={`h-1 w-full transition-all duration-200 ${
                  index < activeSegmentCount
                    ? 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.85)]'
                    : 'bg-white/10'
                }`}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};

export const BrandedLoadingScreen = GlobalLoader;
