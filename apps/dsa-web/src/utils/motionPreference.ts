/**
 * Shared reduced-motion preference helpers.
 * G037 owns this infrastructure for chart and non-essential motion consumers.
 */

export const PREFERS_REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

export function readPrefersReducedMotion(
  mediaList?: MediaQueryList | null,
  matchMediaImpl?: typeof window.matchMedia,
): boolean {
  try {
    if (mediaList) return Boolean(mediaList.matches);
    const impl = matchMediaImpl
      ?? (typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia.bind(window)
        : undefined);
    if (!impl) return false;
    return Boolean(impl(PREFERS_REDUCED_MOTION_QUERY).matches);
  } catch {
    return false;
  }
}

/** ECharts / CSS duration when motion is allowed. */
export function resolveMotionDurationMs(reducedMotion: boolean, normalMs: number): number {
  if (reducedMotion) return 0;
  return Number.isFinite(normalMs) && normalMs > 0 ? normalMs : 0;
}

/** Whether non-essential chart/UI animation should run. */
export function shouldEnableNonEssentialMotion(reducedMotion: boolean): boolean {
  return !reducedMotion;
}
