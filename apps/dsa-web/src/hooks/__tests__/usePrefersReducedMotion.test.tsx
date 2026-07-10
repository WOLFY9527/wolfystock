import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePrefersReducedMotion } from '../usePrefersReducedMotion';
import { PREFERS_REDUCED_MOTION_QUERY } from '../../utils/motionPreference';

type Listener = (event: MediaQueryListEvent) => void;

function installMatchMedia(initialMatches: boolean) {
  const listeners = new Set<Listener>();
  const media: MediaQueryList = {
    matches: initialMatches,
    media: PREFERS_REDUCED_MOTION_QUERY,
    onchange: null,
    addEventListener: vi.fn((type: string, listener: EventListenerOrEventListenerObject) => {
      if (type === 'change' && typeof listener === 'function') {
        listeners.add(listener as Listener);
      }
    }),
    removeEventListener: vi.fn((type: string, listener: EventListenerOrEventListenerObject) => {
      if (type === 'change' && typeof listener === 'function') {
        listeners.delete(listener as Listener);
      }
    }),
    addListener: vi.fn((listener: Listener) => {
      listeners.add(listener);
    }),
    removeListener: vi.fn((listener: Listener) => {
      listeners.delete(listener);
    }),
    dispatchEvent: vi.fn(() => true),
  };

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn((query: string) => {
      expect(query).toBe(PREFERS_REDUCED_MOTION_QUERY);
      return media;
    }),
  });

  return {
    media,
    setMatches(next: boolean) {
      (media as { matches: boolean }).matches = next;
      const event = { matches: next, media: PREFERS_REDUCED_MOTION_QUERY } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event));
    },
  };
}

describe('usePrefersReducedMotion', () => {
  beforeEach(() => {
    installMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('reports false when the user allows motion', () => {
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });

  it('reports true when prefers-reduced-motion is reduce', () => {
    installMatchMedia(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });

  it('updates when the media query changes', () => {
    const control = installMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    act(() => {
      control.setMatches(true);
    });
    expect(result.current).toBe(true);

    act(() => {
      control.setMatches(false);
    });
    expect(result.current).toBe(false);
  });
});
