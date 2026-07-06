import { useEffect, useState } from 'react';
import type React from 'react';
import { BrandLogo } from './BrandLogo';

interface GlobalLoaderProps {
  fading?: boolean;
  text?: string;
  subtext?: string;
}

const SEGMENT_COUNT = 10;
const DEFAULT_LOADING_TEXT = 'Loading the WolfyStock research workspace...';

const GlobalLoader: React.FC<GlobalLoaderProps> = ({ fading = false, text, subtext }) => {
  const [activeSegmentCount, setActiveSegmentCount] = useState(0);
  const headline = text?.trim() || DEFAULT_LOADING_TEXT;
  const detail = subtext?.trim() || null;

  useEffect(() => {
    const segmentTimer = window.setInterval(() => {
      setActiveSegmentCount((count) => Math.min(count + 1, SEGMENT_COUNT));
    }, 170);

    return () => {
      window.clearInterval(segmentTimer);
    };
  }, []);

  return (
    <output
      className={`block fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-[var(--paper)] px-6 text-[color:var(--ink)] transition-opacity duration-200 ${
        fading ? 'pointer-events-none opacity-0' : 'opacity-100'
      }`}
      aria-live="polite"
      aria-label="WolfyStock research workspace loading"
    >
      <style>
        {`
          @keyframes quant-grid-rise {
            from { transform: translate3d(0, 0, 0); }
            to { transform: translate3d(0, -40px, 0); }
          }
        `}
      </style>

      <div
        className="absolute inset-[-40px] bg-[linear-gradient(to_right,rgb(37_33_27/0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgb(37_33_27/0.03)_1px,transparent_1px)] bg-[size:36px_36px]"
        style={{
          animation: 'quant-grid-rise 900ms linear infinite',
          maskImage: 'radial-gradient(circle, black 48%, transparent 84%)',
          WebkitMaskImage: 'radial-gradient(circle, black 48%, transparent 84%)',
        }}
        aria-hidden="true"
      />

      <div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,#F7F2EC_0%,var(--paper)_44%,#EFE7DE_100%)]"
        aria-hidden="true"
      />

      <main className="relative z-10 flex w-full max-w-sm flex-col items-center">
        <div className="relative flex size-40 items-center justify-center md:size-48">
          <span
            className="absolute inset-0 rounded-full bg-[rgb(107_143_113/0.12)] blur-3xl animate-pulse"
            aria-hidden="true"
          />
          <span
            className="absolute inset-[22%] rounded-full bg-[rgb(212_165_116/0.14)] blur-2xl"
            aria-hidden="true"
          />
          <BrandLogo className="relative z-10 w-full h-full animate-pulse" />
        </div>

        <p className="mt-6 text-center font-mono text-lg font-bold uppercase tracking-[0.24em] text-[color:var(--sage-deep)] md:text-xl">
          WOLFYSTOCK
        </p>

        <div className="mt-6 w-72 text-center md:w-80">
          <p className="text-sm font-semibold leading-6 text-[color:var(--ink)] md:text-[15px]">
            {headline}
          </p>
          {detail ? (
            <p className="mt-2 text-xs leading-5 text-[color:var(--muted)] md:text-[13px]">
              {detail}
            </p>
          ) : null}

          <div className="mt-4 flex w-full gap-1" aria-hidden="true">
            {Array.from({ length: SEGMENT_COUNT }).map((_, index) => (
              <span
                key={index}
                className={`h-1 w-full transition-all duration-200 ${
                  index < activeSegmentCount
                    ? 'bg-[var(--sage)]'
                    : 'bg-[rgb(54_48_40/0.12)]'
                }`}
              />
            ))}
          </div>
        </div>
      </main>
    </output>
  );
};

export const BrandedLoadingScreen = GlobalLoader;
