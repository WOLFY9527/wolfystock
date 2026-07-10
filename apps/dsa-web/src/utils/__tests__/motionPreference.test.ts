import { describe, expect, it } from 'vitest';
import {
  readPrefersReducedMotion,
  resolveMotionDurationMs,
  shouldEnableNonEssentialMotion,
} from '../motionPreference';

describe('motionPreference', () => {
  it('reads reduced-motion preference from a MediaQueryList', () => {
    expect(readPrefersReducedMotion({ matches: true } as MediaQueryList)).toBe(true);
    expect(readPrefersReducedMotion({ matches: false } as MediaQueryList)).toBe(false);
  });

  it('reads reduced-motion preference via matchMedia when no list is provided', () => {
    const matchMedia = ((query: string) => ({
      matches: query.includes('reduce'),
      media: query,
    })) as typeof window.matchMedia;

    expect(readPrefersReducedMotion(null, matchMedia)).toBe(true);
  });

  it('disables non-essential motion and zeroes durations under reduce', () => {
    expect(shouldEnableNonEssentialMotion(true)).toBe(false);
    expect(shouldEnableNonEssentialMotion(false)).toBe(true);
    expect(resolveMotionDurationMs(true, 220)).toBe(0);
    expect(resolveMotionDurationMs(false, 220)).toBe(220);
  });
});
