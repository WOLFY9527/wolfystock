import { useEffect, useState } from 'react';
import {
  PREFERS_REDUCED_MOTION_QUERY,
  readPrefersReducedMotion,
} from '../utils/motionPreference';

/**
 * Subscribes to `prefers-reduced-motion: reduce`.
 * Shared motion infrastructure owned by the chart accessibility / motion lane.
 */
export function usePrefersReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => readPrefersReducedMotion());

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined;
    }

    const media = window.matchMedia(PREFERS_REDUCED_MOTION_QUERY);
    const sync = () => {
      setReducedMotion(readPrefersReducedMotion(media));
    };

    sync();

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', sync);
      return () => media.removeEventListener('change', sync);
    }

    // Safari < 14
    media.addListener(sync);
    return () => media.removeListener(sync);
  }, []);

  return reducedMotion;
}
