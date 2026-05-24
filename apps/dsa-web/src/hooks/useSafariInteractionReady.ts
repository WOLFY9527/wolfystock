import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';

const READY_DELAY_MS = 80;
const WARMUP_INTERVAL_MS = 100;
const WARMUP_WINDOW_MS = 500;
const ACTIVATION_GUARD_MS = 32;

function repaintElement(element: HTMLElement | null) {
  if (!element) return;
  element.getBoundingClientRect();
  void element.offsetHeight;
}

export function useSafariRenderReady<T extends HTMLElement = HTMLDivElement>(delayMs = READY_DELAY_MS) {
  const surfaceRef = useRef<T | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let releaseTimer = 0;
    let fallbackTimer = 0;
    let frameA = 0;
    let frameB = 0;

    fallbackTimer = window.setTimeout(() => {
      setIsReady(true);
    }, delayMs + 500);

    frameA = window.requestAnimationFrame(() => {
      repaintElement(surfaceRef.current);
      frameB = window.requestAnimationFrame(() => {
        repaintElement(surfaceRef.current);
        releaseTimer = window.setTimeout(() => {
          setIsReady(true);
        }, delayMs);
      });
    });

    return () => {
      window.cancelAnimationFrame(frameA);
      window.cancelAnimationFrame(frameB);
      window.clearTimeout(releaseTimer);
      window.clearTimeout(fallbackTimer);
    };
  }, [delayMs]);

  return { isReady, surfaceRef };
}

export function getSafariReadySurfaceClassName(isReady: boolean, className: string) {
  return `${className} transition-opacity duration-300 ease-out ${isReady ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'}`.trim();
}

export function shouldApplySafariA11yGuard() {
  if (typeof navigator === 'undefined') {
    return false;
  }
  const userAgent = navigator.userAgent || '';
  return /Safari\//.test(userAgent) && !/(Chrome|Chromium|CriOS|Edg|OPR|Firefox|FxiOS|Android)/.test(userAgent);
}

type SafariActivationEvent =
  | React.MouseEvent<HTMLElement>
  | React.PointerEvent<HTMLElement>;

export function useSafariWarmActivation<T extends HTMLElement>(onActivate: () => void) {
  const ref = useRef<T | null>(null);
  const lastActivationAtRef = useRef(0);

  useEffect(() => {
    let elapsedMs = 0;
    let releaseWarmListener: (() => void) | null = null;

    const clearWarmListener = () => {
      releaseWarmListener?.();
      releaseWarmListener = null;
    };

    const warmTarget = () => {
      clearWarmListener();
      const element = ref.current;
      if (!element) return;
      const noop = () => undefined;
      element.addEventListener('pointerdown', noop, { passive: true });
      releaseWarmListener = () => {
        element.removeEventListener('pointerdown', noop);
      };
      repaintElement(element);
    };

    warmTarget();
    const intervalId = window.setInterval(() => {
      warmTarget();
      elapsedMs += WARMUP_INTERVAL_MS;
      if (elapsedMs >= WARMUP_WINDOW_MS) {
        window.clearInterval(intervalId);
        clearWarmListener();
      }
    }, WARMUP_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
      clearWarmListener();
    };
  }, []);

  const handleActivate = useCallback((event?: SafariActivationEvent) => {
    const now = Date.now();
    if (now - lastActivationAtRef.current < ACTIVATION_GUARD_MS) {
      return;
    }
    lastActivationAtRef.current = now;
    if (event?.type === 'pointerup') {
      event.preventDefault();
    }
    onActivate();
  }, [onActivate]);

  return {
    ref,
    onClick: handleActivate,
    onPointerUp: handleActivate,
  };
}
